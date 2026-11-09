"""Persistenz fuer Telegram: ``TelegramStore`` Protocol und SQLite-Implementierung.

Gleiches Muster wie ``orchestrator/kanban/store.py``: eine geteilte Verbindung
hinter einem ``threading.Lock``, alle synchronen Aufrufe per ``asyncio.to_thread``.
Status-Uebergaenge (CAS) laufen als ``UPDATE ... WHERE id=? AND status=?`` in
einer ``BEGIN IMMEDIATE``-Transaktion: von zwei gleichzeitigen Approves gewinnt
genau einer.
"""

from __future__ import annotations

import asyncio
import contextlib
import sqlite3
import threading
from collections.abc import Callable, Iterator, Sequence
from importlib import resources
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast

from core.protocol import utc_now_iso
from orchestrator.kanban.models import new_id

from .models import (
    ApprovalRequest,
    ApprovalStatus,
    Direction,
    Signal,
    Suggestion,
    SuggestionStatus,
    TgMessage,
    check_transition,
    normalize_peer,
)

__all__ = ["SqliteTelegramStore", "TelegramStore", "migration_scripts"]

_T = TypeVar("_T")

# Per CAS aenderbare Spalten. Schluessel landen im SQL, deshalb nie frei.
_SUGGESTION_CHANGES = frozenset({"status", "text", "decided_at", "error"})
_APPROVAL_CHANGES = frozenset({"status", "decided_at"})


def migration_scripts() -> list[tuple[int, str]]:
    """``[(version, sql), ...]`` aus ``orchestrator/telegram/sql``."""
    folder = resources.files(__package__).joinpath("sql")
    out: list[tuple[int, str]] = []
    for entry in folder.iterdir():
        if entry.name.endswith(".sqlite.sql"):
            out.append((int(entry.name.split("_", 1)[0]), entry.read_text(encoding="utf-8")))
    return sorted(out)


def _check_keys(changes: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"Nicht aenderbare Felder: {sorted(unknown)}")


def _peer_key(peer: int | str) -> str:
    return str(normalize_peer(peer))


class TelegramStore(Protocol):
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def add_messages(self, msgs: Sequence[TgMessage]) -> list[TgMessage]: ...
    async def recent_messages(self, peers: list[int] | None, limit: int) -> list[TgMessage]: ...
    async def unrouted_messages(self, peer: int, limit: int = 500) -> list[TgMessage]: ...
    async def mark_routed(self, peer: int, msg_ids: Sequence[int]) -> None: ...
    async def get_cursor(self, peer: int) -> int: ...
    async def advance_cursor(self, peer: int, msg_id: int) -> None: ...
    async def add_monitored(self, peer: int) -> None: ...
    async def remove_monitored(self, peer: int) -> None: ...
    async def list_monitored(self) -> list[int]: ...
    async def set_pairing(self, source: int, target: int) -> None: ...
    async def remove_pairing(self, source: int) -> None: ...
    async def get_pairing(self, source: int) -> int | None: ...
    async def list_pairings(self) -> dict[int, int]: ...
    async def allow(self, peer: int | str) -> None: ...
    async def disallow(self, peer: int | str) -> None: ...
    async def is_allowed(self, peer: int | str) -> bool: ...
    async def list_allowed(self) -> list[int | str]: ...
    async def add_suggestion(self, suggestion: Suggestion) -> bool: ...
    async def get_suggestion(self, id: str) -> Suggestion | None: ...
    async def list_suggestions(self, status: SuggestionStatus | None = None, limit: int = 100) -> list[Suggestion]: ...
    async def cas_suggestion(self, id: str, expected_status: SuggestionStatus, changes: dict[str, Any]) -> Suggestion | None: ...
    async def fail_stale_sending(self, error: str, now: str) -> list[str]: ...
    async def add_approval(self, approval: ApprovalRequest) -> None: ...
    async def get_approval(self, id: str) -> ApprovalRequest | None: ...
    async def list_approvals(self, status: ApprovalStatus | None = None) -> list[ApprovalRequest]: ...
    async def cas_approval(self, id: str, expected: ApprovalStatus, changes: dict[str, Any]) -> ApprovalRequest | None: ...
    async def add_signal(self, signal: Signal) -> bool: ...
    async def list_signals(self, limit: int = 100, symbol: str | None = None) -> list[Signal]: ...
    async def last_signal(self, symbol: str, direction: Direction) -> Signal | None: ...
    async def set_signal_task(self, id: str, kanban_task_id: str) -> None: ...
    async def record_send(self, peer: int, ts: str) -> None: ...
    async def count_sends_since(self, peer: int, since_iso: str) -> int: ...
    async def send_times_since(self, peer: int, since_iso: str) -> list[str]: ...


