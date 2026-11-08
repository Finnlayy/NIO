# Architektur & Grenzen — Projekt „Neu"

Stand 2026-09-04 · Protokoll **1.2** · beantwortet die Befunde 14 und 15 aus
[`REVIEW-2026-09-04.md`](REVIEW-2026-09-04.md): zwei Stapel in einem Repository,
ein mehrdeutiger Begriff.

---

## 1. Zwei Stapel, eine Grenze

In diesem Repository leben zwei Systeme nebeneinander. Sie teilen sich weder
Laufzeit noch Datenmodell — und das ist Absicht.

| | **Python-Kern „Neu"** | **TypeScript-Middleware (Legacy)** |
|---|---|---|
| Verzeichnisse | `core/`, `orchestrator/`, `limbs/`, `protocol/`, `prompts/`, `tests/`, `scripts/` | `src/`, `frontend/`, `agents/`, `evals/`, `data/`, `prompts/system/` |
| Laufzeit | Python 3.11+, **Standardbibliothek only** | Node 18+/22, npm-Pakete (Express, LangGraph, Pydantic-Rollen) |
| Aufgabe | Aufträge bauen, Uhr führen, Limbs starten und überwachen, Ergebnisse bewerten | HTTP-Eingang, Klassifikation, Telemetrie, UI |
| Vertrag | `neu/intent` → `neu/result` (Protokoll 1.2), dateibasierter Transport | Express-Handler `processTask`, `TelemetryEvent` |
| Zustand | `runtime/` (Queues, Jobs, Zeitpläne, Archiv, Locks) — nicht versioniert | `data/vectors/trace.json` — generiert |
| Tests | 186 Unittests (`make test`), echte Subprozesse und Timer | `pytest evals/tests`, `npm run typecheck` |
| CI | `ci/neu.yml` (aktivierbar mit `git mv` nach `.github/workflows/`, siehe `ci/README.md`) | `.github/workflows/ci-evals.yml` |

**Normative Grenze:** Alles, was ein Auftrag ist, wer ihn ausführt, wie lange er
dauert und was dabei herauskam, gehört zum Python-Kern und wird in Protokoll 1.2
ausgedrückt. Alles, was Eingang, Darstellung und Auswertung für Menschen ist,
gehört zur Middleware. Kein TypeScript-Code entscheidet über Timer, Rechte oder
Iterationen; kein Python-Code rendert UI.

### Andockpunkt für Phase 4

Die Middleware wird zum **Klienten** des Kerns, nicht zu seinem Ersatz:

```
Browser / API-Klient
        │ HTTP
        ▼
src/server.ts  (Middleware: Auth, Rate-Limit, Telemetrie)
        │ 1) Ziel als Job anlegen     ──▶ POST-Auftrag als neu/intent (1.2)
        │ 2) Zustand abfragen         ──▶ runtime/jobs/<job_id>.json / CLI --json
        │ 3) Ereignisse streamen      ──▶ NDJSON-Events (orchestrator/events.py)
        ▼
orchestrator (Python)  ──▶ limbs/*  ──▶ workspace/, runtime/
```

Drei Regeln für diese Anbindung:

1. **Transport bleibt Datei-first.** `runtime/inbox/<limb>/` ist der Vertrag;
   HTTP ist ein zusätzlicher *Kanal*, kein neuer Wahrheitsort. Ein Limb kennt
   weiterhin nur seinen Intent.
2. **Die Uhr bleibt im Kern.** Ein HTTP-Klient darf `deadline_s` oder
   `safety_net_s` *vorschlagen*; geschärft wird der Timer vom Orchestrator, und
   `t_unlimited` zählt ab Job-Erstellung — nicht ab HTTP-Eingang.
3. **Events sind die Schnittstelle für Fortschritt.** Jeder Event trägt
   `job_id`, `intent_id`, `trace_id`, `limb` und `clock_s` (= `t_unlimited`).
   Ein Stream für die UI liest dieselben Zeilen, die Phase 3 nach
   `runtime/system.log` schreibt.

---

## 2. Schichten innerhalb des Kerns

```
prompts/          Rollen-Spezifikationen (Text, keine Logik)
   ▲
orchestrator/     runner · scheduler · planner · events · locks · transport · cli
   ▲                     │  führt aus, überwacht, plant nach
limbs/            base · echo_limb · bootstrap_limb
   ▲                     │  liest Intent, liefert Result
core/             protocol · config · policy · job · kernel · schemacheck
                         │  Datenmodell, Rechte, Bewertung
protocol/         normative Spezifikation + JSON Schemas + Operations-Register
```

