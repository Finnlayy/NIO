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
├── evals/tests/                      # Pytest-Integrationssuite
├── src/                              # TypeScript-Middleware
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
ein KI-Kern, der Ziele in Aufträge zerlegt, ein Orchestrator, der Timer schärft
und Limbs steuert, sowie Limbs, die als Werkzeuge wirklich Dateien ändern.
Protokoll **1.1** (`neu/intent` → `neu/result`), dateibasierter Transport,
keine externen Abhängigkeiten.

```
core/           Protokoll 1.1, Konfiguration, Policy/Sandbox, Job-Lebenszyklus, Kernel
orchestrator/   Runner, Autodidaktik-Planner, Event-Bus, Agent-Slots, Transport, CLI
limbs/          Limb-Laufzeit (Timer-Aufsicht) + Echo-Limb als Konformanz-Harness
protocol/       normative Spezifikation, JSON Schemas, Operations-Register, echte Beispiele
prompts/        Rollen-Spezifikationen für Core und Limbs
workspace/      Sandbox für Limb-Artefakte
runtime/        Queues, Jobs, Archiv, Backups, Locks (nicht versioniert)
tests/          73 Unittests mit echten Subprozessen und echten Timern
docs/NEU.md     Bauplan, Phasen, Operationsregeln
```

Kernmechanik: **jeder Auftrag bekommt vor Anbeginn einen Timer**. Läuft er ab,
liefert der Limb einen klaren Statusbericht (`done` / `remaining` / `blockers`),
und der Orchestrator entwirft den **zweiten Durchgang** selbst — verkleinerter
Umfang, angepasster Timer, Fehlschlags-Briefing, Wiederholungsverbot.
Iterationen zählen pro **Job** (Maximum 2); ein Job ist erst dann wirklich
gescheitert, wenn nach dem Versagen **keine Maßnahme** mehr möglich ist.
Aktuell läuft das System im Dev-Profil: 1 Iteration, 1 Agent, 1 Limb, 1 Job.

```bash
python3 -m orchestrator spec              # Protokoll, Operationen, Timer-Semantik
python3 -m orchestrator status            # Profil, Limits, Queues, Jobs, Limbs

python3 -m orchestrator job run --goal "Roundtrip beweisen" \
  --op sys.echo --param message="Hallo Kern"

python3 -m orchestrator job run --goal "Langlauf" --op sys.simulate \
  --params '{"mode":"timeout","seconds":30}' --deadline 2 --soft-deadline 1

python3 -m orchestrator job show <job_id>  # Historie inkl. Statusberichten
python3 -m unittest discover -s tests -v   # Testsuite (keine Installation nötig)
```

Details: [`docs/NEU.md`](docs/NEU.md) · [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md)

## Literaturhinweis

Die im Telemetrie-Interface hinterlegten Genauigkeitsbenchmarks beziehen sich auf die Studie *Mind Your Tone: Investigating How Prompt Politeness Affects LLM Accuracy* (Dobariya & Kumar, 2025). Darin erreichten sehr direkte Prompts 84.8% Genauigkeit gegenüber 80.8% bei sehr höflichen Prompts — ein Gewinn von +4.0 Prozentpunkten [1](https://fortune.com/article/being-mean-to-chatgpt-boosts-accuracy-scientist-warn-of-consequences/) [2](https://arxiv.org/html/2512.12812v1).
