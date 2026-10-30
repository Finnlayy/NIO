# Dokumentations-Index

Einstiegspunkt für das **Neural Intelligence Network (NIO)**. Diese Seite sagt,
welches Dokument du brauchst — nicht alles lesen.

Stand: `9598911` (Merge PR #243) · Sprache: Deutsch, Code und Identifier englisch.

---

## Drei Lesepfade

### Ich will das System benutzen

1. [`../README.md`](../README.md) — Installation, `npm run ui:dev`, erste Schritte
2. [`APOLLO-CORE.md`](APOLLO-CORE.md) — die Bühne: Orb, Knoten, Deck, Terminal
3. [`OPS-GRID.md`](OPS-GRID.md) — das Widget-Grid unter `/ops`

### Ich will daran entwickeln

1. [`ARCHITECTURE.md`](ARCHITECTURE.md) — Schichten, Grenzen, Entscheidungslog
2. [`../protocol/PROTOCOL.md`](../protocol/PROTOCOL.md) — Intent/Result 1.2 (normativ)
3. [`NEU.md`](NEU.md) — Kern, Orchestrator, Limbs im Detail
4. [`TESTING.md`](TESTING.md) — wie man prüft, dass nichts kaputt ist

### Ich will es betreiben

1. [`OPERATIONS.md`](OPERATIONS.md) — Ports, Umgebungsvariablen, Prozesse, Troubleshooting
2. [`TRADING-LIMB.md`](TRADING-LIMB.md) — Sigma-Worker installieren und fahren
3. [`DATA-FLOW.md`](DATA-FLOW.md) — woher Preise kommen und warum sie manchmal fehlen

---

## Dokumente

| Datei | Zeilen | Inhalt | Für wen |
|---|---:|---|---|
| [`../README.md`](../README.md) | ~290 | Projektüberblick, Quickstart | alle |
| [`INDEX.md`](INDEX.md) | — | diese Seite | alle |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 212 | zwei Stapel, eine Grenze; Schichten; Prozess- und Zeitmodell | Entwickler |
| [`KANBAN.md`](KANBAN.md) | ~140 | Hermes-Kanban: Tasks, Worker, Architektur, Konfiguration und CLI | Entwickler, Betrieb |
| [`NEU.md`](NEU.md) | 470 | Core, Orchestrator, Limbs, Lernschleife | Entwickler |
| [`APOLLO-CORE.md`](APOLLO-CORE.md) | ~240 | Orb, Neuronaler Graph, Router, Deck, Terminal | Nutzer, Frontend |
| [`OPS-GRID.md`](OPS-GRID.md) | ~180 | 10 Widgets, Drag/Resize, MCP-Konsole | Nutzer, Frontend |
| [`DATA-FLOW.md`](DATA-FLOW.md) | ~200 | Marktdaten: MCP → Adapter → Browser; Formate und Messungen | Entwickler, Betrieb |
| [`TRADING-LIMB.md`](TRADING-LIMB.md) | ~230 | Sigma als Handels-Knoten; Sparse-Clone, Pin, Lifecycle | Betrieb |
| [`API.md`](API.md) | ~220 | 4 Next-Routen mit vollständigen Fehlerverträgen | Frontend, Integration |
| [`TESTING.md`](TESTING.md) | ~180 | 360 Python-Tests, 69 UI-Tests, Audit-Harness | Entwickler |
| [`OPERATIONS.md`](OPERATIONS.md) | ~200 | Ports, Env, Prozesse, Troubleshooting | Betrieb |
| [`REA-SUBAGENT.md`](REA-SUBAGENT.md) | 396 | REA-Limb als Subagent mit eigener Sandbox | Entwickler |
| [`../protocol/PROTOCOL.md`](../protocol/PROTOCOL.md) | ~490 | **normativ**: Intent, Result, Timer, Fehlercodes | Entwickler |
| [`../prompts/limbs/`](../prompts/limbs/) | 3 Dateien | Rollen-Specs: bootstrap, rea, trading | Entwickler |

### Historische Dokumente

Bewusst aufbewahrt, aber **nicht mehr maßgeblich** — sie beschreiben einen
früheren Stand und werden nicht gepflegt:

| Datei | Zeitbezug |
|---|---|
| [`AUDIT-2026-09-08-BLUEPRINT-V4-VS-CODE.md`](AUDIT-2026-09-08-BLUEPRINT-V4-VS-CODE.md) | Abgleich Blueprint v4 gegen Code, September 2026 |
| [`REVIEW-2026-09-04.md`](REVIEW-2026-09-04.md) | Review-Snapshot |
| [`ci-architect-frontend-gate.README.md`](ci-architect-frontend-gate.README.md) | CI-Gate des Architect-Stapels |

---

## Statusmatrix

Was ist gebaut, was ist geprüft, was ist geplant. „Geprüft" heißt: es gibt
einen Test, der ohne Netz und ohne Handarbeit läuft.

### Python-Stapel (`core/`, `orchestrator/`, `limbs/`)

| Modul | Zeilen | Status | Geprüft durch |
|---|---:|---|---|
| `core/` — Protokoll, Policy, Kernel, Job | 3 945 | **stabil** | `tests/` (360 gesamt) |
| `orchestrator/` — Planner, Runner, Scheduler, UDS, Locks | 7 910 | **stabil** | `tests/` |
| `limbs/echo` (Phase 1) | — | **aktiv** | `test_limbs.py` |
| `limbs/bootstrap` (Phase 2) | — | **aktiv** | `test_bootstrap.py` |
| `limbs/rea` (Phase 3) | — | **aktiv** | `test_limbs.py`, `support_rea.py` |
| `limbs/trading` (Phase 5) | 552 | **aktiv** | `test_trading_limb.py` (23) |

**26 Operationen** in `protocol/operations.json`: 4 `echo`, 6 `bootstrap`,
5 `rea`, 8 `trading`, 3 deklariert-aber-nicht-implementiert (`shell.exec`,
`test.run`, `core.memory_write`).

### Frontend (`frontend/`, Next 16)

| Route | Typ | Status |
|---|---|---|
| `/` und `/apollo` | ○ statisch | **stabil** |
| `/ops` | ○ statisch | **stabil** |
| `POST /api/apollo` | ƒ dynamisch | **stabil**, fail-closed |
| `POST /api/sandbox` | ƒ dynamisch | **stabil**, Allowlist |
| `GET /api/market/[tool]` | ƒ dynamisch | **stabil**, braucht `TVREMIX_API_KEY` |
| `GET /api/telemetry/stream` | ƒ dynamisch | **stabil**, SSE |

**69 UI-Tests** über `node scripts/ui-test.mjs` (kein Framework, siehe
[`TESTING.md`](TESTING.md)).

### Bekannte Einschränkungen

Diese Punkte sind Absicht oder offen dokumentiert — keine Überraschungen:

| Einschränkung | Warum |
|---|---|
| `/api/market/*` liefert **503/502** ohne `TVREMIX_API_KEY` | fail-closed; die Widgets zeigen `SIM`-Badges und synthetische Daten |
| Telemetrie-Stream meldet `state: "stale"` | Python-Produzent (`runtime/telemetry.sock`) läuft nicht immer |
| Orb nutzt **Canvas2D** ohne WebGL | Software-Rendering in headless-Umgebungen; im Browser WebGL |
| Kein Live-Broker | Trading-Limb exponiert keine Kraken-Routen |
| Kein Qdrant für Candles | Candles sind tabellarisch, nicht vektoriell (siehe [`DATA-FLOW.md`](DATA-FLOW.md)) |

---

## Begriffe

| Begriff | Bedeutung |
|---|---|
| **NEU** | Der Python-Stapel: Core, Orchestrator, Limbs. Stdlib-only. |
| **Intent / Result** | Die zwei Envelopes des Protokolls. Ein Limb liest genau einen Intent und gibt genau ein Result zurück. |
| **Limb** | Ein ausführender Arm. Kennt keine Konversation, nur den Intent. |
| **Subagent** | Ein Limb mit eigener Sandbox und eigenem Werkzeug (`rea`, `trading`). |
| **Sigma** | Externes Handels-Repo, das als Worker hinter dem Trading-Limb läuft. |
| **Apollo** | Die Frontend-Bühne (Orb, Graph, Deck, Terminal). |
| **FreeLLMAPI** | Routing-Schicht über 36 Provider / 635 Endpoints mit Kontext-Übergabe. |
| **Lymp** | Die Mitose-Animation, mit der `/spawn` neue Knoten wachsen lässt. |
