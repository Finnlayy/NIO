# WP-07: FastAPI-Schicht, `neu kanban`-CLI, Runtime-Verdrahtung

Lies zuerst `00-README.md`. Voraussetzung: WP-02, WP-03, WP-04, WP-05 und WP-06 sind gemergt.

## `orchestrator/kanban/runtime.py`
- `@dataclass KanbanRuntime` mit `config`, `store`, `bus`, `locks`, `heartbeats`,
  `tokens`, `ledger`, `service`, `toolbox`, `dispatcher`, `reaper`, `vault`, `notifier`
  und `sandbox`.
- `async build_runtime(config, *, neu_events=None) -> KanbanRuntime` wählt die Backends
  nach `config.store`, `config.bus` und `config.sandbox`:
  - Postgres: `store_pg` lazy importieren.
  - Redis: `redis_resp`.
  - Dazu `store.init()` und ggf. `NeuEventBridge`.
- `async close()` schließt alles in umgekehrter Reihenfolge.
- `async serve(stop: asyncio.Event)` startet Dispatcher und Reaper als Tasks; nach `stop`
  werden sie sauber gecancelt.

## `orchestrator/kanban/api.py` (FastAPI, lazy)
- `build_app(runtime) -> FastAPI` mit `APIRouter(prefix="/api/v1")`.
- Pydantic-v2-Modelle mit `model_config = ConfigDict(extra="forbid")`. **Die Felder sind
  1:1 die der Dataclasses in `models.py`**: `TaskOut`, `WorkerOut`, `ExperienceOut`,
  `AuditEntryOut`, `BoardOut`, `RustLimbIn`, `RustLimbRequestIn`, `RustLimbResponseOut`
  und `ToolCallIn`. Dazu Eingabemodelle `BoardCreate`, `TaskCreate`, `TransitionIn`
  (`target`, `reason`, `expected?`), `WorkerCreate` und `SpawnIn` (`task_id`).
- Auth:
  - Operator-Routen verlangen `Authorization: Bearer {config.api_token}`, Vergleich mit
    `hmac.compare_digest`. Ist der Token leer, gibt jede Operator-Route 503
    "NIO_KANBAN_API_TOKEN not set" zurück.
  - Tool-Routen nehmen den Task-Token und prüfen ihn über die Toolbox.

| Methode + Pfad | Auth | Wirkung |
|---|---|---|
| `GET/POST /kanban/boards` | Operator | Boards auflisten/anlegen |
| `GET /kanban/tasks?board_id&status&parent_id` | Operator | Liste |
| `POST /kanban/tasks` | Operator | `service.create_task` |
| `GET /kanban/tasks/{id}` | Operator | `service.show` |
| `POST /kanban/tasks/{id}/transition` | Operator | `service.transition` (409 bei `ConflictError`, 422 bei `TransitionError`) |
| `GET /kanban/tools` | keine | `TOOL_DEFINITIONS` |
| `POST /kanban/tools/{name}` | Task-Token | `toolbox.call` (401/403/404/422) |
| `GET/POST /workers`, `GET /workers/{uid}` | Operator | Worker |
| `POST /workers/{uid}/spawn` | Operator | `dispatcher.assign_specific(task_id, uid)`; diese Methode in WP-03 ergänzen, falls sie fehlt: dieselbe Lock-/CAS-Logik wie `tick()`, nur für ein Paar |
| `GET /workers/{uid}/experiences` | Operator | Liste |
| `GET /audit?after_seq&limit`, `GET /audit/verify` | Operator | Ledger lesen bzw. prüfen |
| `GET/POST /rust-limbs`, `POST /rust-limbs/{name}/invoke` | Operator | Registry in `runtime/kanban/rust_limbs.json` (atomar), Invoke: `POST {endpoint}/invoke` mit `RustLimbRequest`-JSON, Antwort als `RustLimbResponse` validiert, Audit `category="code"` |

## `orchestrator/kanban/cli.py` + Einhängen in `orchestrator/cli.py`
- `add_kanban_parser(sub, parser_class)` registriert `kanban` mit Unterbefehlen:
  - `init`
  - `board create NAME` / `board list`
  - `task create --board --title [--description|--description-file] [--parent] [--dep …] [--skill …] [--priority] [--repo]`
  - `task list [--board --status]` / `task show ID` / `task transition ID STATUS [--reason]`
  - `worker create UID [--name] [--skill …] [--soul-file]` / `worker list`
  - `tick [--wait]`: ein Dispatcher-Tick plus ein Reaper-Tick
  - `serve [--host --port] [--no-api]`: Dispatcher und Reaper; die API nur, wenn
    `fastapi`/`uvicorn` importierbar sind. Sonst Hinweis und nur die Schleifen.
  - `audit verify` / `audit tail [-n]`
- Jeder Befehl `func(args) -> int` läuft mit `asyncio.run`, die Ausgabe ist bei `--json`
  (globales Flag aus `orchestrator/cli.py`) JSON, sonst kurzer Text.
- **In `orchestrator/cli.py` nur zwei Zeilen**: den Import und `add_kanban_parser(sub, _NeuArgumentParser)`
  in `build_parser()` vor `return parser`. Sonst nichts ändern.

## Tests: `tests/test_kanban_api.py`, `tests/test_kanban_cli.py`
- API: `@skipUnless(fastapi importierbar)`, `fastapi.testclient.TestClient`, Runtime
  mit SQLite in einem Temp-Verzeichnis und `SubprocessSandbox`.
  - Ohne Token 401, mit Token CRUD.
  - Ein Transition-Konflikt ergibt 409.
  - Ein Tool-Aufruf mit falschem Task-Token ergibt 401/403.
  - **Feldparität**: Für jedes `*Out`-Modell gilt
    `set(Model.model_fields) == set(Dataclass.__dataclass_fields__)`.
- CLI: Subprozess `python3 -m orchestrator --json kanban …` mit `NEU_ROOT` und
  `NIO_KANBAN_*` auf ein Temp-Verzeichnis. Ablauf: `init`, `worker create alpha --skill code`,
  `board create demo`, `task create` mit einer Checkliste aus zwei Punkten, `tick --wait`
  dreimal. Erwartet: alle Tasks `completed` und `audit verify` ok.
- `tests/test_cli_contract.py` muss weiter grün sein.

## Fertig, wenn
Die Abnahme ist grün.