Importrichtung: `orchestrator → core`, `limbs → core`. Niemals umgekehrt; `core`
importiert keine NEU-Module. `limbs/*` wird als **Skript** gestartet (und ist
zusätzlich als Paket importierbar) — beide Wege führen über absolute Importe zum
selben `core`, sonst entstünde doppelte Klassenidentität.

### Datenhoheit

| Datum | Eigentümer | Ort |
|---|---|---|
| Auftrag (Intent) | Kernel/Orchestrator | `runtime/inbox/<limb>/`, `runtime/archive/…` |
| Ergebnis (Result) | Limb → Orchestrator | `runtime/archive/…`, `runtime/outbox/` |
| Job-Ledger (Iterationen, Maßnahmen, Uhr) | `core/job.py` | `runtime/jobs/<job_id>.json` + `.history.jsonl` |
| Zeitplan-Zustand (Trigger, Feuerungen) | `orchestrator/scheduler.py` | `runtime/schedules/<job_id>.json` |
| Agent-Slots | `orchestrator/locks.py` | `runtime/locks/agent-*.lock` |
| Ereignisse | `orchestrator/events.py` | stderr (NDJSON), Phase 3: `runtime/system.log` |
| Artefakte des Limbs | Limb | `workspace/` (Sandbox) |

Zwei Grenzen, die bewusst gezogen wurden:

* **Zeitpläne liegen nicht bei den Jobs.** `runtime/jobs/` globbed
  `job_*.json`; Trigger-Zustände dort würden die Job-Liste verfälschen.
* **Kontroll-Jobs sind Jobs, aber eigener Art.** `kind="scheduled"` mit
  `parent_job_id` und `trigger_id` — sichtbar in `job list`, aber mit eigenem
  Slot-Kontingent (`max_scheduled_jobs`) und ohne Verbrauch des
  Iterationsbudgets des beobachteten Auftrags.

---

## 3. Prozess- und Zeitmodell

```
Orchestrator-Prozess
 ├── spawn_async(limb)          Kindprozess, stdout = genau ein Result-JSON
 ├── _supervise: Tick-Schleife  alle tick_s (Default 0.5 s)
 │     ├── Slot-Frist + Job-Heartbeat erneuern   (keine Waisen-Eskalation)
 │     ├── scheduler.tick(state) → DueActions    (gegen t_unlimited)
 │     │     ├── emit_event / log       → Event bzw. Notiz
 │     │     ├── check                  → eigener Kontroll-Job (Subprozess)
 │     │     ├── escalate               → needs_human, Limb wird gestoppt
 │     │     └── finish_job             → planmäßiges Ende, Limb wird gestoppt
 │     └── collect_async()              Kind-Kanäle lesen und schließen
 └── Kernel.evaluate(result)    Verdict; planmäßige Stopps werden korrekt gewertet
```

Zeit ist in diesem System **zweierlei**, und die Unterscheidung ist normativ:

| | `mode="deadline"` | `mode="unlimited"` |
|---|---|---|
| Bedeutung | Budget, das aufgebraucht wird | Uhr, die mitläuft |
| Felder | `deadline_s`, `soft_deadline_s`, `expires_at` | `deadline_s=null`, `expires_at=null`, `t0`, `elapsed_s` |
| Ende | Limb meldet `timeout`, oder der Orchestrator killt | Trigger (`finish_job`/`escalate`), `max_ticks` oder Safety-Netz |
| `remaining_ms` | Zahl | `null` — kein Budget, also wird keines erfunden |
| Zweck | Arbeit begrenzen | Ereignisse in der Zeit auslösen und beobachten |

`safety_net_s` gehört zu **beiden** Modi und ist in beiden dasselbe: reine
Prozess-Hygiene (Zombie-Schutz). Sein Eingriff meldet `E_SAFETY_NET` und
eskaliert — er ist kein inhaltliches Scheitern und kein zweiter Durchgang.

---

## 4. Begriffstrennung: „schedule"

Befund 15: PR #1 (`arena/01a0666f-nio`) führt `schedules`, `tasks`, `skills`
für eine Lern-Engine ein; Protokoll 1.2 kennt `intent.schedule` für
zeitgesteuerte Auslöser. Beide Begriffe sind plausibel — zusammen sind sie
mehrdeutig.

**Gültig in diesem Repository:**

| Begriff | Bedeutung | Ort |
|---|---|---|
| `intent.schedule` / `schedule.triggers[]` | **Zeitgesteuerte Auslöser** dieses Protokolls: `when`, `every_s`, `at_s` + Aktion | `core/protocol.py`, `orchestrator/scheduler.py` |
| `runtime/schedules/` | persistierter Zustand genau dieser Auslöser | `orchestrator/scheduler.py` |
| `kind="scheduled"` | Kontroll-Job, den ein `check`-Trigger gestartet hat | `core/job.py` |

