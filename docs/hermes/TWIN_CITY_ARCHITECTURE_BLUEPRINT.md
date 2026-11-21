# Twin-City Architecture Blueprint (T2, 5 Artefakte + Cut-Line)

Guide-Route, 2026-11-21. Basis: verifiziertes T1-Inventar (docs/twincity/raw/).
Quell-Repo Agent-Quest (Worktree twin-city). Ziel: NIO Sovereign Twin-City
Frontend gemaess ~/Projects/NIO/docs/hermes/TWIN_CITY_INFRA_PLAN.md (D1-D5).

## Artefakt 1 — System-/Scene-Architektur
Phaser-3-Welt (VillageScene, 810 Z.) + React-DOM-Overlays, verbunden ueber
EventBridge (pub/sub, sticky events). PhaserGame.tsx mountet Phaser in React.
BootScene prelaedt Assets; VillageScene.bootstrapWorld() spawnt Gebaeude und
Heroes; Kamera Drag/Pinch-Zoom; Renderloop interpoliert Hero-Bewegung entlang
findRoadPath. Twin-City erweitert: dynamische Districts (Slot-Grid konzentrisch
um Orb-Sanctum), Orb-Sanctum zentral, Twin-View (live/shadow side-by-side).
KEEP: Scene-Graph, EventBridge, Kamera, Hero-Sprites, Renderloop.

## Artefakt 2 — Rendering-/Asset-Pipeline
asset-loader.ts laedt Spritesheets/Images aus themes/tiny-swords-cc0.ts (CC0,
100% lokal unter client/public/assets/themes/tiny-swords-cc0/). TerrainRenderer
malt Boden+Strassen entlang getRoadSegments(); MapConfigRenderer fuer Editor-Maps.
Wetter: prozedurale Canvas-Texturen raindrop/rainsplash + Partikel-Emitter in
VillageScene (Z.206-300), onRainToggle/onNightToggle. Orb: Portierung des
Apollo-GLSL-Shaders (NIO frontend/src/apollo/orbShader.ts; uniforms u_energy/
u_shock/u_error/u_flare) in eine Phaser-Pipeline/WebGL-Quad. Build: tsc -b &&
vite build (client/node_modules/.bin vorhanden). KEINE externen Assets (D4/E5).

## Artefakt 3 — API-/Event-Vertraege
IST: config.ts SERVER_URL http://<host>:4444, WS ws://<host>:4444/ws;
WsEvent snapshot|inventory:update (Agent-State aus Claude/Codex-Session-Parsern).
SOLL (Bridge :8750, NIO FastAPI/Redis = Single Source of Truth):
- WS /ws/world Multiplex live+shadow, <=15 Hz gebatcht, Snapshot-Resume (seq):
  world_snapshot | orb_update | district_upsert/remove | agent_upsert/remove |
  gate_alert | divergence_diff (je world_id + timestamp_ms + payload).
- REST POST /api/world/command: dispatch_prompt | resolve_gate | promote_limb_or_config.
- FastMCP: world_register_district/retire_district/sync_agent/set_orb_state/raise_gate.
- Auth: Bearer NIO_WORLD_TOKEN; loopback 127.0.0.1:8750.
Client-Adapter: hooks/wsEvents.ts + config.ts auf Bridge umstellen; EventBridge
sticky events bleiben (React<->Phaser).

## Artefakt 4 — State-/Datenfluss (D1 Zero Local State)
Single Source of Truth = NIO FastAPI(:8740)/Redis; Bridge aggregiert Welt-Snapshots.
Client haelt NUR View-State: Camera, Wetter-Transition, UI-Flags (useSettings
localStorage <1KB — erlaubt). Agent-/Task-/Gate-/Map-State kommt ausschliesslich
aus WS-Events; kein lokales Task/Agent/Gate/Map-Save. D1-Purge: Editor-Map-
Persistenz (editor-store) + Session-JSONL-Export (report/) entfernen; View-Flags
behalten. Orb-Zustand aus orb_update; Districts aus district_upsert/remove;
Divergenz-Marker aus divergence_diff (nicht lokal berechnen).

## Artefakt 5 — Cut-Line KEEP/DELETE (D4, E3)
KEEP (Phaser-Rendering-Kern):
- client/src/game/scenes/{BootScene,VillageScene}.ts (Scene-Graph, Kamera, Renderloop)
- client/src/game/entities/{Building,HeroSprite,NpcSprite}.ts (Sprites)
- client/src/game/data/road-network.ts (BFS-Waypoint-Pathfinding; dynamisch erweitern)
- client/src/game/data/asset-loader.ts + themes/tiny-swords-cc0.ts (CC0-Assets)
- client/src/game/terrain/{TerrainRenderer,MapConfigRenderer}.ts
- client/src/game/EventBridge.ts + PhaserGame.tsx (React<->Phaser)
- client/src/components/ (React-Overlays), client/public/assets/ (100% lokal)
- Wetter-System (prozedural, VillageScene Z.206-300)
DELETE (im Twin-City-Produkt; separater agent-quest.service bleibt, E3):
- server/ (Hono+Bun :4444): providers/{claude,codex}-provider.ts,
  parsers/{session,codex}-parser.ts (JSONL), watchers/file-watcher.ts
  (~/.claude*/~/.codex chokidar), ws/websocket-server.ts, hooks/claude-hooks.ts,
  map/* (storage/theme-scanner). Begruendung: Twin-City liest NIO-State ueber
  die Bridge, nicht Claude/Codex-Session-Dateien; kein Bun-Server noetig.
- client/src/editor/ Map-Persistenz + report/sessionExport (lokale JSONL) — D1.
- package.json Bun-Server-Scripts (dev:server/start) im Twin-City-Build.
NEU (Twin-City):
- client/src/game/city/{allocator,roads,orb,weather,culling,twinview,ws}.ts
- Gate-Overlay (Klick->resolve_gate), Promote-Modal, dispatch_prompt-UI,
  Divergenz-Marker-Anbindung an divergence_diff.
- vite.twincity.config.ts + build:twincity Script (statisch, von Bridge serviert).
E3: agent-quest.service (:4444/:4445) NICHT stoppen/loeschen; Twin-City ist
separater Build. DELETE wird als Twin-City-Build-Artefakt umgesetzt, nicht als
Zerstoerung des laufenden Nutzer-Tools.

## Verifikations-Checkliste (Guide, gegen echten Baum)
- [offen] ls client/src/game/scenes/VillageScene.ts (810 Z.)
- [offen] grep findRoadPath client/src/game/data/road-network.ts
- [offen] ls client/public/assets/themes/tiny-swords-cc0/
- [offen] grep raindrop client/src/game/scenes/VillageScene.ts
- [offen] ls ~/Projects/NIO/frontend/src/apollo/orbShader.ts
- [offen] cd client && ./node_modules/.bin/tsc -b && ./node_modules/.bin/vite build
