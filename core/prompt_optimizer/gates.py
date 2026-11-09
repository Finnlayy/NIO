"""Die vier Tiefen-Hard-Gates und ihre strukturelle Auffaecherung (Stufe 2).

Ein Gate wird **nie** mit Prosa beantwortet, die nicht belegbar ist. Der
Standard-Filler (:class:`StructuralFiller`) erzeugt deshalb *Anforderungs-
Container*: eine konkrete, subsystem-spezifische Frage plus die Prueflatte,
an der eine spaetere Antwort gemessen wird. Genau das ist der Unterschied
zwischen "breit auffaechern" und "Fakten erfinden".

Wer echte Fachantworten einspeisen will (LLM, Mensch, Datenbank), implementiert
:class:`GateFiller` und uebergibt die Instanz an die Pipeline. Alles, was ein
Filler als ``open_items`` zurueckgibt, bleibt in der Scorecard als Luecke
sichtbar -- der Optimierer glaettet nichts weg.

Struktur-Regeln, die dieses Modul garantiert:

* jedes Subsystem bekommt **alle vier** Gate-Container,
* jedes Gate nennt mindestens einen Anker (Item oder offener Punkt),
* Aussagen ueber den Entwurf ("nennt keine Zahl") werden am Entwurf geprueft,
  nicht behauptet,
* Research-Blaetter entstehen aus den offenen Gate-Punkten, nicht daneben.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from .model import HARD_GATES, Feature, GateAnswer, HardGate, ResearchLeaf, StageDocument, Subsystem

__all__ = [
    "DomainProfile",
    "GateFiller",
    "StructuralFiller",
    "build_leaves",
    "expand_document",
    "profile_for",
]

#: Merkmale, die auf eine echte Schnittstelle im Entwurf hindeuten.
INTERFACE_CUES: tuple[str, ...] = (
    "api",
    "protokoll",
    "protocol",
    "event",
    "webhook",
    "endpoint",
    "schnittstelle",
    "import",
    "export",
    "schema",
    "vertrag",
    "cli",
    "rpc",
    "grpc",
    "mqtt",
    "sse",
)

#: Merkmale, die auf einen echten Randfall hindeuten.
EDGE_CUES: tuple[str, ...] = (
    "fehler",
    "ausfall",
    "timeout",
    "race",
    "deadlock",
    "offline",
    "abbruch",
    "retry",
    "grenzfall",
    "leer",
    "null",
    "überlauf",
    "ueberlauf",
    "overflow",
    "migration",
    "konflikt",
    "429",
    "quota",
    "backpressure",
    "absturz",
)


class DomainProfile:
    """Typisiertes Rohmaterial je Domaenen-Cluster (Fragen, keine Fakten)."""

    def __init__(self, name: str, raw_material: tuple[str, ...], standard: str) -> None:
        self.name = name
        self.raw_material = raw_material
        self.standard = standard


PROFILES: tuple[tuple[tuple[str, ...], DomainProfile], ...] = (
    (
        ("ui", "ux", "render", "webgl", "canvas", "widget", "chart", "animation", "farbe", "design", "frontend"),
        DomainProfile(
            "UI/UX & Rendering",
            (
                "State-Transition-Diagramm der sichtbaren Zustaende (leer/laden/fehler/aktiv)",
                "Frame- und Interaction-Budget als Millisekunden-Tabelle je Zustandswechsel",
                "Pixel-/Layout-Spezifikation (Raster, Kontrast, Fokusringe) als Rohwerte",
            ),
            "Ein UI-Spezialist beginnt beim Zustandsmodell und beim Messwert, nicht beim Mockup.",
        ),
    ),
    (
        ("ipc", "off-heap", "offheap", "shared", "shmem", "mmap", "ring", "queue", "worker", "thread", "zero-copy"),
        DomainProfile(
            "IPC & Speicher",
            (
                "Struct-Layout mit Byte-Offsets und Alignment je Feld",
                "Ringpuffer-Header als Bitfeld (write/index/seq) inklusive Wrap-Regel",
                "Backpressure- und Abbruch-Protokoll als Sequenzdiagramm",
            ),
            "Ein IPC-Spezialist beginnt beim Layout und bei der Speicherordnung, nicht beim Wrapper.",
        ),
    ),
    (
        ("voice", "sprache", "speech", "asr", "tts", "audio", "mikrofon", "ncm", "whisper", "dialog"),
        DomainProfile(
            "Voice & NCM",
            (
                "Audio-Pipeline als Tabelle aus Sample-Rate, Chunk-Groesse und Puffer-Tiefe",
                "Latenz-Budget je Segment (Aufnahme, ASR, Antwort, TTS) in ms",
                "Abbruch-/Barge-in-Semantik als Zustandsmaschine",
            ),
            "Ein Voice-Spezialist beginnt beim Zeitbudget und bei der Abbruch-Semantik.",
        ),
    ),
    (
        ("security", "sicherheit", "auth", "token", "secret", "scrape", "scraper", "proxy", "sandbox", "robots"),
        DomainProfile(
            "Security & Scraping",
            (
                "Threat-Model als STRIDE-Zeilen mit Eintritts- und Schadensmass",
                "Token-/Session-Lebensdauer als Zustandsmaschine mit Ablaufzeitpunkten",
                "Roh-HTTP-Vertrag des Zielsystems (Status, Header, Rate-Limit, robots)",
            ),
            "Ein Security-Spezialist beginnt beim Bedrohungsmodell und beim Rohtranskript.",
        ),
    ),
    (
        ("daten", "data", "storage", "datenbank", "schema", "sqlite", "postgres", "index", "cache", "persistenz"),
        DomainProfile(
            "Daten & Persistenz",
            (
                "Tabellen-Schema als DDL inklusive Constraints und Indizes",
                "Query-Plan und Kardinalitaets-Schaetzung fuer den heissesten Pfad",
                "Migrations- und Rollback-Skript als nummerierte Schritte",
            ),
            "Ein Daten-Spezialist beginnt beim DDL und beim Plan, nicht beim ORM-Modell.",
        ),
    ),
    (
        ("telemetrie", "telemetry", "metric", "monitoring", "evaluation", "eval", "trace", "audit"),
        DomainProfile(
            "Telemetrie & Evaluation",
            (
                "Event-Schema als JSON-Schema mit Pflichtfeldern und Einheiten",
                "Kennzahlen-Definition als Formel (Zaehler/Nenner) je Kennzahl",
                "Trace-Format als Spaltenliste mit Zeitstempel-Semantik",
            ),
            "Ein Evaluations-Spezialist beginnt beim Schema und bei der Formel, nicht beim Dashboard.",
        ),
    ),
)

DEFAULT_PROFILE = DomainProfile(
    "Kern & Orchestrierung",
    (
        "Spezifikationsausschnitt mit Version und Abschnittsnummer",
        "Schnittstellen-Schema als Roh-Bytes (JSON oder IDL)",
        "Zustandsmaschine des Ablaufs inklusive Fehlerzustaenden",
    ),
    "Ein Spezialist beginnt bei der Spezifikation und beim Zustandsmodell.",
)


class GateFiller(Protocol):
    """Schnittstelle fuer echte Fachantworten (LLM, Mensch, Wissensbasis)."""

    def answer(self, subsystem: Subsystem, gate: HardGate, features: Sequence[Feature]) -> GateAnswer:
        """Liefert die Antwort auf genau ein Gate fuer genau ein Subsystem."""


def profile_for(title: str) -> DomainProfile:
    """Waehlt das Domaenenprofil mit den meisten Treffern (nicht das erste).

    Reine Teilstring-Suche mit "erster Treffer gewinnt" war zu grob: "UI" steckt
    auch in "zwischen Worker und UI", obwohl das Subsystem IPC ist. Deshalb
    zaehlen distinkte Treffer, Gleichstand entscheidet die Profil-Reihenfolge.
    """
    folded = title.casefold()
    best: DomainProfile | None = None
    best_hits = 0
    for keywords, profile in PROFILES:
        hits = sum(1 for keyword in keywords if keyword in folded)
        if hits > best_hits:
            best, best_hits = profile, hits
    return best or DEFAULT_PROFILE


def _has_digit(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _short(text: str, limit: int = 72) -> str:
    """Kuerzt lange Feature-Titel fuer die Interpolation (Anker bleibt der `[F-xx]`)."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "…"


