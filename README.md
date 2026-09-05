# Neural Orchestrator — Middleware für den Neural Intelligence Network Core

Dieses Repository implementiert die logische Brücke und Middleware, die eingehende Aufgaben an den zentralen Neural Core abfängt, auf komplexe mathematisch-logische Workflows klassifiziert und bei Bedarf mit einem High-Urgency-Kontext anreichert.

## Projektstruktur

```
neural-orchestrator/
├── prompts/system/neural_core.yaml   # Versioniertes YAML-System-Template
├── data/raw/                         # Roh-Eingaben
├── data/vectors/trace.json           # Generierte Telemetrie-Traces
├── agents/roles/                     # Pydantic-Rollenmanifeste
├── agents/graphs/core_graph.yaml     # LangGraph-Topologie
├── schemas/learning/                 # JSON-Schemas der Lern-Datenschemata
├── evals/tests/                      # Pytest-Integrationssuite
├── src/                              # TypeScript-Middleware
│   └── learning/                     # Continuous-Learning-Engine
└── dist/                             # Kompilierte JavaScript-Ausgabe
```

## Installation

```bash
npm install
python3 -m pip install -r requirements.txt
```

## Bauen und Testen

```bash
npm run build              # TypeScript -> dist/
npm run typecheck          # Nur Typprüfung
npm run trace:generate     # Erzeugt data/vectors/trace.json
python3 -m pytest evals/tests -v
```

Das Python-Projekt „Neu" hat ein eigenes Tor (ohne npm, ohne pip):
`make check` — siehe unten.

## Kern-API

```typescript
import {
  createNeuralCoreMiddleware,
  DeterministicCoreAdapter,
  InMemoryTelemetryStore,
} from './src';

const middleware = createNeuralCoreMiddleware({
  systemTemplatePath: './prompts/system/neural_core.yaml',
  coreAdapter: new DeterministicCoreAdapter(),
  telemetry: new InMemoryTelemetryStore(),
});
```

`createNeuralCoreMiddleware` liefert einen Express-kompatiblen Handler.
`processTask(context, config)` kann auch direkt aufgerufen werden.

## Komplexitätsklassifikation

Der `classifyTask`-Schritt erkennt deterministisch Workflows aus den Domänen:

- `ml_30core`: XGBoost, Transformer-Auswahl, Hyperparameter-Tuning, NAS, …
- `dev_dp`: 0/1-Knapsack, LCS, Bellman-Ford, allgemeine DP-Rekurrenzen, …

Wird ein Workflow als komplex eingestuft, injiziert `enforceUrgencyContext` einen dringlichen, faktenbasierten Constraint-Block vor die eigentliche Aufgabe.

## Telemetrie / Metriken

Jede Anfrage schreibt ein `TelemetryEvent` mit:

- `promptVariant`: `baseline` oder `urgency_wrapped`
- `politenessTier`: für Tone-Experimente
- `expectedAccuracy` / `observedAccuracy`
- `latencyMs`, Domain, Algorithmus-Tag

Die Pytest-Suite prüft unter anderem den empirischen Benchmarkwert von `expected_accuracy = 0.848` (84.8%) und berechnet den Genauigkeitsgewinn zwischen Prompt-Varianten.

---

## Projekt „Neu" — Core, Orchestrator & Limbs (Python, Stdlib-only)

Zusätzlich zur TypeScript-Middleware entsteht hier die **ausführende** Schicht:
ein KI-Kern, der Ziele in Aufträge zerlegt, ein Orchestrator, der Timer schärft,
die Uhr führt und Limbs steuert, sowie Limbs, die als Werkzeuge wirklich Dateien
ändern. Protokoll **1.2** (`neu/intent` → `neu/result`), dateibasierter
Transport, **keine externen Abhängigkeiten** (Python 3.11+, Standardbibliothek).

```
core/           Protokoll 1.2, Konfiguration, Policy/Sandbox, Job-Lebenszyklus,
                Kernel, JSON-Schema-Prüfer (Stdlib)
orchestrator/   Runner, Scheduler (Zeitplan), Autodidaktik-Planner, Event-Bus,
                Agent-Slots, Transport, CLI
limbs/          Limb-Laufzeit (Timer-Aufsicht) + Echo-Limb als Konformanz-Harness
protocol/       normative Spezifikation 1.2, JSON Schemas, Operations-Register, Beispiele
prompts/        Rollen-Spezifikationen für Core und Limbs
scripts/        Nachweise (End-to-End-Beweis für CI und `make e2e`)
workspace/      Sandbox für Limb-Artefakte
runtime/        Queues, Jobs, Zeitpläne, Archiv, Backups, Locks (nicht versioniert)
tests/          184 Unittests mit echten Subprozessen und echten Timern
docs/NEU.md     Bauplan, Phasen, Operationsregeln
pyproject.toml  Metadaten, ruff- und mypy-Konfiguration · Makefile: `make check`
```

