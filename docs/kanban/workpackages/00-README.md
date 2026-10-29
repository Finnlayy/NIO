# Hermes-Kanban: Arbeitspakete für externe Agenten

Jedes Paket `WP-xx-*.md` ist **in sich geschlossen**. Gib einem Agenten zuerst
diese Datei (Konventionen und Schnittstellen) und dann genau ein Paket.
Gesamtplan: `/home/finn-powers/.claude/plans/pasted-content-id-63cd-role-serialized-melody.md`
(oder die Kurzfassung unten).

Branch: `feat/hermes-kanban` (von `main`). **Nichts pushen**, keinen PR öffnen. Jedes
Paket endet mit einem lokalen Commit, deutsche Commit-Nachricht, z. B.
`Kanban WP-02: Bus, Locks, Heartbeats + Redis-RESP-Client`.

## Was schon fertig ist (WP-00, nicht anfassen außer wenn ein Paket es sagt)

| Datei | Inhalt |
|---|---|
| `orchestrator/kanban/models.py` | Dataclasses `KanbanBoard`, `KanbanTask`, `Worker`, `Experience`, `AuditEntry`, `KanbanEvent`, `ToolCall`, `RustLimb`, `RustLimbRequest/Response`; Enums `TaskStatus`, `WorkerStatus`; `ALLOWED_TRANSITIONS`, `check_transition()`, `new_id(prefix)`, `UID_PATTERN` |
| `orchestrator/kanban/config.py` | `KanbanConfig.from_env()`: alle `NIO_KANBAN_*`-Variablen, Defaults ohne Docker/Redis/PG |
| `orchestrator/kanban/audit.py` | `AuditDraft`, `AuditLedger`, `seal()`, `verify_chain()`, `redact()`, `GENESIS_HASH` |
| `orchestrator/kanban/store.py` | `KanbanStore`-Protocol (async) + `SqliteKanbanStore` (WAL, CAS via `UPDATE … RETURNING`, `finish_run` in einer Transaktion), `migration_scripts(dialect)` |
| `orchestrator/kanban/sql/001_kanban.sql` / `.sqlite.sql` | Schema PG/SQLite inkl. Append-only-Trigger auf `audit_ledger` |

Verifiziert: CAS gegen Doppelvergabe, Dekomposition + Roll-up, Abhängigkeits-
Promotion, Hash-Kette, `DELETE` auf das Ledger wird abgewiesen, Secret-Redaktion.

## Harte Konventionen (gelten für jedes Paket)

1. **Stdlib-only** in allem, was nicht explizit Adapter ist. Erlaubte Fremdpakete nur
   lazy importiert in: `store_pg.py` (`asyncpg`), `api.py` (`fastapi`, `pydantic`),
   `cli.py serve` (`uvicorn`). Kein `redis-py`: Redis spricht unser eigener RESP-Client.
2. Python 3.11+, jede Datei beginnt mit `from __future__ import annotations`, volle
   Type-Hints, `__all__`. Ruff-Konfiguration aus `pyproject.toml` (Zeilenlänge 140).
3. **Kommentare/Docstrings Deutsch, Identifier Englisch.** Kommentar-Dichte wie in
   `orchestrator/kanban/store.py`: Modul-Docstring erklärt *warum*, keine trivialen
   Zeilenkommentare.
4. Dateien schreiben **nur** über `core.atomic.atomic_write_bytes(path, data, fsync=True)`
   (Temp-Datei + `os.replace`). Ausnahme: `worker_entry.py` und `mcp_shim.py` müssen
   einzeln in einen Container gemountet werden können, also **keine** NIO-Imports, eigene
   10-Zeilen-Kopie der atomaren Schreibfunktion.
5. Subprozesse: argv-Listen, nie `shell=True`. Geheimnisse **nie** in argv, Logs, Events
   oder Audit-Payload (`audit.redact` hilft, ersetzt aber kein Nachdenken).
6. Niemals ändern: `neu.config.json`, `core/config.py`, `core/policy.py` (human-only).
   `orchestrator/cli.py` nur so weit wie WP-07 es beschreibt.
7. Tests: stdlib `unittest` unter `tests/test_kanban_<thema>.py`, offline, ohne Docker,
   Redis, Postgres oder Netz. Async-Code mit `asyncio.run(...)` in sync-Tests (siehe
   `tests/test_ciel_integration.py`). Temp-Verzeichnisse via `tempfile.TemporaryDirectory`.
8. **Abnahme jedes Pakets** (alle drei müssen grün sein):
   ```bash
   python3 -W error::ResourceWarning -m unittest discover -s tests -t . -q
   python3 -m ruff check orchestrator/kanban tests
   python3 -m mypy orchestrator/kanban
   ```
   (`mypy orchestrator` meldet einen **vorbestehenden** Fehler in `orchestrator/runner.py:2011`, den nicht anfassen.)

## Gemeinsame Schnittstellen (verbindlich, damit Pakete parallel laufen können)

Diese Signaturen sind der Vertrag zwischen den Paketen. Wer ein Paket umsetzt, das eine
dieser Schnittstellen **liefert**, implementiert sie exakt; wer sie **nutzt**, darf sich
darauf verlassen und für Tests eigene Fakes schreiben.

