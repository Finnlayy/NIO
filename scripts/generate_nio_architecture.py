#!/usr/bin/env python3
"""Generate a self-contained NIO architecture map without LLM/API calls."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "graphify-out"
PDF = "/home/finn-powers/Downloads/01_final_manas_ciel_edith_lilith_master_prompt.md.pdf"
LABEL = {"implemented": "IMPLEMENTIERT", "partial": "TEILWEISE", "specified": "SPEZIFIZIERT", "planned": "GEPLANT"}


def n(i, label, sub, status, x, y, evidence, detail, kind="component"):
    return dict(id=i, label=label, subtitle=sub, status=status, x=x, y=y,
                evidence=evidence, detail=detail, kind=kind)


def e(source, target, label, status, evidence):
    return dict(source=source, target=target, label=label, status=status, evidence=evidence)


def model():
    registry = json.loads((ROOT / "limbs/registry.json").read_text(encoding="utf-8"))
    nodes = [
        n("human", "Mensch / Stimme", "Bedienbeginn", "implemented", 130, 470, ["docs/SPEECH.md"], "Sprache wird aufgenommen, aber niemals automatisch ausgeführt."),
        n("speech", "Spracherkennung", "Whisper / Browser Speech", "implemented", 380, 470, ["docs/SPEECH.md", "frontend/src/apollo/dictation.ts", "frontend/src/apollo/browserSpeech.ts"], "MediaRecorder → /api/apollo/transcribe → lokales speaches. Browser Speech ist eine offengelegte Alternative."),
        n("apollo", "APOLLO", "Orb · Terminal · Control Deck", "implemented", 650, 470, ["frontend/src/apollo/", "docs/SPEECH.md"], "Operator-Zentrum. Das Transkript landet als Entwurf; Send und Freigaben bleiben explizit."),
        n("manas", "MANAS: CIEL", "Ring-0 · kanonische Governance", "specified", 650, 65, [PDF], "Oberste Architektur des v8.1-Masterprompts; nicht als produktive Ring-0-Runtime nachgewiesen."),
        n("primordials", "Vier Primordials", "Rouge · Noir · Blanche · Jaune", "specified", 290, 205, [PDF], "Spezifizierte Rollen für Injektion/Ausführung, Gatekeeping, Sharding und Shadow-Ausführung."),
        n("kernels", "Dual-Kernel", "E.D.I.T.H. · L.I.L.I.T.H.", "specified", 650, 205, [PDF], "Im Masterprompt spezifizierte Dual-Kernel-Ebene; kein gleichnamiger produktiver Runtime-Pfad nachgewiesen."),
        n("backbone", "Backbone", "RGCCO · Deep-Sea · Obsidian", "specified", 1010, 205, [PDF], "Kanonische Backbone-Bausteine. Ähnliche Einzelbausteine im Repo beweisen nicht diese Gesamtverdrahtung."),
        n("ciel", "Ciel JIT-Schicht", "NCM · Cold Storage · Sandbox", "partial", 930, 470, ["apollo/ciel/__init__.py", "docs/CIEL.md", "docs/hermes/RUNTIME_PLAN.md"], "Paket und interne Module existieren. Die produktive Hauptverdrahtung ist laut Runtime-Plan nicht vorhanden."),
        n("orchestrator", "NIO Orchestrator", "Intent · Policy · Event Bus", "implemented", 1210, 470, ["orchestrator/runner.py", "orchestrator/events.py"], "Bewiesenes Ausführungszentrum: validiert Intents und startet aktive Limbs als Subprozesse."),
        n("registry", "Limb Registry", "Status · Operationen · Entrypoints", "implemented", 1490, 470, ["limbs/registry.json", "orchestrator/runner.py"], "Aktuelle Wahrheit für Limb-Status, Operationen, Entrypoints und erlaubte Umgebung."),
    ]
    edges = [
        e("human", "speech", "spricht", "implemented", "docs/SPEECH.md"), e("speech", "apollo", "Entwurf", "implemented", "docs/SPEECH.md"),
        e("manas", "primordials", "governs", "specified", PDF), e("manas", "kernels", "orchestriert", "specified", PDF), e("manas", "backbone", "trägt", "specified", PDF),
        e("apollo", "ciel", "Zielpfad", "partial", "docs/hermes/RUNTIME_PLAN.md"), e("ciel", "orchestrator", "Brücke fehlt", "partial", "docs/hermes/RUNTIME_PLAN.md"),
        e("apollo", "orchestrator", "aktueller Bedienpfad", "implemented", "frontend/src/apollo/ + orchestrator/runner.py"), e("orchestrator", "registry", "lädt / dispatcht", "implemented", "orchestrator/runner.py"),
    ]
    targets = {"echo": "Protokoll-Harness", "speech": "speaches / Whisper", "bootstrap": "Workspace-Dateien", "vault": "Obsidian + FTS5", "rea": "REA-Sandbox", "openmanus": "OpenManus-Container", "trading": "Sigma + DuckDB", "toolbox": "Tool-Katalog"}
    for idx, (name, spec) in enumerate(registry["limbs"].items()):
        x = 125 + idx * 235
        status = "implemented" if spec["status"] == "active" else "planned"
        nodes.append(n("limb-" + name, name.upper(), f"{len(spec['operations'])} Operationen · {spec['status']}", status, x, 745, ["limbs/registry.json", spec["entrypoint"]], spec["description"], "limb"))
        edges.append(e("registry", "limb-" + name, "Subprozess" if status == "implemented" else "gesperrt", status, "limbs/registry.json"))
        nodes.append(n("target-" + name, targets[name], "nachgelagertes Ziel", status, x, 975, [spec["entrypoint"]], f"Nachgelagertes System des {name}-Limbs.", "external"))
        edges.append(e("limb-" + name, "target-" + name, "nutzt", status, spec["entrypoint"]))
    return nodes, edges


def html_doc(nodes, edges):
    data = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False).replace("</", "<\\/")
    labels = json.dumps(LABEL, ensure_ascii=False)
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NIO Architekturkarte</title><style>
:root{{--bg:#061019;--ink:#edf5fa;--muted:#93a8b7;--implemented:#34d27e;--partial:#f6ad3c;--specified:#aa8cff;--planned:#718096}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 35% 35%,#102a40,#061019 48%,#03080c);color:var(--ink);font:14px/1.45 Inter,system-ui,sans-serif;overflow:hidden}}header{{height:86px;padding:16px 24px;border-bottom:1px solid #203647;background:#07121bdd;display:flex;align-items:center;justify-content:space-between}}h1{{font-size:21px;margin:0}}.muted{{color:var(--muted)}}.legend{{display:flex;gap:14px;flex-wrap:wrap}}.key{{display:flex;gap:7px;align-items:center}}.dot{{width:10px;height:10px;border-radius:50%;background:var(--c)}}#stage{{position:absolute;left:0;right:365px;top:86px;bottom:0;overflow:auto}}svg{{min-width:2050px;min-height:1150px}}.zone{{fill:#0b1822;stroke:#294154}}.zt{{fill:#7895aa;font-size:13px;font-weight:800;letter-spacing:.11em}}.edge{{fill:none;stroke-width:2.3;opacity:.85;marker-end:url(#arrow)}}.implemented{{stroke:var(--implemented)}}.partial{{stroke:var(--partial);stroke-dasharray:9 6}}.specified{{stroke:var(--specified);stroke-dasharray:2 7}}.planned{{stroke:var(--planned);stroke-dasharray:12 5 2 5}}.el{{fill:#91a7b6;font-size:11px;text-anchor:middle;paint-order:stroke;stroke:#061019;stroke-width:4px}}.card{{cursor:pointer;filter:drop-shadow(0 9px 15px #0009)}}.card rect{{fill:#102230;stroke:var(--s);stroke-width:2}}.card:hover rect,.selected rect{{fill:#183448;stroke-width:3}}.title{{fill:#f6fafc;font-weight:800;font-size:14px;text-anchor:middle}}.sub{{fill:#9fb3c1;font-size:10.5px;text-anchor:middle}}.badge{{fill:var(--s);font-size:9px;font-weight:900;text-anchor:middle;letter-spacing:.08em}}aside{{position:absolute;right:0;top:86px;bottom:0;width:365px;background:#09151edd;border-left:1px solid #294154;padding:22px;overflow:auto;backdrop-filter:blur(9px)}}aside h2{{margin:0 0 4px;font-size:20px}}aside h3{{font-size:11px;letter-spacing:.13em;color:#7895aa;margin:22px 0 8px}}code{{display:block;white-space:normal;overflow-wrap:anywhere;background:#061019;border:1px solid #203647;border-radius:7px;padding:8px;margin:6px 0;color:#bdd0dd}}
</style></head><body><header><div><h1>NIO · Plan und Runtime-Wahrheit</h1><div class="muted">Stimme → Apollo → Orchestrierung → Limb Registry → Limbs</div></div><div class="legend"><span class="key"><i class="dot" style="--c:var(--implemented)"></i>implementiert</span><span class="key"><i class="dot" style="--c:var(--partial)"></i>teilweise</span><span class="key"><i class="dot" style="--c:var(--specified)"></i>nur spezifiziert</span><span class="key"><i class="dot" style="--c:var(--planned)"></i>geplant</span></div></header><main id="stage"><svg id="map" viewBox="0 0 2050 1150"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker></defs></svg></main><aside id="panel"><h2>So liest du die Karte</h2><p>Oben: kanonischer Zielplan aus der PDF. Mitte: heute nachweisbarer Bedien- und Runtime-Pfad. Unten: echte Registry, sternförmig zu allen Limbs.</p><p>Klicke einen Knoten oder eine Kante für Bedeutung und Quellnachweise.</p><h3>WICHTIGSTE LÜCKE</h3><p>Die Ciel-Module existieren. Ihre produktive Brücke in den Haupt-Orchestrator ist aber nicht als durchgängiger Runtime-Pfad belegt.</p></aside><script>
const M={data},L={labels},svg=document.getElementById('map'),panel=document.getElementById('panel'),NS='http://www.w3.org/2000/svg',C={{implemented:'#34d27e',partial:'#f6ad3c',specified:'#aa8cff',planned:'#718096'}};function x(n,a={{}},t=''){{const z=document.createElementNS(NS,n);for(const[k,v]of Object.entries(a))z.setAttribute(k,v);z.textContent=t;return z}}for(const z of [{{x:45,y:30,w:1100,h:285,t:'KANONISCHER ZIELPLAN · PDF v8.1'}},{{x:45,y:380,w:1560,h:220,t:'BEDIEN- UND RUNTIME-PFAD · REPOSITORY'}},{{x:45,y:670,w:1960,h:420,t:'LIMB-STERN · limbs/registry.json'}}]){{svg.append(x('rect',{{class:'zone',x:z.x,y:z.y,width:z.w,height:z.h,rx:18}}));svg.append(x('text',{{class:'zt',x:z.x+18,y:z.y+26}},z.t))}}const B=Object.fromEntries(M.nodes.map(n=>[n.id,n]));function path(a,b){{let sx=a.x+90,sy=a.y+34,tx=b.x-90,ty=b.y+34,m=(sx+tx)/2;return Math.abs(ty-sy)>110?`M${{sx}} ${{sy}}C${{m}} ${{sy}} ${{m}} ${{ty}} ${{tx}} ${{ty}}`:`M${{sx}} ${{sy}}L${{tx}} ${{ty}}`}}function se(e){{panel.innerHTML=`<h2>${{e.label}}</h2><p style="color:${{C[e.status]}};font-weight:900">${{L[e.status]}}</p><p>${{B[e.source].label}} → ${{B[e.target].label}}</p><h3>NACHWEIS</h3><code>${{e.evidence}}</code>`}}for(const q of M.edges){{let a=B[q.source],b=B[q.target],p=x('path',{{class:'edge '+q.status,d:path(a,b)}});p.onclick=()=>se(q);svg.append(p);let t=x('text',{{class:'el',x:(a.x+b.x)/2,y:(a.y+b.y)/2+22}},q.label);t.onclick=()=>se(q);svg.append(t)}}function sn(n,g){{document.querySelectorAll('.card').forEach(v=>v.classList.remove('selected'));g.classList.add('selected');panel.innerHTML=`<h2>${{n.label}}</h2><div>${{n.subtitle}}</div><p style="color:${{C[n.status]}};font-weight:900">${{L[n.status]}}</p><p>${{n.detail}}</p><h3>NACHWEISE</h3>${{n.evidence.map(v=>`<code>${{v}}</code>`).join('')}}`}}for(const q of M.nodes){{let g=x('g',{{class:'card',transform:`translate(${{q.x-90}} ${{q.y}})`,style:`--s:${{C[q.status]}}`}});g.append(x('rect',{{width:180,height:68,rx:12}}));g.append(x('text',{{class:'title',x:90,y:22}},q.label));g.append(x('text',{{class:'sub',x:90,y:40}},q.subtitle.length>29?q.subtitle.slice(0,28)+'…':q.subtitle));g.append(x('text',{{class:'badge',x:90,y:57}},L[q.status]));g.onclick=()=>sn(q,g);svg.append(g)}}
</script></body></html>'''


def report(nodes):
    limbs = [x for x in nodes if x["kind"] == "limb"]
    return f"""# NIO Architecture - Truth Report