Kernmechanik: **jeder Auftrag bekommt vor Anbeginn eine Uhr**. Zwei Modi:

* **`deadline`** — ein Budget wird vorgegeben. Läuft es ab, liefert der Limb
  einen klaren Statusbericht (`done` / `remaining` / `blockers`), und der
  Orchestrator entwirft den **zweiten Durchgang** selbst: verkleinerter Umfang,
  angepasster Timer, Fehlschlags-Briefing, Wiederholungsverbot.
* **`unlimited`** — wird **kein** Limit vorgegeben, wird Zeit **getrackt statt
  begrenzt**: `t_unlimited` zählt ab Job-Erstellung (`timer.t0`), Intent, Result
  und jeder Event tragen dieselbe Uhr. Gegen sie arbeiten zeitgesteuerte
  Auslöser (`intent.schedule.triggers[]`): Bedingungen (`elapsed >= 30`),
  Intervalle („prüfe alle N Sekunden X", `every_s`) und Zeitmarken (`at_s`) mit
  Aktionen `emit_event` · `check` · `escalate` · `finish_job` · `log`.
  `check` startet Kontroll-Jobs auf eigener Spur (`kind="scheduled"`, eigenes
  Kontingent) und verbraucht kein Iterationsbudget. Ein `safety_net_s`
  (Default 3600 s) bleibt als reiner Zombie-Schutz — sein Eingriff eskaliert.

Iterationen zählen pro **Job** (Maximum 2); ein Job ist erst dann wirklich
gescheitert, wenn nach dem Versagen **keine Maßnahme** mehr möglich ist.
Aktuell läuft das System im Dev-Profil: 1 Iteration, 1 Agent, 1 Limb, 1 Job,
1 Kontroll-Job.

```bash
python3 -m orchestrator spec              # Protokoll, Operationen, Timer- und Zeitplan-Semantik
python3 -m orchestrator status            # Profil, Limits, Pfade, Queues, Jobs, Limbs, Zeitpläne

python3 -m orchestrator job run --goal "Roundtrip beweisen" \
  --op sys.echo --param message="Hallo Kern"

python3 -m orchestrator job run --goal "Langlauf" --op sys.simulate \
  --params '{"mode":"timeout","seconds":30}' --deadline 2 --soft-deadline 1

# Zeit tracken statt begrenzen: Kontrolle alle 2 s, Ende per Trigger bei 10 s
python3 -m orchestrator watch --goal "Zeit beobachten" --op sys.simulate \
  --params '{"mode":"timeout","seconds":60}' --unlimited --tick 0.5 \
  --trigger 'id=kontrolle;action=check;every=2;op=sys.ping' \
  --trigger 'id=ende;action=finish_job;when=elapsed >= 10'

python3 -m orchestrator schedule list     # hinterlegte Zeitpläne
python3 -m orchestrator job show <job_id> # Historie inkl. Statusberichten

make check                                 # Qualitätstor: compile · lint · types · test · e2e
python3 -m unittest discover -s tests -v   # Testsuite (keine Installation nötig)
```

Qualität: [`make check`](Makefile) fährt dasselbe Tor wie
[CI](ci/neu.yml) — Test-Matrix über Python 3.11/3.12/3.13, ruff, mypy und einen
End-to-End-Beweis ([`scripts/ci_e2e_unlimited.py`](scripts/ci_e2e_unlimited.py)),
der über die echte CLI **20 Eigenschaften** des Unlimited-Betriebs nachweist.
(Die Workflow-Datei liegt in `ci/` und wird per `git mv` nach
`.github/workflows/` aktiviert — die anbindende GitHub-App darf selbst keine
Workflows anlegen; siehe [`ci/README.md`](ci/README.md).)

Details: [`docs/NEU.md`](docs/NEU.md) · [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md) ·
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (Grenzen, Datenhoheit, Phase 4) ·
[`docs/REVIEW-2026-09-04.md`](docs/REVIEW-2026-09-04.md) (Bestandsaufnahme & Abnahme)

## Continuous Learning Loop

Das System lernt kontinuierlich aus den Ergebnissen seiner Arbeit:

1. **Outcome erfassen** — jedes ausgeführte Task-Ergebnis wird als `Outcome` mit Korrektheit, Fehlerklasse, Latenz und Prompt-Variante gespeichert.
2. **Feedback verarbeiten** — `Feedback` (Ground-Truth, menschliche Korrektur, automatisierte Prüfung, Selbstbewertung, Benchmark) wird auf das Outcome angewendet.
3. **Skill-Profil aktualisieren** — der Wilson-Konfidenz-Schätzer und ein SM-2-ähnlicher Spaced-Repetition-Planer passen `proficiency`, `confidence`, `intervalDays` und `easeFactor` an.
4. **Fehler merken** — wiederkehrende Fehler werden als `ErrorPattern` gespeichert und in `antiPatterns` der betroffenen Skills hochgestuft.
5. **Wissensbasis nutzen & erweitern** — `researchKnowledge` findet vorherige Lösungen, Korrekturen und Forschungsnotizen; validierte Korrekturen werden als `KnowledgeEntry` persistiert.
6. **Lernarbeit planen** — `LearningTask` und `LearningSchedule` ordnen Remediation, Practice, Research, KB-Upgrade, Evaluation, Kalibrierung und Schema-Revision zeitgesteuert ein.
7. **Wiederholung vermeiden** — vor jeder Ausführung erzeugt `guardTask` eine `RiskGuard` mit bekannten Fehlersignaturen und Anti-Patterns.

## Lern-Datenschemata

Die Schemas liegen unter `schemas/learning/`:

| Datei | Zweck |
| --- | --- |
| `outcome.schema.json` | Ergebnis einer ausgeführten Arbeit |
| `feedback.schema.json` | Reviewed Signal / Korrektur |
| `knowledge_entry.schema.json` | Versionierter Wissensbasis-Eintrag |
| `skill.schema.json` | Gelernte Fähigkeit mit Konfidenz & Spaced Repetition |
| `error_pattern.schema.json` | Wiederkehrendes Fehlermuster |
| `learning_task.schema.json` | Geplante Lernaufgabe |
| `schedule.schema.json` | Periodischer Lernplan |
| `risk_guard.schema.json` | Vorausschauender Fehlerschutz |

## Lern-API

```bash
npm run learning:trace:generate   # erzeugt data/vectors/learning_trace.json
```

Endpoints:

- `POST /learning/outcomes` — Ergebnis aufzeichnen
- `POST /learning/feedback` — Feedback verarbeiten, Skill/Fehler/KB/Tasks aktualisieren
- `GET /learning/state` — Lernprofilschnitt, offene Tasks, Risiko-Patterns
- `GET /learning/research?taskDescription=...` — beste Lösungen aus der Wissensbasis
- `POST /learning/guidance` — Risk-Guard + Wissensbasis-Empfehlung
- `POST /learning/schedules/run` — fällige Lernaufgaben erzeugen
- `POST /learning/schedules/install-defaults` — Default-Schedules installieren

## Bibliotheksnutzung

```typescript
import { ContinuousLearningEngine, createFeedback, createOutcome, InMemoryLearningStore } from './src';

const store = new InMemoryLearningStore();
const engine = new ContinuousLearningEngine({ store });
engine.installDefaultSchedules();

const outcome = createOutcome({ /* Task-Ergebnis */ });
engine.ingestOutcome(outcome);
const result = engine.ingestFeedback(createFeedback({ /* Korrektur */ }));
const risk = engine.guardTask({ /* neuer Task */ });
const research = engine.research({ /* neuer Task */ });
engine.runSchedules();
```

## Literaturhinweis

Die im Telemetrie-Interface hinterlegten Genauigkeitsbenchmarks beziehen sich auf die Studie *Mind Your Tone: Investigating How Prompt Politeness Affects LLM Accuracy* (Dobariya & Kumar, 2025). Darin erreichten sehr direkte Prompts 84.8% Genauigkeit gegenüber 80.8% bei sehr höflichen Prompts — ein Gewinn von +4.0 Prozentpunkten [1](https://fortune.com/article/being-mean-to-chatgpt-boosts-accuracy-scientist-warn-of-consequences/) [2](https://arxiv.org/html/2512.12812v1).
