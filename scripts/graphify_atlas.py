#!/usr/bin/env python3
"""Baut aus graphify-out/graph.json eine kuratierte Architektur-Karte von NIO.

Warum dieses Skript existiert: ``graph.html`` zeigt bei ~9000 Knoten nur noch
Community-Blasen. Diese Karte fasst den Graphen stattdessen in Subsysteme
(Pods) um den Orchestrator zusammen, zeigt den belegten Laufzeitpfad
Intent -> Limb und den Limb-Faecher aus ``limbs/registry.json``.

Jede Zahl stammt aus graph.json, jede Pfad-Station traegt ``datei:zeile``,
die beim Erzeugen per Regex im Code gesucht wird. Findet sich ein Anker nicht,
steht "Anker nicht gefunden" statt einer erfundenen Zeile.

Nur Standardbibliothek. Ausgabe: graphify-out/nio-atlas.html
"""

from __future__ import annotations

import argparse
import collections
import html
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HUB = "orchestrator"
# (Schluessel, Titel, Untertitel, Pfad-Praefixe, Akzentfarbe). Erstes passendes Praefix gewinnt,
# deshalb stehen die spezifischeren Praefixe (orchestrator/kanban) vor dem Hub.
PODS = [
    ("kanban", "Kanban", "Aufgaben, Worker, Board", ["orchestrator/kanban/", "frontend/src/kanban/"], "#f59e0b"),
    ("telegram", "Telegram", "Intel-Kanal und Store", ["orchestrator/telegram/", "frontend/src/telegram/"], "#38bdf8"),
    (HUB, "Orchestrator", "Intent, Policy, Dispatch, Events", ["orchestrator/"], "#8b5cf6"),
    ("core", "Core-Protokoll", "Intent, Result, ErrorCode, Kernel", ["core/"], "#a78bfa"),
    ("limbs", "Limbs", "LimbBase, LimbContext, Arme", ["limbs/"], "#10b981"),
    ("apollo", "Apollo · Ciel", "JIT-Schicht, NCM, Cold Storage", ["apollo/"], "#c084fc"),
    ("frontend", "Frontend", "Apollo-UI, Ops, Telemetrie", ["frontend/"], "#22d3ee"),
    ("architect", "Architect", "Lernschleife, EventBus, Policy", ["Architect/"], "#f472b6"),
    ("learning", "Lernen & Evals", "LearningStore, Traces", ["src/", "evals/"], "#34d399"),
    ("protocol", "Schemas & Rust", "JSON-Schemas, nio-contracts", ["protocol/", "rust/"], "#fbbf24"),
    ("infra", "Infra & Skripte", "Sandbox-Proxy, CI, Benchmarks", ["docker/", ".github/", "ci/", "scripts/"], "#94a3b8"),
    ("tests", "Tests", "Vertrags- und Integrationstests", ["tests/"], "#ef4444"),
    ("docs", "Docs & Prompts", "Spezifikationen, Limb-Prompts", ["docs/", "prompts/", "agents/"], "#e2e8f0"),
]

# Laufzeitpfad: (Titel, Erklaerung, Datei, Regex fuer die Ankerzeile)
PATH_STEPS = [
    ("Intent", "Auftrag im NEU-Protokoll", "core/protocol.py", r"^class Intent\b"),
    ("SubagentManager.ensure", "Subagent mit Limb anlegen", "orchestrator/subagent.py", r"def ensure\("),
    ("Orchestrator.run_job", "Job mit Constraints starten", "orchestrator/runner.py", r"def run_job\("),
    ("Orchestrator.dispatch", "Policy prüfen, Limb wählen", "orchestrator/runner.py", r"def dispatch\("),
    ("LimbRegistry", "liest limbs/registry.json", "orchestrator/runner.py", r"^class LimbRegistry\b"),
    ("Kommandozeile", "{python} {entrypoint} --intent …", "orchestrator/runner.py", r'"--intent", "\{intent_file\}"'),
    ("_spawn", "Subprozess in eigener Gruppe", "orchestrator/runner.py", r"def _spawn\("),
    ("LimbBase.execute", "Limb übernimmt den Intent", "limbs/base.py", r"def execute\("),
    ("LimbContext", "Kontext für den Arm", "limbs/base.py", r"= LimbContext\("),
]


