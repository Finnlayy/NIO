"""Persistenz des Hermes-Kanban: ``KanbanStore``-Protokoll und SQLite-Standard.

Die Garantie gegen Doppelvergabe liegt **hier**, nicht in den Redis-Locks: jeder
Statuswechsel ist ein Compare-and-Swap (``UPDATE … WHERE id=? AND status=?
RETURNING *``). Zwei Dispatcher, die denselben ``ready``-Task greifen, bekommen
genau einmal eine Zeile zurueck. Locks sparen nur die vergebliche Arbeit davor.

SQLite laeuft im WAL-Modus mit ``BEGIN IMMEDIATE`` -- mehrere Prozesse (``neu
kanban tick`` neben ``neu kanban serve``) duerfen dieselbe Datei teilen. Die
synchronen Aufrufe laufen per ``asyncio.to_thread`` und blockieren den Loop nie.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any, Protocol, TypeVar

from core.protocol import utc_now_iso

from .audit import GENESIS_HASH, AuditDraft, seal
from .models import AuditEntry, Experience, KanbanBoard, KanbanTask, TaskStatus, Worker, WorkerStatus

__all__ = [
    "TASK_MUTABLE",
    "WORKER_MUTABLE",
    "KanbanStore",
    "SqliteKanbanStore",
    "migration_scripts",
]

_T = TypeVar("_T")

#: Felder, die ``cas_task``/``update_task`` aendern duerfen. Die Schluessel landen im
#: SQL -- deshalb eine feste Liste statt beliebiger ``**kwargs``.
TASK_MUTABLE = frozenset(
    {
        "title",
        "description",
        "status",
        "priority",
        "assigned_worker_uid",
        "parent_id",
        "dependencies",
        "required_skills",
        "is_rollup",
        "attempts",
        "result_payload",
        "block_reason",
        "workspace_repo",
        "started_at",
    }
)
WORKER_MUTABLE = frozenset({"name", "skills", "soul_md", "status", "fail_count", "breaker_open_until"})

_TASK_JSON = frozenset({"dependencies", "required_skills", "result_payload"})
_WORKER_JSON = frozenset({"skills"})
_EXPERIENCE_JSON = frozenset({"lessons", "skills_delta"})


def migration_scripts(dialect: str) -> list[tuple[int, str]]:
    """``[(version, sql), ...]`` aus ``orchestrator/kanban/sql`` fuer ``sqlite``/``postgres``."""
    folder = resources.files(__package__).joinpath("sql")
    out: list[tuple[int, str]] = []
    for entry in folder.iterdir():
        name = entry.name
        if not name.endswith(".sql"):
            continue
        is_sqlite = name.endswith(".sqlite.sql")
        if (dialect == "sqlite") != is_sqlite:
            continue
        out.append((int(name.split("_", 1)[0]), entry.read_text(encoding="utf-8")))
    return sorted(out)


def _check_keys(changes: Mapping[str, Any], allowed: frozenset[str]) -> None:
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"nicht aenderbare Felder: {sorted(unknown)}")


def _plain(value: Any) -> Any:
    """Enums -> Werte, damit Treiber und JSON nur Grundtypen sehen."""
    if isinstance(value, (TaskStatus, WorkerStatus)):
        return value.value
    return value


class KanbanStore(Protocol):
    """Gemeinsame Schnittstelle von SQLite- und Postgres-Store (alles async)."""

    async def init(self) -> None: ...
    async def close(self) -> None: ...

    async def create_board(self, board: KanbanBoard) -> KanbanBoard: ...
    async def get_board(self, board_id: str) -> KanbanBoard | None: ...
    async def list_boards(self) -> list[KanbanBoard]: ...

    async def create_task(self, task: KanbanTask) -> KanbanTask: ...
    async def get_task(self, task_id: str) -> KanbanTask | None: ...
    async def list_tasks(
        self,
        *,
        board_id: str | None = None,
        status: TaskStatus | None = None,
        parent_id: str | None = None,
        limit: int = 500,
    ) -> list[KanbanTask]: ...
    async def cas_task(self, task_id: str, expected: TaskStatus | None, changes: Mapping[str, Any]) -> KanbanTask | None: ...
    async def apply_decomposition(self, parent_id: str, children: Sequence[KanbanTask]) -> KanbanTask | None: ...
    async def promotable_tasks(self) -> list[KanbanTask]: ...
    async def rollup_candidates(self) -> list[KanbanTask]: ...

    async def upsert_worker(self, worker: Worker) -> Worker: ...
    async def get_worker(self, uid: str) -> Worker | None: ...
    async def list_workers(self, *, status: WorkerStatus | None = None) -> list[Worker]: ...
    async def cas_worker(self, uid: str, expected: WorkerStatus | None, changes: Mapping[str, Any]) -> Worker | None: ...

    async def add_experience(self, experience: Experience) -> Experience: ...
    async def list_experiences(self, *, worker_uid: str | None = None, limit: int = 100) -> list[Experience]: ...
    async def pending_vault_experiences(self, *, limit: int = 50) -> list[Experience]: ...
    async def mark_vault_synced(self, experience_id: str) -> None: ...

    async def finish_run(
        self,
        *,
        task_id: str,
        expected: TaskStatus | None,
        task_changes: Mapping[str, Any],
        worker_uid: str | None,
        worker_changes: Mapping[str, Any],
        experience: Experience | None,
        audit: AuditDraft | None,
    ) -> KanbanTask | None: ...

    async def append_audit(self, draft: AuditDraft) -> AuditEntry: ...
    async def list_audit(self, *, after_seq: int = 0, limit: int = 1000) -> list[AuditEntry]: ...


# --------------------------------------------------------------------------- #
# SQLite
# --------------------------------------------------------------------------- #
def _encode(changes: Mapping[str, Any], json_keys: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in changes.items():
        value = _plain(value)
        if key in json_keys:
            out[key] = None if value is None else json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            out[key] = int(value)
        else:
            out[key] = value
    return out


def _decode(row: sqlite3.Row, json_keys: frozenset[str]) -> dict[str, Any]:
    data = dict(row)
    for key in json_keys:
        if key in data and isinstance(data[key], str):
            data[key] = json.loads(data[key])
    return data


def _task(row: sqlite3.Row) -> KanbanTask:
    return KanbanTask.from_dict(_decode(row, _TASK_JSON))


def _worker(row: sqlite3.Row) -> Worker:
    return Worker.from_dict(_decode(row, _WORKER_JSON))


def _experience(row: sqlite3.Row) -> Experience:
    return Experience.from_dict(_decode(row, _EXPERIENCE_JSON))


def _audit(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry.from_dict(_decode(row, frozenset({"payload"})))


class SqliteKanbanStore:
    """Stdlib-Store. ``path=":memory:"`` fuer Tests (eine geteilte Verbindung)."""

    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    # -- Infrastruktur ---------------------------------------------------- #
    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            if self._path != ":memory:":
                Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path, timeout=30.0, isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 30000")
            if self._path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")
            self._conn = conn
        return self._conn

    async def _run(self, fn: Any, *args: Any) -> Any:
        def _call() -> Any:
            with self._lock:
                return fn(self._connection(), *args)

        return await asyncio.to_thread(_call)

    @staticmethod
    @contextlib.contextmanager
    def _tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")

    async def init(self) -> None:
        await self._run(self._migrate)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        for version, script in migration_scripts("sqlite"):
            if version <= current:
                continue
            # ``executescript`` committet selbst -- deshalb steht die Transaktion im
            # Skript: entweder die ganze Migration plus Versionszeile oder nichts.
            try:
                conn.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + script
                    + f"\nINSERT INTO schema_version (version, applied_at) VALUES ({int(version)}, '{utc_now_iso()}');\nCOMMIT;"
                )
            except sqlite3.Error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    async def close(self) -> None:
        def _close() -> None:
            with self._lock:
                if self._conn is not None:
                    self._conn.close()
                    self._conn = None

        await asyncio.to_thread(_close)

    # -- Boards ----------------------------------------------------------- #
    async def create_board(self, board: KanbanBoard) -> KanbanBoard:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute("INSERT INTO kanban_boards (id, name, created_at) VALUES (?, ?, ?)", (board.id, board.name, board.created_at))

        await self._run(_do)
        return board

    async def get_board(self, board_id: str) -> KanbanBoard | None:
        def _do(conn: sqlite3.Connection) -> KanbanBoard | None:
            row = conn.execute("SELECT * FROM kanban_boards WHERE id = ?", (board_id,)).fetchone()
            return None if row is None else KanbanBoard.from_dict(dict(row))

        result: KanbanBoard | None = await self._run(_do)
        return result

    async def list_boards(self) -> list[KanbanBoard]:
        def _do(conn: sqlite3.Connection) -> list[KanbanBoard]:
            return [KanbanBoard.from_dict(dict(r)) for r in conn.execute("SELECT * FROM kanban_boards ORDER BY created_at")]

        result: list[KanbanBoard] = await self._run(_do)
        return result

    # -- Tasks ------------------------------------------------------------ #
    @staticmethod
    def _insert_task(conn: sqlite3.Connection, task: KanbanTask) -> None:
        data = _encode(task.to_dict(), _TASK_JSON)
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO kanban_tasks ({cols}) VALUES ({marks})", tuple(data.values()))

    async def create_task(self, task: KanbanTask) -> KanbanTask:
        await self._run(self._insert_task, task)
        return task

    async def get_task(self, task_id: str) -> KanbanTask | None:
        def _do(conn: sqlite3.Connection) -> KanbanTask | None:
            row = conn.execute("SELECT * FROM kanban_tasks WHERE id = ?", (task_id,)).fetchone()
            return None if row is None else _task(row)

        result: KanbanTask | None = await self._run(_do)
        return result

    async def list_tasks(
        self,
        *,
        board_id: str | None = None,
        status: TaskStatus | None = None,
        parent_id: str | None = None,
        limit: int = 500,
    ) -> list[KanbanTask]:
        where: list[str] = []
        params: list[Any] = []
        for column, value in (("board_id", board_id), ("status", _plain(status)), ("parent_id", parent_id)):
            if value is not None:
                where.append(f"{column} = ?")
                params.append(value)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM kanban_tasks {clause} ORDER BY priority DESC, created_at LIMIT ?"

        def _do(conn: sqlite3.Connection) -> list[KanbanTask]:
            return [_task(r) for r in conn.execute(sql, (*params, int(limit)))]

        result: list[KanbanTask] = await self._run(_do)
        return result

    @staticmethod
    def _cas_task(conn: sqlite3.Connection, task_id: str, expected: TaskStatus | None, changes: Mapping[str, Any]) -> KanbanTask | None:
        _check_keys(changes, TASK_MUTABLE)
        data = _encode(changes, _TASK_JSON)
        data["updated_at"] = utc_now_iso()
        sets = ", ".join(f"{k} = ?" for k in data)
        params: list[Any] = [*data.values(), task_id]
        sql = f"UPDATE kanban_tasks SET {sets} WHERE id = ?"
        if expected is not None:
            sql += " AND status = ?"
            params.append(_plain(expected))
        row = conn.execute(sql + " RETURNING *", params).fetchone()
        return None if row is None else _task(row)

    async def cas_task(self, task_id: str, expected: TaskStatus | None, changes: Mapping[str, Any]) -> KanbanTask | None:
        def _do(conn: sqlite3.Connection) -> KanbanTask | None:
            with self._tx(conn):
                return self._cas_task(conn, task_id, expected, changes)

        result: KanbanTask | None = await self._run(_do)
        return result

    async def apply_decomposition(self, parent_id: str, children: Sequence[KanbanTask]) -> KanbanTask | None:
        def _do(conn: sqlite3.Connection) -> KanbanTask | None:
            with self._tx(conn):
                parent = self._cas_task(
                    conn, parent_id, TaskStatus.TRIAGE, {"status": TaskStatus.BACKLOG, "is_rollup": bool(children)}
                )
                if parent is None:
                    return None
                for child in children:
                    self._insert_task(conn, child)
                return parent

        result: KanbanTask | None = await self._run(_do)
        return result

    async def promotable_tasks(self) -> list[KanbanTask]:
        # Fehlende Abhaengigkeiten (p.id IS NULL) blockieren genauso wie offene.
        sql = """
            SELECT t.* FROM kanban_tasks t
            WHERE t.status = 'backlog' AND t.is_rollup = 0
              AND NOT EXISTS (
                  SELECT 1 FROM json_each(t.dependencies) d
                  LEFT JOIN kanban_tasks p ON p.id = d.value
                  WHERE p.id IS NULL OR p.status <> 'completed')
            ORDER BY t.priority DESC, t.created_at
        """

        def _do(conn: sqlite3.Connection) -> list[KanbanTask]:
            return [_task(r) for r in conn.execute(sql)]

        result: list[KanbanTask] = await self._run(_do)
        return result

    async def rollup_candidates(self) -> list[KanbanTask]:
        sql = """
            SELECT t.* FROM kanban_tasks t
            WHERE t.status = 'backlog' AND t.is_rollup = 1
              AND EXISTS (SELECT 1 FROM kanban_tasks c WHERE c.parent_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM kanban_tasks c WHERE c.parent_id = t.id AND c.status <> 'completed')
            ORDER BY t.created_at
        """

        def _do(conn: sqlite3.Connection) -> list[KanbanTask]:
            return [_task(r) for r in conn.execute(sql)]

        result: list[KanbanTask] = await self._run(_do)
        return result

    # -- Worker ----------------------------------------------------------- #
    async def upsert_worker(self, worker: Worker) -> Worker:
        def _do(conn: sqlite3.Connection) -> Worker:
            data = _encode(worker.to_dict(), _WORKER_JSON)
            cols = ", ".join(data)
            marks = ", ".join("?" for _ in data)
            row = conn.execute(
                f"INSERT INTO kanban_workers ({cols}) VALUES ({marks}) "
                "ON CONFLICT(uid) DO UPDATE SET name = excluded.name, skills = excluded.skills, "
                "soul_md = excluded.soul_md, updated_at = excluded.updated_at RETURNING *",
                tuple(data.values()),
            ).fetchone()
            return _worker(row)

        result: Worker = await self._run(_do)
        return result

    async def get_worker(self, uid: str) -> Worker | None:
        def _do(conn: sqlite3.Connection) -> Worker | None:
            row = conn.execute("SELECT * FROM kanban_workers WHERE uid = ?", (uid,)).fetchone()
            return None if row is None else _worker(row)

        result: Worker | None = await self._run(_do)
        return result

    async def list_workers(self, *, status: WorkerStatus | None = None) -> list[Worker]:
        def _do(conn: sqlite3.Connection) -> list[Worker]:
            if status is None:
                rows = conn.execute("SELECT * FROM kanban_workers ORDER BY uid")
            else:
                rows = conn.execute("SELECT * FROM kanban_workers WHERE status = ? ORDER BY uid", (status.value,))
            return [_worker(r) for r in rows]

        result: list[Worker] = await self._run(_do)
        return result

    @staticmethod
    def _cas_worker(conn: sqlite3.Connection, uid: str, expected: WorkerStatus | None, changes: Mapping[str, Any]) -> Worker | None:
        _check_keys(changes, WORKER_MUTABLE)
        data = _encode(changes, _WORKER_JSON)
        data["updated_at"] = utc_now_iso()
        sets = ", ".join(f"{k} = ?" for k in data)
        params: list[Any] = [*data.values(), uid]
        sql = f"UPDATE kanban_workers SET {sets} WHERE uid = ?"
        if expected is not None:
            sql += " AND status = ?"
            params.append(expected.value)
        row = conn.execute(sql + " RETURNING *", params).fetchone()
        return None if row is None else _worker(row)

    async def cas_worker(self, uid: str, expected: WorkerStatus | None, changes: Mapping[str, Any]) -> Worker | None:
        def _do(conn: sqlite3.Connection) -> Worker | None:
            with self._tx(conn):
                return self._cas_worker(conn, uid, expected, changes)

        result: Worker | None = await self._run(_do)
        return result

    # -- Experiences ------------------------------------------------------ #
    @staticmethod
    def _insert_experience(conn: sqlite3.Connection, experience: Experience) -> None:
        data = _encode(experience.to_dict(), _EXPERIENCE_JSON)
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO experiences ({cols}) VALUES ({marks})", tuple(data.values()))

    async def add_experience(self, experience: Experience) -> Experience:
        await self._run(self._insert_experience, experience)
        return experience

    async def list_experiences(self, *, worker_uid: str | None = None, limit: int = 100) -> list[Experience]:
        def _do(conn: sqlite3.Connection) -> list[Experience]:
            if worker_uid is None:
                rows = conn.execute("SELECT * FROM experiences ORDER BY created_at DESC LIMIT ?", (limit,))
            else:
                rows = conn.execute(
                    "SELECT * FROM experiences WHERE worker_uid = ? ORDER BY created_at DESC LIMIT ?", (worker_uid, limit)
                )
            return [_experience(r) for r in rows]

        result: list[Experience] = await self._run(_do)
        return result

    async def pending_vault_experiences(self, *, limit: int = 50) -> list[Experience]:
        def _do(conn: sqlite3.Connection) -> list[Experience]:
            rows = conn.execute("SELECT * FROM experiences WHERE vault_synced = 0 ORDER BY created_at LIMIT ?", (limit,))
            return [_experience(r) for r in rows]

        result: list[Experience] = await self._run(_do)
        return result

    async def mark_vault_synced(self, experience_id: str) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute("UPDATE experiences SET vault_synced = 1 WHERE id = ?", (experience_id,))

        await self._run(_do)

    # -- Lauf-Abschluss (eine Transaktion) -------------------------------- #
    async def finish_run(
        self,
        *,
        task_id: str,
        expected: TaskStatus | None,
        task_changes: Mapping[str, Any],
        worker_uid: str | None,
        worker_changes: Mapping[str, Any],
        experience: Experience | None,
        audit: AuditDraft | None,
    ) -> KanbanTask | None:
        def _do(conn: sqlite3.Connection) -> KanbanTask | None:
            with self._tx(conn):
                if task_changes:
                    task = self._cas_task(conn, task_id, expected, task_changes)
                    if task is None:
                        conn.execute("ROLLBACK")
                        conn.execute("BEGIN IMMEDIATE")  # _tx schliesst mit COMMIT einer leeren Transaktion
                        return None
                else:
                    row = conn.execute("SELECT * FROM kanban_tasks WHERE id = ?", (task_id,)).fetchone()
                    task = None if row is None else _task(row)
                if worker_uid is not None and worker_changes:
                    self._cas_worker(conn, worker_uid, None, worker_changes)
                if experience is not None:
                    self._insert_experience(conn, experience)
                if audit is not None:
                    self._append_audit(conn, audit)
                return task

        result: KanbanTask | None = await self._run(_do)
        return result

    # -- Audit ------------------------------------------------------------ #
    @staticmethod
    def _append_audit(conn: sqlite3.Connection, draft: AuditDraft) -> AuditEntry:
        last = conn.execute("SELECT entry_hash FROM audit_ledger ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last[0] if last else GENESIS_HASH
        clean, entry_hash = seal(prev, draft)
        row = conn.execute(
            "INSERT INTO audit_ledger (ts, actor, action, category, subject, payload, prev_hash, entry_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
            (
                clean.ts,
                clean.actor,
                clean.action,
                clean.category,
                clean.subject,
                json.dumps(clean.payload, ensure_ascii=False),
                prev,
                entry_hash,
            ),
        ).fetchone()
        return _audit(row)

    async def append_audit(self, draft: AuditDraft) -> AuditEntry:
        def _do(conn: sqlite3.Connection) -> AuditEntry:
            with self._tx(conn):
                return self._append_audit(conn, draft)

        result: AuditEntry = await self._run(_do)
        return result

    async def list_audit(self, *, after_seq: int = 0, limit: int = 1000) -> list[AuditEntry]:
        def _do(conn: sqlite3.Connection) -> list[AuditEntry]:
            rows = conn.execute("SELECT * FROM audit_ledger WHERE seq > ? ORDER BY seq LIMIT ?", (after_seq, limit))
            return [_audit(r) for r in rows]

        result: list[AuditEntry] = await self._run(_do)
        return result
