# Hermes-Kanban

Hermes-Kanban ist ein verteiltes Task-Management-System, das auf Agenten und einem auditierbaren Ledger basiert.
Das System ist in drei Ebenen unterteilt:

## Architektur

```text
+-------------------------------------------------+
| Layer 1: Apollo / Telegram / Obsidian Vault     |
| (Interfaces & Persistence für Menschen)         |
+-------------------------------------------------+
                         |
+-------------------------------------------------+
| Layer 2: Dispatcher / Reaper / Bus / Store      |
| (Kern-Logik, Zustand, Zuweisung, Events)        |
+-------------------------------------------------+
                         |
+-------------------------------------------------+
| Layer 3: Docker-Sandbox / Rust-Limbs            |
| (Sichere, isolierte Ausführung)                 |
+-------------------------------------------------+
```

## Zustandsmaschine (TaskStatus)

Der Zustand eines Tasks folgt einer strengen Maschine.

| Aktuell | Erlaubte Folgezustände |
|---|---|
| `triage` | `backlog`, `blocked` |
| `backlog` | `ready`, `blocked`, `completed` |
| `ready` | `in_progress`, `backlog`, `blocked` |
| `in_progress` | `completed`, `blocked`, `ready` |
| `blocked` | `triage`, `backlog`, `ready` |
| `completed` | (keine) |

*(Quelle: `ALLOWED_TRANSITIONS` in `orchestrator/kanban/models.py`)*

## Konfiguration (Umgebungsvariablen)

Das System wird ausschließlich über `NIO_KANBAN_*` Umgebungsvariablen konfiguriert (additiv und ohne externe Abhängigkeiten lauffähig).

| Variable | Bedeutung | Default |
|---|---|---|
| `NIO_KANBAN_STORE` | Backend-Typ (sqlite / postgres) | `sqlite` |
| `NIO_KANBAN_SQLITE_PATH` | Pfad zur SQLite DB | `runtime/kanban/kanban.db` |
| `NIO_KANBAN_PG_DSN` | DSN für Postgres | `""` |
| `NIO_KANBAN_BUS` | Event-Bus (memory / redis) | `memory` |
| `NIO_KANBAN_REDIS_URL` | Redis URL | `redis://127.0.0.1:6379/0` |
| `NIO_KANBAN_SANDBOX` | Sandbox-Typ (subprocess / docker) | `subprocess` |
| `NIO_KANBAN_IMAGE` | Docker Image für JIT-Worker | `python:3.12-slim` |
| `NIO_KANBAN_CPUS` | CPU-Limit für Sandbox | `1.0` |
| `NIO_KANBAN_MEMORY` | Speicher-Limit für Sandbox | `512m` |
| `NIO_KANBAN_PIDS` | PIDs-Limit für Sandbox | `256` |
| `NIO_KANBAN_NETWORK` | Netzwerkmodus für Sandbox | `none` |
| `NIO_KANBAN_DOCKER_BIN` | Pfad zur Docker Binary | `docker` |
| `NIO_KANBAN_TICK_S` | Scheduler Tick | `2.0` |
| `NIO_KANBAN_HEARTBEAT_S` | Worker Heartbeat Intervall | `5.0` |
| `NIO_KANBAN_HEARTBEAT_TTL_S`| Worker Heartbeat TTL | `20.0` |
| `NIO_KANBAN_REAPER_GRACE_S` | Zeit bis Reaper aufräumt | `30.0` |
| `NIO_KANBAN_TASK_DEADLINE_S`| Maximaldauer eines Tasks | `900.0` |
| `NIO_KANBAN_STOP_GRACE_S` | Grace-Period für Worker Stop | `10.0` |
| `NIO_KANBAN_MAX_CONCURRENT` | Max parallele Worker | `1` |
| `NIO_KANBAN_BREAKER_THRESHOLD`| Failures vor Circuit Break | `3` |
| `NIO_KANBAN_BREAKER_COOLDOWN_S`| Cooldown nach Break | `600.0` |
| `NIO_KANBAN_WORKSPACE` | Workspace Verzeichnis | `workspace/kanban` |
| `NIO_OBSIDIAN_VAULT` | Obsidian Vault Verzeichnis | `workspace/obsidian` |
| `NIO_KANBAN_SECRET_ALLOWLIST`| Erlaubte Secrets | `""` |
| `NIO_KANBAN_API_TOKEN` | Bearer Token für API | `""` |
| `NIO_KANBAN_API_HOST` | Host für FastAPI | `127.0.0.1` |
| `NIO_KANBAN_API_PORT` | Port für FastAPI | `8740` |
| `NIO_KANBAN_SANDBOX_API_URL`| API URL (von innen erreichbar) | `http://host.docker.internal:8740` |
| `TELEGRAM_BOT_TOKEN` | Token für Telegram-Bot | `""` |
| `TELEGRAM_CHAT_ID` | Chat-ID für Alerts | `""` |

*(Defaults stammen aus `orchestrator/kanban/config.py`)*

