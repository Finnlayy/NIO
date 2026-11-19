"""Modul E: Micro-Compaction älterer Tool-Ergebnisse (NIO Phase 5).

Ältere ``role=="tool"``-Nachrichten, die über der Byte-Schwelle liegen, werden
im LLM-Kontext durch ein kleines Receipt-JSON ersetzt. ``tool_call_id`` und
``role`` bleiben unverändert. Das Original liegt im Blob-Store unter
``nio:blob:{sid}:{tool_call_id}`` und ist über das Meta-Tool ``fetch_blob``
verlustfrei zurückholbar.

Die Kompaktion wirkt nur auf die LLM-Sicht (Kopie der Verlaufsliste). Der
gespeicherte Verlauf bleibt vollständig, damit DAG-Checkpoints konsistent
bleiben und die Kompaktion beliebig oft idempotent wiederholbar ist.

Stdlib-only. Redis-Anbindung über :class:`RedisBlobStore` (``redis.asyncio``-Client
mit ``get``/``set`` oder :class:`orchestrator.kanban.redis_resp.RedisClient` mit
``execute``); ohne Redis gilt :class:`DictBlobStore` mit identischer Semantik.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, Protocol

#: Kennzeichen eines Receipts. Dient zur Erkennung bereits kompaktierter Nachrichten.
RECEIPT_MARKER: Final[str] = "nio.compacted/v1"

#: Präfix aller Blob-Schlüssel.
BLOB_PREFIX: Final[str] = "nio:blob:"

#: Name des Meta-Tools zum Zurückholen eines Blobs (TIER_0: rein lesend, nur Session-Scope).
FETCH_BLOB_TOOL_NAME: Final[str] = "fetch_blob"

#: Schema des Meta-Tools ``fetch_blob``.
FETCH_BLOB_SCHEMA: Final[dict[str, Any]] = {
    "name": FETCH_BLOB_TOOL_NAME,
    "description": (
        "Holt das vollständige Original eines zuvor kompaktierten Tool-Ergebnisses zurück. "
        "Args: blob_ref (str) — der Wert 'blob_ref' aus dem Receipt. Liefert den unveränderten Inhalt."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "blob_ref": {"type": "string", "description": "Blob-Referenz aus dem Receipt, z. B. nio:blob:<sid>:<call_id>."},
        },
        "required": ["blob_ref"],
    },
}

#: Maximale Länge einzelner Textwerte im Receipt (Zeichen).
_MAX_VALUE_CHARS: Final[int] = 200
#: Maximale Länge der Vorschau bei Nicht-JSON-Ergebnissen (Zeichen).
_PREVIEW_CHARS: Final[int] = 120
#: Skalare Schlüssel, die aus einem JSON-Objekt in das Receipt übernommen werden.
_SCALAR_KEYS: Final[tuple[str, ...]] = ("status", "ok", "error", "count", "symbol", "price")


class BlobStore(Protocol):
    """Asynchroner Schlüssel-Wert-Speicher für Originale kompaktierter Ergebnisse."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str) -> None: ...


class DictBlobStore:
    """In-Memory-Blob-Store (Default, Tests ohne Redis)."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)


class RedisBlobStore:
    """Redis-Adapter. Akzeptiert ``redis.asyncio``-ähnliche Clients (``get``/``set``) oder ``execute``-Clients."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        if hasattr(self._client, "execute"):
            raw = await self._client.execute("GET", key)
        else:
            raw = await self._client.get(key)
        if raw is None:
            return None
        return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

    async def set(self, key: str, value: str) -> None:
        if hasattr(self._client, "execute"):
            await self._client.execute("SET", key, value)
        else:
            await self._client.set(key, value)


def blob_key(session_id: str, tool_call_id: str) -> str:
    """Schlüssel eines Blobs: ``nio:blob:{sid}:{tool_call_id}``."""
    return f"{BLOB_PREFIX}{session_id}:{tool_call_id}"


def is_receipt(content: str) -> bool:
    """True, wenn ``content`` bereits ein Receipt dieser Schicht ist."""
    if not content.startswith('{"_receipt"'):
        return False
    try:
        data = json.loads(content)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("_receipt") == RECEIPT_MARKER


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_VALUE_CHARS:
        return value[:_MAX_VALUE_CHARS] + "…"
    return value


def extract_structured(data: Any) -> dict[str, Any]:
    """Strukturierte Extraktion: Skalare (status/ok/error/count/symbol/price) und ``<key>_count`` für Listen."""
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for key in _SCALAR_KEYS:
            value = data.get(key)
            if isinstance(value, (str, int, float, bool)):
                out[key] = _clip(value)
        for key, value in data.items():
            if isinstance(value, list):
                out[f"{key}_count"] = len(value)
    elif isinstance(data, list):
        out["count"] = len(data)
    return out