Deterministically generated from the current repository and the canonical v8.1 PDF. No semantic extraction or API call was performed.

## Result

- Operator flow: Human voice -> speech recognition -> Apollo.
- Proven execution flow: Apollo -> NIO Orchestrator -> Limb Registry -> active Limbs.
- Canonical governance: MANAS: CIEL -> Primordials / Dual-Kernel / Backbone.
- Material gap: `apollo/ciel` exists, but its productive bridge to the main Orchestrator is not proven and is marked **partial**.
- Current registry: {len(limbs)} Limbs ({sum(x['status'] == 'implemented' for x in limbs)} active, {sum(x['status'] == 'planned' for x in limbs)} planned).

## Truth rules

- **Implemented:** supported by current source or registry evidence.
- **Partial:** code exists, but productive end-to-end wiring is not proven.
- **Specified:** canonical PDF target, not promoted to runtime fact.
- **Planned:** explicitly planned or blocked in the repository.

## Primary evidence

- `docs/SPEECH.md`
- `frontend/src/apollo/dictation.ts`
- `apollo/ciel/__init__.py`
- `docs/CIEL.md`
- `docs/hermes/RUNTIME_PLAN.md`
- `orchestrator/runner.py`
- `limbs/registry.json`
- `{PDF}`

The full symbol graph remains at `graphify-out/graph.html`; it is supporting evidence, not the architecture narrative.
"""


def main():
    nodes, edges = model()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nio-architecture.html").write_text(html_doc(nodes, edges), encoding="utf-8")
    (OUT / "NIO_ARCHITECTURE_REPORT.md").write_text(report(nodes), encoding="utf-8")
    print(f"wrote nio-architecture.html: {len(nodes)} nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()
