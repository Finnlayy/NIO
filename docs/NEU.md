# Projekt „Neu" — Bootstrapping & rekursive Selbstentwicklung

Stand: **Phase 1 abgeschlossen** (Fundament & Basis-Orchestrierung), Protokoll **1.1**.

Dieses Dokument ist der Bauplan. Es beschreibt Rollen, Schichten, den
Phasenplan und die Operationsregeln des KI-Kerns. Die normative
Protokollspezifikation steht in [`protocol/PROTOCOL.md`](../protocol/PROTOCOL.md).

---

## 1. Rollen

| Rolle | Umsetzung | Aufgabe |
|---|---|---|
| **KI-Kern (Core)** | LLM + `core/kernel.py` | Ziele analysieren, in Aufträge zerlegen, Spezifikationen schreiben, Ergebnisse bewerten. Delegiert Ausführung. |
| **Orchestrator** | `orchestrator/` | Technische Infrastruktur: Timer schärfen, Limb starten, Nachrichtenfluss, Job-Lebenszyklus, Autodidaktik, Archiv. |
| **Limb** | `limbs/` | Ausführender Arm. Liest genau einen Intent, führt ihn strikt aus, liefert genau ein Result. |

Der **intelligente** Teil des Kerns ist das LLM. `core/kernel.py` enthält nur
die *deterministischen* Anteile (Auftrag bauen, Ergebnis bewerten), damit
Entscheidungen nachvollziehbar und testbar bleiben.

---

## 2. Schichten und Importrichtung

```
┌──────────────────────────────────────────────────────────────┐
│ prompts/          Rollen- und Limb-Spezifikationen (Text)    │
├──────────────────────────────────────────────────────────────┤
│ orchestrator/     runner · planner · events · locks          │
│                   transport · cli                            │
├──────────────────────────────────────────────────────────────┤
│ limbs/            base (Limb-Laufzeit) · echo_limb           │
│                   registry.json                              │
├──────────────────────────────────────────────────────────────┤
│ core/             protocol · config · policy · job · kernel  │
└──────────────────────────────────────────────────────────────┘
             workspace/          runtime/           protocol/
             Sandbox des Limbs   Queues, Jobs,      Spec, Schemas,
             (Artefakte)         Archiv, Locks      echte Beispiele
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
Ziel ──▶ Job anlegen (runtime/jobs/<job_id>.json)
      ──▶ Intent bauen (Kernel: Protokoll + Policy-Pre-Flight)
      ──▶ Durchgang i:
            Timer schärfen (armed_at / soft_expires_at / expires_at)
            Agent-Slot belegen (max_agents)
            Intent in runtime/inbox/<limb>/ schreiben
            Limb als Subprozess starten (Timeout = deadline_s + grace_s)
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

Alles, was passiert, landet als Event im Event-Bus
(`orchestrator/events.py`) und als Datei unter `runtime/`:

| Pfad | Inhalt |
|---|---|
| `runtime/inbox/<limb>/` | zugestellte Intents |
| `runtime/outbox/` | Results (optionaler Rückweg) |
| `runtime/archive/<datum>/<intent_id>/` | Intent, Result, Verdict je Durchgang |
| `runtime/jobs/<job_id>.json` + `.history.jsonl` | Job-Zustand und Historie |
| `runtime/backups/` | Rücksicherungen vor Schreiboperationen |
| `runtime/locks/agent-*.lock` | Agent-Slots (PID + TTL) |
| `runtime/system.log` | **Phase-3-Auftrag** — noch leer, bewusst |

---

## 4. Timer und Iterationen (Kernanforderungen)

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
4. **Failed nur ohne Maßnahme.** Ein Job, nach dessen Versagen das System in den
   autodidaktischen Modus übergeht, ist *nicht* failed. Wirklich failed
   (`really_failed = true`) ist er nur bei `failure_kind = no_measure_available`.
5. **Maximal 2 Iterationen pro Job** (Redundanzvermeidung), gezählt pro Job und
   nicht pro Agentenaufruf. Kein stilles Retry.
6. **Dev-Modus aktuell:** 1 Iteration, 1 Agent, 1 Limb, 1 paralleler Job.
   Hochskalieren erst nach Bewährung — und nur mit menschlicher Freigabe
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
* **Ausführung von Code ist in Phase 1 deaktiviert** (`allow_shell_ops=false`,
  `allow_test_ops=false`) und doppelt gated (Konfiguration + Intent).

---

## 6. Phasenplan

### Phase 1 — Fundament & Basis-Orchestrierung ✅

* [x] Projektstruktur (`core/`, `orchestrator/`, `limbs/`, `prompts/`,
      `protocol/`, `workspace/`, `runtime/`, `tests/`, `docs/`)
* [x] Orchestrator mit I/O-Schnittstelle (CLI, Datei-Transport, Event-Bus)
* [x] Kommunikationsprotokoll 1.1 inkl. Timer- und Iterationssemantik
* [x] Echo-Limb als Konformanz-Harness (`sys.ping/echo/noop/simulate`)
* [x] Job-Lebenszyklus, Autodidaktik-Planner, Agent-Slots, Policy/Sandbox
* [x] 73 Tests (`python3 -m unittest discover -s tests`), echte Subprozesse
* [x] Meilenstein: Timer-Ablauf → Statusbericht → 2. Durchgang → `resolved`

### Phase 2 — Limb-Integration (der erste Arm) ⏭

* [ ] `limbs/bootstrap_limb.py` gemäß [`prompts/limbs/bootstrap_limb.md`](../prompts/limbs/bootstrap_limb.md)
      (`fs.read_file`, `fs.write_file`, `fs.patch`, `fs.list`, `fs.mkdir`)
* [ ] Register-Eintrag `bootstrap` von `planned` → `active`
* [ ] Meilenstein: Der Kern lässt über den Limb eine Datei in `workspace/`
      anlegen — mit Artefakt- und Hash-Nachweis im Result

### Phase 3 — Ouroboros-Test (Selbstmodifikation)

* [ ] Der Bootstrap-Limb erweitert `orchestrator/events.py` um einen
      File-Sink, der alle Interaktionen nach `runtime/system.log` schreibt
      (Andockstelle: `NEU-PHASE-3-ANCHOR` in `build_event_bus()`)
* [ ] Prüfung anhand des Logs; bei Fehlern Korrekturdurchgang über denselben Job
* [ ] Danach: Backup- und Hash-Nachweis für Selbstmodifikation verifizieren

### Phase 4 — Rekursive Erweiterung

* [ ] `test.run` / `shell.exec` im Limb (Gating freigeben, nur mit `--approved-by human`)
* [ ] Memory für den Kern (`core.memory_write`, Markdown-Log oder Vektorindex)
* [ ] Spezialisierte Limbs: `research` (Web), `debug` (Fehlersuche)
* [ ] Dauerbetrieb `orchestrator loop --watch`, HTTP-Anbindung an `src/server.ts`
* [ ] Profil `scale` (2 Iterationen, 4 Agenten, 4 Limbs) schrittweise hochfahren

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
5. **Eskalieren statt tricksen.** Verweigert die Policy (Constitution Guard,
   Profilgrenzen), geht der Auftrag an den Menschen. Rechte werden niemals
   umgangen.
6. **Im Charakter bleiben.** Der Kern wartet auf Input, analysiert, delegiert
   und bewertet — er tippt nicht selbst.

---

## 8. Bedienung

```bash
# Protokoll, Operationen, Timer- und Iterationssemantik anzeigen
python3 -m orchestrator spec

