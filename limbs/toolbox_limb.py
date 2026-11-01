"""Toolbox-Limb (Phase 6) -- die Werkzeugkiste, die Agenten mitziehen.

Agenten tragen hier nur noch diesen einen Knoten im Kontext, nicht jedes Tool:
``toolbox.search`` findet Werkzeuge mit einer Zeile pro Treffer,
``toolbox.describe`` laedt die volle Beschreibung genau eines Werkzeugs erst
dann, wenn es gebraucht wird.

Der Katalog entsteht bei jedem Aufruf aus zwei Quellen und kann deshalb nicht
gegen sie driften:

* ``protocol/operations.json`` -- alle NEU-Operationen
* ``docs/knowledge/<paket>/tools/*.md`` -- Leafs externer Tools mit Frontmatter

Dieser Limb liest nur. Er ruft keine Tools auf und braucht weder Netz noch
Zugangsdaten; ausfuehren bleibt Sache des Limbs oder MCP-Servers, der das
Werkzeug besitzt.

Aufruf: ``python3 limbs/toolbox_limb.py --intent runtime/inbox/toolbox/<id>.json``
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

# Zwei Aufrufwege, ein Modul -- Begruendung steht in ``echo_limb.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(Path(__file__).resolve().parent), str(_REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

if __package__ in (None, ""):  # direkter Skriptaufruf durch den Orchestrator
    from base import LimbBase, LimbContext, LimbError  # type: ignore[import-not-found]
else:  # Import als Paket (Tests, Tooling)
    from limbs.base import LimbBase, LimbContext, LimbError

from core.protocol import ErrorCode  # noqa: E402

DEFAULT_LIMIT = 10
MAX_LIMIT = 50
READ_RISKS = ("none", "read")


def _parse_leaf(path: Path) -> dict[str, str]:
    """Frontmatter eines Leafs lesen; der Zweck steht im ersten Fliesstext-Absatz."""
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---\n", 2)
    meta = dict(line.split(": ", 1) for line in frontmatter.splitlines() if ": " in line)
    paragraphs = [block.strip() for block in body.split("\n\n") if block.strip()]
    return {**meta, "summary": paragraphs[2], "text": text.strip()}


def _load_catalog(root: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}

    operations = json.loads((root / "protocol" / "operations.json").read_text(encoding="utf-8"))
    for name, spec in operations["operations"].items():
        catalog[name] = {
            "tool": name,
            "source": "neu",
            "group": name.split(".", 1)[0],
            "access": "read-only" if spec["risk"] in READ_RISKS else "write",
            "summary": spec["description"],
            "detail": spec,
        }

    for path in sorted((root / "docs" / "knowledge").glob("*/tools/*.md")):
        leaf = _parse_leaf(path)
        catalog[leaf["tool"]] = {
            "tool": leaf["tool"],
            "source": path.parent.parent.name,
            "group": leaf["group"],
            "access": leaf["access"],
            "summary": leaf["summary"],
            "detail": leaf["text"],
        }
    return catalog


def _brief(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {key: entry[key] for key in ("tool", "source", "group", "access", "summary")}


class ToolboxLimb(LimbBase):
    name = "toolbox"
    version = "1.0.0"
    description = "Werkzeugkiste der Agenten: toolbox.ping / toolbox.search / toolbox.describe"

    def __init__(self, *args: Any, root: Path = _REPO_ROOT, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.root = root

    def handlers(self) -> dict[str, Callable[[Mapping[str, Any], LimbContext], Mapping[str, Any]]]:
        return {
            "toolbox.ping": self._ping,
            "toolbox.search": self._search,
            "toolbox.describe": self._describe,
        }

    # ---------------------------------------------------------------- Handler
    def _ping(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        catalog = _load_catalog(self.root)
        sources: dict[str, int] = {}
        for entry in catalog.values():
            sources[entry["source"]] = sources.get(entry["source"], 0) + 1
        return {"limb": self.name, "version": self.version, "tools": len(catalog), "sources": sources}

    def _search(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        catalog = _load_catalog(self.root)
        query = str(params.get("query", "")).lower().split()
        source = params.get("source")
        access = params.get("access")
        limit = min(MAX_LIMIT, max(1, int(params.get("limit", DEFAULT_LIMIT))))

        matches: list[tuple[int, dict[str, Any]]] = []
        for entry in catalog.values():
            if (source and entry["source"] != source) or (access and entry["access"] != access):
                continue
            name = entry["tool"].lower()
            haystack = f"{name} {entry['group']} {entry['summary']}".lower()
            if all(word in haystack for word in query):
                matches.append((sum(word in name for word in query), entry))

        matches.sort(key=lambda match: (-match[0], match[1]["tool"]))
        return {
            "total": len(matches),
            "truncated": len(matches) > limit,
            "tools": [_brief(entry) for _, entry in matches[:limit]],
        }

    def _describe(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        tool = str(params.get("tool", "")).strip()
        catalog = _load_catalog(self.root)
        if tool not in catalog:
            raise LimbError(
                ErrorCode.TARGET_NOT_FOUND,
                f"Werkzeug '{tool}' steht nicht im Katalog",
                hint="Mit toolbox.search den genauen Namen ermitteln.",
            )
        entry = catalog[tool]
        return {**_brief(entry), "detail": entry["detail"]}


if __name__ == "__main__":
    sys.exit(ToolboxLimb().main())