def anchor(rel_path: str, pattern: str) -> str | None:
    path = REPO_ROOT / rel_path
    if not path.exists():
        return None
    regex = re.compile(pattern)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if regex.search(line):
            return f"{rel_path}:{number}"
    return None


def pod_of(source_file: str) -> str | None:
    for key, _title, _sub, prefixes, _color in PODS:
        if any(source_file.startswith(prefix) for prefix in prefixes):
            return key
    return None


def collect(graph: dict) -> dict:
    edge_key = "links" if "links" in graph else "edges"
    nodes = {node["id"]: node for node in graph["nodes"]}
    degree: collections.Counter[str] = collections.Counter()
    for edge in graph[edge_key]:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1

    node_pod = {nid: pod_of(node.get("source_file") or "") for nid, node in nodes.items()}
    files: dict[str, set[str]] = collections.defaultdict(set)
    members: dict[str, list[str]] = collections.defaultdict(list)
    for nid, pod in node_pod.items():
        if pod:
            members[pod].append(nid)
            files[pod].add(nodes[nid]["source_file"])

    internal: collections.Counter[str] = collections.Counter()
    pair: collections.Counter[tuple[str, str]] = collections.Counter()
    for edge in graph[edge_key]:
        a, b = node_pod.get(edge["source"]), node_pod.get(edge["target"])
        if not a or not b:
            continue
        if a == b:
            internal[a] += 1
        else:
            pair[tuple(sorted((a, b)))] += 1

    def top_symbols(pod: str, limit: int = 6) -> list[dict]:
        picked, seen = [], set()
        for nid in sorted(members[pod], key=lambda i: -degree[i]):
            node = nodes[nid]
            label = node.get("label", "")
            # Schluessel aus JSON/YAML (properties, steps, ...) und Dateinamen sind keine Architektur-Symbole.
            if (re.search(r"\.(json|ya?ml)$", node["source_file"]) or "/" in label or label in seen
                    or re.search(r"\.(py|ts|tsx|js|mjs|json|ya?ml|rs|md)$", label)):
                continue
            seen.add(label)
            picked.append({"label": label, "degree": degree[nid],
                           "where": f"{node['source_file']}:{str(node.get('source_location') or '').lstrip('L')}".rstrip(":")})
            if len(picked) == limit:
                break
        return picked

    pods = []
    for key, title, sub, prefixes, color in PODS:
        neighbours = sorted(((b if a == key else a, n) for (a, b), n in pair.items() if key in (a, b)), key=lambda x: -x[1])
        pods.append({
            "key": key, "title": title, "subtitle": sub, "paths": prefixes, "color": color,
            "files": len(files[key]), "nodes": len(members[key]), "internal": internal[key],
            "hub_edges": pair.get(tuple(sorted((key, HUB))), 0) if key != HUB else 0,
            "neighbours": neighbours[:3], "symbols": top_symbols(key),
        })

    confidences = collections.Counter(edge.get("confidence", "?") for edge in graph[edge_key])
    total_edges = len(graph[edge_key])
    return {
        "pods": pods,
        "stats": {
            "nodes": len(nodes), "edges": total_edges,
            "files": len({n.get("source_file") for n in nodes.values() if n.get("source_file")}),
            "communities": len({n.get("community") for n in nodes.values() if n.get("community") is not None}),
            "extracted": round(100 * confidences.get("EXTRACTED", 0) / max(total_edges, 1)),
            "limb_edges": sum(1 for e in graph[edge_key] if e.get("_origin") == "limb_registry"),
        },
    }


def limbs() -> list[dict]:
    registry = json.loads((REPO_ROOT / "limbs/registry.json").read_text(encoding="utf-8"))
    return [{"name": name, "status": spec.get("status", "?"), "ops": len(spec.get("operations", [])),
             "entrypoint": spec.get("entrypoint", ""), "description": spec.get("description", "")}
            for name, spec in registry.get("limbs", {}).items()]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def pod_card(pod: dict, titles: dict[str, str], cls: str = "") -> str:
    symbols = "".join(
        f'<li><span class="sym">{esc(s["label"])}</span><span class="deg" title="{esc(s["where"])}">{s["degree"]}</span></li>'
        for s in pod["symbols"])
    neighbours = " · ".join(f"{esc(titles[k])} {n}" for k, n in pod["neighbours"]) or "keine"
    paths = " ".join(f"<code>{esc(p)}</code>" for p in pod["paths"])
    return f'''<section class="pod {cls}" data-pod="{esc(pod["key"])}" data-hub="{pod["hub_edges"]}" style="--c:{pod["color"]}">
  <header><span class="tag">POD</span><h2>{esc(pod["title"])}</h2></header>
  <p class="sub">{esc(pod["subtitle"])}</p>
  <div class="paths">{paths}</div>
  <div class="nums"><span><b>{pod["files"]}</b> Dateien</span><span><b>{pod["nodes"]}</b> Knoten</span><span><b>{pod["internal"]}</b> intern</span></div>
  <ul class="syms">{symbols}</ul>
  <footer><span>Kopplung</span> {neighbours}</footer>
</section>'''


