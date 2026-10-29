"""Unveraenderliches Audit-Ledger: Hash-Kette ueber alle kritischen Aktionen.

Zwei Schutzschichten:

1. **Datenbank** -- Trigger verweigern ``UPDATE``/``DELETE`` (SQLite und Postgres,
   siehe ``sql/``). Das Ledger waechst nur.
2. **Kette** -- jede Zeile traegt ``prev_hash`` und ``entry_hash =
   sha256(prev_hash || kanonisches JSON der Zeile)``. Wer die Datei bzw. Tabelle
   an den Triggern vorbei manipuliert, bricht die Kette; ``verify_chain`` findet
   die erste kaputte Stelle.

Geheimnisse landen nie im Ledger: ``redact`` ersetzt Werte unter verdaechtigen
Schluesseln (token, secret, password, key ...) durch einen kurzen Hash-Fingerabdruck.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.protocol import utc_now_iso

from .models import AUDIT_CATEGORIES, AuditEntry

if TYPE_CHECKING:
    from .store import KanbanStore

__all__ = ["GENESIS_HASH", "AuditDraft", "AuditLedger", "compute_entry_hash", "redact", "verify_chain"]

GENESIS_HASH = "0" * 64

_SECRET_KEY = re.compile(r"(token|secret|password|passwd|api[_-]?key|private[_-]?key|credential|dsn)", re.IGNORECASE)


def fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact(payload: Any) -> Any:
    """Kopie von ``payload`` ohne Klartext-Geheimnisse (rekursiv)."""
    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if _SECRET_KEY.search(str(key)) and isinstance(value, str) and value:
                out[str(key)] = fingerprint(value)
            else:
                out[str(key)] = redact(value)
        return out
    if isinstance(payload, (list, tuple)):
        return [redact(v) for v in payload]
    return payload


@dataclass(frozen=True)
class AuditDraft:
    """Noch nicht verkettete Ledger-Zeile; der Store vergibt ``seq`` und Hashes."""

    actor: str
    action: str
    category: str
    subject: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.category not in AUDIT_CATEGORIES:
            raise ValueError(f"unbekannte Audit-Kategorie {self.category!r}")


def _canonical(data: Mapping[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_entry_hash(prev_hash: str, draft: AuditDraft) -> str:
    body = _canonical(
        {
            "ts": draft.ts,
            "actor": draft.actor,
            "action": draft.action,
            "category": draft.category,
            "subject": draft.subject,
            "payload": draft.payload,
        }
    )
    return hashlib.sha256(prev_hash.encode("ascii") + body).hexdigest()


def seal(prev_hash: str, draft: AuditDraft) -> tuple[AuditDraft, str]:
    """Redigiert die Nutzlast und berechnet den Hash -- Store-Seite, in der Transaktion."""
    clean = AuditDraft(
        actor=draft.actor,
        action=draft.action,
        category=draft.category,
        subject=draft.subject,
        payload=redact(dict(draft.payload)),
        ts=draft.ts,
    )
    return clean, compute_entry_hash(prev_hash, clean)


def verify_chain(entries: Iterable[AuditEntry]) -> list[str]:
    """Prueft die Kette lueckenlos; leere Liste == intakt."""
    errors: list[str] = []
    prev = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != prev:
            errors.append(f"seq {entry.seq}: prev_hash passt nicht zur Vorgaengerzeile")
        draft = AuditDraft(
            actor=entry.actor,
            action=entry.action,
            category=entry.category,
            subject=entry.subject,
            payload=entry.payload,
            ts=entry.ts,
        )
        if compute_entry_hash(entry.prev_hash, draft) != entry.entry_hash:
            errors.append(f"seq {entry.seq}: entry_hash stimmt nicht (Zeile veraendert)")
        prev = entry.entry_hash
    return errors


class AuditLedger:
    """Duenne Fassade ueber dem Store -- der Store garantiert die Atomaritaet."""

    def __init__(self, store: KanbanStore) -> None:
        self._store = store

    async def append(
        self,
        *,
        actor: str,
        action: str,
        category: str,
        subject: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEntry:
        draft = AuditDraft(actor=actor, action=action, category=category, subject=subject, payload=dict(payload or {}))
        return await self._store.append_audit(draft)

    async def entries(self, *, after_seq: int = 0, limit: int = 10_000) -> list[AuditEntry]:
        return await self._store.list_audit(after_seq=after_seq, limit=limit)

    async def verify(self) -> list[str]:
        return verify_chain(await self._store.list_audit(after_seq=0, limit=10**9))