def _row_to_message(row: sqlite3.Row) -> TgMessage:
    return TgMessage(
        peer=row["peer"],
        msg_id=row["msg_id"],
        sender=row["sender"],
        text=row["text"],
        ts=row["ts"],
        outgoing=bool(row["outgoing"]),
        is_bot=bool(row["is_bot"]),
    )


def _row_to_suggestion(row: sqlite3.Row) -> Suggestion:
    return Suggestion(
        id=row["id"],
        source_peer=row["source_peer"],
        target_peer=row["target_peer"],
        text=row["text"],
        based_on_msg_id=row["based_on_msg_id"],
        origin=cast(Any, row["origin"]),
        status=SuggestionStatus(row["status"]),
        created_at=row["created_at"],
        decided_at=row["decided_at"],
        error=row["error"],
    )


def _row_to_approval(row: sqlite3.Row) -> ApprovalRequest:
    return ApprovalRequest(
        id=row["id"],
        request_id=row["request_id"],
        title=row["title"],
        detail=row["detail"],
        status=ApprovalStatus(row["status"]),
        created_at=row["created_at"],
        decided_at=row["decided_at"],
        callback_url=row["callback_url"],
    )


def _row_to_signal(row: sqlite3.Row) -> Signal:
    return Signal(
        id=row["id"],
        symbol=row["symbol"],
        direction=Direction(row["direction"]),
        strength=row["strength"],
        peer=row["peer"],
        msg_id=row["msg_id"],
        evidence=row["evidence"],
        created_at=row["created_at"],
        kanban_task_id=row["kanban_task_id"],
    )


