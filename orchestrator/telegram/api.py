"""FastAPI-Routen ``/api/v1/telegram/*`` (Adapter, Extra ``kanban``).

Wird nur lazy aus ``orchestrator/kanban/api.build_app`` geladen und erbt dessen
Operator-Bearer: jede Route verlangt ihn, ohne Token antwortet die API mit 503.
Login gibt es hier bewusst nicht; Code und 2FA-Passwort laufen nur ueber die CLI.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .approvals import Conflict, NotAllowed, RateLimited, SuggestionNotFound
from .client import TelegramFloodWait, TelegramNotAuthorized, TelegramUnavailable
from .intel import ask
from .models import ApprovalStatus, SuggestionStatus
from .runtime import TelegramRuntime

__all__ = ["build_telegram_router", "sse_frames"]

_T = TypeVar("_T")

_KEEPALIVE_S = 15.0
_LIMIT_MAX = 500


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PeerIn(_In):
    peer: int | str


class PairingIn(_In):
    source: int | str
    target: int | str


class AskIn(_In):
    question: str = Field(min_length=1, max_length=2000)
    peers: list[int] | None = None
    limit: int = Field(default=30, ge=1, le=200)


class ApprovalIn(_In):
    title: str
    detail: str = ""
    request_id: str | None = None
    callback_url: str | None = None


class DecideIn(_In):
    approved: bool


def _too_many(detail: str, seconds: int) -> JSONResponse:
    return JSONResponse({"detail": detail, "retry_after_s": seconds}, status_code=429, headers={"Retry-After": str(seconds)})


async def _guarded(call: Awaitable[_T]) -> _T | JSONResponse:
    """Uebersetzt Fachfehler in HTTP; 429 traegt ``Retry-After``."""
    try:
        return await call
    except SuggestionNotFound as e:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden") from e
    except NotAllowed as e:
        raise HTTPException(status_code=403, detail="Ziel nicht in der Allowlist") from e
    except Conflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RateLimited as e:
        return _too_many(str(e), e.retry_after_s)
    except TelegramFloodWait as e:
        return _too_many(str(e), e.seconds)
    except TelegramNotAuthorized as e:
        raise HTTPException(status_code=409, detail="Telegram nicht eingeloggt: neu telegram login") from e
    except TelegramUnavailable as e:
        raise HTTPException(status_code=503, detail="Extra 'telegram' fehlt") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


async def sse_frames(tg: TelegramRuntime, keepalive_s: float = _KEEPALIVE_S) -> AsyncIterator[str]:
    async for item in tg.hub.subscribe(keepalive_s):
        if item is None:
            yield ": keepalive\n\n"
        else:
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"


def build_telegram_router(tg: TelegramRuntime, operator: Callable[..., str]) -> APIRouter:
    router = APIRouter(prefix="/telegram", dependencies=[Depends(operator)])

    # -- Status + Chats --
    @router.get("/status")
    async def status() -> dict[str, Any]:
        return await tg.status()

    @router.get("/dialogs")
    async def dialogs() -> Any:
        async def _do() -> list[dict[str, Any]]:
            await tg.connect()
            return [d.to_dict() for d in await tg.client.dialogs()]

        return await _guarded(_do())

    @router.get("/messages")
    async def messages(peer: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        peers = None if peer is None else [peer]
        return [m.to_dict() for m in await tg.store.recent_messages(peers, min(limit, _LIMIT_MAX))]

    # -- Monitor, Pairing, Allowlist --
    @router.get("/monitored")
    async def monitored() -> list[int]:
        return await tg.store.list_monitored()

    @router.post("/monitored")
    async def add_monitored(body: PeerIn, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, int]:
            await tg.connect()
            return {"peer": await tg.monitor(body.peer, actor=actor)}

        return await _guarded(_do())

    @router.delete("/monitored/{peer}")
    async def remove_monitored(peer: str, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, int]:
            return {"peer": await tg.unmonitor(peer, actor=actor)}

        return await _guarded(_do())

    @router.get("/pairings")
    async def pairings() -> list[dict[str, int]]:
        return [{"source": s, "target": t} for s, t in (await tg.store.list_pairings()).items()]

    @router.post("/pairings")
    async def add_pairing(body: PairingIn, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, int]:
            await tg.connect()
            source, target = await tg.pair(body.source, body.target, actor=actor)
            return {"source": source, "target": target}

        return await _guarded(_do())

    @router.delete("/pairings/{source}")
    async def remove_pairing(source: str, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, int]:
            return {"source": await tg.unpair(source, actor=actor)}

        return await _guarded(_do())

    @router.get("/allowlist")
    async def allowlist() -> dict[str, list[int | str]]:
        return {"store": await tg.store.list_allowed(), "env": list(tg.config.send_allowlist)}

    @router.post("/allowlist")
    async def add_allowed(body: PeerIn, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, int]:
            await tg.connect()
            return {"peer": await tg.allow(body.peer, actor=actor)}

        return await _guarded(_do())

    @router.delete("/allowlist/{peer}")
    async def remove_allowed(peer: str, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, int | str]:
            return {"peer": await tg.disallow(peer, actor=actor)}

        return await _guarded(_do())

    # -- Vorschlaege --
    @router.get("/suggestions")
    async def suggestions(status: SuggestionStatus | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return [s.to_dict() for s in await tg.store.list_suggestions(status, min(limit, _LIMIT_MAX))]

    @router.post("/suggestions/{sid}/approve")
    async def approve(sid: str, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, Any]:
            await tg.connect()
            return (await tg.approvals.approve(sid, actor=actor)).to_dict()

        return await _guarded(_do())

    @router.post("/suggestions/{sid}/dismiss")
    async def dismiss(sid: str) -> Any:
        async def _do() -> dict[str, Any]:
            return (await tg.approvals.dismiss(sid)).to_dict()

        return await _guarded(_do())

    @router.post("/suggestions/{sid}/retry")
    async def retry(sid: str) -> Any:
        async def _do() -> dict[str, Any]:
            return (await tg.approvals.retry(sid)).to_dict()

        return await _guarded(_do())

    # -- Orchestrator-Freigaben --
    @router.get("/approvals")
    async def approvals(status: ApprovalStatus | None = None) -> list[dict[str, Any]]:
        return [a.to_dict() for a in await tg.store.list_approvals(status)]

    @router.post("/approvals")
    async def request_approval(body: ApprovalIn) -> Any:
        async def _do() -> dict[str, Any]:
            approval = await tg.approvals.request(body.title, body.detail, request_id=body.request_id, callback_url=body.callback_url)
            return approval.to_dict()

        return await _guarded(_do())

    @router.get("/approvals/{approval_id}")
    async def poll_approval(approval_id: str) -> dict[str, Any]:
        approval = await tg.approvals.get(approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Freigabe nicht gefunden")
        return approval.to_dict()

    @router.post("/approvals/{approval_id}/decide")
    async def decide(approval_id: str, body: DecideIn, actor: str = Depends(operator)) -> Any:
        async def _do() -> dict[str, Any]:
            return (await tg.approvals.decide(approval_id, body.approved, actor=actor)).to_dict()

        return await _guarded(_do())

    # -- Intel --
    @router.post("/ask")
    async def post_ask(body: AskIn) -> dict[str, Any]:
        await tg.symbols.ensure()
        return await ask(body.question, store=tg.store, symbols=tg.symbols, llm=tg.llm, peers=body.peers, limit=body.limit)

    @router.get("/signals")
    async def signals(limit: int = 100, symbol: str | None = None) -> list[dict[str, Any]]:
        return [s.to_dict() for s in await tg.store.list_signals(min(limit, _LIMIT_MAX), symbol)]

    @router.get("/gather")
    async def gather() -> dict[str, Any]:
        return tg.gather.status()

    @router.post("/gather/run")
    async def gather_run() -> Any:
        async def _do() -> dict[str, Any]:
            await tg.connect()
            await tg.symbols.ensure()
            return (await tg.gather.tick()).to_dict()

        return await _guarded(_do())

    # -- Live --
    @router.get("/events")
    async def events() -> StreamingResponse:
        headers = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        return StreamingResponse(sse_frames(tg), media_type="text/event-stream", headers=headers)

    return router
