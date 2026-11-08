"""Deterministische Extraktion des Rohentwurfs (Stufe 0).

Der Optimierer darf nichts erfinden. Alles, was in spaeteren Stufen als
Feature, Subsystem oder Widerspruch auftaucht, muss aus dem Entwurf selbst
stammen. Dieses Modul macht den Entwurf deshalb zuerst maschinenlesbar:

* **Features** -- Aufzaehlungspunkte (und, falls es keine gibt, Modal-
  saetze mit ``muss``/``soll``/``must``/``shall``) werden zu ``[F-01]..[F-NN]``.
  Explizit im Text vorhandene IDs (``[F-07]``) bleiben erhalten.
* **Subsysteme** -- Ueberschriften bilden die Gliederung; generische
  Ueberschriften ("Anforderungen", "Ziel") werden ueber eine feste
  Domaenen-Heuristik geclustert.
* **Widersprueche** -- nur solche, die beweisbar sind: derselbe Schluessel
  mit zwei Zahlenwerten, oder ein exklusives Merkmal, das im Text einmal
  bejaht und einmal verneint wird.

Alles Heuristik, aber ohne Zufall: gleicher Text -> gleiches Ergebnis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from hashlib import sha256

from .model import REQUIRED_SECTIONS, Feature, Mode, StageDocument, Subsystem

__all__ = ["Conflict", "detect_conflicts", "extract_features", "parse_draft", "slugify"]

#: Generische Ueberschriften tragen keine Domaene -- sie werden geclustert.
GENERIC_HEADINGS = {
    "ziel",
    "ziele",
    "goal",
    "goals",
    "anforderungen",
    "requirements",
    "features",
    "funktionen",
    "funktion",
    "umfang",
    "scope",
    "hinweise",
    "notes",
    "aufgabe",
    "aufgaben",
    "kontext",
    "context",
    "muss",
    "must",
    "soll",
    "sollte",
    "todo",
    "offen",
    "details",
    "beschreibung",
}

#: Domaenen-Cluster fuer Features ohne aussagekraeftige Ueberschrift.
#: Reihenfolge ist Prioritaet: der erste Treffer gewinnt.
DOMAIN_CLUSTERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("UI/UX & Rendering", ("ui", "ux", "webgl", "shader", "canvas", "render", "layout", "widget", "chart", "animation", "farbe", "design", "frontend", "visual")),
    ("IPC & Speicher", ("ipc", "off-heap", "offheap", "shared memory", "shmem", "mmap", "ring buffer", "ringbuffer", "zero-copy", "worker", "thread", "queue", "serialisierung")),
    ("Voice & NCM", ("voice", "sprache", "speech", "asr", "tts", "mikrofon", "audio", "ncm", "whisper", "dialog")),
    ("Security & Scraping", ("security", "sicherheit", "auth", "token", "secret", "scrape", "scraper", "proxy", "sandbox", "injection", "tls", "rate-limit", "robots")),
    ("Daten & Persistenz", ("datenbank", "storage", "schema", "sqlite", "postgres", "index", "cache", "persistenz", "journal", "migration")),
    ("Telemetrie & Evaluation", ("telemetrie", "metric", "monitoring", "evaluation", "eval", "trace", "audit", "log")),
)

FALLBACK_SUBSYSTEM = "Kern & Orchestrierung"

#: Exklusive Merkmale: bejaht und verneint im selben Entwurf ist ein Widerspruch.
EXCLUSIVE_TOKENS: tuple[str, ...] = (
    "offline",
    "online",
    "synchron",
    "asynchron",
    "websocket",
    "polling",
    "zustandslos",
    "stateful",
    "zstd",
    "gzip",
)

_NEGATION = re.compile(r"\b(nicht|ohne|kein|keine|keinen|keinerlei|nie|niemals|no)\b", re.IGNORECASE)
_NUMBER_KV = re.compile(
    r"(?P<key>[A-Za-zÄÖÜäöüß][\w\-äöüß]*(?:\s+[A-Za-zÄÖÜäöüß][\w\-äöüß]*){0,3})\s*[:=]\s*"
    r"(?P<val>\d+(?:[.,]\d+)?\s*(?:ms|s|sec|sek|min|h|%|px|mb|gb|kb|hz|fps|eur|€|x)?)",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d{1,2}[.)])\s+(?P<body>\S.*)$")
_HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*#*$")
_EXPLICIT_FID = re.compile(r"\[F-(\d{1,3})\]")
_MODAL = re.compile(r"\b(muss|müssen|soll|sollen|sollte|must|shall|needs? to|erfordert)\b", re.IGNORECASE)

MAX_FEATURES = 60


@dataclass(frozen=True)
class Conflict:
    """Ein beweisbarer Widerspruch im Rohentwurf."""

    kind: str
    key: str
    values: tuple[str, ...]
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def render(self) -> str:
        joined = " / ".join(self.values) if self.values else "—"
        proof = "; ".join(self.evidence[:2])
        return f"{self.kind}: „{self.key}“ ist mehrdeutig ({joined}) — Beleg: {proof}"


def slugify(text: str) -> str:
    """Stabiler ASCII-Slug fuer Vergleiche (keine Umlaute, keine Satzzeichen)."""
    table = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
    lowered = text.casefold().translate(table)
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def _clean(text: str) -> str:
    """Entfernt Markdown-Dekoration, behaelt aber Code-Tokens."""
    cleaned = text.strip()
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\w)[*_]([^*_]+)[*_](?!\w)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" .;:")


def _cluster_for(text: str) -> str:
    folded = text.casefold()
    for name, keywords in DOMAIN_CLUSTERS:
        if any(keyword in folded for keyword in keywords):
            return name
    return FALLBACK_SUBSYSTEM


def _iter_lines(text: str) -> list[str]:
    """Zeilen ohne Fenced-Code-Bloecke (Code ist Belegmaterial, kein Feature)."""
    lines: list[str] = []
    fenced = False
    for raw in text.splitlines():
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            lines.append(raw)
    return lines


def _feature_candidates(lines: list[str]) -> list[tuple[str, str]]:
    """(Text, Domaenen-Kontext) je Kandidat. Kontext = letzte Ueberschrift."""
    candidates: list[tuple[str, str]] = []
    heading = ""
    bullets = 0
    for line in lines:
        match = _HEADING.match(line)
        if match:
            heading = match.group("title").strip()
            continue
        bullet = _BULLET.match(line)
        if bullet:
            text = _clean(bullet.group("body"))
            if len(text) >= 8:
                candidates.append((text, heading))
                bullets += 1
    if bullets >= 3:
        return candidates
    # Fallback: Modal-Saetze, wenn der Entwurf keine belastbare Liste hat.
    heading = ""
    for line in lines:
        match = _HEADING.match(line)
        if match:
            heading = match.group("title").strip()
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line.strip()):
            text = _clean(sentence)
            if len(text) >= 20 and _MODAL.search(text):
                candidates.append((text, heading))
    return candidates


def extract_features(text: str) -> list[Feature]:
    """Features in Dokumentreihenfolge, dedupliziert, mit stabilen ``[F-xx]``."""
    explicit: list[str] = []
    for match in _EXPLICIT_FID.finditer(text):
        fid = f"F-{int(match.group(1)):02d}"
        if fid not in explicit:
            explicit.append(fid)

    seen: set[str] = set()
    features: list[Feature] = []
    for title, heading in _feature_candidates(_iter_lines(text)):
        key = slugify(title)
        if not key or key in seen:
            continue
        seen.add(key)
        subsystem = heading if heading and heading.casefold() not in GENERIC_HEADINGS else _cluster_for(f"{heading} {title}")
        features.append(Feature(fid="", title=title, subsystem=subsystem, source_ref=heading or "Entwurf"))
        if len(features) >= MAX_FEATURES:
            break

    # Explizite IDs zuerst binden, danach fortlaufend numerieren.
    for index, feature in enumerate(features):
        if index < len(explicit):
            features[index] = Feature(
                fid=explicit[index],
                title=feature.title,
                subsystem=feature.subsystem,
                source_ref=feature.source_ref,
                explicit_id=True,
            )
        else:
            features[index] = Feature(
                fid=f"F-{index + 1:02d}",
                title=feature.title,
                subsystem=feature.subsystem,
                source_ref=feature.source_ref,
            )
    return features


def _subsystems_for(features: list[Feature]) -> list[Subsystem]:
    order: list[str] = []
    grouped: dict[str, list[str]] = {}
    for feature in features:
        if feature.subsystem not in grouped:
            grouped[feature.subsystem] = []
            order.append(feature.subsystem)
        grouped[feature.subsystem].append(feature.fid)
    return [
        Subsystem(sid=f"S-{index + 1:02d}", title=title, features=grouped[title])
        for index, title in enumerate(order)
    ]


def detect_conflicts(text: str) -> list[Conflict]:
    """Nur beweisbare Widersprueche -- keine Vermutungen."""
    conflicts: list[Conflict] = []

    keyed: dict[str, dict[str, str]] = {}
    for match in _NUMBER_KV.finditer(text):
        key = re.sub(r"\s+", " ", match.group("key")).strip().casefold()
        value = re.sub(r"\s+", "", match.group("val")).casefold()
        if len(key) < 4:
            continue
        keyed.setdefault(key, {}).setdefault(value, match.group(0).strip())
    for key, values in keyed.items():
        if len(values) > 1:
            conflicts.append(Conflict("Zahlenwiderspruch", key, tuple(values), tuple(values.values())))

    for token in EXCLUSIVE_TOKENS:
        pattern = re.compile(rf"(?<![\w-]){re.escape(token)}(?![\w-])", re.IGNORECASE)
        affirmed: list[str] = []
        negated: list[str] = []
        for match in pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            window = text[line_start : match.start()]
            snippet = _line_of(text, match.start())
            if _NEGATION.search(window):
                negated.append(snippet)
            else:
                affirmed.append(snippet)
        if affirmed and negated:
            conflicts.append(Conflict("Ausschlusswiderspruch", token, ("bejaht", "verneint"), (affirmed[0], negated[0])))
    return conflicts


def _line_of(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return _clean(text[start : end if end != -1 else len(text)])[:160]


def _title_of(text: str) -> str:
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match and len(match.group("level")) == 1:
            return _clean(match.group("title"))
    for line in text.splitlines():
        if line.strip():
            return _clean(line)[:90]
    return "Rohentwurf"


def _goal_of(text: str, title: str) -> str:
    lines = [line.strip() for line in _iter_lines(text)]
    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            continue
        if _HEADING.match(line) or _BULLET.match(line):
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        paragraphs.append(" ".join(buffer))
    for paragraph in paragraphs:
        cleaned = re.sub(r"\s+", " ", paragraph).strip()
        if len(cleaned) >= 15 and cleaned.rstrip(".") != title:
            return cleaned if cleaned.endswith((".", "!", "?", ":")) else cleaned + "."
    return title


def parse_draft(text: str, *, mode: Mode = Mode.NORMAL) -> StageDocument:
    """Baut den Baseline-Snapshot (Stufe 0) aus dem Rohentwurf."""
    title = _title_of(text)
    features = extract_features(text)
    conflicts = detect_conflicts(text)
    subsystems = _subsystems_for(features)
    # Feature -> Subsystem-ID (nicht Titel): ohne diese Bindung findet die
    # Auffaecherung in Stufe 2 keine Features zu ihrem Block.
    by_title = {subsystem.title: subsystem.sid for subsystem in subsystems}
    features = [replace(feature, subsystem=by_title.get(feature.subsystem, feature.subsystem)) for feature in features]
    sections = ["rolle_ziel"] if _goal_of(text, title) != title else []
    sections.append("feature_manifest")
    return StageDocument(
        stage=0,
        mode=mode,
        title=title,
        goal=_goal_of(text, title),
        features=features,
        subsystems=subsystems,
        constraints=[],
        security=[],
        decisions=[],
        contract=[],
        draft_sha256=sha256(text.encode("utf-8")).hexdigest(),
        draft_text=text,
        sections=sections,
        conflicts=[conflict.render() for conflict in conflicts],
    )


def required_section_keys() -> tuple[str, ...]:
    """Die Pflicht-Sektionen des Makro-Skeletts (Vertrag der Technik-Sperre)."""
    return REQUIRED_SECTIONS