## Backends wählen

- **Datenbank:** `NIO_KANBAN_STORE=sqlite` oder `postgres`. Bei `postgres` wird `NIO_KANBAN_PG_DSN` benötigt. (Erfordert das Extra `kanban` mit `asyncpg`).
- **Bus:** `NIO_KANBAN_BUS=memory` für lokale Single-Process Tests, `redis` für verteiltes Setup.
- **Sandbox:** `NIO_KANBAN_SANDBOX=subprocess` für lokale Ausführung oder `docker` für vollständige Isolation.

## Sicherheitsmodell

- **Task-Token-Scopes:** Jede Sandbox erhält ein dediziertes, kurzlebiges Token, das nur für spezifische Tool-Aufrufe (über `/api/v1/kanban/tools/{name}`) gültig ist.
- **Secret-Injektion:** Secrets werden nicht in Shell-Argumenten (`argv`) übergeben.
- **Container-Härtung:** Docker-Sandboxes haben strenge CPU-, Memory- und PID-Limits und verwenden standardmäßig kein Netzwerk (`network=none`), außer es wird explizit autorisiert.
- **Audit-Ledger:** Jede wichtige Aktion wird append-only im Hash-Ketten-Ledger dokumentiert. Die Datenbank schützt die Tabelle durch Append-Only-Trigger.
- **Prinzip:** "Kein Push/PR durch Worker" - Der Agent meldet den Erfolg oder Patch zurück, commited aber nicht selbst in den Haupt-Branch.

## SOUL.md und Vault

Die "Seele" eines Workers (System Prompt und Anweisungen) liegt in `SOUL.md`. Jede Ausführung eines Tasks erzeugt "Experiences" (Erfahrungsberichte), die als Markdown-Dateien im Obsidian Vault synchronisiert werden:
`workspace/obsidian/workers/{worker_uid}/experiences/{experience_id}.md`

## API-Routen

Präfix: `/api/v1`
Authentifizierung: Bearer-Token aus `NIO_KANBAN_API_TOKEN`. Ohne Token antwortet die API mit `503 Service Unavailable`. Tool-Routen (`/api/v1/kanban/tools/{name}`) akzeptieren nur kurzlebige Task-Tokens.

- `GET /kanban/boards`
- `POST /kanban/boards`
- `GET /kanban/tasks`
- `POST /kanban/tasks`
- `GET /kanban/tasks/{task_id}`
- `POST /kanban/tasks/{task_id}/transition`
- `GET /kanban/tools`
- `POST /kanban/tools/{name}` (nimmt Task-Token)
- `GET /workers`
- `POST /workers`
- `GET /workers/{uid}`
- `POST /workers/{uid}/spawn`
- `GET /workers/{uid}/experiences`
- `GET /audit`
- `GET /audit/verify`
- `GET /rust-limbs`
- `POST /rust-limbs`
- `POST /rust-limbs/{name}/invoke`

## CLI-Befehle

Der Einstieg ist `python3 -m orchestrator [--json] kanban`:
- `kanban init`: Store anlegen / Schema migrieren.
- `kanban board create <name>`: Neues Board erstellen.
- `kanban board list`: Boards auflisten.
- `kanban task create --board <id> --title <title> [--description <desc> | --description-file <file>] [--parent <id>] [--dep <id>] [--skill <skill>] [--priority <prio>] [--status <status>] [--repo <repo>]`: Task erstellen.
- `kanban task list [--board <id>] [--status <status>]`: Tasks auflisten.
- `kanban task show <id>`: Details eines Tasks anzeigen.
- `kanban task transition <id> <status> [--reason <reason>]`: Zustand ändern.
- `kanban worker create <uid> [--name <name>] [--skill <skill>] [--soul-file <file>]`: Worker anlegen.
- `kanban worker list`: Worker auflisten.
- `kanban tick [--wait]`: Führt Dispatcher und Reaper manuell aus (mit `--wait` wartet er auf gestartete Worker).
- `kanban serve [--host <host>] [--port <port>] [--no-api]`: Startet die Dauerüberwachung, standardmäßig inkl. API.
- `kanban audit verify`: Prüft die Integrität der Hash-Kette.
- `kanban audit tail [-n <int>]`: Gibt die letzten N Audit-Einträge aus.

## Betriebsrezepte

- **Crash-Recovery:** Falls Worker abstürzen, erkennt der `Reaper` das nach Ablauf der `reaper_grace_s` (und Heartbeat TTL) und setzt den Task auf den vorherigen Zustand oder blockiert ihn zurück.
- **Breaker zurücksetzen:** Ein Circuit Breaker blockiert Worker/Tasks bei zu vielen Fehlern. Rücksetzen über die CLI: `python3 -m orchestrator kanban task transition <ID> ready`.
- **Audit:** Regelmäßig mit `python3 -m orchestrator kanban audit verify` die Hash-Kette prüfen, um unbemerkte Manipulationen auszuschließen.
