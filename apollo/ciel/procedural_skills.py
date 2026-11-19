"""Modul F: Prozedurale Skills (NIO Phase 5).

Ein prozeduraler Skill ist eine geordnete Tool-Kette mit Datenfluss zwischen den
Schritten. Argumente eines Schritts können an einen Wert aus einem früheren
Schritt gebunden sein (``input_bindings``: ``arg -> "step_<j>.<key>"``); alle
übrigen Argumente sind feste ``static_args``.

Bausteine:

* :class:`SkillStepSpec` / :class:`ProceduralSkillSpec` — Spezifikation und Playbook (Markdown mit YAML-Frontmatter).
* :class:`ProceduralSkillRegistry` — SQLite-Ablage mit Wilson-Lower-Bound-Ranking (z = 1.96).
* :class:`TrajectorySkillDistiller` — destilliert aus einer erfolgreichen Tool-Trajektorie einen Skill.
* :func:`load_skill_payload` — Tool-Result des Meta-Tools ``load_skill``.

Die Wilson-Formel ist aus ``Architect/core/learning/skill_profiles.py`` stdlib-only übernommen.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .models import BaseModel, ConfigDict, Field

#: Name des Meta-Tools zum Laden eines prozeduralen Skills.
LOAD_SKILL_TOOL_NAME: Final[str] = "load_skill"

#: Schema des Meta-Tools ``load_skill``.
LOAD_SKILL_SCHEMA: Final[dict[str, Any]] = {
    "name": LOAD_SKILL_TOOL_NAME,
    "description": (
        "Lädt ein gespeichertes Playbook (prozeduraler Skill) als Tool-Result. "
        "Args: skill_id (str) — ID aus dem Skill-Index. Die benötigten Tools werden danach aktiviert."
    ),
    "parameters": {
        "type": "object",
        "properties": {"skill_id": {"type": "string", "description": "ID des prozeduralen Skills."}},
        "required": ["skill_id"],
    },
}

#: z-Wert für das 95-%-Konfidenzintervall (Wilson-Lower-Bound).
WILSON_Z: Final[float] = 1.96

_STEP_REF = re.compile(r"^step_(\d+)\.([A-Za-z_][A-Za-z0-9_]*)$")


class SkillStepSpec(BaseModel):
    """Ein Schritt eines prozeduralen Skills."""

    model_config = ConfigDict(extra="ignore")

    tool: str
    input_bindings: dict[str, str] = Field(default_factory=dict)
    static_args: dict[str, Any] = Field(default_factory=dict)


class ProceduralSkillSpec(BaseModel):
    """Vollständige Spezifikation eines prozeduralen Skills."""

    model_config = ConfigDict(extra="ignore")

    skill_id: str
    name: str
    description: str = ""
    steps: list[SkillStepSpec] = Field(default_factory=list)
    source_intent: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)

    def required_tools(self) -> list[str]:
        """Eindeutige Tool-Namen in Ausführungsreihenfolge."""
        return list(dict.fromkeys(step.tool for step in self.steps))

    def validate_spec(self) -> None:
        """Prüft, dass jeder Verweis ``step_<j>.<key>`` auf einen *früheren* Schritt zeigt."""
        if not self.steps:
            raise ValueError(f"Skill {self.skill_id!r} hat keine Schritte.")
        for index, step in enumerate(self.steps):
            for arg, ref in step.input_bindings.items():
                match = _STEP_REF.match(ref)
                if match is None:
                    raise ValueError(f"Ungültige Bindung {ref!r} für Argument {arg!r} in Schritt {index}.")
                source = int(match.group(1))
                if source >= index:
                    raise ValueError(f"Bindung {ref!r} in Schritt {index} zeigt nicht auf einen früheren Schritt.")

    def to_markdown_playbook(self) -> str:
        """Playbook als Markdown mit YAML-Frontmatter. Strings sind JSON-kodiert (gültiges YAML)."""
        tools = self.required_tools()
        lines = [
            "---",
            f"skill_id: {json.dumps(self.skill_id, ensure_ascii=False)}",
            f"name: {json.dumps(self.name, ensure_ascii=False)}",
            f"description: {json.dumps(self.description, ensure_ascii=False)}",
            f"required_tools: {json.dumps(tools, ensure_ascii=False)}",
            "---",
            "",
            f"# {self.name}",
            "",
        ]
        if self.description:
            lines += [self.description, ""]
        lines.append("## Schritte")
        for index, step in enumerate(self.steps):
            lines.append(f"{index}. `{step.tool}`")
            for arg, ref in step.input_bindings.items():
                lines.append(f"   - {arg} ← {ref}")
            for arg, value in step.static_args.items():
                lines.append(f"   - {arg} = {json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)}")
        return "\n".join(lines) + "\n"


def wilson_lower_bound(successes: float, total: float, z: float = WILSON_Z) -> float:
    """Wilson-Score-Untergrenze in [0, 1] (Formel aus ``Architect/core/learning/skill_profiles.py``)."""
    if total <= 0:
        return 0.0
    p_hat = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = p_hat + z2 / (2.0 * total)
    margin = z * math.sqrt(p_hat * (1.0 - p_hat) / total + z2 / (4.0 * total * total))
    return max(0.0, min(1.0, (centre - margin) / denominator))


@dataclass(frozen=True)
class SkillRanking:
    """Eintrag des Rankings: Erfolgszähler und Wilson-Untergrenze."""

    skill_id: str
    name: str
    successes: int
    attempts: int
    wilson: float


class ProceduralSkillRegistry:
    """SQLite-Ablage prozeduraler Skills mit Erfolgsstatistik."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS procedural_skills ("
                " skill_id TEXT PRIMARY KEY,"
                " name TEXT NOT NULL,"
                " description TEXT NOT NULL DEFAULT '',"
                " spec_json TEXT NOT NULL,"
                " successes INTEGER NOT NULL DEFAULT 0,"
                " attempts INTEGER NOT NULL DEFAULT 0,"
                " wilson REAL NOT NULL DEFAULT 0.0,"
                " updated_ms INTEGER NOT NULL)"
            )
            self._conn.commit()

    def register(self, spec: ProceduralSkillSpec) -> None:
        """Legt einen Skill an oder aktualisiert Spezifikation und Beschreibung; Statistik bleibt erhalten."""
        spec.validate_spec()
        payload = json.dumps(spec.model_dump(), ensure_ascii=False, sort_keys=True, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO procedural_skills (skill_id, name, description, spec_json, updated_ms) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(skill_id) DO UPDATE SET name=excluded.name, description=excluded.description, "
                "spec_json=excluded.spec_json, updated_ms=excluded.updated_ms",
                (spec.skill_id, spec.name, spec.description, payload, int(time.time() * 1000)),
            )
            self._conn.commit()

    def get(self, skill_id: str) -> ProceduralSkillSpec | None:
        with self._lock:
            row = self._conn.execute("SELECT spec_json FROM procedural_skills WHERE skill_id = ?", (skill_id,)).fetchone()
        if row is None:
            return None
        return ProceduralSkillSpec.model_validate(json.loads(row[0]))

    def __contains__(self, skill_id: object) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM procedural_skills WHERE skill_id = ?", (str(skill_id),)).fetchone()
        return row is not None

    def record_outcome(self, skill_id: str, *, success: bool) -> float:
        """Zählt einen Lauf des Skills und liefert die neue Wilson-Untergrenze. Unbekannte IDs: ``KeyError``."""
        with self._lock:
            row = self._conn.execute(
                "SELECT successes, attempts FROM procedural_skills WHERE skill_id = ?", (skill_id,)
            ).fetchone()
            if row is None:
                raise KeyError(skill_id)
            successes = int(row[0]) + (1 if success else 0)
            attempts = int(row[1]) + 1
            wilson = wilson_lower_bound(successes, attempts)
            self._conn.execute(
                "UPDATE procedural_skills SET successes = ?, attempts = ?, wilson = ?, updated_ms = ? WHERE skill_id = ?",
                (successes, attempts, wilson, int(time.time() * 1000), skill_id),
            )
            self._conn.commit()
        return wilson

    def ranked(self, *, limit: int | None = None) -> list[SkillRanking]:
        """Skills nach Wilson-Untergrenze absteigend; bei Gleichstand gewinnt die größere Stichprobe."""
        sql = "SELECT skill_id, name, successes, attempts, wilson FROM procedural_skills ORDER BY wilson DESC, attempts DESC, skill_id"
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (max(0, limit),)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [SkillRanking(str(r[0]), str(r[1]), int(r[2]), int(r[3]), float(r[4])) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def build_compact_header_index(registry: ProceduralSkillRegistry, *, limit: int = 20) -> str:
    """Kompakter Skill-Index (eine Zeile je Skill, nach Ranking). Enthält keine Schritte, nur ID, Name und Wilson."""
    lines = []
    for entry in registry.ranked(limit=limit):
        lines.append(f"- {entry.skill_id}: {entry.name} (wilson={entry.wilson:.2f}, n={entry.attempts})")
    return "\n".join(lines)


def load_skill_payload(registry: ProceduralSkillRegistry, skill_id: str) -> dict[str, Any] | None:
    """Tool-Result für ``load_skill``: Playbook, benötigte Tools und Schritte. ``None``, wenn der Skill fehlt."""
    spec = registry.get(skill_id)
    if spec is None:
        return None
    return {
        "skill_id": spec.skill_id,
        "playbook": spec.to_markdown_playbook(),
        "required_tools": spec.required_tools(),
        "steps": [step.model_dump() for step in spec.steps],
    }


@dataclass(frozen=True)
class TrajectoryStep:
    """Ein erfolgreich ausgeführter Tool-Aufruf einer Trajektorie."""

    tool: str
    arguments: Mapping[str, Any]
    output: Any


def trajectory_from_messages(
    messages: Sequence[Mapping[str, Any]],
    results: Sequence[Any],
) -> list[TrajectoryStep]:
    """Baut die erfolgreiche Trajektorie aus Verlauf und Ergebnissen.

    Argumente kommen aus den Assistant-``tool_calls``, Ausgaben aus den ``ToolResult``-Objekten
    (``call_id``, ``ok``, ``result``). Fehlgeschlagene oder unbekannte Calls fehlen in der Liste.
    """
    ok_outputs: dict[str, Any] = {}
    for item in results:
        call_id = str(getattr(item, "call_id", ""))
        if bool(getattr(item, "ok", False)):
            ok_outputs[call_id] = getattr(item, "result", None)
    steps: list[TrajectoryStep] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            call_id = str(call.get("id", ""))
            if call_id in ok_outputs:
                arguments = call.get("arguments") or {}
                steps.append(TrajectoryStep(tool=str(call.get("name", "")), arguments=dict(arguments), output=ok_outputs[call_id]))
    return steps


class TrajectorySkillDistiller:
    """Erkennt Datenfluss in einer Trajektorie: Argumentwert == Top-Level-Ausgabe eines früheren Schritts."""

    def distill(
        self,
        steps: Sequence[TrajectoryStep],
        *,
        intent: str = "",
        skill_id: str | None = None,
    ) -> ProceduralSkillSpec | None:
        """Destilliert einen Skill. ``None`` bei weniger als zwei verschiedenen Tools."""
        if len({step.tool for step in steps}) < 2:
            return None
        out_steps: list[SkillStepSpec] = []
        for index, step in enumerate(steps):
            bindings: dict[str, str] = {}
            static: dict[str, Any] = {}
            for arg, value in step.arguments.items():
                source = self._find_source(steps[:index], value)
                if source is None:
                    static[str(arg)] = value
                else:
                    bindings[str(arg)] = f"step_{source[0]}.{source[1]}"
            out_steps.append(SkillStepSpec(tool=step.tool, input_bindings=bindings, static_args=static))
        chain = " -> ".join(step.tool for step in steps)
        sid = skill_id or f"skill_{hashlib.sha256(_canonical(out_steps).encode('utf-8')).hexdigest()[:12]}"
        spec = ProceduralSkillSpec(
            skill_id=sid,
            name=chain,
            description=f"Destilliert aus einer erfolgreichen Trajektorie: {chain}.",
            steps=out_steps,
            source_intent=intent,
            meta={"distilled": True, "step_count": len(steps)},
        )
        spec.validate_spec()
        return spec

    @staticmethod
    def _find_source(prior: Sequence[TrajectoryStep], value: Any) -> tuple[int, str] | None:
        """Sucht den jüngsten früheren Schritt, dessen Top-Level-Ausgabe genau ``value`` als Skalar enthält."""
        if not isinstance(value, (str, int, float)) or isinstance(value, bool) or value == "":
            return None
        for index in range(len(prior) - 1, -1, -1):
            output = prior[index].output
            if not isinstance(output, dict):
                continue
            for key, candidate in output.items():
                if isinstance(candidate, (str, int, float)) and not isinstance(candidate, bool) and candidate == value:
                    return index, str(key)
        return None


def _canonical(steps: Sequence[SkillStepSpec]) -> str:
    return json.dumps([step.model_dump() for step in steps], ensure_ascii=False, sort_keys=True, default=str)


__all__ = [
    "LOAD_SKILL_SCHEMA",
    "LOAD_SKILL_TOOL_NAME",
    "WILSON_Z",
    "ProceduralSkillRegistry",
    "ProceduralSkillSpec",
    "SkillRanking",
    "SkillStepSpec",
    "TrajectorySkillDistiller",
    "TrajectoryStep",
    "build_compact_header_index",
    "load_skill_payload",
    "trajectory_from_messages",
    "wilson_lower_bound",
]
