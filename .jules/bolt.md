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