# Zustand: Profil, Limits, Queues, Jobs, Limbs, Agent-Slots
python3 -m orchestrator status

# Job ausführen (Dev-Modus: genau ein Durchgang)
python3 -m orchestrator job run --goal "Roundtrip beweisen" \
  --op sys.echo --param message="Hallo Kern"

# Timer-Ablauf + Statusbericht erzwingen
python3 -m orchestrator job run --goal "Langlauf" --op sys.simulate \
  --params '{"mode":"timeout","seconds":30}' --deadline 2 --soft-deadline 1

# Autodidaktischen 2. Durchgang erlauben (nur für diesen Aufruf)
python3 -m orchestrator --mode scale job run --goal "…" --op sys.simulate \
  --params '{"mode":"timeout","seconds":1.5}' --max-iterations 2 \
  --deadline 2 --soft-deadline 1

# Job-Historie inkl. Statusberichten
python3 -m orchestrator job show <job_id>
python3 -m orchestrator job list

# Intent erzeugen / validieren / einzeln zustellen
python3 -m orchestrator intent --op sys.ping --limb echo --print
python3 -m orchestrator validate --intent protocol/examples/intent.sys_echo.json
python3 -m orchestrator dispatch --intent runtime/inbox/echo/<id>.json

# Testsuite (Stdlib, keine Installation nötig)
python3 -m unittest discover -s tests -v
```

Globale Flags (`--repo-root`, `--mode`, `--json`, `--quiet`) stehen **vor** dem
Subkommando. `--json` liefert maschinenlesbare Ausgabe auf stdout, Events
laufen als JSON-Zeilen auf stderr.