class StructuralFiller:
    """Standard-Filler: Anforderungs-Container statt erfundener Fachfakten."""

    def answer(self, subsystem: Subsystem, gate: HardGate, features: Sequence[Feature]) -> GateAnswer:
        profile = profile_for(" ".join([subsystem.title, *(feature.title for feature in features)]))
        names = [_short(feature.title) for feature in features[:3]]
        primary = names[0] if names else subsystem.title
        quoted = " / ".join(f"„{name}“" for name in names) or f"„{subsystem.title}“"
        items: list[str] = []
        open_items: list[str] = []

        if gate.key == "G1":
            items.append(f"Qualitätslatte für {quoted}: p95-Latenz, Determinismus und Fehlertoleranz beziffern (Zahl + Messpunkt).")
            items.append(profile.standard)
            if not any(_has_digit(name) for name in names):
                open_items.append(f"OFFEN: Für {primary} nennt der Entwurf keine Schwelle — Zahl und Bezugspunkt sind zu setzen.")
            else:
                open_items.append(f"OFFEN: Schwelle für {primary} steht im Entwurf ohne Bezugspunkt (worauf gemessen?) — prüfen.")
        elif gate.key == "G2":
            items.extend(f"Rohmaterial: {anchor}." for anchor in profile.raw_material)
            open_items.append(f"OFFEN: Quelle der Wahrheit für {primary} ist nicht benannt — Spezifikation mit Version/Abschnitt festlegen.")
        elif gate.key == "G3":
            items.append(f"Methode für {quoted}: Protokoll/Algorithmus benennen und Version pinnen.")
            items.append("Werkzeugkette festlegen: Messwerkzeug, Prüfwerkzeug, Reproduktionskommando.")
            open_items.append(f"OFFEN: Werkzeug und Version für {primary} sind offen.")
        else:
            items.append(f"Nachweis für {quoted}: ein Test oder eine Schema-Validierung, die ohne Modell und ohne Nutzer entscheidet.")
            items.append("Abbruchkriterium: Der Nachweis muss bei absichtlich eingebautem Fehler rot werden (Mutation).")
            open_items.append(f"OFFEN: Kein ausführbarer Nachweis für {primary} im Entwurf — Gate bleibt bis Stufe 3 offen.")
        return GateAnswer(gate=gate.key, items=items, open_items=open_items, source="struct")


