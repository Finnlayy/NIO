from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from core.protocol import format_timestamp, parse_timestamp

from .audit import GENESIS_HASH, AuditDraft, seal
from .models import AuditEntry, Experience, KanbanBoard, KanbanTask, TaskStatus, Worker, WorkerStatus
from .store import TASK_MUTABLE, WORKER_MUTABLE, _plain, migration_scripts

__all__ = ["PostgresKanbanStore"]


_TASK_JSON = frozenset({"dependencies", "required_skills", "result_payload"})
_WORKER_JSON = frozenset({"skills"})
_EXPERIENCE_JSON = frozenset({"lessons", "skills_delta"})
_TIMESTAMP_COLS = frozenset(
    {"created_at", "updated_at", "started_at", "breaker_open_until", "ts"}
)


def _to_db(changes: Mapping[str, Any], json_keys: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in changes.items():
        val = _plain(value)
        if key in json_keys:
            out[key] = val
        elif key in _TIMESTAMP_COLS and val is not None:
            out[key] = parse_timestamp(val, key)
        else:
            out[key] = val
    return out


def _from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key, val in data.items():
        if isinstance(val, datetime):
            data[key] = format_timestamp(val)
    return data


def _task(row: Mapping[str, Any]) -> KanbanTask:
    return KanbanTask.from_dict(_from_row(row))


def _worker(row: Mapping[str, Any]) -> Worker:
    return Worker.from_dict(_from_row(row))


def _experience(row: Mapping[str, Any]) -> Experience:
    return Experience.from_dict(_from_row(row))


def _audit(row: Mapping[str, Any]) -> AuditEntry:
    return AuditEntry.from_dict(_from_row(row))


class PostgresKanbanStore:
    def __init__(self, dsn: str, server_settings: dict[str, str] | None = None) -> None:
        self._dsn = dsn
        self._server_settings = server_settings
        self._pool: Any = None

    async def init(self) -> None:
        try:
            import asyncpg
        except ImportError as e:
            raise RuntimeError("PostgresKanbanStore braucht asyncpg: pip install -e '.[kanban]'") from e

        async def _init_conn(conn: asyncpg.Connection) -> None:
            await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
            await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")

        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=1,
            max_size=10,
            init=_init_conn,
            server_settings=self._server_settings,
        )

        async with self._pool.acquire() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INT PRIMARY KEY, applied_at TIMESTAMPTZ)")

            for version, script in migration_scripts("postgres"):
                async with conn.transaction():
                    await conn.execute("SELECT pg_advisory_xact_lock(hashtext('nio_kanban_migrate'))")

                    row = await conn.fetchrow("SELECT version FROM schema_version WHERE version = $1", version)
                    if row is not None:
                        continue

                    await conn.execute(script)
                    await conn.execute(
                        "INSERT INTO schema_version (version, applied_at) VALUES ($1, $2)",
                        version, datetime.now(UTC)
                    )


    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # -- Boards ----------------------------------------------------------- #
    async def create_board(self, board: KanbanBoard) -> KanbanBoard:
        data = _to_db(board.to_dict(), frozenset())
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO kanban_boards (id, name, created_at) VALUES ($1, $2, $3)",
                data["id"], data["name"], data["created_at"]
            )
        return board

    async def get_board(self, board_id: str) -> KanbanBoard | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM kanban_boards WHERE id = $1", board_id)
        if row is None:
            return None
        return KanbanBoard.from_dict(_from_row(row))

    async def list_boards(self) -> list[KanbanBoard]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM kanban_boards ORDER BY created_at")
        return [KanbanBoard.from_dict(_from_row(r)) for r in rows]

    # -- Tasks ------------------------------------------------------------ #
    async def create_task(self, task: KanbanTask) -> KanbanTask:
        data = _to_db(task.to_dict(), _TASK_JSON)
        cols = list(data.keys())
        marks = [f"${i+1}" for i in range(len(cols))]
        sql = f"INSERT INTO kanban_tasks ({', '.join(cols)}) VALUES ({', '.join(marks)})"

        async with self._pool.acquire() as conn:
            await conn.execute(sql, *[data[k] for k in cols])
        return task

    async def get_task(self, task_id: str) -> KanbanTask | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM kanban_tasks WHERE id = $1", task_id)
        return None if row is None else _task(row)

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

        if board_id is not None:
            params.append(board_id)
            where.append(f"board_id = ${len(params)}")
        if status is not None:
            params.append(status.value)
            where.append(f"status = ${len(params)}")
        if parent_id is not None:
            params.append(parent_id)
            where.append(f"parent_id = ${len(params)}")

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit)
        sql = f"SELECT * FROM kanban_tasks {clause} ORDER BY priority DESC, created_at LIMIT ${len(params)}"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [_task(r) for r in rows]

    async def _cas_task(self, conn: Any, task_id: str, expected: TaskStatus | None, changes: Mapping[str, Any]) -> KanbanTask | None:
        unknown = set(changes) - TASK_MUTABLE
        if unknown:
            raise ValueError(f"nicht aenderbare Felder: {sorted(unknown)}")

        data = _to_db(changes, _TASK_JSON)
        data["updated_at"] = datetime.now(UTC)

        cols = list(data.keys())
        sets = [f"{k} = ${i+1}" for i, k in enumerate(cols)]

        params: list[Any] = [data[k] for k in cols]
        params.append(task_id)

        sql = f"UPDATE kanban_tasks SET {', '.join(sets)} WHERE id = ${len(params)}"

        if expected is not None:
            params.append(expected.value)
            sql += f" AND status = ${len(params)}"

        row = await conn.fetchrow(sql + " RETURNING *", *params)
        return None if row is None else _task(row)

    async def cas_task(self, task_id: str, expected: TaskStatus | None, changes: Mapping[str, Any]) -> KanbanTask | None:
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._cas_task(conn, task_id, expected, changes)

    async def apply_decomposition(self, parent_id: str, children: Sequence[KanbanTask]) -> KanbanTask | None:
        async with self._pool.acquire() as conn, conn.transaction():
            parent = await self._cas_task(
                conn, parent_id, TaskStatus.TRIAGE, {"status": TaskStatus.BACKLOG, "is_rollup": bool(children)}
            )
            if parent is None:
                return None

            for child in children:
                data = _to_db(child.to_dict(), _TASK_JSON)
                cols = list(data.keys())
                marks = [f"${i+1}" for i in range(len(cols))]
                sql = f"INSERT INTO kanban_tasks ({', '.join(cols)}) VALUES ({', '.join(marks)})"
                await conn.execute(sql, *[data[k] for k in cols])

            return parent

    async def promotable_tasks(self) -> list[KanbanTask]:
        sql = """
            SELECT t.* FROM kanban_tasks t
            WHERE t.status = 'backlog' AND t.is_rollup = false
              AND NOT EXISTS (
                  SELECT 1 FROM jsonb_array_elements_text(t.dependencies) AS d(dep_id)
                  LEFT JOIN kanban_tasks p ON p.id = d.dep_id
                  WHERE p.id IS NULL OR p.status <> 'completed')
            ORDER BY t.priority DESC, t.created_at
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql)
        return [_task(r) for r in rows]

    async def rollup_candidates(self) -> list[KanbanTask]:
        sql = """
            SELECT t.* FROM kanban_tasks t
            WHERE t.status = 'backlog' AND t.is_rollup = true
              AND EXISTS (SELECT 1 FROM kanban_tasks c WHERE c.parent_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM kanban_tasks c WHERE c.parent_id = t.id AND c.status <> 'completed')
            ORDER BY t.created_at
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql)
        return [_task(r) for r in rows]

    # -- Worker ----------------------------------------------------------- #
    async def upsert_worker(self, worker: Worker) -> Worker:
        data = _to_db(worker.to_dict(), _WORKER_JSON)
        cols = list(data.keys())
        marks = [f"${i+1}" for i in range(len(cols))]
        sql = f"""
            INSERT INTO kanban_workers ({', '.join(cols)}) VALUES ({', '.join(marks)})
            ON CONFLICT(uid) DO UPDATE SET name = excluded.name, skills = excluded.skills,
            soul_md = excluded.soul_md, updated_at = excluded.updated_at RETURNING *
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *[data[k] for k in cols])
        return _worker(row)

    async def get_worker(self, uid: str) -> Worker | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM kanban_workers WHERE uid = $1", uid)
        return None if row is None else _worker(row)

    async def list_workers(self, *, status: WorkerStatus | None = None) -> list[Worker]:
        async with self._pool.acquire() as conn:
            if status is None:
                rows = await conn.fetch("SELECT * FROM kanban_workers ORDER BY uid")
            else:
                rows = await conn.fetch("SELECT * FROM kanban_workers WHERE status = $1 ORDER BY uid", status.value)
        return [_worker(r) for r in rows]

    async def _cas_worker(self, conn: Any, uid: str, expected: WorkerStatus | None, changes: Mapping[str, Any]) -> Worker | None:
        unknown = set(changes) - WORKER_MUTABLE
        if unknown:
            raise ValueError(f"nicht aenderbare Felder: {sorted(unknown)}")

        data = _to_db(changes, _WORKER_JSON)
        data["updated_at"] = datetime.now(UTC)

        cols = list(data.keys())
        sets = [f"{k} = ${i+1}" for i, k in enumerate(cols)]

        params: list[Any] = [data[k] for k in cols]
        params.append(uid)

        sql = f"UPDATE kanban_workers SET {', '.join(sets)} WHERE uid = ${len(params)}"
        if expected is not None:
            params.append(expected.value)
            sql += f" AND status = ${len(params)}"

        row = await conn.fetchrow(sql + " RETURNING *", *params)
        return None if row is None else _worker(row)

    async def cas_worker(self, uid: str, expected: WorkerStatus | None, changes: Mapping[str, Any]) -> Worker | None:
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._cas_worker(conn, uid, expected, changes)

    # -- Experiences ------------------------------------------------------ #
    async def add_experience(self, experience: Experience) -> Experience:
        data = _to_db(experience.to_dict(), _EXPERIENCE_JSON)
        cols = list(data.keys())
        marks = [f"${i+1}" for i in range(len(cols))]
        sql = f"INSERT INTO experiences ({', '.join(cols)}) VALUES ({', '.join(marks)})"
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *[data[k] for k in cols])
        return experience

    async def list_experiences(self, *, worker_uid: str | None = None, limit: int = 100) -> list[Experience]:
        async with self._pool.acquire() as conn:
            if worker_uid is None:
                rows = await conn.fetch("SELECT * FROM experiences ORDER BY created_at DESC LIMIT $1", limit)
            else:
                rows = await conn.fetch(
                    "SELECT * FROM experiences WHERE worker_uid = $1 ORDER BY created_at DESC LIMIT $2",
                    worker_uid, limit
                )
        return [_experience(r) for r in rows]

    async def pending_vault_experiences(self, *, limit: int = 50) -> list[Experience]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM experiences WHERE vault_synced = false ORDER BY created_at LIMIT $1", limit)
        return [_experience(r) for r in rows]

    async def mark_vault_synced(self, experience_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE experiences SET vault_synced = true WHERE id = $1", experience_id)

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
        class _Rollback(Exception):
            pass

        async with self._pool.acquire() as conn:
            try:
                async with conn.transaction():
                    if task_changes:
                        task = await self._cas_task(conn, task_id, expected, task_changes)
                        if task is None:
                            raise _Rollback() # Manually trigger rollback
                    else:
                        row = await conn.fetchrow("SELECT * FROM kanban_tasks WHERE id = $1", task_id)
                        task = None if row is None else _task(row)

                    if worker_uid is not None and worker_changes:
                        await self._cas_worker(conn, worker_uid, None, worker_changes)

                    if experience is not None:
                        data = _to_db(experience.to_dict(), _EXPERIENCE_JSON)
                        cols = list(data.keys())
                        marks = [f"${i+1}" for i in range(len(cols))]
                        sql = f"INSERT INTO experiences ({', '.join(cols)}) VALUES ({', '.join(marks)})"
                        await conn.execute(sql, *[data[k] for k in cols])

                    if audit is not None:
                        await self._append_audit(conn, audit)

                    return task
            except _Rollback:
                return None

    # -- Audit ------------------------------------------------------------ #
    async def _append_audit(self, conn: Any, draft: AuditDraft) -> AuditEntry:
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('nio_audit_ledger'))")

        last = await conn.fetchrow("SELECT entry_hash FROM audit_ledger ORDER BY seq DESC LIMIT 1")
        prev = last["entry_hash"].strip() if last else GENESIS_HASH

        clean, entry_hash = seal(prev, draft)

        # payload is JSON object
        row = await conn.fetchrow(
            """
            INSERT INTO audit_ledger (ts, actor, action, category, subject, payload, prev_hash, entry_hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *
            """,
            parse_timestamp(clean.ts, "ts"),
            clean.actor,
            clean.action,
            clean.category,
            clean.subject,
            clean.payload,
            prev,
            entry_hash
        )
        return _audit(row)

    async def append_audit(self, draft: AuditDraft) -> AuditEntry:
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._append_audit(conn, draft)

    async def list_audit(self, *, after_seq: int = 0, limit: int = 1000) -> list[AuditEntry]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM audit_ledger WHERE seq > $1 ORDER BY seq LIMIT $2", after_seq, limit)
        return [_audit(r) for r in rows]