**Umbenennungsvorschlag für den anderen Zweig** (dortige Aufgabe ist
Aufgabenplanung, nicht Zeitsteuerung): `schedules` → `study_plans` oder
`curricula`, `tasks` → `exercises`, `skills` → `capabilities`. Sollte PR #1
 merge-ready werden, ist die Umbenennung dort billiger als hier — dieser Zweig
ist normativ über `protocol/*.schema.json` und 210 Tests abgesichert.

---

## 5. Entscheidungslog (warum es so ist, wie es ist)

| Entscheidung | Grund | Konsequenz |
|---|---|---|
| **Stdlib-only (Python 3.11+)** | Projektvorgabe; ein Limb muss überall laufen, auch ohne Netz | Kein `pip install` für Betrieb und CI; eigener JSON-Schema-Prüfer (`core/schemacheck.py`) statt `jsonschema` |
| **Dateitransport statt RPC** | Nachvollziehbarkeit: jeder Auftrag und jedes Ergebnis liegt als Datei im Archiv | Phase 4 ergänzt HTTP als Kanal, ersetzt aber nichts |
| **Zwei Ausführungspfade** (synchron / überwacht) | `subprocess.run(timeout=…)` blockiert — während eines unbegrenzten Laufs könnte kein Tick ausgewertet werden | `spawn_async`/`collect_async`/`_supervise`; Kind-Kanäle werden nach dem Ernten geschlossen (kein fd-Leck) |
| **Eine Uhr pro Auftrag** (`t0` = Job-Erstellung) | Intent, Result, Ledger und Events sollen dieselbe Zahl nennen | `bind_job_clock` vor dem ersten Event; Nachweis in `scripts/ci_e2e_unlimited.py` |
| **Kontroll-Jobs mit eigenem Kontingent** | Eine Beobachtung darf ihre eigenen Kontrollen nicht blockieren und kein Iterationsbudget fressen | `kind="scheduled"`, `max_scheduled_jobs`, `timer.skipped` statt stillem Wegfall |
| **Planmäßige Stopps werten** | Ohne Regel gälte jedes `finish_job` als korrekturbedürftig — die Uhr liefe erneut ab | Kernel: `finish_job` ⇒ accept (mit Warnung), `escalate` ⇒ reject + Eskalation |
| **Persistenz der Trigger-Zustände** | Neustart darf nichts doppelt auslösen | `runtime/schedules/<job_id>.json`; Re-attach erhält `t0` und Feuerungen |
| **Fail-fast bei Triggern** | Rechteausweitung über die Zeitachse wäre sonst erst zur Laufzeit sichtbar | `Policy._check_schedule()` → `E_TRIGGER_INVALID` vor dem Start |
| **Unittest statt pytest** | Keine Abhängigkeit, keine Konfiguration, überall lauffähig | `python3 -m unittest discover -s tests -t .`; CI braucht kein pip |
| **Lint/Typen als Dev-Extra** | Qualitätstor ohne Laufzeitkosten | `pyproject.toml` (`ruff`, `mypy`), `make check`, CI-Job `quality` |

Bewusst **nicht** getan: kein Wechsel auf 3.13-exklusive Syntax, kein
Asyncio-Rewrite des Transports, keine externen Dienste, kein Framework.

---

## 6. Wo Phase 3 andockt — und was ein Limb dort *nicht* darf

`orchestrator/events.py::build_event_bus()` enthält die Marke
`NEU-PHASE-3-ANCHOR`. Dort gehört ein File-Sink hin, der dieselben Events, die
heute als NDJSON auf stderr laufen, nach `runtime/system.log` schreibt —
erzeugt vom Bootstrap-Limb selbst (Ouroboros-Test).

Vorbereitet ist dafür bereits:

* Jeder Event trägt `job_id`, `intent_id`, `trace_id`, `limb` und `clock_s`.
* `VALID_EVENT_KINDS` ist die Whitelist; ein Test prüft, dass nur bekannte Arten
  emittiert werden (Event-Vertrag statt Dekoration).
* `config.system_log_path` zeigt auf `runtime/system.log`; `status --json`
  meldet, ob die Datei existiert (aktuell bewusst: nein).

**Entscheidend ist die Reihenfolge der Pfadprüfung** (`core/policy.py::resolve_path`):
`denied_globs` wird *vor* `allowed_repo_globs` und *vor* `human_only_globs`
geprüft und kennt keine Ausnahme — auch `approved_by="human"` hebt eine Sperre
nicht auf. `neu.config.json` sperrt `runtime/*` und `*.log`. Daraus folgt:

1. **Ein Limb kann `runtime/system.log` niemals selbst schreiben.** Der erste
   Ouroboros-Auftrag lautet deshalb nicht „schreibe das Log", sondern
   „ergänze `orchestrator/events.py` um einen Sink" — `orchestrator/*` ist
   freigegeben, nicht gesperrt und nicht menschenpflichtig, braucht aber
   `elevation.level="repo_write"` mit **deklarierten** Pfaden
   (`elevation.requested_paths`) und Backup.
2. **Der Sink schreibt als Orchestrator-Code**, nicht als Limb-Operation: Die
   Sandbox-Regeln gelten für Arme, nicht für den Körper.
3. **Das Log bleibt eine unabhängige Instanz.** Da kein Limb es ändern kann,
   kann ein Arm sein eigenes Protokoll nicht fälschen — genau die Eigenschaft,
   die Phase 3 als Beweis braucht (Selbstmodifikation anhand des Logs prüfen).

Wer diese Grenze verschieben will (z. B. `runtime/system.log` für Limbs
öffnen), ändert `neu.config.json` — und die ist `human_only`.

---

## 7. Dynamische FFI-Plugin-Architektur mit Hot-Reloading (Rust-Limbs)

Rust-Limbs werden nicht länger als statische Binärdateien oder Container
ausgeliefert, sondern als **Shared Libraries (`.so` unter Linux, gebaut als
Rust-`cdylib`)**. Der Python-Orchestrator ladet sie zur Laufzeit über `ctypes`
und tauscht sie atomar aus, wenn der Refinement-Vault (Ciel) eine geheilte
Version einer Limb freigibt — ohne Neustart des Hauptprozesses und ohne
Unterbruch des Shared-Memory-Ring-Buffers.

### 7.1 Vertrag (C-ABI)

Jede Limb-Bibliothek exportiert die stabile Schnittstelle
(`rust/nio-limb/src/lib.rs`, Contract-Version `1.0`):

| Symbol | Signatur | Aufgabe |
|--------|----------|---------|
| `limb_contract_version` | `() -> *const c_char` | Contract-Version; wird beim Laden geprüft |
| `init_limb` | `() -> c_int` | Einmalige Initialisierung (0 = Erfolg) |
| `process_payload` | `(data, data_len, out, out_cap, out_len) -> c_int` | High-Speed-Verarbeitung direkt auf dem Pointer |
| `shutdown_limb` | `(void)` | Ressourcen freigeben vor `dlclose` |

### 7.2 Laden und atomarer Hot-Swap (`orchestrator/kanban/limb_ffi.py`)

`LimbHotReloader` hält genau eine Version einer Limb im RAM:

* **Laden:** `ctypes.CDLL` öffnet die `.so`, Symbole werden aufgelöst,
  `limb_contract_version` mit dem Python-Kontrakt abgeglichen, dann
  `init_limb` aufgerufen.
* **`reload(neue_so)`:** Die neue Bibliothek wird **zuerst** geladen und
  initialisiert. Schlägt das fehl, läuft die alte Limb unverändert weiter
  (fail-fast). Erst dann wird die alte über `shutdown_limb` + `dlclose`
  entladen und der Funktionszeiger umgebogen.
* **`process_payload(data)`:** Übermittelt Bytes an die aktuell geladene Limb
  und liefert die Ausgabebytes zurück — kein Subprozess, kein Neustart.
* `process_intent_file()` ist die Bridge zum Protokoll-1.2-Intent (liest die
  Task-Parameter, ruft die Limb auf, liefert das Ergebnis als Dict).

### 7.3 Schreibsperre auf dem Ring während des Swaps

Während des Funktionszeiger-Wechsels hält der Dispatcher eine
Schreibsperre auf dem betroffenen Slot des Shared-Memory-Rings
(`SharedMemoryRingSink.write_lock()`, `orchestrator/ring.py`): kein Event
wird in den Ring geschrieben, während der Zeiger umgebogen wird. Nach
`dlclose` der alten und Aktivierung der neuen Bibliothek wird die Sperre
wieder aufgehoben — der Austausch ist unterbrechungsfrei (Null Downtime).

### 7.4 Build

```bash
cargo build --release --manifest-path rust/nio-limb/Cargo.toml
# -> rust/nio-limb/target/release/libnio_limb.so
```

Die fertige `.so` wird vom Refinement-Vault/Ciel-Pipeline angetragen und
im Hintergrund kompiliert; der Repository-Build selbst benötigt keinen
Rust-Toolchain (`make rust-limb` überspringt sauber ohne `cargo`).
Build-Artefakte (`rust/*/target/`) sind in `.gitignore` ausgenommen.


