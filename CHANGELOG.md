# Changelog

Alle nennenswerten Änderungen. Format orientiert sich an *Keep a Changelog*;
Datumsangaben in UTC.

---

## [Unreleased]

### Geändert

- Marktdaten (`/api/market/*`) laufen über den **offiziellen TradingView-MCP**
  (`mcp.tradingview.com`) statt über das abgeschaltete tvremix. Anmeldung per
  OAuth 2.1 (Dynamic Client Registration, PKCE, Refresh-Token) über
  `/api/market/oauth/{start,callback,status}`; Tokens nur lokal in
  `frontend/.tradingview-oauth.json`. Feste Tool-Zuordnung in
  `src/server/tradingview/tools.ts`, Adapter für die neuen Antwortformen, der
  generische Durchreich erreicht nur Lese-Tools. `TVREMIX_*` entfällt.

### Behoben

- Refresh-Buttons der Markt-Widgets luden nur neue Simulationsdaten; jetzt
  holen sie sofort Live-Daten und umgehen dafür einmal den Server-Cache
  (`refreshKey` in `useMarketData`, `?fresh=1`).
- Technik-Gauge zeigte feste Platzhalter-Zählungen (3 Buy / 10 Sell) auch bei
  „Strong Buy“; die Zählung kommt jetzt aus den echten Indikatoren.

### Hinzugefügt

- `apollo/ciel/mcp_nodes.py` + `mcp_config.json` — externe MCP-Nodes als
  Ciel-Skills (u. a. StalkChain `https://data.stalkchain.com/mcp`, via
  `npx mcp-remote` oder direkt per SSE ohne Node). Stdio-JSON-RPC- und
  SSE-Transport (Stdlib-only, strikte Timeouts), Claude-style Config-Loader
  mit `${VAR}`-Expansion, Registrierung als `<node>.<tool>` im Cold-Storage,
  fail-closed je Node (`ciel.mcp.node_failed`), `mcp_config`-Parameter in
  `build_ciel_layer`. 8 neue Offline-Tests in
  `tests/test_ciel_mcp_nodes.py` (Fake-Stdio-Subprozess + Fake-SSE-Server,
  grün mit wie ohne pydantic).
- `apollo/ciel/telemetry.py` — Modul E: Real-Time Graph-UI Telemetry.
  Typsichere `CielGraphEvent`-Payloads (`CIEL_COLD_STATE_SYNC`,
  `CIEL_NCM_ROUTING` mit `SYSTEM_1_BYPASS`/`SYSTEM_2_JIT`, `CIEL_JIT_RELOAD`,
  `CIEL_MACRO_EVOLUTION`), inkl. `active_nodes` mit Confidence-Scores,
  `saved_tokens_estimate` (Cold minus injiziert) und `node_id` je Tool.
  Non-blocking via begrenzter `asyncio.Queue` + Worker-Task
  (`drain()`/`close()`), Subscriber auf Event-Bus (`ciel.graph.event`) und
  optional direkt als UDS-Datagramm an `runtime/telemetry.sock` (Pfad ins
  Dashboard: UDS → `telemetryBridge` → SSE `/api/telemetry/stream`).
  Verdrahtung in Registry/Gate/Agent/Synthesizer/`build_ciel_layer` (neue
  optionale Parameter, Default `None` = altes Verhalten), 3 neue Tests
  (14/14 grün mit wie ohne pydantic).

### Hinzugefügt (Ciel A–D, PR #249)

- `apollo/ciel/` — Ciel JIT-Tool-Orchestrator (NCM + Sandbox-Agent), rein
  additiv ohne Änderung am Bestandscode: Modul A Cold-Storage Skill Registry
  (In-Memory + SQLite/JSON-Cache, FastMCP-Interceptor), Modul B System-1 NCM
  Gatekeeper (Direct Bypass ab Confidence ≥ 0.88 mit 0 Tokens, sonst JIT
  Top-3), Modul C isolierter Sandbox-Agent (hart hinterlegter System-Prompt,
  exakt ein Meta-Tool `request_additional_skill`, strikte
  `asyncio.wait_for`-Timeouts), Modul D Macro-Skill Synthesizer (3×
  hintereinander erfolgreiche Ketten → Makro-Tool). Inkl.
  `tests/test_ciel_integration.py` (11 Tests, grün mit wie ohne pydantic) und
  `docs/CIEL.md`. Optionales Extra `pip install -e '.[ciel]'` (pydantic v2);
  ohne bleibt die Laufzeit Stdlib-only per Fallback.
