# Bolt — Journal

## 2026-09-06 - Watch/Supervise-Tick: Write-Amplifikation ist der architektonische Hot Path

**Learning:** Der ueberwachte Unlimited-Betrieb (orchestrator/runner.py `_supervise_loop` +
`Scheduler.tick`) persistiert pro Tick (Default 0,5 s) den kompletten Zustand auf Platte:
Slot-Lock-Datei, ganze Job-Datei (Heartbeat) und die ganze Schedule-Datei inkl. Historie.
Runtime-JSON-Dateien wachsen dabei mit (Schedule-Historie bis 200 Eintraege = ~67 KB
pretty-printed), und `json.dumps(..., indent=2)` ist auf solchen Strukturen ~4x teurer
als kompakte Separators (gemessen 1,48 ms vs. 0,37 ms). Gemessen: 1,69 ms/Tick gesamt,
davon Scheduler-Tick 63 %, Heartbeat 24 %, Renew 12 %. Schlimmer: 3 von 4 Ticks feuern
nichts und schrieben trotzdem die volle Datei. Das ist KEIN Cold Path — ein
`watch`/`demo`-Lauf schreibt bei 0,5 s-Tick und every=2 s-Trigger ~1800+
File-Writes/Stunde.

**Action:** (1) `Scheduler.tick()` nur noch bei durabler Aenderung persistieren
(Feuerung, Kantenwechsel, Safety-Net) — abgeleitete Felder (`next_interval_at`,
`last_tick`) brauchen keinen Save, sie rekonstruieren sich aus `t0`/`gate_at`; (2)
Renew/Heartbeat nur alle `renew_s/5` Sekunden (Fristen >= 30 s -> ~92 % weniger Writes);
(3) Schedule-Dateien kompakt serialisieren (Maschinenformat; CLI = menschliche Sicht).
Ergebnis: 1,69 -> 0,19 ms/Tick (-89 %). Fuer kuenftige Optimierungen: erst pruefen, ob
ein "Pro-Tick-Schreiber" mit derivablem Zustand existiert; bei jeder neuen
Runtime-Persistenz fragen: Was ist durabler Zustand vs. abgeleitete Metrik?

## 2026-09-08 - Keyboard shortcuts for core menus
**Learning:** Operators clicked to toggle the MCP Console and Template Gallery, which slows rapid workspace changes. A new `react-hotkeys-hook` dependency would have fought the frozen `package.json` rule (Specter 2026-09-06).
**Action:** `mod+k` toggles MCP Console, `mod+g` toggles Gallery, Escape closes both. Mapping lives in `frontend/src/ops/hotkeys.ts` (`enableOnFormTags: false` via `isTypingTarget`). Badges on the buttons read `Ctrl/⌘` so they stay true on Windows/Linux. No new npm dependency.

## 2026-09-09 - React Render Loop Write-Amplification
**Learning:** Computing heavy nested filters and object derivations directly inside a React component (like DomainsGrid computing nodes, topics, and links per domain) triggers an expensive  execution on every re-render, creating CPU spikes even when underlying static data (e.g., ) hasn't changed. This is a common performance anti-pattern in dashboards fetching layout configuration.
**Action:** When component properties are derived from static configurations (like  and ), extract the calculation into a module-level constant (e.g., ) instead of keeping it in the render loop or relying exclusively on .
## 2026-09-09 - React Render Loop Write-Amplification
**Learning:** Computing heavy nested filters and object derivations directly inside a React component (like DomainsGrid computing nodes, topics, and links per domain) triggers an expensive O(N*M) execution on every re-render, creating CPU spikes even when underlying static data hasn't changed.
**Action:** When component properties are derived from static configurations, extract the calculation into a module-level constant instead of keeping it in the render loop or relying on useMemo.
