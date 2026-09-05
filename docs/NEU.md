# Projekt „Neu" — Bootstrapping & rekursive Selbstentwicklung

Stand: **Phase 1 + Zeit-Schicht 1.2 + Phase 2 abgeschlossen** (Fundament,
Zeit-Tracking, erster echter Arm: Bootstrap-Limb), Protokoll **1.2**.

Dieses Dokument ist der Bauplan. Es beschreibt Rollen, Schichten, den
Phasenplan und die Operationsregeln des KI-Kerns. Die normative
Protokollspezifikation steht in [`protocol/PROTOCOL.md`](../protocol/PROTOCOL.md);
massgeblich bei Uneinigkeit ist die Referenzimplementierung `core/protocol.py`.
Grenzen zu den übrigen Repository-Teilen, Datenhoheit und Entscheidungslog:
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Bestandsaufnahme und Abnahme der
Protokoll-1.2-Arbeit: [`docs/REVIEW-2026-09-04.md`](REVIEW-2026-09-04.md).

---

## 1. Rollen

| Rolle | Umsetzung | Aufgabe |
|---|---|---|
| **KI-Kern (Core)** | LLM + `core/kernel.py` | Ziele analysieren, in Aufträge zerlegen, Spezifikationen schreiben, Ergebnisse bewerten. Delegiert Ausführung. |
| **Orchestrator** | `orchestrator/` | Technische Infrastruktur: Timer schärfen, Uhr führen, Zeitplan auswerten, Limb starten und überwachen, Nachrichtenfluss, Job-Lebenszyklus, Autodidaktik, Archiv. |
| **Limb** | `limbs/` | Ausführender Arm. Liest genau einen Intent, führt ihn strikt aus, liefert genau ein Result. |

Der **intelligente** Teil des Kerns ist das LLM. `core/kernel.py` enthält nur
die *deterministischen* Anteile (Auftrag bauen, Uhr schärfen, Ergebnis
bewerten), damit Entscheidungen nachvollziehbar und testbar bleiben.

---

## 2. Schichten und Importrichtung

```
┌────────────────────────────────────────────────────────────────────┐
│ prompts/          Rollen- und Limb-Spezifikationen (Text)          │
├────────────────────────────────────────────────────────────────────┤
│ orchestrator/     runner · scheduler · planner · events · locks    │
│                   transport · cli                                  │
├────────────────────────────────────────────────────────────────────┤
│ limbs/            base (Limb-Laufzeit) · echo_limb · bootstrap_limb │
│                   registry.json                                    │
├────────────────────────────────────────────────────────────────────┤
│ core/             protocol · config · policy · job · kernel        │
│                   schemacheck (JSON-Schema-Prüfer, Stdlib)         │
└────────────────────────────────────────────────────────────────────┘
        workspace/         runtime/              protocol/      scripts/
        Sandbox des Limbs  Queues, Jobs, Archiv, Spec, Schemas,  Nachweise
        (Artefakte)        Locks, Zeitpläne      Beispiele       (CI, lokal)
```

Importrichtung: `orchestrator → core`, `limbs → core`. Niemals umgekehrt.
`core` importiert keine NEU-Module.

Bestehende Repository-Teile bleiben unangetastet und andockbar: `src/`
(TypeScript-Middleware, Port 4000), `frontend/` (UI, Port 4001), `prompts/system/`,
`agents/`, `evals/`. Projekt „Neu" liefert den ausführenden Unterbau, den die
Middleware bisher nur simuliert (`DeterministicCoreAdapter`).

---

## 3. Ablauf eines Jobs

