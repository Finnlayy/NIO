from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .audit import AuditLedger
from .bus import HeartbeatStore, KanbanBus, TokenStore
from .config import KanbanConfig
from .models import UID_PATTERN, KanbanBoard, KanbanEvent, KanbanTask, TaskStatus, Worker, WorkerStatus, check_transition, new_id
from .soul import default_soul
from .store import KanbanStore

__all__ = ["ConflictError", "KanbanService"]

class ConflictError(Exception):
    """Geworfen wenn ein CAS-Update im Store fehlschlägt."""

class KanbanService:
    def __init__(
        self,
        *,
        store: KanbanStore,
        bus: KanbanBus,
        ledger: AuditLedger,
        heartbeats: HeartbeatStore,
        tokens: TokenStore,
        config: KanbanConfig,
    ) -> None:
        self._store = store
        self._bus = bus
        self._ledger = ledger
        self._heartbeats = heartbeats
        self._tokens = tokens
        self._config = config

    async def create_board(self, name: str, *, actor: str) -> KanbanBoard:
        board = KanbanBoard(id=new_id("b"), name=name)
        await self._store.create_board(board)
        await self._ledger.append(
            actor=actor,
            action="create_board",
            category="task",
            subject=board.id,
            payload={"name": name}
        )
        await self.emit("board.created", payload={"board_id": board.id})
        return board

    async def create_task(
        self,
        *,
        board_id: str,
        title: str,
        description: str = "",
        parent_id: str | None = None,
        dependencies: frozenset[str] | tuple[str, ...] | list[str] = (),
        required_skills: frozenset[str] | tuple[str, ...] | list[str] = (),
        priority: int = 0,
        status: TaskStatus = TaskStatus.TRIAGE,
        workspace_repo: str | None = None,
        actor: str,
    ) -> KanbanTask:
        if not (1 <= len(title) <= 200):
            raise ValueError("Der Titel muss zwischen 1 und 200 Zeichen lang sein")

        board = await self._store.get_board(board_id)
        if board is None:
            raise ValueError(f"Board {board_id} existiert nicht")

        if parent_id is not None:
            parent = await self._store.get_task(parent_id)
            if parent is None:
                raise ValueError(f"Parent {parent_id} existiert nicht")

        dep_list = list(dependencies)
        for dep_id in dep_list:
            if await self._store.get_task(dep_id) is None:
                raise ValueError(f"Abhängigkeit {dep_id} existiert nicht")

        if dep_list:
            await self._check_cycles(dep_list)

        task = KanbanTask(
            id=new_id("t"),
            board_id=board_id,
            title=title,
            description=description,
            parent_id=parent_id,
            dependencies=dep_list,
            required_skills=list(required_skills),
            priority=priority,
            status=status,
            workspace_repo=workspace_repo,
        )
        await self._store.create_task(task)
        await self._ledger.append(
            actor=actor,
            action="create_task",
            category="task",
            subject=task.id,
            payload={"title": title, "parent_id": parent_id, "dependencies": dep_list}
        )
        await self.emit("task.created", task=task)
        return task

    async def _check_cycles(self, dependencies: list[str]) -> None:
        """Sucht per DFS nach Zyklen in den Abhängigkeiten."""
        visited = set()
        stack = set()

        async def visit(task_id: str) -> None:
            if task_id in stack:
                raise ValueError(f"Zyklus in Abhängigkeiten entdeckt bei {task_id}")
            if task_id in visited:
                return

            stack.add(task_id)
            task = await self._store.get_task(task_id)
            if task and task.dependencies:
                for dep in task.dependencies:
                    await visit(dep)
            stack.remove(task_id)
            visited.add(task_id)

        for dep in dependencies:
            await visit(dep)

    async def show(self, task_id: str) -> dict[str, Any]:
        task = await self._store.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} existiert nicht")
        children = await self._store.list_tasks(parent_id=task_id)
        return {"task": task.to_dict(), "children": [c.to_dict() for c in children]}

    async def transition(
        self,
        task_id: str,
        target: TaskStatus,
        *,
        actor: str,
        reason: str = "",
        expected: TaskStatus | None = None,
        changes: Mapping[str, Any] | None = None,
    ) -> KanbanTask:
        task = await self._store.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} existiert nicht")

        current = expected if expected is not None else task.status
        target_status = check_transition(current, target)

        updates: dict[str, Any] = {"status": target_status}
        if changes:
            updates.update(changes)

        updated_task = await self._store.cas_task(task_id, current, updates)
        if updated_task is None:
            raise ConflictError(f"CAS-Update für Task {task_id} fehlgeschlagen")

        await self._ledger.append(
            actor=actor,
            action="transition",
            category="task",
            subject=task_id,
            payload={"from": current.value, "to": target_status.value, "reason": reason}
        )
        await self.emit("task.transition", task=updated_task)
        return updated_task

    async def block(self, task_id: str, reason: str, *, actor: str) -> KanbanTask:
        return await self.transition(
            task_id,
            TaskStatus.BLOCKED,
            actor=actor,
            reason=reason,
            changes={"block_reason": reason}
        )

    async def complete(self, task_id: str, result_payload: dict[str, Any], *, actor: str) -> KanbanTask:
        return await self.transition(
            task_id,
            TaskStatus.COMPLETED,
            actor=actor,
            expected=TaskStatus.IN_PROGRESS,
            changes={"result_payload": result_payload}
        )

    async def heartbeat(self, task_id: str, *, worker_uid: str = "") -> None:
        await self._heartbeats.beat(task_id, self._config.heartbeat_ttl_s, worker_uid=worker_uid)

    async def create_worker(
        self,
        *,
        uid: str,
        name: str,
        skills: list[str],
        soul_md: str = "",
        actor: str,
    ) -> Worker:
        if not UID_PATTERN.match(uid):
            raise ValueError(f"Ungültige Worker-UID: {uid}")

        if not soul_md:
            soul_md = default_soul(uid=uid, name=name, skills=tuple(skills))

        worker = Worker(uid=uid, name=name, skills=skills, soul_md=soul_md, status=WorkerStatus.IDLE)
        await self._store.upsert_worker(worker)

        await self._ledger.append(
            actor=actor,
            action="create_worker",
            category="worker",
            subject=uid,
            payload={"name": name, "skills": skills}
        )
        await self.emit("worker.created", worker_uid=uid, payload={"name": name, "skills": skills})
        return worker

    async def emit(self, kind: str, *, task: KanbanTask | None = None, worker_uid: str | None = None, payload: dict[str, Any] | None = None) -> None:
        event = KanbanEvent(
            kind=kind,
            task_id=task.id if task else None,
            board_id=task.board_id if task else None,
            status=task.status.value if task else None,
            worker_uid=worker_uid,
            payload=payload or {},
        )
        await self._bus.publish(event)
