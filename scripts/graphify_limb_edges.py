#!/usr/bin/env python3
"""Ergaenzt graphify-out/graph.json um die Laufzeit-Kanten Orchestrator -> Limb.

Warum dieses Skript existiert: Der Orchestrator startet Limbs nicht per Import,
sondern liest ``entrypoint`` aus ``limbs/registry.json`` und ruft das Skript als
Unterprozess auf (``orchestrator/runner.py``, ``--intent``). Die AST-Extraktion
von graphify sieht dafuer keine Kante, daher fehlt im Graphen jeder Pfad vom
Runner zu den Limbs.

Die Kanten stehen woertlich im Register und werden deshalb als EXTRACTED mit
Quelle ``limbs/registry.json`` und der Zeile des ``entrypoint`` eingetragen.
Das Skript ist idempotent. Nach ``/graphify --update`` erneut ausfuehren, weil
der Neubau ``graph.json`` ueberschreibt.

Nur Standardbibliothek.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = "limbs/registry.json"
DISPATCHER = "orchestrator_runner_orchestrator"
RELATION = "invokes"
ORIGIN = "limb_registry"


def node_id_for(rel_path: str) -> str:
    """Datei-Knoten-ID nach graphify-Regel: Pfad ohne Endung, Segmente mit ``_``."""
    stem = rel_path.rsplit(".", 1)[0]
    return "_".join(re.sub(r"\W", "_", part.lower()) for part in stem.split("/"))


def entrypoint_lines(registry_path: Path) -> dict[str, int]:
    """Zeilennummer jedes ``"entrypoint": "<pfad>"`` im Register."""
    lines: dict[str, int] = {}
    for number, line in enumerate(registry_path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.search(r'"entrypoint"\s*:\s*"([^"]+)"', line)
        if match:
            lines.setdefault(match.group(1), number)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--graph", default=str(REPO_ROOT / "graphify-out" / "graph.json"))
    args = parser.parse_args(argv)

    graph_path = Path(args.graph)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edge_key = "links" if "links" in graph else "edges"
    node_ids = {node["id"] for node in graph["nodes"]}
    if DISPATCHER not in node_ids:
        print(f"Dispatcher-Knoten fehlt: {DISPATCHER}", file=sys.stderr)
        return 1

    registry_path = REPO_ROOT / REGISTRY
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    lines = entrypoint_lines(registry_path)

    # Alte Kanten dieses Skripts entfernen, damit ein erneuter Lauf nichts verdoppelt.
    edges = [edge for edge in graph[edge_key] if edge.get("_origin") != ORIGIN]
    added, missing = [], []
    for name, body in registry.get("limbs", {}).items():
        entrypoint = str(body.get("entrypoint", ""))
        target = node_id_for(entrypoint)
        if target not in node_ids:
            missing.append(f"{name}: {entrypoint}")
            continue
        edges.append({
            "source": DISPATCHER,
            "target": target,
            "relation": RELATION,
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": REGISTRY,
            "source_location": f"L{lines.get(entrypoint, 0)}",
            "weight": 1.0,
            "_origin": ORIGIN,
        })
        added.append(f"{name} -> {target}")

    graph[edge_key] = edges
    graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    for line in added:
        print(f"+ {line}")
    for line in missing:
        print(f"! kein Knoten fuer {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