- `pyproject.toml`: `apollo`/`apollo.ciel` in `packages`, neues Extra `ciel`

### Dokumentation

- `docs/INDEX.md` als Einstiegspunkt mit drei Lesepfaden und Statusmatrix
- `docs/DATA-FLOW.md` — tvremix-MCP-Kette, SSE-Telemetrie, Formatvergleich mit
  Messwerten (JSON/CSV/TOON/Parquet) und die Abgrenzung zu Qdrant
- `docs/TRADING-LIMB.md` — Sigma-Worker, Sparse-Clone, Pin, Lifecycle, Nachweise
- `docs/API.md` — vier Routen mit vollständigen Fehlerverträgen
- `docs/OPS-GRID.md` — 13 Widgets, Interaktion, Fail-closed-Badges
- `docs/TESTING.md` — 360 Python- und 69 UI-Tests, Browser-Audit, Merge-Gates
- `docs/OPERATIONS.md` — Ports, Env, Prozesse, Troubleshooting
- `CHANGELOG.md` (diese Datei)
- `README.md` um das Trading-Limb ergänzt (fehlte vollständig)

---

## [9598911] — 2026-10-27

Merge von PR **#243**: Trading-Limb (Sigma als Handels-Knoten).

### Hinzugefügt

- `limbs/trading_limb.py` — acht Operationen: `ping`, `install`, `start`,
  `stop`, `status`, `lake_summary`, `lake_compact`, `backtest_run`
- `prompts/limbs/trading_limb.md` — Rollen-Spezifikation
- `tests/test_trading_limb.py` — 23 Tests (Vertrag, Isolation, Fail-closed,
  Parameterfilter, Skript-Aufrufweg)

### Geändert

- `limbs/registry.json` — Limb `trading` (Phase 5, Status `active`)
- `protocol/operations.json` — acht neue Operationen, Version `1.2`,
  `updated_at` 2026-10-27

### Behoben

- **Installationsgröße:** Sigma ist ~818 MB (davon ~166 MB fremde
  `.deb`-Partials). Sparse + Blobless reduziert den Arbeitsbaum auf **2,2 MB**,
  Installation in **32 s**.
- **Fehlender Importpfad:** `/sigma/` muss im Sparse-Cone stehen, sonst
  scheitert der Worker-Start mit `ModuleNotFoundError: No module named 'sigma'`.
- **Re-Install nach `.git`-Entfernung:** ein `git fetch` im `.git`-losen Baum
  scheitert mit `upload-pack: not our ref`. Der Limb erkennt Nicht-Installation
  jetzt über den Marker und baut neu auf.
- **Operationsnamen:** das Protokoll erlaubt genau einen Punkt.
  `trading.lake.summary` → `trading.lake_summary` (sonst `E_SCHEMA_INVALID`).
- **Testisolation:** ein Test benutzte die Produktions-Sandbox und beendete
  über die PID-Datei einen laufenden Worker. Fail-closed-Tests haben jetzt eine
  eigene Sandbox.

### Nachweise

`install` 32,3 s / 2 234 505 B · `start` 2,1 s · Lake 30 240 Zeilen in 4
Parquet-Dateien · Backtest `tv_541cc810da` (300 Candles, 17 Trades,
10 000 → 9 982,66) · `stop` schließt Port und PID. NIO-Suite **360 OK**,
Sigma-Suite **912 passed, 1 skipped** (zweimal identisch).

---

## [c139ca6] — 2026-10-26

Merge von PR **#242**: Apollo Core UI.

### Hinzugefügt

- **Hermes-Apollo-Orb** — WebGL-Shader mit Canvas2D-Fallback: SDF-Kugel,
  domain-warped Plasma, Fresnel-Rim, Amethyst-Schockwelle, Crimson-Fehlerring
