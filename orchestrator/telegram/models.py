"""Datenmodelle für die Telegram-Integration.

Analog zum Kanban-Modul: reines Stdlib-Dataclass-Design, das für Serialisierung
die to_dict/from_dict-Methoden bereitstellt.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

__all__ = [
    "ALLOWED_APPROVAL_TRANSITIONS",
    "ALLOWED_SUGGESTION_TRANSITIONS",
    "EVIDENCE_MAX",
    "ApprovalRequest",
    "ApprovalStatus",
    "Direction",
    "InvalidTransitionError",
    "LoginState",
    "Signal",
    "Suggestion",
    "SuggestionStatus",
    "TgDialog",
    "TgMessage",
    "check_transition",
    "normalize_peer",
]

EVIDENCE_MAX = 500


def normalize_peer(peer: int | str) -> int | str:
    """Kanonische Peer-Form: numerische IDs als ``int``, Usernames als ``@name`` klein.

    Telethon braucht numerische IDs als ``int`` (``str(int)`` wird als Username
    aufgeloest) und Usernames sind case-insensitiv. Allowlist, Store und Client
    vergleichen deshalb immer die normalisierte Form.
    """
    if isinstance(peer, bool):
        raise ValueError("Ungueltiger Peer")
    if isinstance(peer, int):
        return peer
    raw = str(peer).strip()
    if not raw:
        raise ValueError("Leerer Peer")
    try:
        return int(raw)
    except ValueError:
        pass
    name = raw.lower()
    return name if name.startswith("@") else f"@{name}"


class LoginState(StrEnum):
    UNCONFIGURED = "unconfigured"
    DISCONNECTED = "disconnected"
    CODE_SENT = "code_sent"
    NEEDS_PASSWORD = "needs_password"
    AUTHORIZED = "authorized"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    DISMISSED = "dismissed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Direction(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class TgDialog:
    id: int
    name: str
    kind: Literal["user", "group", "channel"]
    is_bot: bool
    unread: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TgDialog:
        return cls(**data)


@dataclass
class TgMessage:
    peer: int
    msg_id: int
    sender: str
    text: str
    ts: str
    outgoing: bool
    is_bot: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TgMessage:
        return cls(**data)


@dataclass
class Suggestion:
    id: str
    source_peer: int
    target_peer: int
    text: str
    based_on_msg_id: int | None
    origin: Literal["llm", "rules"]
    status: SuggestionStatus
    created_at: str
    decided_at: str | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Suggestion:
        d = data.copy()
        if "status" in d:
            d["status"] = SuggestionStatus(d["status"])
        return cls(**d)


@dataclass
class ApprovalRequest:
    id: str
    request_id: str | None
    title: str
    detail: str
    status: ApprovalStatus
    created_at: str
    decided_at: str | None
    callback_url: str | None

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        d = data.copy()
        if "status" in d:
            d["status"] = ApprovalStatus(d["status"])
        return cls(**d)


@dataclass
class Signal:
    id: str
    symbol: str
    direction: Direction
    strength: int
    peer: int
    msg_id: int
    evidence: str
    created_at: str
    kanban_task_id: str | None

    def __post_init__(self) -> None:
        if not 0 <= self.strength <= 10:
            raise ValueError("strength muss in 0..10 liegen")
        if len(self.evidence) > EVIDENCE_MAX:
            self.evidence = self.evidence[:EVIDENCE_MAX]

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["direction"] = self.direction.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Signal:
        d = data.copy()
        if "direction" in d:
            d["direction"] = Direction(d["direction"])
        return cls(**d)


ALLOWED_SUGGESTION_TRANSITIONS: dict[SuggestionStatus, set[SuggestionStatus]] = {
    SuggestionStatus.PENDING: {SuggestionStatus.SENDING, SuggestionStatus.DISMISSED},
    SuggestionStatus.SENDING: {SuggestionStatus.SENT, SuggestionStatus.FAILED},
    SuggestionStatus.FAILED: {SuggestionStatus.PENDING, SuggestionStatus.DISMISSED},
}

ALLOWED_APPROVAL_TRANSITIONS: dict[ApprovalStatus, set[ApprovalStatus]] = {
    ApprovalStatus.PENDING: {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED},
}


class InvalidTransitionError(ValueError):
    """Fehler bei einem ungueltigen Zustandsuebergang."""


def check_transition(kind: Literal["suggestion", "approval"], current: Any, target: Any) -> None:
    table: dict[Any, set[Any]]
    if kind == "suggestion":
        table, label = dict(ALLOWED_SUGGESTION_TRANSITIONS), "Suggestion"
    elif kind == "approval":
        table, label = dict(ALLOWED_APPROVAL_TRANSITIONS), "Approval"
    else:
        raise ValueError(f"Unbekannte Transition-Art: {kind}")
    if target not in table.get(current, set()):
        raise InvalidTransitionError(f"Ungueltiger Uebergang fuer {label}: {current} -> {target}")
