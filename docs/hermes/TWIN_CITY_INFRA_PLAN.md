# TWIN-CITY INFRA PLAN — NIO Sovereign Twin-City Frontend

Leitprinzip (Operator-Kanon): Software ist Informationsfluss. Alles kann mit
allem verbunden werden, wenn man die Software selbst entwirft statt diskrete
Pakete zu kaufen; Software dient dazu, Information zu wandeln, auszutauschen
und zu bewegen. Die Twin-City ist die Sicht- und Steueroberflaeche dieses
Flusses: Agenten tragen Tasks zwischen Districts (Information bewegt sich),
Gates sind Wandlungspunkte (Approval/Reject), das Orb-Sanctum ist der
Dispatch-Hub. Jede Phase wird daran gemessen, ob sie Informationsfluss
sichtbarer, steuerbarer und verlustfreier macht (D1-D5 sind seine Regeln).

Guide-Entwurf (Hermes), 2026-11-19. Basis: Master-Prompt v8.1/v8.2 (Twin-City
UI Extraction & API Synthesis), Git-Guardrails-Direktive des Operators,
verifizierte Ist-Infrastruktur. Umsetzung ausschliesslich ueber NIO-Kanban
(Phasen P1-P4, jede mit Merge-Gate). Dieses Dokument ist der Plan, nicht der Code.

## 0. Invarianten (NON-NEGOTIABLE, aus Master-Prompt + Direktiven)

- D1 Zero Local State: Frontend ist reiner View-/Dispatch-Client. Single
  Source of Truth = NIO FastAPI/Redis. Kein Task-, Agent-, Gate-, Map-Save
  im Client.
- D2 Kein Mock/Fallback im Produktivpfad. Ohne Backend-Events: nur das
  NIO-Orb-Sanctum, State disconnected/idle.
- D3 Welt-Isolation: jeder API-Call, jedes WS-Event, jeder Command traegt
  world_id live|shadow. Shadow-Commands erreichen NIE Live-Execution oder
  Live-Gates. Isolation wird SERVERSEITIG erzwungen, nicht im Client.
- D4 Maximale Wiederverwendung: Phaser-Rendering, Sprites, Pathfinding,
  Tilemap bleiben; Bun-Server + ~/.claude*/~/.codex-File-Watcher entfallen
  restlos.
- D5 Git-Guardrails: Limbs arbeiten nur auf orchestrator-verwalteten
  Worktrees/Branches; parken statt verwerfen; Merge/Loeschen nur durch
  Orchestrator nach Gate-Freigabe (resolve_gate approve).

## 1. Ist-Stand (verifiziert 2026-11-19)

| Komponente | Ort | Rolle |
|---|---|---|
| nio-kanban (FastAPI) | 127.0.0.1:8740, systemd user | Tasks/Workers/Boards, SSE-Bus, Approvals; Redis (sigma-redis) fuer Locks/Policy/DAG |
| nio-apollo (Next.js) | 127.0.0.1:4001, systemd user | bestehendes Orb-UI + Terminal (CLI /tasks, /approvals, /approve) |
| NEU-Orchestrator | ~/Projects/NIO, CLI | Jobs/Intents/Limbs, Policy-Gates, Refinement-Vault (geparkte Limbs), Audit-Ledger |
| CIEL | apollo/ciel/ | DAG-State (Redis), Pre-Execution-Policy, Sandbox-Agent, Telemetry — produktiv nur teilweise verdrahtet |
| Worker | Docker, nio-opencode-model (internal) | opencode-Runtime, freellmapi/auto via Relay; States idle/busy/disabled |
| Agent-Quest | ~/Projects/Agent-Quest | Client: Phaser + React + Vite (KEEP); Bun-Server :4444 + File-Watcher (DELETE) |
| FreeLLMAPI | 127.0.0.1:3001 | Modell-Router, unified key, Provider google/groq/mistral/openrouter |
| Twin-Repo | ~/NIN | zweiter Clone fuer Shadow-/Mirror-Arbeit (blue-green) |

Es gibt KEINEN world_id-/Twin-City-Code in NIO (grep-verifiziert) — Greenfield.

## 2. Soll-Topologie

```
 Operator-Browser (loopback)
   |  HTTP/WS
   v
 nio-world-bridge (NEU, FastAPI, 127.0.0.1:8750, systemd user)
   |-- GET /            -> statischer Frontend-Build (Phaser/React, offline)
   |-- WS  /ws/world    -> Multiplex-Stream live+shadow (<=15 Hz gebatcht)
   |-- POST /api/world/command -> Command-Router (world_id-Gate)
   |-- FastMCP: world_register_district / world_retire_district /
   |            world_sync_agent / world_set_orb_state / world_raise_gate
   |
   |-- liest: kanban-SSE-Bus (:8740), Redis (DAG/Policy/Worker-State),
   |          Orchestrator-Status (Jobs, Refinement-Vault, Gates)
   |-- schreibt: kanban-API (Tasks/Transitions), Approvals-API,
   |             Orchestrator-Gate-Flow — IMMER mit world_id
   v
 NIO State Engine (FastAPI :8740 + Redis) = Single Source of Truth
   live:   Haupt-Board b-5fb62933ab27, Repo ~/Projects/NIO, main
   shadow: Shadow-Board (neu, world_id=shadow), Repo ~/NIN (Twin)
```