def build_receipt(*, name: str, content: str, blob_ref: str) -> str:
    """Erzeugt das Receipt-JSON für ein kompaktiertes Ergebnis (kompakt, deterministisch sortiert)."""
    raw_bytes = len(content.encode("utf-8"))
    try:
        parsed: Any = json.loads(content)
        is_json = True
    except ValueError:
        parsed = None
        is_json = False
    receipt: dict[str, Any] = {
        "_receipt": RECEIPT_MARKER,
        "blob_ref": blob_ref,
        "bytes": raw_bytes,
        "json": is_json,
        "tool": name,
    }
    if is_json:
        receipt.update(extract_structured(parsed))
    else:
        receipt["preview"] = content[:_PREVIEW_CHARS]
    return json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fetch_blob_allowed(blob_ref: str, session_id: str) -> bool:
    """Blob-Referenzen sind auf die eigene Session beschränkt (kein Zugriff auf fremde Sessions)."""
    return isinstance(blob_ref, str) and blob_ref.startswith(f"{BLOB_PREFIX}{session_id}:")


class MicroCompactor:
    """Ersetzt ältere, große Tool-Ergebnisse durch Receipts.

    * ``byte_threshold``: Nachrichten bis zu dieser UTF-8-Größe bleiben unverändert.
    * ``keep_recent_tool_turns``: so viele zuletzt ausgeführte Tool-Turns bleiben vollständig.
    """

    def __init__(
        self,
        *,
        byte_threshold: int = 1024,
        keep_recent_tool_turns: int = 1,
        blob_store: BlobStore | None = None,
    ) -> None:
        if byte_threshold < 0:
            raise ValueError("byte_threshold darf nicht negativ sein.")
        if keep_recent_tool_turns < 0:
            raise ValueError("keep_recent_tool_turns darf nicht negativ sein.")
        self._threshold = byte_threshold
        self._keep = keep_recent_tool_turns
        self._blobs: BlobStore = blob_store if blob_store is not None else DictBlobStore()

    @property
    def blob_store(self) -> BlobStore:
        return self._blobs

    @property
    def byte_threshold(self) -> int:
        return self._threshold

    async def compact(self, messages: Sequence[Mapping[str, Any]], *, session_id: str) -> list[dict[str, Any]]:
        """Liefert eine kompaktierte Kopie der Nachrichten. Die Eingabe bleibt unverändert."""
        copies = [dict(m) for m in messages]
        owners = self._owner_turns(copies)
        last_turn = max(owners.values(), default=-1)
        cutoff = last_turn - self._keep + 1
        for idx, message in enumerate(copies):
            if message.get("role") != "tool":
                continue
            if owners.get(idx, -1) >= cutoff:
                continue
            content = message.get("content")
            if not isinstance(content, str) or is_receipt(content):
                continue
            if len(content.encode("utf-8")) <= self._threshold:
                continue
            tool_call_id = str(message.get("tool_call_id") or f"idx{idx}")
            key = blob_key(session_id, tool_call_id)
            if await self._blobs.get(key) is None:
                await self._blobs.set(key, content)
            message["content"] = build_receipt(name=str(message.get("name", "")), content=content, blob_ref=key)
        return copies

    @staticmethod
    def _owner_turns(messages: Sequence[Mapping[str, Any]]) -> dict[int, int]:
        """Ordnet jeder Tool-Nachricht den Index ihres Assistant-Turns zu (-1 ohne Assistant davor)."""
        owners: dict[int, int] = {}
        turn = -1
        for idx, message in enumerate(messages):
            role = message.get("role")
            if role == "assistant":
                turn += 1
            elif role == "tool":
                owners[idx] = turn
        return owners


async def fetch_blob(store: BlobStore, blob_ref: str, *, session_id: str) -> str | None:
    """Holt ein Original aus dem Blob-Store. ``None``, wenn die Referenz fremd oder unbekannt ist."""
    if not fetch_blob_allowed(blob_ref, session_id):
        return None
    return await store.get(blob_ref)


__all__ = [
    "BLOB_PREFIX",
    "FETCH_BLOB_SCHEMA",
    "FETCH_BLOB_TOOL_NAME",
    "RECEIPT_MARKER",
    "BlobStore",
    "DictBlobStore",
    "MicroCompactor",
    "RedisBlobStore",
    "blob_key",
    "build_receipt",
    "extract_structured",
    "fetch_blob",
    "fetch_blob_allowed",
    "is_receipt",
]
