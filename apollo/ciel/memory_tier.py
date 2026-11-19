"""Gedächtnisschichten für Apollo Ciel (NIO Phase 2).

* :class:`WorkingMemoryPin` — rendert den Working State deterministisch und
  hart gekappt auf ``max_chars``. Wird am Ende der Nachrichtenliste angehängt,
  nie in den Prefix.
* :class:`EpisodicMemoryStore` — episodisches Gedächtnis in SQLite (WAL).
  Volltextsuche über FTS5 (``porter unicode61``). Ohne FTS5-Modul fällt die
  Suche auf eine BM25-Bewertung in Python zurück.
* :func:`register_recall_tool` — registriert ``recall_episodic_memory`` als
  normales Ciel-Tool im Cold-Storage.

Kopplung: keine Imports aus ``orchestrator``/``core``/``workspace``.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .models import ToolSchema
from .registry import ColdStorageRegistry

#: Name des Recall-Tools im Cold-Storage.
RECALL_TOOL_NAME: Final[str] = "recall_episodic_memory"

#: BM25-Parameter für den Fallback.
_BM25_K1: Final[float] = 1.2
_BM25_B: Final[float] = 0.75

# Alphanumerische Tokens (Unicode), Satzzeichen wie ``/`` und ``:`` trennen.
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[^\W_]+")


def _tokens(text: str) -> list[str]:
    """Kleinschreibung und alphanumerische Tokens, in Reihenfolge, ohne Duplikate."""
    seen: dict[str, None] = {}
    for token in _TOKEN_RE.findall(text):
        seen.setdefault(token.lower(), None)
    return list(seen)


def _sanitize_fts5_query(raw: str) -> str:
    """Macht eine Freitext-Anfrage FTS5-sicher: nur Tokens, jeweils gequotet, mit OR verknüpft.

    Sonderzeichen wie ``/`` oder ``:`` landen nie im Ausdruck. Leere Anfragen ergeben ``""``.
    """
    return " OR ".join(f'"{token}"' for token in _tokens(raw))


def _render_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class WorkingMemoryPin:
    """Rendert den Working State als kurzen, deterministischen Textblock."""

    def __init__(self, max_chars: int = 1600) -> None:
        self._max = max(0, int(max_chars))

    @property
    def max_chars(self) -> int:
        return self._max

    def render(self, state: Mapping[str, Any] | None) -> str:
        """Liefert höchstens ``max_chars`` Zeichen. Schlüssel sind sortiert, Abschneiden endet mit ``...``."""
        if not state or self._max == 0:
            return ""
        lines = [f"{key}: {_render_value(state[key])}" for key in sorted(state, key=str)]
        text = "\n".join(lines)
        if len(text) <= self._max:
            return text
        if self._max <= 3:
            return text[: self._max]
        return text[: self._max - 3] + "..."


@dataclass(frozen=True)
class EpisodeHit:
    """Ein Treffer der Gedächtnissuche. Höherer ``score`` ist relevanter."""

    memory_id: str
    session_id: str
    category: str
    content: str
    score: float
    created_at_ms: int


_SCHEMA_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS episodic_memories (
    memory_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodic_session_category ON episodic_memories(session_id, category);
"""

_FTS_SQL: Final[str] = """
CREATE VIRTUAL TABLE IF NOT EXISTS episodic_memories_fts USING fts5(
    memory_id UNINDEXED,
    content,
    tokenize='porter unicode61'
);
"""


