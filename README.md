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