class SqliteTelegramStore:
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
            conn.execute("PRAGMA busy_timeout = 30000")
            if self._path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")
            self._conn = conn
        return self._conn

    async def _run(self, fn: Callable[[sqlite3.Connection], _T]) -> _T:
        def _call() -> _T:
            with self._lock:
                return fn(self._connection())

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
        for version, script in migration_scripts():
            if version <= current:
                continue
            # ``executescript`` committet selbst -- Migration plus Versionszeile oder nichts.
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

    # -- Nachrichten + Cursor -------------------------------------------- #
    async def add_messages(self, msgs: Sequence[TgMessage]) -> list[TgMessage]:
        """INSERT OR IGNORE; liefert nur die neuen Nachrichten (Dedupe ueber (peer, msg_id))."""
        if not msgs:
            return []

        def _do(conn: sqlite3.Connection) -> list[TgMessage]:
            added: list[TgMessage] = []
            with self._tx(conn):
                for m in msgs:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO messages (peer, msg_id, sender, text, ts, outgoing, is_bot) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (m.peer, m.msg_id, m.sender, m.text, m.ts, int(m.outgoing), int(m.is_bot)),
                    )
                    if cur.rowcount > 0:
                        added.append(m)
            return added

        return await self._run(_do)

    async def recent_messages(self, peers: list[int] | None, limit: int) -> list[TgMessage]:
        """Die letzten ``limit`` Nachrichten, die neueste zuletzt."""
        if peers is not None and not peers:
            return []
        query = "SELECT * FROM messages"
        args: list[Any] = []
        if peers is not None:
            query += f" WHERE peer IN ({','.join('?' * len(peers))})"
            args.extend(peers)
        query += " ORDER BY ts DESC, msg_id DESC LIMIT ?"
        args.append(limit)

        def _do(conn: sqlite3.Connection) -> list[TgMessage]:
            rows = conn.execute(query, args).fetchall()
            return [_row_to_message(r) for r in reversed(rows)]

        return await self._run(_do)

    async def unrouted_messages(self, peer: int, limit: int = 500) -> list[TgMessage]:
        """Noch nicht zugestellte Nachrichten, aufsteigend nach ``msg_id``."""

        def _do(conn: sqlite3.Connection) -> list[TgMessage]:
            rows = conn.execute(
                "SELECT * FROM messages WHERE peer=? AND routed_at IS NULL ORDER BY msg_id LIMIT ?",
                (peer, limit),
            ).fetchall()
            return [_row_to_message(r) for r in rows]

        return await self._run(_do)

    async def mark_routed(self, peer: int, msg_ids: Sequence[int]) -> None:
        if not msg_ids:
            return
        now = utc_now_iso()

        def _do(conn: sqlite3.Connection) -> None:
            with self._tx(conn):
                conn.executemany(
                    "UPDATE messages SET routed_at=? WHERE peer=? AND msg_id=?",
                    [(now, peer, msg_id) for msg_id in msg_ids],
                )

        await self._run(_do)

    async def get_cursor(self, peer: int) -> int:
        def _do(conn: sqlite3.Connection) -> int:
            row = conn.execute("SELECT last_msg_id FROM cursors WHERE peer=?", (peer,)).fetchone()
            return int(row["last_msg_id"]) if row else 0

        return await self._run(_do)

    async def advance_cursor(self, peer: int, msg_id: int) -> None:
        """Nur vorwaerts: ein kleinerer ``msg_id`` laesst den Cursor stehen."""

        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO cursors (peer, last_msg_id) VALUES (?, ?)"
                " ON CONFLICT(peer) DO UPDATE SET last_msg_id = MAX(last_msg_id, excluded.last_msg_id)",
                (peer, msg_id),
            )

        await self._run(_do)

    # -- Monitored / Pairings / Allowlist -------------------------------- #
    async def add_monitored(self, peer: int) -> None:
        await self._run(lambda c: c.execute("INSERT OR IGNORE INTO monitored (peer, added_at) VALUES (?, ?)", (peer, utc_now_iso())))

    async def remove_monitored(self, peer: int) -> None:
        await self._run(lambda c: c.execute("DELETE FROM monitored WHERE peer=?", (peer,)))

    async def list_monitored(self) -> list[int]:
        return await self._run(lambda c: [r["peer"] for r in c.execute("SELECT peer FROM monitored ORDER BY added_at, peer")])

    async def set_pairing(self, source: int, target: int) -> None:
        await self._run(
            lambda c: c.execute(
                "INSERT INTO pairings (source_peer, target_peer) VALUES (?, ?)"
                " ON CONFLICT(source_peer) DO UPDATE SET target_peer=excluded.target_peer",
                (source, target),
            )
        )

    async def remove_pairing(self, source: int) -> None:
        await self._run(lambda c: c.execute("DELETE FROM pairings WHERE source_peer=?", (source,)))

    async def get_pairing(self, source: int) -> int | None:
        def _do(conn: sqlite3.Connection) -> int | None:
            row = conn.execute("SELECT target_peer FROM pairings WHERE source_peer=?", (source,)).fetchone()
            return int(row["target_peer"]) if row else None

        return await self._run(_do)

    async def list_pairings(self) -> dict[int, int]:
        return await self._run(lambda c: {r["source_peer"]: r["target_peer"] for r in c.execute("SELECT * FROM pairings")})

    async def allow(self, peer: int | str) -> None:
        key = _peer_key(peer)
        await self._run(lambda c: c.execute("INSERT OR IGNORE INTO allowlist (peer, added_at) VALUES (?, ?)", (key, utc_now_iso())))

    async def disallow(self, peer: int | str) -> None:
        key = _peer_key(peer)
        await self._run(lambda c: c.execute("DELETE FROM allowlist WHERE peer=?", (key,)))

    async def is_allowed(self, peer: int | str) -> bool:
        key = _peer_key(peer)
        return await self._run(lambda c: c.execute("SELECT 1 FROM allowlist WHERE peer=?", (key,)).fetchone() is not None)

    async def list_allowed(self) -> list[int | str]:
        return await self._run(lambda c: [normalize_peer(r["peer"]) for r in c.execute("SELECT peer FROM allowlist ORDER BY added_at")])

    # -- Suggestions ------------------------------------------------------ #
    async def add_suggestion(self, suggestion: Suggestion) -> bool:
        """Idempotent ueber die ID; ``True`` nur, wenn die Zeile neu ist."""
        s = suggestion
        return await self._run(
            lambda c: (
                c.execute(
                    "INSERT OR IGNORE INTO suggestions (id, source_peer, target_peer, text, based_on_msg_id, origin, status,"
                    " created_at, decided_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        s.id,
                        s.source_peer,
                        s.target_peer,
                        s.text,
                        s.based_on_msg_id,
                        s.origin,
                        s.status.value,
                        s.created_at,
                        s.decided_at,
                        s.error,
                    ),
                ).rowcount
                > 0
            )
        )

    async def get_suggestion(self, id: str) -> Suggestion | None:
        def _do(conn: sqlite3.Connection) -> Suggestion | None:
            row = conn.execute("SELECT * FROM suggestions WHERE id=?", (id,)).fetchone()
            return _row_to_suggestion(row) if row else None

        return await self._run(_do)

    async def list_suggestions(self, status: SuggestionStatus | None = None, limit: int = 100) -> list[Suggestion]:
        query = "SELECT * FROM suggestions"
        args: list[Any] = []
        if status is not None:
            query += " WHERE status=?"
            args.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        return await self._run(lambda c: [_row_to_suggestion(r) for r in c.execute(query, args)])

    async def cas_suggestion(self, id: str, expected_status: SuggestionStatus, changes: dict[str, Any]) -> Suggestion | None:
        """Aendert die Suggestion nur, wenn sie noch ``expected_status`` hat; sonst ``None``."""
        _check_keys(changes, _SUGGESTION_CHANGES)
        if "status" in changes:
            check_transition("suggestion", expected_status, SuggestionStatus(changes["status"]))
        row = await self._run(lambda c: self._cas(c, "suggestions", id, expected_status.value, changes))
        return _row_to_suggestion(row) if row else None

    async def fail_stale_sending(self, error: str, now: str) -> list[str]:
        """Setzt alles in ``sending`` auf ``failed``: nur beim Start, wenn kein Versand laufen kann."""

        def _do(conn: sqlite3.Connection) -> list[str]:
            with self._tx(conn):
                rows = conn.execute(
                    "UPDATE suggestions SET status=?, error=?, decided_at=? WHERE status=? RETURNING id",
                    (SuggestionStatus.FAILED.value, error, now, SuggestionStatus.SENDING.value),
                ).fetchall()
            return [r["id"] for r in rows]

        return await self._run(_do)

    # -- Approvals -------------------------------------------------------- #
    async def add_approval(self, approval: ApprovalRequest) -> None:
        a = approval
        await self._run(
            lambda c: c.execute(
                "INSERT INTO approvals (id, request_id, title, detail, status, created_at, decided_at, callback_url)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (a.id, a.request_id, a.title, a.detail, a.status.value, a.created_at, a.decided_at, a.callback_url),
            )
        )

    async def get_approval(self, id: str) -> ApprovalRequest | None:
        def _do(conn: sqlite3.Connection) -> ApprovalRequest | None:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (id,)).fetchone()
            return _row_to_approval(row) if row else None

        return await self._run(_do)

    async def list_approvals(self, status: ApprovalStatus | None = None) -> list[ApprovalRequest]:
        query = "SELECT * FROM approvals"
        args: list[Any] = []
        if status is not None:
            query += " WHERE status=?"
            args.append(status.value)
        query += " ORDER BY created_at DESC"
        return await self._run(lambda c: [_row_to_approval(r) for r in c.execute(query, args)])

    async def cas_approval(self, id: str, expected: ApprovalStatus, changes: dict[str, Any]) -> ApprovalRequest | None:
        _check_keys(changes, _APPROVAL_CHANGES)
        if "status" in changes:
            check_transition("approval", expected, ApprovalStatus(changes["status"]))
        row = await self._run(lambda c: self._cas(c, "approvals", id, expected.value, changes))
        return _row_to_approval(row) if row else None

    def _cas(self, conn: sqlite3.Connection, table: str, id: str, expected: str, changes: dict[str, Any]) -> sqlite3.Row | None:
        with self._tx(conn):
            if not changes:
                cur = conn.execute(f"SELECT * FROM {table} WHERE id=? AND status=?", (id, expected))
            else:
                sets = ", ".join(f"{k}=?" for k in changes)
                args = [v.value if hasattr(v, "value") else v for v in changes.values()]
                cur = conn.execute(f"UPDATE {table} SET {sets} WHERE id=? AND status=? RETURNING *", (*args, id, expected))
            row: sqlite3.Row | None = cur.fetchone()
        return row

    # -- Signale ---------------------------------------------------------- #
    async def add_signal(self, signal: Signal) -> bool:
        """Idempotent ueber die ID; ``True`` nur, wenn die Zeile neu ist."""
        s = signal
        return await self._run(
            lambda c: (
                c.execute(
                    "INSERT OR IGNORE INTO signals (id, symbol, direction, strength, peer, msg_id, evidence, created_at,"
                    " kanban_task_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (s.id, s.symbol, s.direction.value, s.strength, s.peer, s.msg_id, s.evidence, s.created_at, s.kanban_task_id),
                ).rowcount
                > 0
            )
        )

    async def list_signals(self, limit: int = 100, symbol: str | None = None) -> list[Signal]:
        query = "SELECT * FROM signals"
        args: list[Any] = []
        if symbol is not None:
            query += " WHERE symbol=?"
            args.append(symbol)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        return await self._run(lambda c: [_row_to_signal(r) for r in c.execute(query, args)])

    async def last_signal(self, symbol: str, direction: Direction) -> Signal | None:
        def _do(conn: sqlite3.Connection) -> Signal | None:
            row = conn.execute(
                "SELECT * FROM signals WHERE symbol=? AND direction=? ORDER BY created_at DESC LIMIT 1",
                (symbol, direction.value),
            ).fetchone()
            return _row_to_signal(row) if row else None

        return await self._run(_do)

    async def set_signal_task(self, id: str, kanban_task_id: str) -> None:
        await self._run(lambda c: c.execute("UPDATE signals SET kanban_task_id=? WHERE id=?", (kanban_task_id, id)))

    # -- Sends (Rate-Limit) ---------------------------------------------- #
    async def record_send(self, peer: int, ts: str) -> None:
        await self._run(lambda c: c.execute("INSERT INTO sends (id, peer, ts) VALUES (?, ?, ?)", (new_id("send"), peer, ts)))

    async def count_sends_since(self, peer: int, since_iso: str) -> int:
        """Zeitstempel sind ``utc_now_iso``-Strings (gleiches Format), daher String-Vergleich."""
        return await self._run(
            lambda c: int(c.execute("SELECT COUNT(*) FROM sends WHERE peer=? AND ts >= ?", (peer, since_iso)).fetchone()[0])
        )

    async def send_times_since(self, peer: int, since_iso: str) -> list[str]:
        """Sendezeitpunkte ab ``since_iso``, aelteste zuerst (fuer ``retry_after``)."""
        return await self._run(
            lambda c: [r["ts"] for r in c.execute("SELECT ts FROM sends WHERE peer=? AND ts >= ? ORDER BY ts", (peer, since_iso))]
        )