```python
# orchestrator/kanban/bus.py  (liefert WP-02)
class KanbanBus(Protocol):
    async def publish(self, event: KanbanEvent) -> None: ...
    def subscribe(self) -> AsyncIterator[KanbanEvent]: ...   # endlos, bis close()
    async def close(self) -> None: ...

class LockManager(Protocol):
    async def acquire(self, key: str, owner: str, ttl_s: float) -> bool: ...   # SET NX PX
    async def release(self, key: str, owner: str) -> bool: ...                 # nur wenn owner passt
    async def refresh(self, key: str, owner: str, ttl_s: float) -> bool: ...

class HeartbeatStore(Protocol):
    async def beat(self, task_id: str, ttl_s: float, *, worker_uid: str = "") -> None: ...
    async def alive(self, task_id: str) -> bool: ...
    async def clear(self, task_id: str) -> None: ...

class TokenStore(Protocol):                       # kurzlebige Task-Tokens fuer Sandbox-Tools
    async def put(self, token: str, claims: dict[str, str], ttl_s: float) -> None: ...
    async def get(self, token: str) -> dict[str, str] | None: ...   # claims: task_id, worker_uid
    async def revoke(self, token: str) -> None: ...
# Redis-Schluessel: kanban:lock:{key}, kanban:hb:{task_id}, kanban:token:{sha256(token)}, Kanal kanban:events

# orchestrator/kanban/sandbox.py  (liefert WP-04)
@dataclass(frozen=True)
class SandboxSpec:
    run_id: str                  # f"{task_id}-a{attempt}"
    task: KanbanTask
    worker: Worker
    run_dir: Path                # enthaelt in/ (ro), out/ (rw), work/ (rw)
    env: dict[str, str]          # nicht-geheime Variablen
    secrets: dict[str, str]      # Name -> Wert; nie in argv
    image: str
    deadline_s: float

@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None        # None = abgebrochen/Timeout
    timed_out: bool
    cancelled: bool
    out_dir: Path
    stderr_tail: str

class SandboxRunner(Protocol):
    async def run(self, spec: SandboxSpec, *, on_heartbeat: Callable[[], Awaitable[None]]) -> SandboxResult: ...
    async def cancel(self, run_id: str) -> None: ...

# Dateivertrag Sandbox <-> Host (WP-04 schreibt, WP-05 liest):
#   in/task.json      KanbanTask.to_dict()
#   in/SOUL.md        aktuelle Seele des Workers
#   in/history.md     bisheriges Lebensprotokoll
#   out/heartbeat     ISO-Zeitstempel, atomar alle heartbeat_s neu geschrieben
#   out/result.json   {"status": "completed"|"blocked"|"failed", "result_payload": {...}, "reason": str}
#   out/experience.json  {"summary": str, "lessons": [str], "skills_delta": [str], "outcome": str}
#   out/SOUL.md       aktualisierte Seele (optional; fehlt = unveraendert)

# orchestrator/kanban/sync.py  (liefert WP-05)
async def sync_back(*, store: KanbanStore, vault: ObsidianVault, workspace_dir: Path,
                    task: KanbanTask, worker: Worker, result: SandboxResult) -> RunOutcome: ...
@dataclass(frozen=True)
class RunOutcome:
    status: str                  # "completed" | "blocked" | "failed"
    reason: str
    result_payload: dict[str, Any] | None
    experience: Experience | None
    soul_md: str | None          # neue Seele oder None

# orchestrator/kanban/notify.py  (liefert WP-03)
class Notifier(Protocol):
    async def alert(self, text: str) -> bool: ...

# orchestrator/kanban/service.py  (liefert WP-06): eine Fassade fuer API, Tools, CLI
class KanbanService:
    def __init__(self, *, store, bus, ledger: AuditLedger, heartbeats, tokens, config: KanbanConfig) -> None
    async def create_board(self, name: str, *, actor: str) -> KanbanBoard
    async def create_task(self, *, board_id, title, description="", parent_id=None, dependencies=(),
                          required_skills=(), priority=0, status=TaskStatus.TRIAGE,
                          workspace_repo=None, actor: str) -> KanbanTask
    async def show(self, task_id: str) -> dict[str, Any]            # {"task": …, "children": […]}
    async def transition(self, task_id, target: TaskStatus, *, actor, reason="",
                         expected: TaskStatus | None = None, changes: Mapping[str, Any] | None = None) -> KanbanTask
    async def block(self, task_id, reason, *, actor) -> KanbanTask
    async def complete(self, task_id, result_payload, *, actor) -> KanbanTask
    async def heartbeat(self, task_id, *, worker_uid="") -> None
    async def create_worker(self, *, uid, name, skills, soul_md="", actor) -> Worker
    async def emit(self, kind: str, *, task: KanbanTask | None = None, worker_uid=None, payload=None) -> None
```

## Reihenfolge / Parallelität

```
WP-00 (fertig)
 ├─ WP-01 Postgres-Store            ┐
 ├─ WP-02 Bus/Locks/Redis-RESP      │  parallel möglich
 ├─ WP-04 Sandbox + worker_entry    │
 ├─ WP-05 SOUL.md + Vault + sync    │
 └─ WP-08 Verträge + Rust-Crate     ┘
WP-03 Dispatcher/Reaper/Breaker/Telegram  (nach WP-02, WP-04, WP-05)
WP-06 Service + kanban_*-Tools + MCP-Shim (nach WP-02; WP-03 nutzt den Service, also
       WP-06 vor oder zusammen mit WP-03, oder WP-03 schreibt gegen die Signatur oben)
WP-07 FastAPI + CLI + Runtime-Verdrahtung (nach WP-03, WP-06)
WP-09 Doku, CHANGELOG, pyproject, Makefile, Ende-zu-Ende-Abnahme (zuletzt)
```

Empfehlung für Kosten: WP-01, WP-02, WP-05, WP-08 und WP-09 sind mechanisch und
gut für günstige Modelle. WP-03, WP-04 und WP-06 enthalten die Nebenläufigkeits- und
Sicherheitslogik. Dort lohnt sich ein stärkeres Modell oder zumindest ein Review.
