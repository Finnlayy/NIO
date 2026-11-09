"""Datenmodell des dynamischen Prompt-Optimierers (Ping-Pong-Architektur).

Der Optimierer trennt zwei Achsen strikt: **Prompting-Technik** (Struktur,
Komprimierung, LLM-Steuerung) und **Fach-Inhalt** (Domaene, UI/UX, Fakten).
Pro Stufe ist genau eine Achse aktiv, die andere ist gesperrt. Dieses Modul
haelt ausschliesslich die Daten, die diese Invarianten transportieren:

* :class:`Mode` -- ``NORMAL`` (ein Durchlauf) oder ``DEEP_CHAIN`` (4 Stufen).
* :class:`HardGate` -- die vier verpflichtenden Tiefen-Pruefungen.
* :class:`Feature`/:class:`Subsystem`/:class:`ResearchLeaf` -- das Material,
  das die Stufen weiterschieben (``[F-..]``, ``[S-..]``, ``[R-..]``).
* :class:`StageDocument` -- der vollstaendige Stand einer Stufe inklusive
  Fingerprints, mit denen die Sperren maschinell geprueft werden.
* :class:`ScoreCard` -- die vorgeschriebene Dual-Achsen-Telemetrie.

Stdlib-only, keine Importe nach oben (``core/`` importiert nichts aus
``orchestrator/`` oder ``limbs/``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any

__all__ = [
    "ARTIFACT_NORMAL",
    "FINAL_MARKER",
    "HARD_GATES",
    "MODE_MARKER",
    "PASS_MARKER",
    "STAGE_ARTIFACTS",
    "Axis",
    "Feature",
    "GateAnswer",
    "HardGate",
    "Mode",
    "ResearchLeaf",
    "ScoreCard",
    "Source",
    "StageDocument",
    "Subsystem",
    "fingerprint",
]


class Mode(StrEnum):
    """Betriebsmodus. ``ERWEITERT`` ist ein Alias fuer ``DEEP_CHAIN``."""

    NORMAL = "normal"
    DEEP_CHAIN = "deep-chain"

    @classmethod
    def parse(cls, value: str | Mode | None) -> Mode:
        """Nimmt beliebige Schreibweisen (``deep``, ``ERWEITERT``, ``4-stufen``)."""
        if isinstance(value, Mode):
            return value
        raw = (value or "").strip().casefold()
        if raw in {"deep", "deep-chain", "deep_chain", "deepchain", "erweitert", "extended", "4", "4-stufen", "4-stufen-kette"}:
            return cls.DEEP_CHAIN
        return cls.NORMAL


#: Dateinamen der Exporte (Checkpointing). Stufe 0 ist der Baseline-Snapshot
#: des Rohentwurfs und traegt die "Vorher"-Werte der ersten Scorecard.
STAGE_ARTIFACTS: dict[int, str] = {
    0: "stage_0_baseline.md",
    1: "stage_1_macro_skeleton.md",
    2: "stage_2_domain_expansion.md",
    3: "stage_3_verified_research_leaves.md",
    4: "stage_4_FINAL_MASTER_PROMPT.md",
}

#: Ergebnisdatei des Modus ``NORMAL`` (ein einziger Durchlauf, keine Kette).
ARTIFACT_NORMAL = "optimized_prompt.md"

#: Pass-Marker, die jede Stufe in den Kopf ihres Artefakts schreibt.
PASS_MARKER: dict[int, str] = {1: "1", 2: "2", 3: "3", 4: "4-final"}
MODE_MARKER = "ERWEITERT"
FINAL_MARKER = "<!-- prompt-optimizer-pass: 4-final; status: FINAL -->"


@dataclass(frozen=True)
class HardGate:
    """Eine der vier verpflichtenden Tiefen-Pruefungen."""

    key: str
    index: int
    title: str
    question: str

    @property
    def label(self) -> str:
        return f"Hard Gate {self.index} — {self.title}"


#: Reihenfolge und Wortlaut sind Vertrag: die Gates werden in jeder Stufe
#: sichtbar beantwortet, nie stillschweigend uebersprungen.
HARD_GATES: tuple[HardGate, ...] = (
    HardGate(
        "G1",
        1,
        "Professioneller Maßstab",
        "Was würde ein Top-Experte in genau diesem Fachgebiet hier tun, wonach der aktuelle Entwurf noch nicht fragt?",
    ),
    HardGate(
        "G2",
        2,
        "Rohestes Ausgangsmaterial",
        "Von welchem rohesten Ausgangsmaterial (Bytes, Spezifikationen, Schemata, State-Transitions) würde ein Profi starten statt von vorverdauter Prosa?",
    ),
    HardGate(
        "G3",
        3,
        "Spezifische Methoden & Werkzeuge",
        "Welche konkreten Methoden, Algorithmen, Protokolle und Werkzeuge würde er einsetzen?",
    ),
    HardGate(
        "G4",
        4,
        "Unabhängiger Erfolgsnachweis",
        "Welcher objektive, maschinen- oder drittprüfbare Beweis zeigt eindeutig, dass das Ergebnis korrekt ist?",
    ),
)

GATES_BY_KEY: dict[str, HardGate] = {gate.key: gate for gate in HARD_GATES}


def fingerprint(parts: list[str] | tuple[str, ...]) -> str:
    """Kurzer, stabiler Fingerprint ueber eine sortierte Liste von Zeilen."""
    digest = sha256()
    for part in sorted(part.strip() for part in parts if part and part.strip()):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:16]


@dataclass(frozen=True)
class Feature:
    """Ein Feature aus dem Rohentwurf. ``fid`` ist der ``[F-xx]``-Anker."""

    fid: str
    title: str
    subsystem: str
    source_ref: str = ""
    explicit_id: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "fid": self.fid,
            "title": self.title,
            "subsystem": self.subsystem,
            "source_ref": self.source_ref,
            "explicit_id": self.explicit_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Feature:
        return cls(
            fid=str(data["fid"]),
            title=str(data["title"]),
            subsystem=str(data["subsystem"]),
            source_ref=str(data.get("source_ref", "")),
            explicit_id=bool(data.get("explicit_id", False)),
        )


@dataclass
class GateAnswer:
    """Antwort-Container eines Hard Gates. ``open_items`` bleibt sichtbar."""

    gate: str
    items: list[str] = field(default_factory=list)
    open_items: list[str] = field(default_factory=list)
    source: str = "struct"

    @property
    def complete(self) -> bool:
        return bool(self.items) and not self.open_items

    @property
    def anchor_count(self) -> int:
        return len(self.items) + len(self.open_items)

    def to_dict(self) -> dict[str, Any]:
        return {"gate": self.gate, "items": list(self.items), "open_items": list(self.open_items), "source": self.source}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GateAnswer:
        return cls(
            gate=str(data["gate"]),
            items=[str(item) for item in data.get("items", [])],
            open_items=[str(item) for item in data.get("open_items", [])],
            source=str(data.get("source", "struct")),
        )


@dataclass
class Subsystem:
    """Ein Subsystem-Block ``[S-xx]`` mit seinen Gate-Antworten."""

    sid: str
    title: str
    features: list[str] = field(default_factory=list)
    gates: dict[str, GateAnswer] = field(default_factory=dict)
    interfaces: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    raw_material: list[str] = field(default_factory=list)

    def gate(self, key: str) -> GateAnswer:
        return self.gates.setdefault(key, GateAnswer(gate=key))

    @property
    def raw_material_anchors(self) -> list[str]:
        """Anker aus Gate 2 plus explizit gelistetes Rohmaterial."""
        anchors = list(self.raw_material)
        anchors.extend(self.gate("G2").items)
        return [anchor for anchor in anchors if anchor.strip()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sid": self.sid,
            "title": self.title,
            "features": list(self.features),
            "gates": {key: answer.to_dict() for key, answer in sorted(self.gates.items())},
            "interfaces": list(self.interfaces),
            "edge_cases": list(self.edge_cases),
            "raw_material": list(self.raw_material),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Subsystem:
        return cls(
            sid=str(data["sid"]),
            title=str(data["title"]),
            features=[str(item) for item in data.get("features", [])],
            gates={str(key): GateAnswer.from_dict(value) for key, value in (data.get("gates") or {}).items()},
            interfaces=[str(item) for item in data.get("interfaces", [])],
            edge_cases=[str(item) for item in data.get("edge_cases", [])],
            raw_material=[str(item) for item in data.get("raw_material", [])],
        )


@dataclass(frozen=True)
class Source:
    """Quelle einer Blatt-Aussage.

    ``tier``: 0 = unbelegt, 1 = entwurfsintern, 2 = Primaerquelle mit Locator
    und woertlichem Zitat, 3 = zusaetzlich lokal nachgeprueft (Checksum /
    Datei / Test). Verifiziert ist ein Blatt erst ab Tier 2 **und** gesetztem
    ``checked``-Flag.
    """

    tier: int
    locator: str
    quote: str = ""
    retrieved_at: str = ""
    checked: bool = False

    @property
    def verified(self) -> bool:
        return self.tier >= 2 and bool(self.quote.strip()) and self.checked

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "locator": self.locator,
            "quote": self.quote,
            "retrieved_at": self.retrieved_at,
            "checked": self.checked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        return cls(
            tier=int(data.get("tier", 0)),
            locator=str(data.get("locator", "")),
            quote=str(data.get("quote", "")),
            retrieved_at=str(data.get("retrieved_at", "")),
            checked=bool(data.get("checked", False)),
        )


@dataclass
class ResearchLeaf:
    """Ein Research-Blatt ``[R-xx]`` aus Stufe 2, gehaertet in Stufe 3."""

    rid: str
    sid: str
    gate: str
    question: str
    status: str = "OFFEN"
    sources: list[Source] = field(default_factory=list)
    kill_criteria: str = ""
    uncertainty: str = ""

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIZIERT" and any(source.verified for source in self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rid": self.rid,
            "sid": self.sid,
            "gate": self.gate,
            "question": self.question,
            "status": self.status,
            "sources": [source.to_dict() for source in self.sources],
            "kill_criteria": self.kill_criteria,
            "uncertainty": self.uncertainty,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchLeaf:
        return cls(
            rid=str(data["rid"]),
            sid=str(data["sid"]),
            gate=str(data.get("gate", "G3")),
            question=str(data.get("question", "")),
            status=str(data.get("status", "OFFEN")),
            sources=[Source.from_dict(item) for item in data.get("sources", [])],
            kill_criteria=str(data.get("kill_criteria", "")),
            uncertainty=str(data.get("uncertainty", "")),
        )


#: Pflicht-Sektionen des Makro-Skeletts. Die Reihenfolge ist der Vertrag, gegen
#: den die Technik-Sperre der Stufen 2 und 3 geprueft wird.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "rolle_ziel",
    "feature_manifest",
    "globale_constraints",
    "sicherheitsgrenzen",
    "subsysteme",
    "ausgabevertrag",
    "entscheidungen",
)

#: Anzeigenamen der Pflicht-Sektionen (deutsch, wie im Artefakt).
SECTION_TITLES: dict[str, str] = {
    "rolle_ziel": "Rolle & Ziel",
    "feature_manifest": "Feature-Manifest",
    "globale_constraints": "Globale Constraints",
    "sicherheitsgrenzen": "Sicherheitsgrenzen",
    "subsysteme": "Subsystem-Blöcke",
    "ausgabevertrag": "Ausgabevertrag",
    "entscheidungen": "Entscheidungen & aufgelöste Widersprüche",
    "research": "Research-Blätter",
    "fakten": "Fakten-Register (verifiziert)",
    "coverage": "Coverage-Nachweis",
}


@dataclass
class StageDocument:
    """Der vollstaendige Stand einer Stufe — Eingabe fuer Renderer und Scorecard."""

    stage: int
    mode: Mode
    title: str
    goal: str
    features: list[Feature] = field(default_factory=list)
    subsystems: list[Subsystem] = field(default_factory=list)
    leaves: list[ResearchLeaf] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    security: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    contract: list[str] = field(default_factory=list)
    research_notes: list[str] = field(default_factory=list)
    draft_sha256: str = ""
    draft_text: str = ""
    sections: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    # ---- Anker -----------------------------------------------------------
    @property
    def feature_ids(self) -> list[str]:
        return [feature.fid for feature in self.features]

    @property
    def subsystem_ids(self) -> list[str]:
        return [subsystem.sid for subsystem in self.subsystems]

    @property
    def leaf_ids(self) -> list[str]:
        return [leaf.rid for leaf in self.leaves]

    def subsystem(self, sid: str) -> Subsystem:
        for subsystem in self.subsystems:
            if subsystem.sid == sid:
                return subsystem
        raise KeyError(sid)

    def features_of(self, sid: str) -> list[Feature]:
        return [feature for feature in self.features if feature.subsystem == sid]

    # ---- Sperren ---------------------------------------------------------
    @property
    def content_fingerprint(self) -> str:
        """Inhaltliche Identitaet: Features, Fakten, Entscheidungen.

        Aendert sich dieser Wert zwischen einer inhaltlich gesperrten Stufe und
        ihrem Vorgaenger, hat der Lauf Inhalte erfunden oder geloescht.
        """
        parts = [feature.fid + "::" + feature.title for feature in self.features]
        parts.extend(leaf.question + "::" + leaf.status for leaf in self.leaves)
        for leaf in self.leaves:
            parts.extend(source.locator + "::" + source.quote for source in leaf.sources)
        return fingerprint(parts)

    @property
    def technique_fingerprint(self) -> str:
        """Strukturelle Identitaet: Sektionsfolge plus Operator-Geruest."""
        parts = [f"SECTION::{name}" for name in self.sections]
        parts.extend(f"SID::{sid}" for sid in self.subsystem_ids)
        parts.extend(f"CONTRACT::{line}" for line in self.contract)
        return fingerprint(parts)

    # ---- Serialisierung --------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "mode": self.mode.value,
            "title": self.title,
            "goal": self.goal,
            "features": [feature.to_dict() for feature in self.features],
            "subsystems": [subsystem.to_dict() for subsystem in self.subsystems],
            "leaves": [leaf.to_dict() for leaf in self.leaves],
            "constraints": list(self.constraints),
            "security": list(self.security),
            "decisions": list(self.decisions),
            "contract": list(self.contract),
            "research_notes": list(self.research_notes),
            "draft_sha256": self.draft_sha256,
            "sections": list(self.sections),
            "conflicts": list(self.conflicts),
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageDocument:
        return cls(
            stage=int(data["stage"]),
            mode=Mode.parse(str(data.get("mode", "deep-chain"))),
            title=str(data.get("title", "")),
            goal=str(data.get("goal", "")),
            features=[Feature.from_dict(item) for item in data.get("features", [])],
            subsystems=[Subsystem.from_dict(item) for item in data.get("subsystems", [])],
            leaves=[ResearchLeaf.from_dict(item) for item in data.get("leaves", [])],
            constraints=[str(item) for item in data.get("constraints", [])],
            security=[str(item) for item in data.get("security", [])],
            decisions=[str(item) for item in data.get("decisions", [])],
            contract=[str(item) for item in data.get("contract", [])],
            research_notes=[str(item) for item in data.get("research_notes", [])],
            draft_sha256=str(data.get("draft_sha256", "")),
            sections=[str(item) for item in data.get("sections", [])],
            conflicts=[str(item) for item in data.get("conflicts", [])],
        )


@dataclass(frozen=True)
class Axis:
    """Eine Achse der Telemetrie: Status, Vorher, Aktuell, Nachweis."""

    name: str
    status: str
    before: int
    after: int
    evidence: tuple[str, ...] = ()
    criteria: tuple[int, ...] = ()

    @property
    def delta(self) -> int:
        return self.after - self.before

    @property
    def locked(self) -> bool:
        return self.status.startswith("LOCK")


@dataclass(frozen=True)
class ScoreCard:
    """Die vorgeschriebene Dual-Achsen-Telemetrie einer Stufe."""

    stage: int
    artifact: str
    content: Axis
    technique: Axis
    label: str = ""

    @property
    def total(self) -> tuple[int, int]:
        return (self.content.after, self.technique.after)

    def render(self) -> str:
        """Rendert exakt die vertraglich vereinbarte Markdown-Tabelle."""
        shown = self.label or str(self.stage)
        head = (
            f"### 📊 Optimierungs-Telemetrie (Stufe {shown} von 4 — Export: `{self.artifact}`)\n"
            "| Dimension | Status in Stufe "
            f"{shown} | Vorher | Aktuell | Delta (Δ) | Nachweis & Haupttreiber |\n"
            "| :--- | :---: | :---: | :---: | :---: | :--- |\n"
        )
        rows = []
        for label, axis in (
            ("**1. Inhaltliche Tiefe (Domäne & Kontext)**", self.content),
            ("**2. Prompting-Technik (LLM-Steuerung)**", self.technique),
        ):
            evidence = "<br>".join(escape_cell(item) for item in axis.evidence if item.strip()) or "—"
            rows.append(
                f"| {label} | `[{axis.status}]` | {axis.before} % | **{axis.after} %** | "
                f"**{axis.delta:+d} %** | {evidence} |"
            )
        return head + "\n".join(rows) + "\n"


def escape_cell(text: str) -> str:
    """Macht eine Zeile tabellenfest (Pipes und Zeilenumbrueche)."""
    return text.replace("|", "\\|").replace("\n", " ")