```
Ziel ──▶ Job anlegen (runtime/jobs/<job_id>.json)  →  t0 der Job-Uhr
      ──▶ Intent bauen (Kernel: Protokoll + Policy-Pre-Flight inkl. Trigger)
      ──▶ Durchgang i:
            Timer schärfen (mode, armed_at, t0; deadline-Variante:
                            soft_expires_at / expires_at)
            Agent-Slot belegen (max_agents)
            Intent in runtime/inbox/<limb>/ schreiben
            Limb starten — synchron oder überwacht (siehe unten)
            Result parsen/validieren — bei Crash/Timeout: synthetisieren
            Verdict fällen (accept | needs_correction | reject)
            Intent + Result + Verdict archivieren
      ──▶ accept?  ── ja ──▶ Job resolved
                └── nein ─▶ Diagnose (planner)
                              ├─ Maßnahme + Budget ──▶ Maßnahmen registrieren,
                              │                        Korrektur-Intent entwerfen,
                              │                        Durchgang i+1  (Autodidaktik)
                              ├─ Eskalation nötig ───▶ Job escalated
                              └─ keine Maßnahme ─────▶ Job failed (wirklich failed)
```

### Zwei Ausführungspfade

| Pfad | Wann | Mechanik |
|---|---|---|
| **synchron** (`dispatch`) | Auftrag ohne Uhr-Bedarf: kein Trigger, `mode=deadline` | starten, warten, ernten |
| **überwacht** (`spawn_async` → `_supervise` → `collect_async`) | `mode=unlimited` **oder** Trigger vorhanden (auch per `--supervise` erzwingbar) | Tick-Schleife: pro Tick Slot-Frist und Job-Heartbeat erneuern, Zeitplan auswerten, fällige Aktionen ausführen, Limb ernten |

Der überwachte Pfad blockiert nicht: `subprocess.run(timeout=…)` würde die
Tick-Schleife lahmlegen, deshalb wird asynchron gestartet und pro Tick geerntet.

### Zeitplan (Scheduler)

`orchestrator/scheduler.py` wertet `intent.schedule.triggers[]` gegen die
Job-Uhr aus und liefert pro Tick fällige Aktionen (`DueAction`). Sein Zustand
liegt **nicht** bei den Jobs, sondern in `runtime/schedules/<job_id>.json`
(`runtime/jobs/` bleibt eindeutig Job-Speicher). Ein Neustart hängt denselben
Zustand wieder an: `t0` und die Feuerungen bleiben erhalten, es wird nichts
doppelt ausgelöst.

Alles, was passiert, landet als Event im Event-Bus (`orchestrator/events.py`)
und als Datei unter `runtime/`. Jeder Event eines Auftrags trägt `clock_s`
(= `t_unlimited`), ab dem ersten Event nach der Job-Erstellung:

| Pfad | Inhalt |
|---|---|
| `runtime/inbox/<limb>/` | zugestellte Intents |
| `runtime/outbox/` | Results (optionaler Rückweg) |
| `runtime/archive/<datum>/<intent_id>/` | Intent, Result, Verdict je Durchgang |
| `runtime/jobs/<job_id>.json` + `.history.jsonl` | Job-Zustand und Historie |
| `runtime/schedules/<job_id>.json` | Zustand der zeitgesteuerten Auslöser |
| `runtime/backups/` | Rücksicherungen vor Schreiboperationen |
| `runtime/locks/agent-*.lock` | Agent-Slots (PID + TTL), getrennt nach `kind` |
| `runtime/system.log` | **Phase-3-Auftrag** — noch leer, bewusst |

Wichtige Event-Arten: `timer.armed`, `timer.tick`, `timer.trigger`,
`timer.finished`, `timer.skipped`, `timer.safety_net`, `job.scheduled`,
`schedule.attached`, `schedule.detached`, `loop.supervised`, `limb.terminated`.

---

## 4. Zeit: Timer, Tracking und Iterationen (Kernanforderungen)

### 4.1 Begrenzen (Modus `deadline`, seit 1.1)

1. **Timer vor Anbeginn.** Jeder Auftrag bekommt einen Timer, den der
   *Orchestrator* schärft, bevor der Limb startet. Der Limb kennt seine
   absolute Deadline.
2. **Statusbericht bei Ablauf.** Läuft der Timer ab, meldet der Limb selbst
   `status="timeout"` mit `status_report` (state, explanation, done, remaining,
   blockers, suggested_next). Bleibt er stumm, synthetisiert der Orchestrator
   denselben Bericht — ein Durchgang endet nie ohne klaren Stand.
