"""Die 4-Stufen-Zustandsmaschine des Prompt-Optimierers (Ping-Pong-Architektur).

Der Lauf ist ein Reissverschluss: pro Stufe ist **eine** Achse aktiv, die andere
gesperrt. Diese Datei haelt den Zustand, erzwingt die Reihenfolge, exportiert die
Artefakte, prueft die Sperren und leert nach jeder Stufe den Arbeitskontext.

Wichtige Eigenschaften (alle getestet):

* **Stufen-Gate.** Nach jeder Stufe muss :meth:`PromptOptimizer.approve` gerufen
  werden, sonst startet Stufe ``n+1`` nicht. ``auto_approve=True`` (Modus
  "DEEP-CHAIN alle 4 Stufen am Stueck") ist die einzige Ausnahme.
* **Cache Eviction.** Nach jeder Stufe wird der Arbeitskontext geeraeumt; die
  naechste Stufe laedt ausschliesslich die Checkpoints von der Platte
  (``stage_N.model.json``). Stufe 4 liest 1, 2 und 3 gleichzeitig frisch.
* **Sperr-Pruefung.** Ein gesperrter Fingerprint, der sich aendert, ist ein
  :class:`LockViolation` -- kein Hinweis, ein Abbruch.
* **Final ist final.** Ein Dokument mit ``4-final``-Marker wird bei erneutem
  Lauf unveraendert zurueckgegeben (:class:`StageResult.no_op`).
* **Coverage.** Stufe 4 prueft ``[F-..]`` und ``[R-..]`` gegen das Manifest und
  bricht bei Verlust mit :class:`CoverageError` ab.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..atomic import atomic_write_bytes
from .extract import parse_draft
from .gates import GateFiller, expand_document
from .model import (
    ARTIFACT_NORMAL,
    FINAL_MARKER,
    REQUIRED_SECTIONS,
    STAGE_ARTIFACTS,
    Mode,
    ScoreCard,
    StageDocument,
    Subsystem,
)
from .render import (
    DEFAULT_CONSTRAINTS,
    DEFAULT_CONTRACT,
    render_baseline,
    render_body,
    render_normal,
    render_stage,
)
from .research import LocalSourceChecker, ResearchProvider, harden_document
from .scorecard import (
    LockViolation,
    Measurement,
    build_scorecard,
    check_final_immutability,
    enforce_lock,
    measure_content,
    measure_technique,
)

__all__ = [
    "ApprovalRequired",
    "CoverageError",
    "OptimizerError",
    "PromptOptimizer",
    "StageOrderError",
    "StageResult",
    "default_security",
    "resolve_mode",
]

#: Ausdrueckliche Befehle, die den erweiterten Modus oeffnen. Das blosse Wort
#: "Research" oder "Deep Research" im Entwurf ist **kein** Ausloeser.
DEEP_TRIGGERS: tuple[str, ...] = (
    "erweiterte optimierung",
    "erweiterten modus",
    "deep optimization",
    "deep-chain",
    "deep chain",
    "modus: erweitert",
    "modus: deep",
    "4-stufen-kette",
    "viertstufenkette",
    "starte 4-stufen",
    "starte die 4-stufen",
)


def resolve_mode(explicit: str | Mode | None = None, text: str = "") -> tuple[Mode, str]:
    """Ermittelt den Modus. Ohne ausdruecklichen Befehl gilt ``NORMAL``."""
    if explicit is not None:
        return Mode.parse(explicit), "explizite Angabe"
    folded = text.casefold()
    for trigger in DEEP_TRIGGERS:
        if trigger in folded:
            return Mode.DEEP_CHAIN, f"Befehl im Text: „{trigger}“"
    return Mode.NORMAL, "Standard (kein Deep-Chain-Befehl)"


class OptimizerError(RuntimeError):
    """Basisklasse aller Abbruchgruende des Optimierers."""


class StageOrderError(OptimizerError):
    """Eine Stufe wurde ausser der Reihe angefordert."""


class ApprovalRequired(OptimizerError):
    """Die vorherige Stufe ist noch nicht freigegeben (Stufen-Gate)."""


class CoverageError(OptimizerError):
    """Ein Feature oder Research-Blatt fehlt im finalen Dokument."""


def default_security(doc: StageDocument) -> list[str]:
    """Sicherheitsgrenzen: allgemeine Vertragsregeln plus Hinweise aus dem Entwurf."""
    base = [
        "Der Optimierer liest und schreibt ausschließlich im Export-Verzeichnis; er startet keine Netz-Aufrufe.",
        "Research ist nur über einen Provider mit Quellen-Tiering erlaubt; jede Aussage ohne Locator bleibt `OFFEN`.",
        "Ein gesperrter Fingerprint bricht den Lauf ab — lieber kein Artefakt als ein unbemerkt verändertes.",
    ]
    cues = ("secret", "token", "auth", "passwort", "api_key", "credential", "scrape", "sandbox", "injection", "tls", "berechtigung")
    for feature in doc.features:
        folded = feature.title.casefold()
        if any(cue in folded for cue in cues):
            base.append(f"Sicherheitsgrenze zu `[{feature.fid}]`: Umgang mit Geheimnissen und Berechtigungen muss belegt sein, nicht behauptet.")
    return base


@dataclass(frozen=True)
class StageResult:
    """Ergebnis einer ausgeführten Stufe."""

    stage: int
    artifact: str
    path: Path
    markdown: str
    scorecard: ScoreCard
    awaiting_approval: bool
    coverage: tuple[str, ...] = ()
    no_op: bool = False

    def render(self) -> str:
        """Telemetrie plus Handover-Informationen (Datei, Gate, Coverage)."""
        lines = [self.scorecard.render().rstrip("\n"), ""]
        status = "unverändert zurückgegeben (`4-final` ist final)" if self.no_op else f"geschrieben: `{self.path}`"
        lines.append(f"- **Export:** {status}")
        if self.coverage:
            lines.append(f"- **Coverage:** {' · '.join(self.coverage)}")
        if self.awaiting_approval:
            lines.append(f"- **Stufen-Gate:** geschlossen — Freigabe für Stufe {self.stage + 1} erforderlich (`approve()`).")
        lines.append("- **Arbeitskontext:** geleert (nächste Stufe lädt ausschließlich Checkpoints von der Platte).")
        return "\n".join(lines) + "\n"


class PromptOptimizer:
    """Führt den Rohentwurf durch die 4-Stufen-Kette (oder den Ein-Durchlauf)."""

    def __init__(
        self,
        draft: str,
        *,
        out_dir: Path | str,
        mode: str | Mode | None = None,
        auto_approve: bool = False,
        filler: GateFiller | None = None,
        provider: ResearchProvider | None = None,
        checker: LocalSourceChecker | None = None,
        title: str = "",
    ) -> None:
        self.draft = draft
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.mode, self.mode_reason = resolve_mode(mode, draft)
        self.auto_approve = auto_approve
        self.filler = filler
        self.provider = provider
        self.checker = checker
        self.title = title
        self._context: dict[str, object] = {}
        self._stage = 0
        self._approved = True
        self._scores: dict[int, tuple[int, int]] = {}
        self._state_path = self.out_dir / "run_state.json"
        self._restore()

    def _restore(self) -> None:
        """Setzt einen abgebrochenen Lauf am letzten Checkpoint fort (CLI-Nutzung)."""
        if not self._state_path.exists():
            return
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._stage = int(state.get("stage", 0))
        self._approved = bool(state.get("approved", True))
        self._scores = {
            int(stage): (int(values[0]), int(values[1]))
            for stage, values in (state.get("scores") or {}).items()
            if isinstance(values, list) and len(values) == 2
        }

    # ------------------------------------------------------------------ Pfade
    def artifact_path(self, stage: int) -> Path:
        return self.out_dir / STAGE_ARTIFACTS[stage]

    def model_path(self, stage: int) -> Path:
        return self.out_dir / f"stage_{stage}.model.json"

    # ------------------------------------------------------------- Zustand
    def _write(self, path: Path, text: str) -> Path:
        atomic_write_bytes(path, text.encode("utf-8"))
        return path

    def _save_model(self, doc: StageDocument) -> None:
        self._write(self.model_path(doc.stage), doc.dumps())

    def _load(self, stage: int) -> StageDocument:
        """Frischer Read von der Platte — es gibt keinen In-Memory-Kanal."""
        raw = self.model_path(stage).read_text(encoding="utf-8")
        return StageDocument.from_dict(json.loads(raw))

    def _evict(self) -> None:
        """Cache Eviction: kein Arbeitskontext über eine Stufe hinweg."""
        self._context = {}

    def _save_state(self) -> None:
        state = {
            "mode": self.mode.value,
            "mode_reason": self.mode_reason,
            "stage": self._stage,
            "approved": self._approved,
            "scores": {str(stage): list(values) for stage, values in sorted(self._scores.items())},
            "context_empty": not self._context,
            "artifacts": {str(stage): str(self.artifact_path(stage).name) for stage in range(0, self._stage + 1)},
        }
        self._write(self._state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    @property
    def state(self) -> dict[str, Any]:
        """Kopie des persistierten Zustands (Diagnose/Tests)."""
        data: dict[str, Any] = json.loads(self._state_path.read_text(encoding="utf-8"))
        return data

    @property
    def current_stage(self) -> int:
        """Zuletzt abgeschlossene Stufe (0 = nur Baseline)."""
        return self._stage

    @property
    def scores(self) -> dict[int, tuple[int, int]]:
        return dict(self._scores)

    # ------------------------------------------------------------ Baseline
    def prepare(self) -> StageResult:
        """Stufe 0: Baseline des unveraenderten Rohentwurfs."""
        if self.model_path(0).exists():
            doc0 = self._load(0)
            markdown = self.artifact_path(0).read_text(encoding="utf-8")
            content, technique = self._measure_baseline(doc0, markdown)
            self._scores[0] = (content.points, technique.points)
            card = build_scorecard(
                0,
                STAGE_ARTIFACTS[0],
                content=content,
                technique=technique,
                before_content=0,
                before_technique=0,
            )
            self._save_state()
            return StageResult(0, STAGE_ARTIFACTS[0], self.artifact_path(0), markdown, card, awaiting_approval=False)

        doc0 = parse_draft(self.draft, mode=self.mode)
        if self.title:
            doc0.title = self.title
        content, technique = self._measure_document(doc0, render_baseline)
        card = build_scorecard(
            0,
            STAGE_ARTIFACTS[0],
            content=content,
            technique=technique,
            before_content=0,
            before_technique=0,
        )
        markdown = render_baseline(doc0, card)
        self._save_model(doc0)
        self._write(self.artifact_path(0), markdown)
        self._scores[0] = (content.points, technique.points)
        self._stage = 0
        self._approved = True
        self._evict()
        self._save_state()
        return StageResult(0, STAGE_ARTIFACTS[0], self.artifact_path(0), markdown, card, awaiting_approval=False)

    def _measure_document(self, doc: StageDocument, renderer) -> tuple[Measurement, Measurement]:
        """Misst das Nutzdokument ohne Telemetrie (keine Selbstbeeinflussung)."""
        placeholder = build_scorecard(
            0,
            "measure.md",
            content=Measurement(0, (0, 0, 0, 0), ()),
            technique=Measurement(0, (0, 0, 0, 0), ()),
            before_content=0,
            before_technique=0,
        )
        body = renderer(doc, placeholder).split("---\n\n### 📊", 1)[0]
        unresolved = len(doc.conflicts) if doc.stage == 0 else 0
        return measure_content(doc, body), measure_technique(doc, body, unresolved_conflicts=unresolved)

    def _measure_baseline(self, doc: StageDocument, text: str) -> tuple[Measurement, Measurement]:
        body = text.split("---\n\n### 📊", 1)[0]
        unresolved = len(doc.conflicts)
        return measure_content(doc, body), measure_technique(doc, body, unresolved_conflicts=unresolved)

    # --------------------------------------------------------------- Stufen
    def approve(self) -> None:
        """Oeffnet das Stufen-Gate fuer die naechste Stufe."""
        self._approved = True
        self._save_state()

    def run_stage(self, stage: int) -> StageResult:
        """Fuehrt genau eine Stufe aus (1..4) und respektiert das Stufen-Gate."""
        if stage not in (1, 2, 3, 4):
            raise StageOrderError(f"Stufe {stage} existiert nicht (erlaubt: 1..4).")
        if not self.model_path(0).exists():
            self.prepare()
        if stage != self._stage + 1:
            raise StageOrderError(f"Stufe {stage} ist nicht als nächstes dran (aktuell: {self._stage}).")
        if stage > 1 and not (self._approved or self.auto_approve):
            raise ApprovalRequired(f"Stufe {stage - 1} ist nicht freigegeben — Stufe {stage} bleibt gesperrt.")
        handler = {1: self._stage1, 2: self._stage2, 3: self._stage3, 4: self._stage4}[stage]
        result = handler()
        self._stage = stage
        self._approved = self.auto_approve
        self._evict()
        self._save_state()
        return result

    def run_all(self) -> list[StageResult]:
        """DEEP-CHAIN am Stueck: Stufen 1..4 mit automatischer Freigabe.

        Existiert bereits ein finales Dokument, wird es unveraendert
        zurueckgegeben -- kein zweiter Durchlauf, kein Rewrite.
        """
        final = self.artifact_path(4)
        if final.exists() and FINAL_MARKER in final.read_text(encoding="utf-8"):
            return [self._final_no_op(final)]
        results: list[StageResult] = []
        explicit = self.auto_approve
        # "Alle Stufen am Stück" ist selbst der ausdrückliche Befehl: der Lauf
        # öffnet seine Gates, sonst wäre die Fortsetzung nach einem Abbruch
        # ohne zusätzliche Freigabe unmöglich.
        self.auto_approve = True
        try:
            if self.current_stage == 0:
                results.append(self.prepare())
            for stage in range(self.current_stage + 1, 5):
                results.append(self.run_stage(stage))
                self.approve()
        finally:
            self.auto_approve = explicit
        return results

    def run_normal(self) -> StageResult:
        """MODUS NORMAL: ein einziger Durchlauf ``0 -> 1-final``."""
        doc0 = parse_draft(self.draft, mode=Mode.NORMAL)
        if self.title:
            doc0.title = self.title
        doc = StageDocument(
            stage=1,
            mode=Mode.NORMAL,
            title=doc0.title,
            goal=doc0.goal,
            features=doc0.features,
            subsystems=[Subsystem(sid=sub.sid, title=sub.title, features=list(sub.features)) for sub in doc0.subsystems],
            constraints=list(DEFAULT_CONSTRAINTS),
            security=default_security(doc0),
            decisions=[f"[ENTSCHEIDUNG NÖTIG] {conflict}" for conflict in doc0.conflicts],
            contract=list(DEFAULT_CONTRACT),
            draft_sha256=doc0.draft_sha256,
            draft_text=doc0.draft_text,
            sections=list(REQUIRED_SECTIONS),
            conflicts=list(doc0.conflicts),
        )
        # Ein Durchlauf: die Gates werden direkt auf das Gesamtziel beantwortet.
        expand_document(doc, self.filler)
        doc.leaves = []
        body = render_normal_body(doc)
        content = measure_content(doc, body)
        technique = measure_technique(doc, body, unresolved_conflicts=0)
        card = build_scorecard(
            stage=1,
            artifact=ARTIFACT_NORMAL,
            content=content,
            technique=technique,
            before_content=0,
            before_technique=0,
            mode=Mode.NORMAL,
            label="1-final",
        )
        markdown = render_normal(doc, card)
        path = self._write(self.out_dir / ARTIFACT_NORMAL, markdown)
        self._save_model(doc)
        self._scores[1] = (card.content.after, card.technique.after)
        self._stage = 1
        self._approved = True
        self._evict()
        self._save_model(doc)
        self._save_state()
        return StageResult(1, ARTIFACT_NORMAL, path, markdown, card, awaiting_approval=False)

    # ---------------------------------------------------------- Stufe 1
    def _stage1(self) -> StageResult:
        base = self._load(0)
        doc = StageDocument(
            stage=1,
            mode=Mode.DEEP_CHAIN if self.mode is Mode.DEEP_CHAIN else Mode.NORMAL,
            title=base.title,
            goal=base.goal,
            features=base.features,
            subsystems=[Subsystem(sid=sub.sid, title=sub.title, features=list(sub.features)) for sub in base.subsystems],
            constraints=list(DEFAULT_CONSTRAINTS),
            security=default_security(base),
            decisions=[f"[ENTSCHEIDUNG NÖTIG] {conflict}" for conflict in base.conflicts],
            contract=list(DEFAULT_CONTRACT),
            draft_sha256=base.draft_sha256,
            draft_text="",
            sections=[*REQUIRED_SECTIONS, "research"],
            conflicts=list(base.conflicts),
        )
        self._assert_no_feature_drift(base, doc)
        body = render_body(doc)
        content = measure_content(doc, body)
        technique = measure_technique(doc, body, unresolved_conflicts=0)
        before_content, before_technique = self._scores[0]
        card = build_scorecard(
            1,
            STAGE_ARTIFACTS[1],
            content=content,
            technique=technique,
            before_content=before_content,
            before_technique=before_technique,
        )
        markdown = render_stage(doc, card)
        self._save_model(doc)
        path = self._write(self.artifact_path(1), markdown)
        self._scores[1] = (card.content.after, card.technique.after)
        return StageResult(1, STAGE_ARTIFACTS[1], path, markdown, card, awaiting_approval=not self.auto_approve)

    @staticmethod
    def _assert_no_feature_drift(before: StageDocument, after: StageDocument) -> None:
        """Zero-Feature-Drop: gleiche IDs, gleiche Titel, gleiche Zuordnung."""
        left = [(feature.fid, feature.title, feature.subsystem) for feature in before.features]
        right = [(feature.fid, feature.title, feature.subsystem) for feature in after.features]
        if left != right:
            raise LockViolation(after.stage, "content", f"{len(left)} Features", f"{len(right)} Features")

    # ---------------------------------------------------------- Stufe 2
    def _stage2(self) -> StageResult:
        previous = self._load(1)
        doc = StageDocument.from_dict(previous.to_dict())
        doc.stage = 2
        expand_document(doc, self.filler)
        enforce_lock(doc, previous, "technique")
        body = render_body(doc)
        content = measure_content(doc, body)
        technique = measure_technique(doc, body, unresolved_conflicts=0)
        before_content, before_technique = self._scores[1]
        card = build_scorecard(
            2,
            STAGE_ARTIFACTS[2],
            content=content,
            technique=technique,
            before_content=before_content,
            before_technique=before_technique,
        )
        markdown = render_stage(doc, card)
        self._save_model(doc)
        path = self._write(self.artifact_path(2), markdown)
        self._scores[2] = (card.content.after, card.technique.after)
        return StageResult(2, STAGE_ARTIFACTS[2], path, markdown, card, awaiting_approval=not self.auto_approve)

    # ---------------------------------------------------------- Stufe 3
    def _stage3(self) -> StageResult:
        previous = self._load(2)
        doc = StageDocument.from_dict(previous.to_dict())
        doc.stage = 3
        harden_document(doc, self.provider, self.checker)
        enforce_lock(doc, previous, "technique")
        body = render_body(doc)
        content = measure_content(doc, body)
        technique = measure_technique(doc, body, unresolved_conflicts=0)
        before_content, before_technique = self._scores[2]
        card = build_scorecard(
            3,
            STAGE_ARTIFACTS[3],
            content=content,
            technique=technique,
            before_content=before_content,
            before_technique=before_technique,
        )
        markdown = render_stage(doc, card)
        self._save_model(doc)
        path = self._write(self.artifact_path(3), markdown)
        self._scores[3] = (card.content.after, card.technique.after)
        return StageResult(3, STAGE_ARTIFACTS[3], path, markdown, card, awaiting_approval=not self.auto_approve)

    # ---------------------------------------------------------- Stufe 4
    def _stage4(self) -> StageResult:
        existing = self.artifact_path(4)
        if existing.exists() and FINAL_MARKER in existing.read_text(encoding="utf-8"):
            markdown = existing.read_text(encoding="utf-8")
            card = self._card_from_final(markdown)
            return StageResult(4, STAGE_ARTIFACTS[4], existing, markdown, card, awaiting_approval=False, no_op=True)

        first = self._load(1)
        second = self._load(2)
        third = self._load(3)
        self._context["fresh_read"] = [first.draft_sha256, second.stage, third.stage]
        doc = StageDocument(
            stage=4,
            mode=Mode.DEEP_CHAIN,
            title=third.title,
            goal=third.goal,
            features=list(third.features),
            subsystems=[Subsystem.from_dict(subsystem.to_dict()) for subsystem in third.subsystems],
            leaves=list(third.leaves),
            constraints=list(third.constraints),
            security=list(third.security),
            decisions=list(third.decisions),
            contract=list(SYNTHESIS_CONTRACT),
            draft_sha256=third.draft_sha256,
            draft_text="",
            sections=[*REQUIRED_SECTIONS, "research", "fakten", "coverage"],
            conflicts=list(third.conflicts),
        )
        enforce_lock(doc, third, "content")
        body = render_body(doc)
        coverage = self._coverage(doc, body, strict=True)
        content = measure_content(doc, body)
        technique = measure_technique(doc, body, unresolved_conflicts=0)
        before_content, before_technique = self._scores[3]
        card = build_scorecard(
            4,
            STAGE_ARTIFACTS[4],
            content=content,
            technique=technique,
            before_content=before_content,
            before_technique=before_technique,
        )
        markdown = render_stage(doc, card)
        check_final_immutability(4, "", markdown)
        self._save_model(doc)
        path = self._write(existing, markdown)
        self._scores[4] = (card.content.after, card.technique.after)
        return StageResult(4, STAGE_ARTIFACTS[4], path, markdown, card, awaiting_approval=False, coverage=coverage)

    def _final_no_op(self, path: Path) -> StageResult:
        markdown = path.read_text(encoding="utf-8")
        card = self._card_from_final(markdown)
        self._stage = 4
        self._approved = False
        return StageResult(
            4,
            STAGE_ARTIFACTS[4],
            path,
            markdown,
            card,
            awaiting_approval=False,
            no_op=True,
        )

    def _card_from_final(self, markdown: str) -> ScoreCard:
        """Liest die Telemetrie eines bereits finalen Dokuments nicht neu — sie gilt."""
        content, technique = self._scores.get(4, self._scores.get(3, (0, 0)))
        note = ("Final unverändert zurückgegeben - keine Neubewertung, kein Rewrite.",)
        return build_scorecard(
            4,
            STAGE_ARTIFACTS[4],
            content=Measurement(content, (0, 0, 0, 0), note),
            technique=Measurement(technique, (0, 0, 0, 0), note),
            before_content=content,
            before_technique=technique,
        )

    # --------------------------------------------------------- Coverage
    def _coverage(self, doc: StageDocument, text: str, *, strict: bool) -> tuple[str, ...]:
        fid_missing = [feature.fid for feature in doc.features if f"[{feature.fid}]" not in text]
        rid_missing = [leaf.rid for leaf in doc.leaves if f"[{leaf.rid}]" not in text]
        feature_line = f"Features: {len(doc.features) - len(fid_missing)}/{len(doc.features)} = 100 % enthalten"
        leaf_line = f"Research-Blätter: {len(doc.leaves) - len(rid_missing)}/{len(doc.leaves)} = 100 % enthalten"
        if strict and (fid_missing or rid_missing):
            raise CoverageError(f"Coverage verletzt: fehlende Features {fid_missing}, fehlende Blätter {rid_missing}.")
        return (feature_line, leaf_line)


#: Ausgabevertrag der Reverse-Synthese (Stufe 4). Struktur, keine Inhalte.
SYNTHESIS_CONTRACT: tuple[str, ...] = (
    "Dieses Dokument ist die Reverse-Synthese aus Stufe 1 bis 3 und ohne weitere Umschreibung ausführbar.",
    "Jeder `[F-xx]`- und `[R-xx]`-Anker ist Pflicht; die Coverage-Zeile weist 100 % maschinell nach.",
    "Verifizierte Fakten stehen wörtlich im Fakten-Register; unbelegte Aussagen bleiben `OFFEN`.",
    "Die Telemetrie am Ende ist Teil des Artefakts: sie nennt Zahl, Kriterium und Nachweis.",
)


def render_normal_body(doc: StageDocument) -> str:
    """Nutzdokument des Modus ``NORMAL`` ohne Telemetrie (Messgrundlage)."""
    from .render import render_normal as _render_normal

    dummy = build_scorecard(
        1,
        ARTIFACT_NORMAL,
        content=Measurement(0, (0, 0, 0, 0), ()),
        technique=Measurement(0, (0, 0, 0, 0), ()),
        before_content=0,
        before_technique=0,
        mode=Mode.NORMAL,
        label="1-final",
    )
    text = _render_normal(doc, dummy)
    return text.split("---\n\n### 📊", 1)[0]


def final_marker_present(text: str) -> bool:
    """Schneller Vertragstest fuer "ist dieses Dokument schon final?"."""
    return FINAL_MARKER in text


def coverage_tokens(text: str) -> tuple[int, int]:
    """Anzahl der im Text vorhandenen Feature- und Blatt-Anker (Diagnose)."""
    return (len(set(re.findall(r"\[F-\d{2,3}\]", text))), len(set(re.findall(r"\[R-\d{2,3}\]", text))))