class EpisodicMemoryStore:
    """Episodisches Gedächtnis in SQLite.

    Mit ``prefer_fts=False`` wird der BM25-Fallback erzwungen, auch wenn FTS5
    verfügbar wäre. Er bewertet ohne Porter-Stemming, sonst identisch.
    """

    def __init__(self, db_path: str | Path = ":memory:", *, prefer_fts: bool = True) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        self._fts = False
        if prefer_fts:
            try:
                self._conn.executescript(_FTS_SQL)
                self._fts = True
            except sqlite3.OperationalError:
                self._fts = False
        self._conn.commit()

    @property
    def uses_fts(self) -> bool:
        """``True``, wenn die Suche über FTS5 läuft, ``False`` beim BM25-Fallback."""
        return self._fts

    def store_episode(
        self,
        *,
        session_id: str,
        category: str,
        content: str,
        tags: Sequence[str] = (),
        memory_id: str | None = None,
        created_at_ms: int | None = None,
    ) -> str:
        """Speichert eine Episode. Existiert ``memory_id`` bereits, bleibt der Bestand unverändert (idempotent)."""
        mid = memory_id or uuid.uuid4().hex
        stamp = int(created_at_ms if created_at_ms is not None else time.time() * 1000)
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO episodic_memories (memory_id, session_id, category, content, tags, created_at_ms) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(memory_id) DO NOTHING",
                (mid, session_id, category, content, json.dumps(list(tags), ensure_ascii=False), stamp),
            )
            if cursor.rowcount == 1 and self._fts:
                self._conn.execute(
                    "INSERT INTO episodic_memories_fts (memory_id, content) VALUES (?, ?)",
                    (mid, content),
                )
            self._conn.commit()
        return mid

    def has_episode(self, memory_id: str) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM episodic_memories WHERE memory_id = ?", (memory_id,)).fetchone()
        return row is not None

    def recall(
        self,
        query: str,
        *,
        top_k: int = 5,
        session_id: str | None = None,
        category: str | None = None,
    ) -> list[EpisodeHit]:
        """Sucht Episoden nach Relevanz. Sonderzeichen in ``query`` sind unschädlich."""
        if top_k <= 0:
            return []
        match = _sanitize_fts5_query(query)
        if not match:
            return []
        with self._lock:
            if self._fts:
                return self._recall_fts(match, top_k, session_id, category)
            return self._recall_bm25(_tokens(query), top_k, session_id, category)

    def _filters(self, session_id: str | None, category: str | None) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("m.session_id = ?")
            params.append(session_id)
        if category is not None:
            clauses.append("m.category = ?")
            params.append(category)
        return "".join(f" AND {clause}" for clause in clauses), params

    def _recall_fts(self, match: str, top_k: int, session_id: str | None, category: str | None) -> list[EpisodeHit]:
        extra, params = self._filters(session_id, category)
        sql = (
            "SELECT m.memory_id, m.session_id, m.category, m.content, m.created_at_ms, "
            "bm25(episodic_memories_fts) AS rank "
            "FROM episodic_memories_fts JOIN episodic_memories AS m ON m.memory_id = episodic_memories_fts.memory_id "
            "WHERE episodic_memories_fts MATCH ?" + extra + " ORDER BY rank, m.created_at_ms DESC, m.memory_id LIMIT ?"
        )
        rows = self._conn.execute(sql, [match, *params, top_k]).fetchall()
        # bm25() liefert kleinere Werte für bessere Treffer; der Score dreht das Vorzeichen um.
        return [
            EpisodeHit(
                memory_id=str(row["memory_id"]),
                session_id=str(row["session_id"]),
                category=str(row["category"]),
                content=str(row["content"]),
                score=-float(row["rank"]),
                created_at_ms=int(row["created_at_ms"]),
            )
            for row in rows
        ]

    def _recall_bm25(self, query_tokens: list[str], top_k: int, session_id: str | None, category: str | None) -> list[EpisodeHit]:
        extra, params = self._filters(session_id, category)
        sql = "SELECT m.memory_id, m.session_id, m.category, m.content, m.created_at_ms FROM episodic_memories AS m WHERE 1 = 1" + extra
        rows = self._conn.execute(sql, params).fetchall()
        if not rows:
            return []
        docs = [(row, Counter(_TOKEN_RE.findall(str(row["content"]).lower()))) for row in rows]
        doc_count = len(docs)
        avg_len = sum(sum(counts.values()) for _, counts in docs) / doc_count or 1.0
        doc_freq = {token: sum(1 for _, counts in docs if token in counts) for token in query_tokens}
        scored: list[tuple[float, Any]] = []
        for row, counts in docs:
            length = sum(counts.values())
            score = 0.0
            for token in query_tokens:
                freq = counts.get(token, 0)
                if freq == 0:
                    continue
                df = doc_freq[token]
                idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
                score += idf * freq * (_BM25_K1 + 1) / (freq + _BM25_K1 * (1 - _BM25_B + _BM25_B * length / avg_len))
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], -int(item[1]["created_at_ms"]), str(item[1]["memory_id"])))
        return [
            EpisodeHit(
                memory_id=str(row["memory_id"]),
                session_id=str(row["session_id"]),
                category=str(row["category"]),
                content=str(row["content"]),
                score=score,
                created_at_ms=int(row["created_at_ms"]),
            )
            for score, row in scored[:top_k]
        ]


def register_recall_tool(registry: ColdStorageRegistry, store: EpisodicMemoryStore) -> ToolSchema:
    """Registriert ``recall_episodic_memory`` als normales Ciel-Tool (Schema und Handler)."""

    async def _recall(arguments: Mapping[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", ""))
        top_k = int(arguments.get("top_k") or 5)
        session_id = arguments.get("session_id") or None
        category = arguments.get("category") or None
        hits = await asyncio.to_thread(
            store.recall,
            query,
            top_k=top_k,
            session_id=str(session_id) if session_id else None,
            category=str(category) if category else None,
        )
        return {
            "query": query,
            "hits": [
                {
                    "memory_id": hit.memory_id,
                    "session_id": hit.session_id,
                    "category": hit.category,
                    "content": hit.content,
                    "score": round(hit.score, 6),
                }
                for hit in hits
            ],
        }

    schema = {
        "name": RECALL_TOOL_NAME,
        "description": (
            "Durchsucht das episodische Gedächtnis nach früheren Episoden (Volltext, BM25-gewichtet). "
            "Args: query (str) Freitext; optional top_k (int), session_id (str), category (str)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Freitext-Suchanfrage."},
                "top_k": {"type": "integer", "description": "Maximale Trefferzahl (Standard 5)."},
                "session_id": {"type": "string", "description": "Optional: nur diese Session."},
                "category": {"type": "string", "description": "Optional: nur diese Kategorie."},
            },
            "required": ["query"],
        },
    }
    # Keine required_state_keys: "query" ist ein Tool-Argument, kein Zustandsschlüssel des Gates.
    return registry.register(schema, handler=_recall, required_state_keys=[], is_deterministic=True, timeout_sec=10.0)


__all__ = [
    "RECALL_TOOL_NAME",
    "EpisodeHit",
    "EpisodicMemoryStore",
    "WorkingMemoryPin",
    "register_recall_tool",
]
