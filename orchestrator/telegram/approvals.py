"""Freigaben: Vorschlaege erst nach Klick senden, Orchestrator-Anfragen entscheiden.

Vorschlag und Orchestrator-Anfrage sind getrennte Entitaeten (im Original ein Dict,
das Approve schickte an Peer 0). Ein Doppelklick sendet einmal: Sperre pro Ziel plus
CAS ``pending -> sending``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import urllib.request
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from core.protocol import format_timestamp, parse_timestamp, utc_now_iso
from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.models import new_id

from .client import TelegramFloodWait, TelegramPort
from .config import TelegramConfig
from .llm import no_redirect_opener
from .models import ApprovalRequest, ApprovalStatus, Suggestion, SuggestionStatus
from .router import Emit, safe_emit, target_allowed
from .store import TelegramStore

__all__ = ["Approvals", "Conflict", "NotAllowed", "RateLimited", "SuggestionNotFound"]

logger = logging.getLogger(__name__)

Poster = Callable[[str, Mapping[str, Any]], Awaitable[None]]

_RATE_WINDOW = timedelta(hours=1)
_TITLE_MAX = 200
_DETAIL_MAX = 2000
_AUDIT_TEXT_MAX = 500
_CALLBACK_TIMEOUT_S = 10.0


class SuggestionNotFound(LookupError):
    pass


class NotAllowed(Exception):
    pass


class Conflict(Exception):
    """Zustand passt nicht (mehr), z. B. schon entschieden."""


class RateLimited(Exception):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"Sendelimit erreicht, erneut in {retry_after_s} s")
        self.retry_after_s = retry_after_s


def _callback_ok(url: str, allowlist: tuple[str, ...]) -> bool:
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    # Userinfo und Backslashes parsen Clients unterschiedlich: nie akzeptieren.
    if parts.scheme not in ("http", "https") or not host or "@" in parts.netloc or "\\" in url:
        return False
    return host.lower() in {item.lower() for item in allowlist}


def _post_json(url: str, payload: bytes) -> None:
    # Keine Redirects und kein Env-Proxy: sonst verlaesst der Callback die geprueften Hosts.
    opener = no_redirect_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with opener.open(request, timeout=_CALLBACK_TIMEOUT_S):
        pass


async def _default_poster(url: str, payload: Mapping[str, Any]) -> None:
    await asyncio.to_thread(_post_json, url, json.dumps(payload).encode("utf-8"))


class Approvals:
    def __init__(
        self,
        store: TelegramStore,
        client: TelegramPort,
        config: TelegramConfig,
        *,
        ledger: AuditLedger | None = None,
        clock: Callable[[], str] = utc_now_iso,
        poster: Poster | None = None,
        emit: Emit | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._config = config
        self._ledger = ledger
        self._clock = clock
        self._poster = poster or _default_poster
        self._emit = emit
        self._target_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _audit(self, actor: str, action: str, category: str, subject: str, payload: Mapping[str, Any]) -> None:
        if self._ledger is not None:
            await self._ledger.append(actor=actor, action=action, category=category, subject=subject, payload=payload)

    async def _load(self, sid: str) -> Suggestion:
        suggestion = await self._store.get_suggestion(sid)
        if suggestion is None:
            raise SuggestionNotFound(sid)
        return suggestion

    async def _check_rate(self, target: int) -> None:
        now = parse_timestamp(self._clock(), "clock")
        sends = await self._store.send_times_since(target, format_timestamp(now - _RATE_WINDOW))
        over = len(sends) - self._config.send_rate_per_hour
        if over >= 0:
            # Erst wenn dieser Versand aus dem Fenster faellt, ist wieder Platz.
            free_at = parse_timestamp(sends[over], "sends.ts") + _RATE_WINDOW
            raise RateLimited(max(1, math.ceil((free_at - now).total_seconds())))

    async def _mark_failed(self, suggestion: Suggestion, exc: BaseException, actor: str) -> Suggestion:
        error = f"{type(exc).__name__}: {str(exc)[:200]}"
        failed = await self._store.cas_suggestion(
            suggestion.id,
            SuggestionStatus.SENDING,
            {"status": SuggestionStatus.FAILED, "decided_at": self._clock(), "error": error},
        )
        await self._audit(
            actor,
            "telegram.send_failed",
            "trading",
            suggestion.id,
            {"suggestion_id": suggestion.id, "target_peer": suggestion.target_peer, "error": error},
        )
        return failed or suggestion

    async def approve(self, sid: str, *, actor: str) -> Suggestion:
        """Sendet den Vorschlag nach dem Klick des Operators.

        ``TelegramFloodWait`` wird nach dem Markieren als ``failed`` weitergeworfen, weil
        der Aufrufer die Wartezeit braucht; andere Sendefehler liefern die ``failed``-Suggestion.
        """
        suggestion = await self._load(sid)
        if suggestion.status is not SuggestionStatus.PENDING:
            raise Conflict(f"Status {suggestion.status.value}")
        target = suggestion.target_peer
        if not await target_allowed(self._store, self._config, target):
            await self._audit(actor, "telegram.send_refused", "trading", sid, {"suggestion_id": sid, "target_peer": target})
            raise NotAllowed(str(target))

        async with self._target_locks[target]:
            await self._check_rate(target)
            sending = await self._store.cas_suggestion(sid, SuggestionStatus.PENDING, {"status": SuggestionStatus.SENDING})
            if sending is None:
                raise Conflict("Status geaendert")
            try:
                await self._client.send(target, sending.text)
            except asyncio.CancelledError as exc:
                await self._mark_failed(sending, exc, actor)
                raise
            except TelegramFloodWait as exc:
                await self._mark_failed(sending, exc, actor)
                raise
            except Exception as exc:
                failed = await self._mark_failed(sending, exc, actor)
                await safe_emit(self._emit, "suggestion", failed.to_dict())
                return failed
            # Ab hier ist die Nachricht draussen: nichts darf sie wieder auf ``failed`` setzen.
            now = self._clock()
            await self._store.record_send(target, now)
            sent = await self._store.cas_suggestion(sid, SuggestionStatus.SENDING, {"status": SuggestionStatus.SENT, "decided_at": now})
        await self._audit(
            actor,
            "telegram.sent",
            "trading",
            sid,
            {"suggestion_id": sid, "target_peer": target, "origin": sending.origin, "text": sending.text[:_AUDIT_TEXT_MAX]},
        )
        result = sent or sending
        await safe_emit(self._emit, "suggestion", result.to_dict())
        return result

    async def retry(self, sid: str) -> Suggestion:
        await self._load(sid)
        pending = await self._store.cas_suggestion(sid, SuggestionStatus.FAILED, {"status": SuggestionStatus.PENDING, "error": None})
        if pending is None:
            raise Conflict("Nur fehlgeschlagene Vorschlaege lassen sich wiederholen")
        await safe_emit(self._emit, "suggestion", pending.to_dict())
        return pending

    async def dismiss(self, sid: str) -> Suggestion:
        suggestion = await self._load(sid)
        if suggestion.status not in (SuggestionStatus.PENDING, SuggestionStatus.FAILED):
            raise Conflict(f"Status {suggestion.status.value}")
        dismissed = await self._store.cas_suggestion(
            sid, suggestion.status, {"status": SuggestionStatus.DISMISSED, "decided_at": self._clock()}
        )
        if dismissed is None:
            raise Conflict("Status geaendert")
        await safe_emit(self._emit, "suggestion", dismissed.to_dict())
        return dismissed

    # -- Orchestrator-Freigaben ------------------------------------------- #
    async def request(
        self,
        title: str,
        detail: str,
        *,
        request_id: str | None = None,
        callback_url: str | None = None,
    ) -> ApprovalRequest:
        title = title.strip()
        if not 1 <= len(title) <= _TITLE_MAX:
            raise ValueError(f"title muss 1..{_TITLE_MAX} Zeichen haben")
        if len(detail) > _DETAIL_MAX:
            raise ValueError(f"detail darf hoechstens {_DETAIL_MAX} Zeichen haben")
        if callback_url is not None and not _callback_ok(callback_url, self._config.callback_allowlist):
            raise ValueError("callback_url nicht erlaubt")
        approval = ApprovalRequest(
            id=new_id("appr"),
            request_id=request_id,
            title=title,
            detail=detail,
            status=ApprovalStatus.PENDING,
            created_at=self._clock(),
            decided_at=None,
            callback_url=callback_url,
        )
        await self._store.add_approval(approval)
        await self._audit(
            "telegram",
            "telegram.approval_requested",
            "system",
            approval.id,
            {"approval_id": approval.id, "request_id": request_id, "title": title},
        )
        await safe_emit(self._emit, "approval", approval.to_dict())
        return approval

    async def decide(self, approval_id: str, approved: bool, *, actor: str) -> ApprovalRequest:
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        decided = await self._store.cas_approval(approval_id, ApprovalStatus.PENDING, {"status": status, "decided_at": self._clock()})
        if decided is None:
            raise Conflict("Freigabe fehlt oder ist schon entschieden")
        await self._audit(
            actor,
            "telegram.approval_decided",
            "system",
            approval_id,
            {"approval_id": approval_id, "request_id": decided.request_id, "approved": approved},
        )
        await safe_emit(self._emit, "approval", decided.to_dict())
        await self._notify(decided)
        return decided

    async def _notify(self, approval: ApprovalRequest) -> None:
        """Best effort: der Orchestrator kann alternativ ``get`` pollen."""
        url = approval.callback_url
        if url is None:
            return
        if not _callback_ok(url, self._config.callback_allowlist):
            logger.warning("Callback fuer %s nicht mehr erlaubt", approval.id)
            return
        payload = {
            "request_id": approval.request_id or approval.id,
            "approval_id": approval.id,
            "approved": approval.status is ApprovalStatus.APPROVED,
            "decided_at": approval.decided_at,
        }
        try:
            await self._poster(url, payload)
        except Exception as exc:
            logger.warning("Callback fuer %s fehlgeschlagen: %s", approval.id, type(exc).__name__)

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        return await self._store.get_approval(approval_id)

    async def pending(self) -> list[ApprovalRequest]:
        return await self._store.list_approvals(ApprovalStatus.PENDING)
