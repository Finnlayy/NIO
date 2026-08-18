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

## Start (NIO + Cody Telegram)

One command starts both the neural orchestrator API and the Cody Telegram poller:

```bash
cd nio/backend
npm start
```

This runs:

- **NIO API** on `http://0.0.0.0:4000` (override with `PORT` / `HOST`)
- **Cody Telegram daemon** (`python telegram_notify.py serve`) spawned as a child process **after** the HTTP server is listening

Cody is enabled by default when `TELEGRAM_BOT_TOKEN` is set in the workspace `.env`. Set `CODY_ENABLED=false` to run NIO only. Set `CODY_ENABLED=true` to force-enable even without a token (the poller will warn and exit if credentials are missing).

| Variable | Default | Purpose |
|----------|---------|---------|
| `CODY_ENABLED` | `true` when `TELEGRAM_BOT_TOKEN` is set | Enable/disable Cody child process |
| `CODY_PYTHON` | `python` | Python executable for `telegram_notify.py` |
| `WORKSPACE_ROOT` | `../../` from `nio/backend` | Root containing `telegram_notify.py` and `.env` |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token (required for Cody) |
| `TELEGRAM_CHAT_ID` | — | Allowed chat ID (required for Cody) |
| `TELEGRAM_NOTIFICATIONS_ENABLED` | `true` when Cody starts | Must be true for `serve` mode |
| `NIO_API_URL` | `http://localhost:4000` | Cody → NIO task endpoint |

Stop both processes with `Ctrl+C` (SIGINT) or `SIGTERM`; the server shuts down Cody gracefully before exiting.

For debugging Cody alone:

```bash
python D:\General\telegram_notify.py serve
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

## Literaturhinweis

Die im Telemetrie-Interface hinterlegten Genauigkeitsbenchmarks beziehen sich auf die Studie *Mind Your Tone: Investigating How Prompt Politeness Affects LLM Accuracy* (Dobariya & Kumar, 2025). Darin erreichten sehr direkte Prompts 84.8% Genauigkeit gegenüber 80.8% bei sehr höflichen Prompts — ein Gewinn von +4.0 Prozentpunkten [1](https://fortune.com/article/being-mean-to-chatgpt-boosts-accuracy-scientist-warn-of-consequences/) [2](https://arxiv.org/html/2512.12812v1).