def _cues(features: Sequence[Feature], cues: Sequence[str]) -> list[str]:
    hits: list[str] = []
    for feature in features:
        folded = feature.title.casefold()
        if any(cue in folded for cue in cues):
            hits.append(feature.title)
    return hits


def interfaces_for(subsystem: Subsystem, features: Sequence[Feature]) -> list[str]:
    """Nur echte Schnittstellen-Hinweise aus dem Entwurf (keine Platzhalter)."""
    return [f"Schnittstelle: „{title}“ (Ein-/Ausgangsvertrag prüfen)" for title in _cues(features, INTERFACE_CUES)]


def edge_cases_for(subsystem: Subsystem, features: Sequence[Feature]) -> list[str]:
    """Nur echte Randfall-Hinweise aus dem Entwurf (keine Platzhalter)."""
    return [f"Randfall: „{title}“ (Fehler-/Grenzverhalten belegen)" for title in _cues(features, EDGE_CUES)]


def research_question(subsystem: Subsystem, features: Sequence[Feature], gate: HardGate) -> str:
    primary = _short(features[0].title) if features else subsystem.title
    if gate.key == "G2":
        return f"Welches Rohmaterial (Bytes/Schema/State-Transitions) ist für „{primary}“ die Quelle der Wahrheit, und wo ist es normativ spezifiziert?"
    if gate.key == "G3":
        return f"Welches Protokoll bzw. welcher Algorithmus löst „{primary}“ messbar, und welche Version ist zu pinnen?"
    return f"Welcher drittprüfbare Nachweis zeigt, dass „{primary}“ korrekt ist (Test, Schema-Validierung, Checksum)?"


def build_leaves(doc: StageDocument) -> list[ResearchLeaf]:
    """Research-Blaetter aus den offenen Gate-Punkten der Subsysteme."""
    leaves: list[ResearchLeaf] = []
    counter = 0
    for subsystem in doc.subsystems:
        features = doc.features_of(subsystem.sid)
        for gate in HARD_GATES:
            if gate.key == "G1":
                continue  # G1 ist eine Setzungsentscheidung, keine recherchierbare Frage.
            counter += 1
            leaves.append(
                ResearchLeaf(
                    rid=f"R-{counter:02d}",
                    sid=subsystem.sid,
                    gate=gate.key,
                    question=research_question(subsystem, features, gate),
                    status="OFFEN",
                    kill_criteria=(
                        "Verworfen, wenn die Quelle keine normative Fundstelle mit Version/Abschnitt nennt "
                        "oder nur Sekundärliteratur ohne Zitat vorliegt."
                    ),
                    uncertainty="unbelegt — Stufe 3 (Deep Research) ausstehend",
                )
            )
    return leaves


def expand_document(doc: StageDocument, filler: GateFiller | None = None) -> StageDocument:
    """Stufe 2: Gate-Container fuellen, Schnittstellen/Randfaelle und Blaetter bauen.

    Die Struktur (Sektionen, Subsystem-IDs, Ausgabevertrag) bleibt unberuehrt --
    das ist die Sperre der Achse "Prompting-Technik" in Stufe 2 und 3.
    """
    active = filler or StructuralFiller()
    expanded: list[Subsystem] = []
    for subsystem in doc.subsystems:
        features = doc.features_of(subsystem.sid)
        gates = {gate.key: active.answer(subsystem, gate, features) for gate in HARD_GATES}
        profile = profile_for(" ".join([subsystem.title, *(feature.title for feature in features)]))
        expanded.append(
            Subsystem(
                sid=subsystem.sid,
                title=subsystem.title,
                features=list(subsystem.features),
                gates=gates,
                interfaces=interfaces_for(subsystem, features),
                edge_cases=edge_cases_for(subsystem, features),
                raw_material=list(profile.raw_material),
            )
        )
    doc.subsystems = expanded
    doc.leaves = build_leaves(doc)
    return doc