- **Neuronaler Graph** — radialer Ring, Bezier-Axone, Impuls-Pakete,
  Lymp-Mitose-Vesikel
- **Apollo Control Deck** — Primär-Runtime, FreeLLMAPI-Vault, Routing-Gewichte,
  Fallback-Kette, MCP- und Sandbox-Rechte
- **Hybrid-Terminal** — Chat/Log/CLI mit `/spawn`, `/dispatch`,
  `/failover simulate`, `/router status`, `/config set`, `/sandbox exec`,
  `/clear`, `/help`
- `POST /api/apollo` (fail-closed Proxy), `POST /api/sandbox` (Allowlist)
- 29 Router-/Geometrie-Tests (`apollo-router.test.js`), Browser-Audit-Skripte
- `docs/APOLLO-CORE.md`

### Behoben

- **Deck-Fokusfalle:** Fokus blieb auf dem Trigger, `activeElement === first/last`
  traf nie zu. Jetzt Fokus hinein beim Öffnen, Capture-Phase-Trap, Wiederherstellung
  beim Schließen.
- **Backdrop:** der Handler lag am Overlay mit `target === currentTarget`, der
  Scrim ist aber ein eigenes Kind. Handler jetzt am Scrim, `stopPropagation` am Panel.
- **Gewichtsregler:** schrieben in den Live-Router statt in den Entwurf — Thumb
  und Anzeige widersprachen sich, Escape behielt die Änderung. Jetzt `patchRouting`
  mit normalisierter Vorschau.
- **„Maximum update depth exceeded":** `setQuota` spiegelte den Quotienten in
  `config`, der Seed-Effect des Decks war auf `config` geschlüsselt → Reset bei
  jedem Tick. Erst **60 schnelle Ticks** lösten es aus (`a9f-bisect.mjs` als
  Regressionstor).
- **Terminal:** kein Autofokus, keine Copy-Rückmeldung, `/clear` lief mitten
  im Turn. Jetzt 40-ms-Fokus, Copy-Badge mit Fallback, Busy-Gate.
- **Ring-Kollisionen:** `/spawn` stapelte Karten übereinander. `fitEllipse()`
  vergrößert die Ellipse, skaliert Karten 196 → 149 px und fällt erst dann auf
  ein scrollbares Node-Board zurück.
- **Hydration:** bei Größe 0 meldete der Fitter „crowded" und wechselte das
  Markup. Vor der Messung gilt jetzt eine nominale 1440×720-Szene.
- **Kontrast:** 45 Textknoten unter AA auf `/`, 10 auf `/ops` (slate-500/600 →
  slate-400; Treemap-Kacheln auf Weiß) → **0**.
- **`/ops`-Clipping:** Trade-Plan-Leiter 7 px, Limb-Mesh 4 px abgeschnitten.

### Nachweise

`tsc` sauber · 69/69 UI-Tests · Build grün mit 8 Routen · Audit `fails: 0`
über 7 Viewports · 0 Knoten unter AA.

---

## [b570763] — REA-Subagent

Merge von PR **#241**.

- `limbs/rea_limb.py` — erster echter Subagent mit eigener Sandbox
- `orchestrator/subagent.py`, `docs/REA-SUBAGENT.md`
- Suite **337 Tests OK**
- Nachweise: REA installiert und ausgeführt; Digests
  `7→180/18 74a4535c672292c5`, `42→130/13 b191cdb7f40334ea`,
  `1337→170/17 09878289a23ea706`, Tetris `79712df5ccf2daaf`

---

## Frühere Phasen

| Phase | Limb | Inhalt |
|---|---|---|
| 1 | `echo` | Protokoll-Roundtrip, Fehlerpfade (`fail`/`timeout`/`partial`/`crash`) |
| 2 | `bootstrap` | Dateioperationen in der Sandbox, `repo_write` mit Elevation |
| 3 | `rea` | Subagent: fremdes Werkzeug installieren und betreiben |

`shell.exec`, `test.run` und `core.memory_write` sind in
`protocol/operations.json` deklariert, aber **noch von keinem aktiven Limb
implementiert** — sie gelten damit als nicht verfügbar.