def render(data: dict, limb_list: list[dict], steps: list[dict]) -> str:
    titles = {p["key"]: p["title"] for p in data["pods"]}
    hub = next(p for p in data["pods"] if p["key"] == HUB)
    ring = [p for p in data["pods"] if p["key"] != HUB]
    s = data["stats"]
    step_html = "".join(
        f'<li><span class="num">{i}</span><b>{esc(st["title"]).replace(".", ".<wbr>")}</b><small>{esc(st["text"])}</small>'
        f'<code>{esc(st["where"] or "Anker nicht gefunden")}</code></li>'
        for i, st in enumerate(steps, 1))
    limb_html = "".join(
        f'<article class="limb {"on" if l["status"] == "active" else "off"}"><header><b>{esc(l["name"])}</b>'
        f'<span>{esc(l["status"])} · {l["ops"]} Ops</span></header><p>{esc(l["description"][:150])}{"…" if len(l["description"]) > 150 else ""}</p>'
        f'<code>{esc(l["entrypoint"])}</code></article>'
        for l in limb_list)
    hub_syms = "".join(f'<li><span class="sym">{esc(x["label"])}</span><span class="deg" title="{esc(x["where"])}">{x["degree"]}</span></li>' for x in hub["symbols"])
    pods_html = "".join(pod_card(p, titles) for p in ring)
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIO Atlas</title>
<style>
:root{{color-scheme:dark;--bg:#08090c;--panel:rgba(18,20,28,.78);--line:rgba(255,255,255,.08);--ink:#e8eaf2;--muted:#8a90a6;--violet:#8b5cf6;--emerald:#10b981;--amber:#f59e0b;--crimson:#ef4444;--mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace}}
*{{box-sizing:border-box}}
body{{margin:0;background:radial-gradient(1200px 700px at 50% 30%,#171433 0%,#0b0b14 45%,var(--bg) 100%);color:var(--ink);font:14px/1.45 Inter,system-ui,sans-serif;min-height:100vh}}
.wrap{{max-width:1500px;margin:0 auto;padding:28px 24px 48px}}
.top h1{{margin:0;font-size:clamp(26px,3.4vw,44px);letter-spacing:.02em;font-weight:800;background:linear-gradient(90deg,#c4b5fd,#67e8f9 55%,#6ee7b7);-webkit-background-clip:text;background-clip:text;color:transparent}}
.top p{{margin:6px 0 0;color:var(--muted)}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:22px 0 26px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}}
.kpi small{{display:block;color:var(--muted);font-size:10px;letter-spacing:.12em;text-transform:uppercase}}
.kpi b{{font:600 22px var(--mono);font-variant-numeric:tabular-nums}}
.stage{{position:relative;display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:auto;gap:18px}}
#wires{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:visible}}
#wires path{{fill:none;stroke:var(--c);opacity:.35;transition:opacity .18s}}
#wires path.hot{{opacity:.95}}
.pod,.hub{{position:relative;z-index:1;background:var(--panel);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:12px;padding:14px 16px;transition:border-color .18s cubic-bezier(.16,1,.3,1),transform .18s cubic-bezier(.16,1,.3,1)}}
.pod:hover{{border-color:color-mix(in srgb,var(--c) 60%,transparent);transform:translateY(-2px)}}
.pod header{{display:flex;align-items:center;gap:8px}}
.tag{{font:600 9px var(--mono);letter-spacing:.14em;color:var(--c);border:1px solid color-mix(in srgb,var(--c) 50%,transparent);border-radius:4px;padding:1px 5px}}
.pod h2{{margin:0;font-size:15px;letter-spacing:.06em;text-transform:uppercase}}
.sub{{margin:4px 0 6px;color:var(--muted);font-size:12px}}
.paths code,.limb code,.flow code{{font:11px var(--mono);color:#b9c0d6;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:4px;padding:1px 5px;margin-right:4px;white-space:nowrap}}
.nums{{display:flex;gap:12px;margin:10px 0 8px;color:var(--muted);font-size:12px}}
.nums b{{color:var(--ink);font:600 13px var(--mono)}}
.syms{{list-style:none;margin:0;padding:0;display:grid;gap:3px}}
.syms li{{display:flex;justify-content:space-between;gap:10px;padding:3px 8px;border-radius:5px;background:linear-gradient(90deg,color-mix(in srgb,var(--c) 12%,transparent),transparent)}}
.sym{{font:12px var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.deg{{font:11px var(--mono);color:var(--c);font-variant-numeric:tabular-nums}}
.pod footer{{margin-top:10px;border-top:1px dashed var(--line);padding-top:8px;font-size:11px;color:var(--muted)}}
.pod footer span{{font:600 9px var(--mono);letter-spacing:.14em;color:var(--c);text-transform:uppercase;margin-right:6px}}
.hub{{grid-column:2;grid-row:2 / span 2;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border-color:rgba(139,92,246,.45);box-shadow:0 0 60px rgba(139,92,246,.18) inset,0 0 40px rgba(139,92,246,.12);--c:var(--violet)}}
.core{{width:150px;height:150px;border-radius:50%;display:grid;place-items:center;margin:6px auto 12px;background:radial-gradient(circle,#2e1f6b 0%,#14102b 60%,transparent 70%);border:1px solid rgba(139,92,246,.6);box-shadow:0 0 50px rgba(139,92,246,.45);animation:pulse 4s ease-in-out infinite}}
.core b{{font-size:20px;letter-spacing:.08em}}.core small{{display:block;font:10px var(--mono);color:#c4b5fd}}
@keyframes pulse{{50%{{box-shadow:0 0 80px rgba(139,92,246,.7)}}}}
.hub .syms{{width:100%;max-width:330px;text-align:left}}
h3.sec{{margin:40px 0 12px;font:600 12px var(--mono);letter-spacing:.18em;color:#c4b5fd;text-transform:uppercase}}
.flow{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(9,1fr);gap:8px;counter-reset:s}}
.flow li{{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:4px;min-width:0}}
.flow li:not(:last-child)::after{{content:"→";position:absolute;right:-9px;top:14px;color:var(--emerald);font-weight:700;z-index:2}}
.flow .num{{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font:600 11px var(--mono);background:rgba(16,185,129,.15);color:var(--emerald);border:1px solid rgba(16,185,129,.5)}}
.flow b{{font:600 12px var(--mono);overflow-wrap:break-word}}.flow small{{color:var(--muted);font-size:11px}}
.flow code{{white-space:normal;overflow-wrap:anywhere;margin-top:auto}}
.limbs{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.limb{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--emerald);border-radius:10px;padding:12px}}
.limb.off{{border-left-color:#64748b;opacity:.7}}
.limb header{{display:flex;justify-content:space-between;align-items:baseline}}
.limb header b{{font:600 14px var(--mono);text-transform:uppercase}}
.limb header span{{font:11px var(--mono);color:var(--muted)}}
.limb p{{margin:6px 0 8px;font-size:12px;color:#b4b9cc}}
.note{{margin-top:28px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}}
@media (max-width:1100px){{.flow{{grid-template-columns:repeat(3,1fr)}}.limbs{{grid-template-columns:repeat(2,1fr)}}.kpis{{grid-template-columns:repeat(3,1fr)}}}}
@media (max-width:820px){{.wrap{{padding:20px 16px}}.stage{{grid-template-columns:1fr}}.hub{{grid-column:auto;grid-row:auto;order:-1}}#wires{{display:none}}.flow,.limbs{{grid-template-columns:1fr}}.flow li::after{{display:none}}.kpis{{grid-template-columns:repeat(2,1fr)}}}}
@media (prefers-reduced-motion:reduce){{.core{{animation:none}}}}
</style></head><body><div class="wrap">
<div class="top"><h1>NIO · Architektur-Atlas</h1><p>Aus graphify-out/graph.json verdichtet: Subsysteme um den Orchestrator, belegter Laufzeitpfad, Limb-Fächer. Zahl am Symbol = Kanten im Graphen (Datei:Zeile beim Überfahren).</p></div>
<div class="kpis">
<div class="kpi"><small>Knoten</small><b>{s["nodes"]:,}</b></div><div class="kpi"><small>Kanten</small><b>{s["edges"]:,}</b></div>
<div class="kpi"><small>Dateien</small><b>{s["files"]:,}</b></div><div class="kpi"><small>Communities</small><b>{s["communities"]}</b></div>
<div class="kpi"><small>Extrahiert</small><b>{s["extracted"]}%</b></div><div class="kpi"><small>Limb-Kanten</small><b>{s["limb_edges"]}</b></div>
</div>
<div class="stage" id="stage"><svg id="wires"></svg>
{pods_html}
<section class="hub" data-pod="{HUB}"><span class="tag">HUB</span><div class="core"><div><b>NIO</b><small>ORCHESTRATOR</small></div></div>
<p class="sub">{esc(hub["subtitle"])} · {hub["files"]} Dateien · {hub["nodes"]} Knoten</p><ul class="syms">{hub_syms}</ul>
<p class="sub" style="margin-top:10px">Linienstärke = Kanten zwischen Pod und Orchestrator</p></section>
</div>
<h3 class="sec">Laufzeitpfad · Intent → Limb</h3><ol class="flow">{step_html}</ol>
<h3 class="sec">Limb-Fächer · limbs/registry.json</h3><div class="limbs">{limb_html}</div>
<p class="note">Erzeugt von scripts/graphify_atlas.py. Kopplung zählt Kanten zwischen Pods im Graphen (AST + INFERRED), nicht Laufzeitaufrufe. Dateien ohne Pod (Repo-Root, .nio, .jules, .cursor) zählen in den KPIs mit, aber in keinem Pod.</p>
</div>
<script>
(function(){{
  const stage=document.getElementById('stage'),svg=document.getElementById('wires'),hub=stage.querySelector('.hub');
  const pods=[...stage.querySelectorAll('.pod')];
  const max=Math.max(1,...pods.map(p=>+p.dataset.hub));
  function draw(){{
    if(getComputedStyle(svg).display==='none')return;
    const r=stage.getBoundingClientRect(),h=hub.getBoundingClientRect();
    const hx=h.left+h.width/2-r.left,hy=h.top+h.height/2-r.top;
    svg.innerHTML=pods.map(p=>{{
      const n=+p.dataset.hub;if(!n)return'';
      const b=p.getBoundingClientRect(),x=b.left+b.width/2-r.left,y=b.top+b.height/2-r.top;
      const w=(1+5*Math.log(1+n)/Math.log(1+max)).toFixed(2),mx=(x+hx)/2;
      return `<path data-for="${{p.dataset.pod}}" style="--c:${{p.style.getPropertyValue('--c')}}" stroke-width="${{w}}" d="M${{x}},${{y}} C${{mx}},${{y}} ${{mx}},${{hy}} ${{hx}},${{hy}}"><title>${{n}} Kanten</title></path>`;
    }}).join('');
  }}
  pods.forEach(p=>{{
    p.addEventListener('mouseenter',()=>svg.querySelector(`[data-for="${{p.dataset.pod}}"]`)?.classList.add('hot'));
    p.addEventListener('mouseleave',()=>svg.querySelector(`[data-for="${{p.dataset.pod}}"]`)?.classList.remove('hot'));
  }});
  addEventListener('resize',draw);new ResizeObserver(draw).observe(stage);draw();
}})();
</script></body></html>'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--graph", default=str(REPO_ROOT / "graphify-out" / "graph.json"))
    parser.add_argument("--out", default=str(REPO_ROOT / "graphify-out" / "nio-atlas.html"))
    args = parser.parse_args(argv)

    data = collect(json.loads(Path(args.graph).read_text(encoding="utf-8")))
    steps = [{"title": t, "text": x, "where": anchor(f, p)} for t, x, f, p in PATH_STEPS]
    Path(args.out).write_text(render(data, limbs(), steps), encoding="utf-8")
    missing = [st["title"] for st in steps if not st["where"]]
    print(f"geschrieben: {args.out}")
    if missing:
        print("Anker nicht gefunden: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