3. **Zweiter Durchgang mit optimalem Prompt.** Ist der Timer abgelaufen und die
   Aufgabe nicht in einem Durchgang umsetzbar, entwirft der **Orchestrator**
   den nächsten Auftrag: verkleinerter Umfang, angepasster Timer,
   Fehlschlags-Briefing, Wiederholungsverbot.

### 4.2 Tracken statt begrenzen (Modus `unlimited`, neu in 1.2)

4. **Ohne `t_limit` wird Zeit aufgezeichnet, nicht begrenzt.** Wird kein
   `deadline_s` vorgegeben (CLI: `--unlimited`), gilt `timer.mode="unlimited"`,
   `deadline_s=null`, `expires_at=null`. `timer.t0` ist der Referenzpunkt
   (Job-Erstellung), `elapsed_s` die vergangene Zeit: **`t_unlimited`**.
   `remaining_ms` ist `null` — es gibt kein Budget, also wird keines erfunden.
5. **Eine Uhr pro Auftrag.** `t0` wird vor dem ersten Event auf den Job
   gebunden; Intent, Result, Statusbericht und jeder Event tragen dieselbe Uhr.
   Damit ist jeder Datensatz gegen den Auftragsbeginn einordenbar — die
   Voraussetzung für Korrelation in Phase 3.
