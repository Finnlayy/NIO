"""Fakten-Haertung der Research-Blaetter (Stufe 3) ohne Fakten-Erfindung.

Der Optimierer selbst recherchiert nicht. Er stellt sicher, dass jede Aussage
entweder eine **pruefbare Fundstelle** bekommt oder sichtbar unbelegt bleibt:

* :class:`NullProvider` -- kein Research-Adapter: alles bleibt ``UNVERIFIZIERT``.
  Das ist der ehrliche Standardzustand, kein Fehler.
* :class:`FixtureProvider` -- liefert Quellen aus einer JSON-Datei
  (``{ "R-01": [{"tier": 3, "locator": "repo:protocol/PROTOCOL.md", "quote": "..."}] }``).
* :class:`LocalSourceChecker` -- prueft ``repo:``-Locators gegen das Repo:
  Datei muss existieren, das Zitat muss woertlich enthalten sein. Erst dann gilt
  die Quelle als ``checked`` und damit als verifiziert (Tier >= 2 + Zitat + Haken).

Damit ist "verifiziert" eine Eigenschaft, die jeder Dritte nachrechnen kann --
per ``git grep`` und Datei-Hash, nicht per Vertrauen in das Modell.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from .model import ResearchLeaf, Source, StageDocument

__all__ = [
    "FixtureProvider",
    "LocalSourceChecker",
    "NullProvider",
    "ResearchProvider",
    "harden_document",
    "load_fixture",
]

_REPO_PREFIX = "repo:"


class ResearchProvider(Protocol):
    """Adapter fuer echte Recherche (Web, Doku-Index, Wissensbasis)."""

    def resolve(self, leaf: ResearchLeaf) -> tuple[Source, ...]:
        """Liefert die Quellen zu genau einem Blatt (ggf. leer)."""


class NullProvider:
    """Kein Adapter: keine Quellen, keine Behauptungen."""

    def resolve(self, leaf: ResearchLeaf) -> tuple[Source, ...]:
        return ()


class FixtureProvider:
    """Quellen aus einer JSON-Fixture -- reproduzierbar und ohne Netz."""

    def __init__(self, sources: Mapping[str, list[Source] | list[dict]]) -> None:
        self._sources: dict[str, list[Source]] = {}
        for key, value in sources.items():
            self._sources[str(key)] = [item if isinstance(item, Source) else Source.from_dict(item) for item in value]

    def resolve(self, leaf: ResearchLeaf) -> tuple[Source, ...]:
        return tuple(self._sources.get(leaf.rid, ()))


def load_fixture(path: Path | str) -> dict[str, list[Source]]:
    """Liest die Fixture-Datei; unbekannte Felder werden ignoriert."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Research-Fixture muss ein JSON-Objekt {Blatt-ID: [Quelle, ...]} sein.")
    result: dict[str, list[Source]] = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue  # Kommentarfeld der Fixture (z. B. "_hinweis")
        items = value if isinstance(value, list) else [value]
        result[str(key)] = [Source.from_dict(item) for item in items if isinstance(item, dict)]
    return result


class LocalSourceChecker:
    """Prueft ``repo:``-Quellen gegen das Dateisystem (Zitat + Pfad)."""

    def __init__(self, repo_root: Path | str) -> None:
        self.repo_root = Path(repo_root)

    def check(self, source: Source) -> Source:
        locator = source.locator.strip()
        if not locator.startswith(_REPO_PREFIX):
            return source  # Netzquellen kann dieser Checker nicht belegen.
        relative = locator[len(_REPO_PREFIX) :].split("#", 1)[0]
        target = (self.repo_root / relative).resolve()
        try:
            target.relative_to(self.repo_root.resolve())
        except ValueError:
            return Source(source.tier, locator, source.quote, source.retrieved_at, checked=False)
        if not target.is_file():
            return Source(source.tier, locator, source.quote, source.retrieved_at, checked=False)
        content = target.read_text(encoding="utf-8", errors="replace")
        normalised = re.sub(r"\s+", " ", content)
        quote = re.sub(r"\s+", " ", source.quote).strip()
        checked = bool(quote) and quote in normalised
        return Source(source.tier, locator, source.quote, source.retrieved_at, checked=checked)


def _risk_note(leaf: ResearchLeaf, checked_sources: tuple[Source, ...]) -> str:
    if not checked_sources:
        return "unbelegt — Provider lieferte keine Quelle mit Locator; Gate bleibt OFFEN."
    if not any(source.verified for source in checked_sources):
        return "Quelle vorhanden, aber nicht verifiziert (Tier < 2, Zitat leer oder lokal nicht prüfbar)."
    return "verifiziert: Primärquelle mit Locator, wörtlichem Zitat und lokalem Prüfvermerk."


def harden_document(
    doc: StageDocument,
    provider: ResearchProvider | None = None,
    checker: LocalSourceChecker | None = None,
) -> StageDocument:
    """Stufe 3: jedes Blatt bekommt Quellen oder einen expliziten Unbelegt-Vermerk.

    Die Struktur des Dokuments bleibt unangetastet -- geaendert werden nur die
    Blatt-Status, Quellen und Unsicherheits-Vermerke (Achse "Inhalt & Fakten").
    """
    active = provider or NullProvider()
    for leaf in doc.leaves:
        sources = tuple(active.resolve(leaf))
        if checker is not None:
            sources = tuple(checker.check(source) for source in sources)
        leaf.sources = list(sources)
        leaf.status = "VERIFIZIERT" if any(source.verified for source in sources) else "UNVERIFIZIERT"
        leaf.uncertainty = _risk_note(leaf, sources)
    return doc
