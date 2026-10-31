"""FastAPI-Schicht fuer das Hermes-Kanban (Adapter, Extra ``kanban``).

Dieses Modul importiert ``fastapi``/``pydantic`` auf Modulebene und wird deshalb
nur lazy geladen (``neu kanban serve``) -- der stdlib-Kern importiert es nie.

Zwei Authentifizierungen: Operator-Routen verlangen ``NIO_KANBAN_API_TOKEN`` als
Bearer (ohne gesetztes Token antwortet die API mit 503 statt offen zu sein), die
Tool-Routen verlangen ein kurzlebiges Task-Token aus dem ``TokenStore``.

Die ``*Out``-Modelle spiegeln die Dataclasses aus ``models.py`` Feld fuer Feld;
``tests/test_kanban_api.py`` prueft diese Paritaet.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from core.atomic import atomic_write_bytes
from orchestrator.kanban.models import RustLimb, RustLimbRequest, RustLimbResponse, TaskStatus, TransitionError
from orchestrator.kanban.runtime import KanbanRuntime
from orchestrator.kanban.service import ConflictError
from orchestrator.kanban.tools import TOOL_DEFINITIONS

__all__ = [
    "AuditEntryOut",
    "BoardOut",
    "ExperienceOut",
    "RustLimbOut",
    "TaskOut",
    "WorkerOut",
    "build_app",
]

_LIMB_TIMEOUT_S = 30.0


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoardOut(_Out):
    id: str
    name: str
    created_at: str


class TaskOut(_Out):
    id: str
    board_id: str
    title: str
    description: str
    status: str
    priority: int
    assigned_worker_uid: str | None
    parent_id: str | None
    dependencies: list[str]
    required_skills: list[str]
    is_rollup: bool
    attempts: int
    result_payload: dict[str, Any] | None
    block_reason: str
    workspace_repo: str | None
    created_at: str
    updated_at: str
    started_at: str | None


class WorkerOut(_Out):
    uid: str
    name: str
    skills: list[str]
    soul_md: str
    status: str
    fail_count: int
    breaker_open_until: str | None
    updated_at: str


class ExperienceOut(_Out):
    id: str
    worker_uid: str
    task_id: str
    summary: str
    lessons: list[str]
    skills_delta: list[str]
    outcome: str
    vault_synced: bool
    created_at: str


class AuditEntryOut(_Out):
    seq: int
    ts: str
    actor: str
    action: str
    category: str
    subject: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str


class RustLimbOut(_Out):
    name: str
    version: str
    contract_version: str
    endpoint: str


class RustLimbResponseOut(_Out):
    request_id: str
    ok: bool
    result: dict[str, Any] | None
    error: str | None


class BoardCreate(_Out):
    name: str


class TaskCreate(_Out):
    board_id: str
    title: str
    description: str = ""
    parent_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    priority: int = 0
    status: TaskStatus = TaskStatus.TRIAGE
    workspace_repo: str | None = None


class TransitionIn(_Out):
    target: TaskStatus
    reason: str = ""
    expected: TaskStatus | None = None


class WorkerCreate(_Out):
    uid: str
    name: str = ""
    skills: list[str] = Field(default_factory=list)
    soul_md: str = ""


class SpawnIn(_Out):
    task_id: str


class ToolCallIn(_Out):
    arguments: dict[str, Any] = Field(default_factory=dict)


class RustLimbRequestIn(_Out):
    request_id: str
    operation: str
    params: dict[str, Any] = Field(default_factory=dict)


def _limbs_path(runtime: KanbanRuntime) -> Path:
    return runtime.config.repo_root / "runtime" / "kanban" / "rust_limbs.json"


def _load_limbs(path: Path) -> dict[str, RustLimb]:
    if not path.exists():
        return {}
    return {d["name"]: RustLimb.from_dict(d) for d in json.loads(path.read_bytes())}


def _post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=_LIMB_TIMEOUT_S) as resp:
        data = json.loads(resp.read())
    if not isinstance(data, dict):
        raise ValueError("Limb-Antwort ist kein JSON-Objekt")
    return data


def build_app(runtime: KanbanRuntime) -> FastAPI:
    app = FastAPI(title="Hermes Kanban API", version="1.0")
    router = APIRouter(prefix="/api/v1")
    bearer = HTTPBearer(auto_error=False)

    def operator(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:  # noqa: B008
        expected = runtime.config.api_token
        if not expected:
            raise HTTPException(status_code=503, detail="NIO_KANBAN_API_TOKEN ist nicht gesetzt")
        if credentials is None or not hmac.compare_digest(credentials.credentials.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="ungueltiges Operator-Token")
        return "operator"

    def task_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:  # noqa: B008
        if credentials is None or not credentials.credentials:
            raise HTTPException(status_code=401, detail="Task-Token fehlt")
        return credentials.credentials

    # -- Boards --
    @router.get("/kanban/boards", response_model=list[BoardOut])
    async def list_boards(actor: str = Depends(operator)) -> list[dict[str, Any]]:
        return [b.to_dict() for b in await runtime.store.list_boards()]

    @router.post("/kanban/boards", response_model=BoardOut)
    async def create_board(body: BoardCreate, actor: str = Depends(operator)) -> dict[str, Any]:
        return (await runtime.service.create_board(body.name, actor=actor)).to_dict()

    # -- Tasks --
    @router.get("/kanban/tasks", response_model=list[TaskOut])
    async def list_tasks(
        board_id: str | None = None,
        status: TaskStatus | None = None,
        parent_id: str | None = None,
        actor: str = Depends(operator),
    ) -> list[dict[str, Any]]:
        tasks = await runtime.store.list_tasks(board_id=board_id, status=status, parent_id=parent_id)
        return [t.to_dict() for t in tasks]

    @router.post("/kanban/tasks", response_model=TaskOut)
    async def create_task(body: TaskCreate, actor: str = Depends(operator)) -> dict[str, Any]:
        try:
            task = await runtime.service.create_task(
                board_id=body.board_id,
                title=body.title,
                description=body.description,
                parent_id=body.parent_id,
                dependencies=tuple(body.dependencies),
                required_skills=tuple(body.required_skills),
                priority=body.priority,
                status=body.status,
                workspace_repo=body.workspace_repo,
                actor=actor,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return task.to_dict()

    @router.get("/kanban/tasks/{task_id}")
    async def show_task(task_id: str, actor: str = Depends(operator)) -> dict[str, Any]:
        try:
            return await runtime.service.show(task_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @router.post("/kanban/tasks/{task_id}/transition", response_model=TaskOut)
    async def transition_task(task_id: str, body: TransitionIn, actor: str = Depends(operator)) -> dict[str, Any]:
        try:
            task = await runtime.service.transition(
                task_id, body.target, actor=actor, reason=body.reason, expected=body.expected
            )
        except ConflictError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except TransitionError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return task.to_dict()

    # -- Tools (Task-Token statt Operator-Token) --
    @router.get("/kanban/tools")
    async def list_tools() -> list[dict[str, Any]]:
        extra = list(runtime.telegram.toolbox.definitions) if runtime.telegram is not None else []
        return [*TOOL_DEFINITIONS, *extra]

    @router.post("/kanban/tools/{name}")
    async def call_tool(name: str, body: ToolCallIn, token: str = Depends(task_token)) -> dict[str, Any]:
        if await runtime.tokens.get(token) is None:
            raise HTTPException(status_code=401, detail="Task-Token ungueltig oder abgelaufen")
        try:
            if runtime.telegram is not None and runtime.telegram.toolbox.handles(name):
                return await runtime.telegram.toolbox.call(name, body.arguments)
            return await runtime.toolbox.call(name, body.arguments, token)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ConflictError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except (ValueError, TransitionError) as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    # -- Workers --
    @router.get("/workers", response_model=list[WorkerOut])
    async def list_workers(actor: str = Depends(operator)) -> list[dict[str, Any]]:
        return [w.to_dict() for w in await runtime.store.list_workers()]

    @router.post("/workers", response_model=WorkerOut)
    async def create_worker(body: WorkerCreate, actor: str = Depends(operator)) -> dict[str, Any]:
        try:
            worker = await runtime.service.create_worker(
                uid=body.uid, name=body.name or body.uid, skills=list(body.skills), soul_md=body.soul_md, actor=actor
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return worker.to_dict()

    @router.get("/workers/{uid}", response_model=WorkerOut)
    async def get_worker(uid: str, actor: str = Depends(operator)) -> dict[str, Any]:
        worker = await runtime.store.get_worker(uid)
        if worker is None:
            raise HTTPException(status_code=404, detail="Worker nicht gefunden")
        return worker.to_dict()

    @router.post("/workers/{uid}/spawn")
    async def spawn_worker(uid: str, body: SpawnIn, actor: str = Depends(operator)) -> dict[str, Any]:
        if not await runtime.dispatcher.assign_specific(body.task_id, uid):
            raise HTTPException(status_code=409, detail="Zuweisung nicht moeglich (gesperrt, belegt oder nicht ready)")
        return {"ok": True, "task_id": body.task_id, "worker_uid": uid}

    @router.get("/workers/{uid}/experiences", response_model=list[ExperienceOut])
    async def list_experiences(uid: str, limit: int = 100, actor: str = Depends(operator)) -> list[dict[str, Any]]:
        return [e.to_dict() for e in await runtime.store.list_experiences(worker_uid=uid, limit=limit)]

    # -- Audit --
    @router.get("/audit", response_model=list[AuditEntryOut])
    async def list_audit(after_seq: int = 0, limit: int = 100, actor: str = Depends(operator)) -> list[dict[str, Any]]:
        return [e.to_dict() for e in await runtime.ledger.entries(after_seq=after_seq, limit=limit)]

    @router.get("/audit/verify")
    async def verify_audit(actor: str = Depends(operator)) -> dict[str, Any]:
        errors = await runtime.ledger.verify()
        return {"ok": not errors, "errors": errors}

    # -- Rust-Limbs --
    @router.get("/rust-limbs", response_model=list[RustLimbOut])
    async def list_rust_limbs(actor: str = Depends(operator)) -> list[dict[str, Any]]:
        return [limb.to_dict() for limb in _load_limbs(_limbs_path(runtime)).values()]

    @router.post("/rust-limbs", response_model=RustLimbOut)
    async def register_rust_limb(body: RustLimbOut, actor: str = Depends(operator)) -> dict[str, Any]:
        path = _limbs_path(runtime)
        limbs = _load_limbs(path)
        limb = RustLimb(name=body.name, version=body.version, contract_version=body.contract_version, endpoint=body.endpoint)
        limbs[limb.name] = limb
        atomic_write_bytes(path, json.dumps([lb.to_dict() for lb in limbs.values()], indent=2).encode("utf-8"), fsync=True)
        await runtime.ledger.append(
            actor=actor, action="rust_limb.register", category="system", subject=limb.name, payload=limb.to_dict()
        )
        return limb.to_dict()

    @router.post("/rust-limbs/{name}/invoke", response_model=RustLimbResponseOut)
    async def invoke_rust_limb(name: str, body: RustLimbRequestIn, actor: str = Depends(operator)) -> dict[str, Any]:
        limb = _load_limbs(_limbs_path(runtime)).get(name)
        if limb is None:
            raise HTTPException(status_code=404, detail="Limb nicht registriert")
        request = RustLimbRequest(request_id=body.request_id, operation=body.operation, params=body.params)
        await runtime.ledger.append(
            actor=actor,
            action="rust_limb.invoke",
            category="code",
            subject=name,
            payload={"request_id": request.request_id, "operation": request.operation},
        )
        try:
            raw = await asyncio.to_thread(_post_json, f"{limb.endpoint.rstrip('/')}/invoke", request.to_dict())
            return RustLimbResponse.from_dict(raw).to_dict()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Limb-Aufruf fehlgeschlagen: {type(e).__name__}") from e

    if runtime.telegram is not None:
        from orchestrator.telegram.api import build_telegram_router

        router.include_router(build_telegram_router(runtime.telegram, operator))

    app.include_router(router)
    return app