6. **`t_unlimited` ist vergleichbar.** Kern und Orchestrator nutzen die Uhr für
   zeitgesteuerte Ereignisse („wenn `t_unlimited >= 30` → tue X") und für
   Intervall-Checks („prüfe alle N Sekunden X und Y"). Grammatik:
   `elapsed <op> <sekunden>` mit `==`, `!=`, `<`, `<=`, `>`, `>=`
   (Toleranz `tolerance_s` nur bei `==`/`!=`).
7. **Safety-Netz ist Hygiene, kein Aufgabenlimit.** `safety_net_s`
   (Default 3600 s) beendet Zombies. Ein Eingriff meldet `E_SAFETY_NET` und
   **eskaliert** — kein zweiter Durchgang, denn die Schwelle ist eine
   Menschenentscheidung (Auftrag zerlegen oder Netz bewusst anheben).

### 4.3 Zeitgesteuerte Auslöser (`intent.schedule.triggers[]`)

| Feld | Bedeutung |
|---|---|
| `when` | Bedingung, kantengesteuert: feuert einmal, wenn sie wahr wird (`null` = keine Bedingung) |
| `every_s` | Intervall; zusammen mit `when` erst ab Bedingungseintritt, mit Catch-up für verpasste Ticks |
| `at_s` | feste Zeitmarken seit `t0` (Liste) |
| `clock` | `job` (Default, `t_unlimited`) oder `wall` |
| `tolerance_s`, `max_fires`, `once` | Toleranz bei `==`/`!=`, Feuerungs-Limit, Einmaligkeit |
| `action` | `emit_event` \| `check` \| `escalate` \| `finish_job` \| `log` |

8. **`check` läuft auf eigener Spur.** Ein Kontroll-Job ist ein eigener Job mit
   `kind="scheduled"`, eigenem Slot-Kontingent (`max_scheduled_jobs`) und
   `max_iterations=1`. Er verbraucht **kein** Iterationsbudget des beobachteten
   Auftrags. Ist das Kontingent belegt (laufende Kontrollen **plus** im
   selben Tick gestartete), wird die Feuerung als `timer.skipped` dokumentiert
   — sie verschwindet nicht still.
9. **Planmäßige Stopps werden korrekt bewertet.** Beendet ein Trigger den Limb
   (`finish_job` / `escalate`), synthetisiert der Orchestrator ein ehrliches
   `status="partial"`-Result (`synthesized_by="orchestrator"`, `stop_reason`) —
   und der Kernel wertet: `finish_job` ⇒ **accept** (mit Warnung „durch Zeitplan
   gestoppt, nicht vom Limb selbst beendet"), `escalate` ⇒ **reject** +
   Eskalation. Ohne diese Regel gälte jede planmäßige Beendigung als
   korrekturbedürftig und die Uhr liefe erneut ab.

### 4.4 Iterationen und Scheitern

10. **Failed nur ohne Maßnahme.** Ein Job, nach dessen Versagen das System in
    den autodidaktischen Modus übergeht, ist *nicht* failed. Wirklich failed
    (`really_failed = true`) ist er nur bei `failure_kind = no_measure_available`.
11. **Maximal 2 Iterationen pro Job** (Redundanzvermeidung), gezählt pro Job und
    nicht pro Agentenaufruf. Kein stilles Retry.
12. **Profile.** `dev`: 1 Iteration, 1 Agent, 1 Limb, 1 paralleler Job,
    1 Kontroll-Job. `scale`: 2/4/4/2/4. Hochskalieren erst nach Bewährung — und
    nur mit menschlicher Freigabe
    (`orchestrator scale --profile scale --approved-by human`).

---

## 5. Sicherheit

* **Sandbox doppelt geprüft** — Pre-Flight im Orchestrator und erneut zur
  Laufzeit im Limb. `..`, absolute Pfade und Nullbytes fliegen raus.
* **Constitution Guard** — `neu.config.json`, `core/policy.py`,
  `core/config.py`, `.git/*`, `.github/*` sind nur mit `approved_by="human"`
  änderbar. Selbstmodifikation darf sich nicht selbst berechtigen.
* **Deklarationspflicht** — bei `repo_write` müssen alle Zielpfade in
  `elevation.requested_paths` stehen; nicht deklarierte Pfade werden abgelehnt.
* **Backup vor Schreibzugriff** auf bestehende Dateien (`runtime/backups/`).
* **Atomare Schreibvorgänge** (Temp-Datei + `os.replace`), Hash-Nachweise
  (`sha256`) in jedem Artefakt, vom Kern gegen die Platte geprüft.
* **Ausführung von Code ist deaktiviert** (`allow_shell_ops=false`,
  `allow_test_ops=false`) und doppelt gated (Konfiguration + Intent).
* **Zeitpläne sind Policy-pflichtig** — `Policy._check_schedule()` prüft jeden
  Trigger gegen Operations-Register, Rechte, Elevation und Sandbox, bevor der
  Auftrag gebaut wird (`E_TRIGGER_INVALID`). Ein `check`-Auslöser darf nichts,
  was der Auftrag selbst nicht dürfte; Selbst-Eskalation über Trigger ist
  ausgeschlossen. Warnungen (nicht Abbruch) gibt es bei `every_s` unter der
  Tick-Rate und bei mehr Auslösern als `max_scheduled_jobs`.
* **Ressourcen-Hygiene im Dauerbetrieb** — überwachte Läufe erneuern pro Tick
  Slot-Frist und Job-Heartbeat (keine Waisen-Eskalation), schließen die
  Kind-Kanäle nach dem Ernten (kein fd-Leck) und beenden den Limb geordnet
  (SIGTERM → Nachfrist → SIGKILL), wenn die Überwachung abbricht.

---

## 6. Phasenplan

### Phase 1 — Fundament & Basis-Orchestrierung ✅

* [x] Projektstruktur (`core/`, `orchestrator/`, `limbs/`, `prompts/`,
      `protocol/`, `workspace/`, `runtime/`, `tests/`, `docs/`)
* [x] Orchestrator mit I/O-Schnittstelle (CLI, Datei-Transport, Event-Bus)
* [x] Kommunikationsprotokoll inkl. Timer- und Iterationssemantik
* [x] Echo-Limb als Konformanz-Harness (`sys.ping/echo/noop/simulate`)
* [x] Job-Lebenszyklus, Autodidaktik-Planner, Agent-Slots, Policy/Sandbox
* [x] Meilenstein: Timer-Ablauf → Statusbericht → 2. Durchgang → `resolved`

### Zeit-Schicht 1.2 — Tracken statt begrenzen ✅

* [x] Protokoll 1.2: `timer.mode`, `t0`/`elapsed_s`, `safety_net_s`,
      `schedule.triggers[]`, `TimerReport` (nullable Budgets)
* [x] JSON Schemas auf 1.2 + Stdlib-Prüfer (`core/schemacheck.py`) mit
      Paritätstest gegen die Referenzimplementierung
* [x] Scheduler mit virtueller Uhr, Persistenz und Re-attach; Policy-Prüfung
      der Trigger; Kernel-Verdicts für planmäßige Stopps
* [x] Überwachter Ausführungspfad (async spawn/collect, Tick-Schleife,
      Kontroll-Jobs auf eigener Spur)
* [x] CLI: `--unlimited/--safety-net/--tick/--trigger/--max-ticks`, `watch`
      (live und `--job`), `schedule show/list/clear`, `validate --schema`,
      `--runtime-dir`, Exit-Code-Vertrag
* [x] Qualitätstor: `pyproject.toml`, ruff + mypy sauber, `Makefile`,
      CI-Workflow mit Matrix und End-to-End-Beweis
* [x] Meilenstein: unbegrenzter Auftrag mit Intervall-Kontrolle, der durch
      `finish_job` bei `t_unlimited ≈ 2,1 s` endet, obwohl der Limb 30 s
      gewartet hätte — 15 Nachweise in `scripts/ci_e2e_unlimited.py`

### Phase 2 — Limb-Integration (der erste Arm) ✅

* [x] `limbs/bootstrap_limb.py` gemäß [`prompts/limbs/bootstrap_limb.md`](../prompts/limbs/bootstrap_limb.md)
      (`fs.read_file`, `fs.write_file`, `fs.patch`, `fs.list`, `fs.mkdir`)
* [x] Register-Eintrag `bootstrap` von `planned` → `active` (`version=1.0.0`)
* [x] Meilenstein: Der Kern lässt über den Limb eine Datei in `workspace/`
      anlegen — mit Artefakt- und Hash-Nachweis im Result
      (`tests/test_bootstrap.py::TestMeilensteinOrchestrator`)

### Phase 3 — Ouroboros-Test (Selbstmodifikation)

* [ ] Der Bootstrap-Limb erweitert `orchestrator/events.py` um einen
      File-Sink, der alle Interaktionen nach `runtime/system.log` schreibt
      (Andockstelle: `NEU-PHASE-3-ANCHOR` in `build_event_bus()`)
* [ ] Prüfung anhand des Logs; bei Fehlern Korrekturdurchgang über denselben Job
* [ ] Danach: Backup- und Hash-Nachweis für Selbstmodifikation verifizieren
* [ ] Vorarbeit ist gelegt: Jeder Event trägt `clock_s`/`job_id`/`intent_id`,
      `runtime/system.log` ist als Ziel konfiguriert und unbeschrieben

### Phase 4 — Rekursive Erweiterung

* [ ] `test.run` / `shell.exec` im Limb (Gating freigeben, nur mit `--approved-by human`)
* [ ] Memory für den Kern (`core.memory_write`, Markdown-Log oder Vektorindex)
* [ ] Spezialisierte Limbs: `research` (Web), `debug` (Fehlersuche)
* [ ] Dauerbetrieb `orchestrator loop --watch`, HTTP-Anbindung an `src/server.ts`
* [ ] Profil `scale` schrittweise hochfahren

---

## 7. Operationsregeln für den KI-Kern

1. **Keine halluzinierten Ausführungen.** Ein Auftrag gilt erst als erledigt,
   wenn das echte Result des Limbs gelesen wurde — inkl. Artefakt-Hashes.
   `Verdict.decision == "accept"` ist nötig, nicht hinreichend: Die Artefakte
   sind zusätzlich zu lesen.
2. **Fail-Safe-Iteration.** Bei `failed`/`timeout`/`partial` ist die Aufgabe
   nicht beendet. Diagnose lesen, Korrekturauftrag entwerfen (oder den vom
   Orchestrator entworfenen prüfen und nachschärfen).
3. **Mikro-Schritte.** Niemals das ganze System neu schreiben lassen. Ein
   Durchgang = eine testbare Änderung (z. B. „Funktion X in Datei Y ersetzen").
4. **Budget respektieren.** Maximal 2 Durchgänge pro Job. Ist das Budget leer,
   wird ein neuer Job mit engerem Ziel aufgesetzt — nicht derselbe gestreckt.
5. **Zeit bewusst wählen.** Wer ein Limit will, nennt `deadline_s`. Wer keins
   nennt, bekommt Tracking — und **muss** sagen, woran der Auftrag endet:
   `finish_job`-Schwelle, `escalate`-Bedingung oder `max_ticks`. Ein
   unbegrenzter Auftrag ohne Auslöser endet nur am Safety-Netz, und das ist
   eine Eskalation, kein Ergebnis.
6. **Kontrollen statt Blindflug.** Für „prüfe alle N Sekunden X" einen
   `check`-Trigger mit `every_s` setzen und die Kontroll-Jobs lesen
   (`job list`/`job show`, `kind="scheduled"`); sie sind über `trigger_id` und
   `parent_job_id` rückverfolgbar.
7. **Eskalieren statt tricksen.** Verweigert die Policy (Constitution Guard,
   Profilgrenzen, Trigger-Rechte), geht der Auftrag an den Menschen. Rechte
   werden niemals umgangen.
8. **Im Charakter bleiben.** Der Kern wartet auf Input, analysiert, delegiert
   und bewertet — er tippt nicht selbst.

---

## 8. Bedienung

Globale Flags (`--repo-root`, `--runtime-dir`, `--mode`, `--json`, `--quiet`)
stehen **vor** dem Subkommando. `--json` liefert maschinenlesbare Ausgabe auf
stdout, Events laufen als JSON-Zeilen auf stderr — stdout bleibt pipe-fähig.

Exit-Codes: `0` Erfolg · `1` Protokoll-/Validierungsfehler · `2` Job nicht
aufgelöst (failed/escalated) · `3` Nutzungsfehler. „Nichts gefunden" ist kein
Nutzungsfehler und endet mit `0` plus Befund.

```bash
# Selbstauskunft: Protokoll, Operationen, Timer- und Zeitplan-Semantik
python3 -m orchestrator spec

# Zustand: Profil, Limits, Pfade, Queues, Jobs, Limbs, Agent-Slots, Zeitpläne
python3 -m orchestrator status

# Klassisch: Auftrag mit Deadline (Dev-Profil: genau ein Durchgang)
python3 -m orchestrator job run --goal "Roundtrip beweisen" \
  --op sys.echo --param message="Hallo Kern"

# Phase 2: Datei in der Sandbox anlegen (Bootstrap-Limb)
python3 -m orchestrator job run --goal "Der Kern laesst eine Datei anlegen" \
  --limb bootstrap --op fs.write_file \
  --params '{"path":"hallo.txt","content":"Phase 2","mode":"create"}' \
  --deadline 15 --soft-deadline 10

python3 -m orchestrator job run --goal "Langlauf" --op sys.simulate \
  --params '{"mode":"timeout","seconds":30}' --deadline 2 --soft-deadline 1

# 1.2: Zeit tracken statt begrenzen, mit Intervall-Kontrolle und Ende per Trigger
python3 -m orchestrator watch \
  --goal "Zeit beobachten" --op sys.simulate \
  --params '{"mode":"timeout","seconds":60}' \
  --unlimited --tick 0.5 \
  --trigger 'id=kontrolle;action=check;every=2;op=sys.ping' \
  --trigger 'id=schwelle;action=emit_event;when=elapsed >= 5;kind=timer.threshold' \
  --trigger 'id=ende;action=finish_job;when=elapsed >= 10'

# Nur den Scheduler eines bestehenden Auftrags ticken (Limb läuft woanders)
python3 -m orchestrator watch --job <job_id> --tick 0.5 --for 30

# Zeitpläne einsehen und aufräumen
python3 -m orchestrator schedule list
python3 -m orchestrator schedule show <job_id>
python3 -m orchestrator schedule clear <job_id>

# Gegen die normativen Schemas prüfen (Stdlib-Prüfer, kein jsonschema nötig)
python3 -m orchestrator validate --intent <datei.json> --schema --json

# Isoliert arbeiten, ohne das Repo-runtime/ zu berühren
python3 -m orchestrator --runtime-dir /tmp/neu-lauf status --json

# Job-Historie inkl. Statusberichten
python3 -m orchestrator job show <job_id>
python3 -m orchestrator job list
```

### Trigger-Minisprache (`--trigger`)

Drei Schreibweisen, mehrfach angegeben, in Reihenfolge ausgewertet:

```
id=kontrolle;action=check;every=10;op=sys.ping;params={"message":"Status?"}
id=ende;action=finish_job;when=elapsed >= 120
{"id":"marke","action":"log","at_s":[5,15,30],"payload":{"message":"Zwischenstand"}}
@trigger.json                                  # Datei (Objekt oder Liste)
```

Schlüssel: `id`, `action`, `when`, `every` (= `every_s`), `at` (= `at_s`,
Kommaliste), `clock`, `tolerance`, `max-fires`, `once`; für die Aktion `op`,
`params`, `checks`, `limb`, `goal`, `title`, `kind`, `message`.

---

## 9. Qualitätstor

Laufzeit: **Python 3.11+, Standardbibliothek only** — keine Installation, kein
`pip install`, keine Lockfiles. Entwicklungswerkzeuge (ruff, mypy) sind optional:
`python3 -m pip install -e '.[dev]'`.

```bash
make check        # dasselbe Tor wie CI: compile · lint · types · test · e2e
make test         # 210 Tests (unittest, echte Subprozesse und echte Timer)
make lint         # ruff (Konfiguration in pyproject.toml)
make types        # mypy über core/, orchestrator/, limbs/
make e2e          # End-to-End-Beweis für Protokoll 1.2
make demo         # Live-Demo: unbegrenzter Auftrag mit Kontrollen und finish_job
```

CI: [`ci/neu.yml`](../ci/neu.yml) — Aktivierung per `git mv` nach `.github/workflows/` (siehe [`ci/README.md`](../ci/README.md); die anbindende GitHub-App darf keine Workflows anlegen). Test-Matrix
über Python 3.11/3.12/3.13 (`PYTHONWARNINGS=error::ResourceWarning`, damit ein
fd-Leck im Dauerbetrieb kein stiller Fehler ist), ein Lint-/Typen-Job und ein
End-to-End-Job, der die echte CLI fährt und den Exit-Code-Vertrag prüft.
(`ci-evals.yml` prüft weiterhin das Legacy-Harness unter `evals/`.)

### Test-Inventar (210)

| Modul | Anzahl | Was bewiesen wird |
|---|---|---|
| `tests/test_protocol.py` | 26 | Envelopes, strikte Validierung, Timer, Abwärtskompatibilität 1.1 → 1.2 |
| `tests/test_policy.py` | 22 | Sandbox, Elevation, Constitution Guard, Trigger-Policy, Phase-3-Grenze |
| `tests/test_orchestrator.py` | 24 | End-to-End mit echten Limbs: Roundtrip, Timeout, Autodidaktik, Job-Store |
| `tests/test_planner.py` | 9 | Diagnose, Maßnahmen, Budget, Korrektur-Intent |
| `tests/test_schema_parity.py` | 32 | JSON Schemas ≡ Referenzimplementierung (Stdlib-Prüfer) |
| `tests/test_schedule.py` | 33 | Scheduler-Semantik mit virtueller Uhr, Persistenz/Re-attach, CLI-Zeitplan |
| `tests/test_unlimited.py` | 19 | `t_unlimited`, Trigger während der Limb läuft, Safety-Netz, Budget-Trennung |
| `tests/test_limbs.py` | 9 | Beide Aufrufwege, Versions-/Register-Drift, Limb-Uhr, Bootstrap-Register |
| `tests/test_bootstrap.py` | 18 | Phase 2: fs.*, Sandbox, Backup, Patch, Hash, Meilenstein über den Orchestrator |
| `tests/test_cli_contract.py` | 18 | Einstiegspunkt, Exit-Codes, `--json`-Kanäle, `--runtime-dir`-Isolation |

`scripts/ci_e2e_unlimited.py` ergänzt die Suite um den Nachweis am lebenden
System: 15 Prüfungen über die echte CLI, darunter `deadline_s/expires_at/
remaining_ms = null`, `t_unlimited` an der Triggerschwelle (nicht an der
Wartezeit des Limbs), rückverfolgbare Kontroll-Jobs und aufgeräumter Zeitplan.