Begruendung Bridge als eigener Dienst: enge, typisierte Schnittstelle
(FastAPI/FastMCP) ohne Business-Logik-Duplikate; kanban-API bleibt
unveraendert; Frontend hat genau einen Endpoint. Loopback-Bindung wie alle
NIO-Dienste; Auth: Bearer-Token (NIO_WORLD_TOKEN, neu in nio.env).

## 3. State-Mapping (NIO -> Stadt)

| NIO-Entity | Stadt-Entity | Mapping-Quelle |
|---|---|---|
| Worker (idle/busy/disabled) | Agent/Held | GET /workers; busy->working, idle->idle, disabled->error |
| Task in_progress + assigned_worker | Agent moving/working + task_summary | SSE task.* Events, target_district aus required_skills/limb |
| Refinement-Vault parked limb | tavern_limbs-Bewohner (parked_limb) | orchestrator refinement status |
| Approval-Ticket (Policy-Gate) | gate_outpost + gate_alert (severity, prompt, diff) | /api/runtime/approvals + SSE |
| Limb-Domaene (trading/forge=bootstrap/library=vault/tavern) | district_type | limbs/registry.json, statisch + world_register_district |
| Orb-Zustand (orchestrator aktiv/leer/gate-offen) | orb_update (idle/listening/dispatching/alert) | Job-Queue + offene Tickets, aggregiert in Bridge |
| Live vs Shadow Delta | divergence_diff | Bridge vergleicht Welt-Snapshots (gleiche Entity-IDs) |

Districts sind dynamisch (Slot-Grid), keine Pixel-Koordinaten vom Backend.
Gebaeude-Slots: konzentrisch um Orb-Sanctum (0,0); Strassen-Tiles automatisch;
A*-Graph-Update zur Laufzeit; parked limbs automatisch in tavern_limbs.

## 4. Welt-Isolation (D3) — serverseitig

- Bridge haelt zwei Welt-Adapter: live (Haupt-Board, ~/Projects/NIO) und
  shadow (Shadow-Board, ~/NIN). Jeder Adapter hat eigene API-Clients/Queues.
- Commands tragen world_id; Router lehnt fehlende/ungueltige world_id ab
  (fail-closed). Cross-World-Zugriffe sind im Router unmoeglich (kein
  gemeinsamer Client-Pool).
- promote_limb_or_config: einziger Pfad shadow->live; erfordert explizites
  Modal + resolve_gate(approve) durch Operator; Orchestrator merged nach
  Git-Guardrails (FF/squash auf main nach Gate), danach kontrolliertes
  Branch-Cleanup.
- Shadow-Board initial: eigenes Board auf derselben kanban-Instanz
  (billig, gleiche API). Spaeter: zweite Instanz aus ~/NIN (echtes
  blue-green) — Entscheidung E1.

## 5. Event-Pipeline

kanban-SSE + Redis-Polling (Bridge) -> Transform (Mapping Tabelle 3) ->
Batch/Throttle max 15 Hz pro Welt -> WS /ws/world (Schema Master-Prompt 2.1:
world_snapshot | orb_update | district_upsert/remove | agent_upsert/remove |
gate_alert | divergence_diff, jeweils world_id + timestamp_ms + payload).
Client: 60-FPS-Renderloop interpoliert zwischen Snapshots; kein eigener
State ausser View (Camera, Wetter-Transition, UI-Flags).

## 6. Command-Router (POST /api/world/command)

| Command | Ziel | Guard |
|---|---|---|
| dispatch_prompt | kanban task create (Welt-Board, required_skills explizit!) | world_id; kein implizites Skill-Empty (Routing-Guard!) |
| resolve_gate | Approvals-API approve/reject | world_id; Gate muss zur Welt gehoeren |
| promote_limb_or_config | Orchestrator-Gate-Flow shadow->live | Modal-Bestaetigung + Operator-Gate |

## 7. Frontend-Infrastruktur (Phase 3, auf Agent-Quest-Client)

- KEEP: Phaser-Scene, Tilemap, Sprites, A*/Waypoints, React-DOM-Overlays.
- DELETE: server/ (Bun, :4444), Claude/Codex-Provider/Watcher, alle
  lokalen JSONL-Pfade; package.json-Scripts ohne Bun-Server.
