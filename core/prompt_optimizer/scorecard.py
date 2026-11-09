"""Dual-Achsen-Telemetrie und Sperr-Pruefung (deterministisch, 4 x 25 %).

Die Prozentwerte werden **nicht** geschaetzt, sondern aus dem Artefakt gezaehlt.
Jede Achse besteht aus vier Kriterien zu je 25 Punkten:

Inhaltliche Tiefe            Prompting-Technik
1. Feature-Vollstaendigkeit  1. Makro-Topologie & Hierarchie
2. Spezialisten-Rohmaterial  2. Widerspruchsfreiheit
3. Verifizierte Primaerfakten 3. Signal-to-Noise / Attention-Routing
4. Randfall-/Schnittstellentiefe 4. Maschinenpruefbare Verifikations-Gates

Sperr-Semantik: Ist eine Achse gesperrt (``LOCK``), wird ihr Wert aus dem
Vorgaenger-Checkpoint uebernommen -- nicht neu berechnet. Das ist Absicht:
eine Sperre ist ein Vertrag, keine Messung. Zusaetzlich muss der Fingerprint
der gesperrten Achse unveraendert sein, sonst fliegt :class:`LockViolation`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Axis, Mode, ScoreCard, StageDocument

__all__ = [
    "ACTIVE",
    "LOCKED",
    "LockViolation",
    "Measurement",
    "build_scorecard",
    "check_final_immutability",
    "enforce_lock",
    "measure_content",
    "measure_technique",
    "substantive_lines",
]

ACTIVE = "AKTIV"
LOCKED = "LOCK 🔒"

CONTENT_CRITERIA = (
    "Feature-Vollständigkeit",
    "Spezialisten-Rohmaterial",
    "Verifizierte Primärfakten",
    "Randfall- & Schnittstellen-Tiefe",
)

TECHNIQUE_CRITERIA = (
    "Makro-Topologie & Hierarchie",
    "Widerspruchsfreiheit",
    "Signal-to-Noise / Attention-Routing",
    "Maschinenprüfbare Verifikations-Gates",
)

_FID = re.compile(r"\[F-\d{2,3}\]")
_RID = re.compile(r"\[R-\d{2,3}\]")
_COVERAGE = re.compile(r"\[F-01\.\.\d+[^\]]*\]\s*(?:&|und)\s*\[R-01\.\.\d+[^\]]*\]\s*=\s*100\s*%")


class LockViolation(RuntimeError):
    """Eine gesperrte Achse wurde inhaltlich oder strukturell veraendert."""

    def __init__(self, stage: int, axis: str, before: str, after: str) -> None:
        super().__init__(f"Stufe {stage}: Sperre der Achse „{axis}“ verletzt ({before} -> {after}).")
        self.stage = stage
        self.axis = axis
        self.before = before
        self.after = after


@dataclass(frozen=True)
class Measurement:
    """Messwert einer aktiven Achse inklusive der vier Einzelkriterien."""

    points: int
    criteria: tuple[int, int, int, int]
    notes: tuple[str, ...]

    def scaled(self, value: float) -> int:
        """Rundet einen Anteil 0..1 auf 0..25 Punkte, nie ueber die Kappungsgrenze."""
        return max(0, min(25, round(25 * max(0.0, min(1.0, value)))))


def substantive_lines(text: str) -> list[str]:
    """Traegt Information: keine Leerzeile, kein reines Markup, kein Einzelwort."""
    lines: list[str] = []
    fenced = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not stripped:
            continue
        plain = re.sub(r"^[#>*\-+|:\s]+", "", stripped)
        plain = re.sub(r"`", "", plain)
        if len(plain) < 12:
            continue
        if set(plain) <= set("-|: "):
            continue
        lines.append(plain)
    return lines


def _unique_ratio(text: str) -> float:
    lines = substantive_lines(text)
    if not lines:
        return 0.0
    keys = {re.sub(r"\s+", " ", line).casefold() for line in lines}
    return len(keys) / len(lines)


def _section_present(doc: StageDocument, name: str, text: str) -> bool:
    if name in doc.sections:
        return True
    from .model import SECTION_TITLES  # lokaler Import: vermeidet Zyklus beim Modulstart

    title = SECTION_TITLES.get(name, name)
    return title.casefold() in text.casefold()


def measure_content(doc: StageDocument, text: str) -> Measurement:
    """Inhaltliche Tiefe: 4 x 25 Punkte, alle aus dem Artefakt gezaehlt."""
    features_total = len(doc.features)
    found_ids = {match.group(0) for match in _FID.finditer(text)}
    coverage = (sum(1 for feature in doc.features if f"[{feature.fid}]" in found_ids) / features_total) if features_total else 0.0
    c1 = max(0, min(25, round(25 * coverage)))

    subs = doc.subsystems
    raw_hits = [subsystem.title for subsystem in subs if subsystem.raw_material_anchors]
    c2 = max(0, min(25, round(25 * (len(raw_hits) / len(subs))))) if subs else 0

    leaves_total = len(doc.leaves)
    verified = [leaf for leaf in doc.leaves if leaf.verified]
    c3 = max(0, min(25, round(25 * (len(verified) / leaves_total)))) if leaves_total else 0

    interfaced = [subsystem.title for subsystem in subs if subsystem.interfaces and subsystem.edge_cases]
    c4 = max(0, min(25, round(25 * (len(interfaced) / len(subs))))) if subs else 0

    notes = (
        f"Feature-Vollständigkeit {c1}/25: {int(coverage * features_total)}/{features_total} `[F-xx]` im Artefakt verankert (Zero-Feature-Drop-Gate).",
        f"Spezialisten-Rohmaterial {c2}/25: {len(raw_hits)}/{len(subs)} Subsysteme mit typisiertem Rohmaterial-Container (Bytes/Schema/State-Transitions).",
        f"Verifizierte Primärfakten {c3}/25: {len(verified)}/{leaves_total} Research-Blätter mit Tier≥2-Quelle, Zitat und lokalem Prüfvermerk.",
        f"Randfall- & Schnittstellen-Tiefe {c4}/25: {len(interfaced)}/{len(subs)} Subsysteme mit belegter Schnittstelle **und** belegtem Randfall.",
    )
    return Measurement(points=c1 + c2 + c3 + c4, criteria=(c1, c2, c3, c4), notes=notes)


def measure_technique(doc: StageDocument, text: str, *, unresolved_conflicts: int = 0) -> Measurement:
    """Prompting-Technik: 4 x 25 Punkte, alle aus dem Artefakt gezaehlt."""
    from .model import REQUIRED_SECTIONS

    present = [name for name in REQUIRED_SECTIONS if _section_present(doc, name, text)]
    t1 = max(0, min(25, round(25 * (len(present) / len(REQUIRED_SECTIONS)))))

    t2 = max(0, min(25, 25 - 5 * max(0, unresolved_conflicts)))

    ratio = _unique_ratio(text)
    t3 = max(0, min(25, round(25 * ratio)))

    gates_present = 0
    if _FID.search(text):
        gates_present += 1
    if _RID.search(text):
        gates_present += 1
    if re.search(r"Nachweis|Verifikation|Gate-Prüfung", text, re.IGNORECASE):
        gates_present += 1
    if _COVERAGE.search(text):
        gates_present += 1
    t4 = max(0, min(25, round(25 * (gates_present / 4))))

    notes = (
        f"Makro-Topologie {t1}/25: {len(present)}/{len(REQUIRED_SECTIONS)} Pflicht-Sektionen vorhanden ({', '.join(present) or '—'}).",
        f"Widerspruchsfreiheit {t2}/25: {unresolved_conflicts} offene Widersprüche (jeder offene kostet 5 Punkte; aufgelöste werden zu Entscheidungen).",
        f"Signal-to-Noise {t3}/25: {ratio:.0%} eindeutige Zeilen — Duplikate senken den Wert, ID-Referenzen statt Wiederholung heben ihn.",
        f"Verifikations-Gates {t4}/25: {gates_present}/4 maschinell prüfbare Marker (`[F-xx]`, `[R-xx]`, Nachweis-Sektion, Coverage-Zeile).",
    )
    return Measurement(points=t1 + t2 + t3 + t4, criteria=(t1, t2, t3, t4), notes=notes)


def enforce_lock(doc: StageDocument, previous: StageDocument, axis: str) -> None:
    """Prueft einen Sperr-Fingerprint und wirft bei Abweichung ``LockViolation``."""
    if axis == "content":
        before, after = previous.content_fingerprint, doc.content_fingerprint
    else:
        before, after = previous.technique_fingerprint, doc.technique_fingerprint
    if before != after:
        raise LockViolation(doc.stage, axis, before, after)


def check_final_immutability(stage: int, previous_text: str, new_text: str) -> bool:
    """Ein bereits finalisiertes Dokument wird nie ein zweites Mal umgeschrieben."""
    from .model import FINAL_MARKER

    if FINAL_MARKER in previous_text:
        if previous_text != new_text:
            raise LockViolation(stage, "final", "4-final", "rewrite")
        return True
    return False


STATUSES: dict[int, tuple[str, str]] = {
    1: (LOCKED, ACTIVE),
    2: (ACTIVE, LOCKED),
    3: (ACTIVE, LOCKED),
    4: (LOCKED, ACTIVE),
}


def build_scorecard(
    stage: int,
    artifact: str,
    *,
    content: Measurement,
    technique: Measurement,
    before_content: int,
    before_technique: int,
    mode: Mode = Mode.DEEP_CHAIN,
    label: str | None = None,
) -> ScoreCard:
    """Setzt die Telemetrie zusammen; gesperrte Achsen tragen ihren Vorwert."""
    if mode is Mode.NORMAL or stage not in STATUSES:
        # Ein Durchlauf: beide Achsen werden in derselben Stufe gemessen.
        content_status = technique_status = ACTIVE
    else:
        content_status, technique_status = STATUSES[stage]
    content_after = before_content if content_status == LOCKED else content.points
    technique_after = before_technique if technique_status == LOCKED else technique.points
    return ScoreCard(
        stage=stage,
        artifact=artifact,
        content=Axis(
            "Inhaltliche Tiefe (Domäne & Kontext)",
            content_status,
            before_content,
            content_after,
            content.notes,
            content.criteria if content_status == ACTIVE else (),
        ),
        technique=Axis(
            "Prompting-Technik (LLM-Steuerung)",
            technique_status,
            before_technique,
            technique_after,
            technique.notes,
            technique.criteria if technique_status == ACTIVE else (),
        ),
        label=label or "",
    )