- NEU: Slot-Grid-Allocator (deterministisch, konzentrisch), Orb-Sanctum
  zentral (idle pulsieren / listening Cyan-Gold-Wirbel + Ringe / dispatching
  Energie-Partikel zu Ziel-Districts / alert roter Puls), Wetter-Shader
  (Sonne=live, Regen=shadow mit Laternen/Reflexionen), Single-View-Toggle
  + Side-by-Side-Twin-View mit Camera-Sync + Divergenz-Markern,
  Viewport-Culling >15 Gebaeude, WS-Client mit Reconnect + Snapshot-Resume.
- Assets: 100% lokal (Phase-1-Audit als Checkliste), Build = vite build,
  Auslieferung statisch durch Bridge (ein Dienst, offline-faehig).

## 8. Deployment

- systemd user: nio-world-bridge.service (Restart=on-failure, loopback,
  EnvironmentFile nio.env, NIO_WORLD_TOKEN neu). Frontend statisch im
  Bridge — kein zweiter Unit noetig. nio-apollo bleibt bestehen (Ops-UI).
- Keine neuen externen Dependencies; Bridge stdlib+FastAPI/fastmcp wie
  kanban; keine Docker-Netz-Aenderungen (Worker bleiben internal).
- Ports: 8750 Bridge (Vorschlag E2), 4444/4445 werden frei (Agent-Quest-
  Altserver entfaellt; agent-quest.service des Nutzers bleibt unberuehrt,
  falls gewuenscht — Entscheidung E3).

## 9. Phasen + Gates (Kanban-_tasks, required_skills explizit)

- P1 REA-Extraktion Agent-Quest -> architecture_blueprint.md (laeuft:
  t-78deecf6e32b, coder). Gate: Blueprint vollstaendig (5 Artefakten).
- P2 nio_world_api_spec.yaml + nio_world_bridge.py (FastAPI/WS/FastMCP,
  ohne Business-Duplikate) + Welt-Adapter live/shadow + Tests. Gate:
  Spec-Validation + pytest gruen + WS-Schema-Contract-Test.
- P3 Frontend-Refactor (Allocator, Orb, Wetter, Twin-View, Culling,
  Asset-Bundle) auf P1-Cut-Line. Gate: vite build fehlerfrei, DoD-Kriterien
  manuell + automatisch.
- P4 Integration + DoD: register_district -> Gebaeude + Strasse + A*-Lauf;
  Wetter-Toggle + Twin-View routen strikt getrennt; Gate-Klick ->
  resolve_gate erfolgreich; ohne Backend nur Orb idle. Gate: Operator.

Serialisierung: P2 und P3 teilen sich die Bridge-Spec — P3 startet erst
nach P2-Merge. Git-Guardrails (t-2264c44babc5, EDITH) laufen parallel auf
NIO-Core; P2 baut auf deren Park/Gate-Semantik auf (Rebase nach Merge).

## 10. Offene Entscheidungen (Operator)

- E1 Shadow-Realisierung: Board-Isolation auf einer Instanz (Start,
  empfohlen) vs. zweite kanban-Instanz aus ~/NIN (spaeter, echtes
  blue-green).
- E2 Bridge-Port 8750 + NIO_WORLD_TOKEN: ok?
- E3 Agent-Quest-Altserver (agent-quest.service, :4445): behalten als
  separates Spiel-Dashboard oder nach P3-Merge stilllegen? (Nutzer-Tool,
  nicht NIO-Eigentum — nur mit Nutzer-Ok anfassen.)
- E4 Orb-Sanctum-Quelle: Apollo-Orb-Shader (frontend/src/apollo/orbShader.ts)
  portieren vs. neuen Phaser-Shader schreiben. Empfehlung: Portierung
  (Wiederverwendung, D4).
- E5 Wetter-Asset-Lizenz/Quelle: vorhanden in Agent-Quest-Assets?
  Phase-1-Audit abwarten.

## 11. Risiken

- FreeLLMAPI-Quota: zwei parallele Worker + Bridge-Tests teilen sich
  Free-Tier-Limits; Router-Failover mildert, aber P2/P3 nicht parallel
  dispatchen.
- Phaser-Lernkurve fuer Worker: P3 in Teil-Tasks schneiden (Allocator,
  Orb, Wetter, Twin-View je ein Task) — 600s-opencode-Fenster.
- Shadow-Drift: Twin ~/NIN kann main hinterherhinken; Bridge muss
  Commit-Stand je Welt im Snapshot melden (divergence_diffGrundlage).
- CIEL-Telemetry ist nicht produktiv verdrahtet; Orb-States zunaechst aus
  kanban-/Orchestrator-Status aggregieren, CIEL-Events spaeter andocken.
