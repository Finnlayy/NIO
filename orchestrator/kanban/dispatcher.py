from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import secrets
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .breaker import CircuitBreaker
from .bus import HeartbeatStore, LockManager, TokenStore
from .config import KanbanConfig
from .decomposer import Decomposer
from .models import KanbanEvent, KanbanTask, TaskStatus, Worker, WorkerStatus, new_id
from .sandbox import SandboxRunner, SandboxSpec
from .store import KanbanStore
from .sync import sync_back
from .vault import ObsidianVault

if TYPE_CHECKING:
    from .service import KanbanService

__all__ = ["Dispatcher", "TickReport"]


@dataclass
class TickReport:
    decomposed: int = 0
    promoted: int = 0
    rolled_up: int = 0
    assigned: int = 0
    spawned: int = 0


class Dispatcher:
    def __init__(
        self,
        *,
        store: KanbanStore,
        service: KanbanService,
        locks: LockManager,
        heartbeats: HeartbeatStore,
        tokens: TokenStore,
        sandbox: SandboxRunner,
        breaker: CircuitBreaker,
        vault: ObsidianVault,
        decomposer: Decomposer,
        config: KanbanConfig,
        owner_id: str,
    ) -> None:
        self.store = store
        self.service = service
        self.locks = locks
        self.heartbeats = heartbeats
        self.tokens = tokens
        self.sandbox = sandbox
        self.breaker = breaker
        self.vault = vault
        self.decomposer = decomposer
        self.config = config
        self.owner_id = owner_id
        self.log = logging.getLogger(__name__)
        self._active: dict[str, asyncio.Task[Any]] = {}

    async def tick(self, wait: bool = False) -> TickReport:
        report = TickReport()

        # 1. Triage
        triage_tasks = await self.store.list_tasks(status=TaskStatus.TRIAGE)
        for task in triage_tasks:
            children_specs = await self.decomposer.decompose(task)
            children: list[KanbanTask] = []

            for _i, spec in enumerate(children_specs):
                deps = [children[dep_i].id for dep_i in spec.depends_on if dep_i < len(children)]
                if not deps:
                    deps = list(task.dependencies)

                child = KanbanTask(
                    id=new_id("t"),
                    title=spec.title,
                    description=spec.description,
                    status=TaskStatus.BACKLOG,
                    board_id=task.board_id,
                    parent_id=task.id,
                    required_skills=spec.required_skills,
                    dependencies=deps,
                )
                children.append(child)

            await self.store.apply_decomposition(task.id, children)
            await self.service.ledger.append(actor="system", action="task.decomposed", category="task", subject=task.id,
                                              payload={"children": [c.id for c in children]})
            report.decomposed += 1

        # 2. Promote
        promotable = await self.store.promotable_tasks()
        for task in promotable:
            cas_res = await self.store.cas_task(task.id, TaskStatus.BACKLOG, {"status": TaskStatus.READY})
            if cas_res:
                await self.service.bus.publish(KanbanEvent("task.promoted", task.id))
                report.promoted += 1

        # 3. Roll-up
        rollup_cands = await self.store.rollup_candidates()
        for task in rollup_cands:
            children_tasks = await self.store.list_tasks(board_id=task.board_id) # Optimization: could be filtered to parent_id
            children_payloads = {c.id: c.result_payload for c in children_tasks if c.parent_id == task.id}

            cas_res = await self.store.cas_task(
                task.id,
                TaskStatus.BACKLOG,
                {"status": TaskStatus.COMPLETED, "result_payload": {"children": children_payloads}}
            )
            if cas_res:
                await self.service.bus.publish(KanbanEvent("task.completed", task.id))
                report.rolled_up += 1

        # 4. Assign
        ready_tasks = await self.store.list_tasks(status=TaskStatus.READY)
        if ready_tasks:
            idle_workers = await self.store.list_workers(status=WorkerStatus.IDLE)
            available_workers = [w for w in idle_workers if not self.breaker.is_open(w)]

            for task in ready_tasks:
                if not available_workers:
                    break

                # Worker Wahl
                candidates = []
                for w in available_workers:
                    if set(task.required_skills) <= set(w.skills):
                        candidates.append(w)

                if not candidates:
                    continue

                candidates.sort(key=lambda w: (w.fail_count, w.uid))
                worker = candidates[0]

                assigned = await self.assign_specific(task.id, worker.uid)
                if assigned:
                    available_workers.remove(worker)
                    report.assigned += 1
                    report.spawned += 1

        if wait and self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)

        return report

    async def assign_specific(self, task_id: str, worker_uid: str) -> bool:
        task = await self.store.get_task(task_id)
        worker = await self.store.get_worker(worker_uid)

        if not task or task.status != TaskStatus.READY:
            return False
        if not worker or worker.status != WorkerStatus.IDLE or self.breaker.is_open(worker):
            return False

        deadline = self.config.task_deadline_s
        ttl = deadline + 60

        lock_worker = await self.locks.acquire(f"worker:{worker_uid}", self.owner_id, ttl)
        if not lock_worker:
            return False

        lock_task = await self.locks.acquire(f"task:{task_id}", self.owner_id, ttl)
        if not lock_task:
            await self.locks.release(f"worker:{worker_uid}", self.owner_id)
            return False

        worker_cas = await self.store.cas_worker(worker_uid, WorkerStatus.IDLE, {"status": WorkerStatus.BUSY})
        if not worker_cas:
            await self.locks.release(f"worker:{worker_uid}", self.owner_id)
            await self.locks.release(f"task:{task_id}", self.owner_id)
            return False

        now_iso = datetime.now(UTC).isoformat()
        task_cas = await self.store.cas_task(
            task_id,
            TaskStatus.READY,
            {"status": TaskStatus.IN_PROGRESS, "assigned_worker_uid": worker_uid, "started_at": now_iso}
        )

        if not task_cas:
            await self.store.cas_worker(worker_uid, WorkerStatus.BUSY, {"status": WorkerStatus.IDLE})
            await self.locks.release(f"worker:{worker_uid}", self.owner_id)
            await self.locks.release(f"task:{task_id}", self.owner_id)
            return False

        await self.heartbeats.beat(task_id, ttl, worker_uid=worker_uid)

        task_obj = asyncio.create_task(self._run_worker(task_cas, worker_cas))
        self._active[task_id] = task_obj

        # Clean up _active when done
        task_obj.add_done_callback(lambda _: self._active.pop(task_id, None))
        return True

    async def _run_worker(self, task: KanbanTask, worker: Worker) -> None:
        run_id = f"{task.id}-a{task.attempts}"
        run_dir = self.config.workspace_dir / "runs" / run_id
        work_dir = run_dir / "work"
        # Vor dem ``try`` gebunden: das ``finally`` raeumt auch nach einem fruehen
        # Fehler auf, ohne an einer ungebundenen Variable zu scheitern.
        token: str | None = None

        try:
            in_dir = run_dir / "in"
            out_dir = run_dir / "out"

            in_dir.mkdir(parents=True, exist_ok=True)
            out_dir.mkdir(parents=True, exist_ok=True)
            work_dir.mkdir(parents=True, exist_ok=True)

            # Write task.json
            import json

            from core.atomic import atomic_write_bytes
            task_json = json.dumps(task.to_dict()).encode("utf-8")
            atomic_write_bytes(in_dir / "task.json", task_json)

            # Write SOUL.md
            soul_bytes = worker.soul_md.encode("utf-8")
            atomic_write_bytes(in_dir / "SOUL.md", soul_bytes)

            # Write history.md if it exists
            history_path = self.config.workspace_dir / "workers" / worker.uid / "history.md"
            if history_path.exists():
                atomic_write_bytes(in_dir / "history.md", history_path.read_bytes())

            # Setup Git worktree
            git_repo = None
            if task.workspace_repo:
                git_repo = task.workspace_repo
                try:
                    subprocess.run(
                        ["git", "-C", git_repo, "worktree", "add", str(work_dir), "-b", f"kanban/{run_id}"],
                        check=True,
                        capture_output=True
                    )
                except subprocess.CalledProcessError as e:
                    self.log.error(f"Failed to setup git worktree: {e.stderr.decode()}")
                    await self.breaker.record_failure(task.id, worker.uid, "git worktree setup failed")
                    return

            # Tokens
            token = secrets.token_urlsafe(32)
            await self.tokens.put(token, {"task_id": task.id, "worker_uid": worker.uid}, self.config.task_deadline_s + 60)

            secrets_env = {"NIO_KANBAN_TASK_TOKEN": token}
            for n in self.config.secret_allowlist:
                if n in os.environ:
                    secrets_env[n] = os.environ[n]

            # Use specific log function logic here to only log names of secrets
            await self.service.ledger.append(
                actor="system",
                action="worker.spawn",
                category="worker",
                payload={"worker_uid": worker.uid, "task_id": task.id, "secrets_injected": list(secrets_env.keys())}
            )

            async def hb_callback():
                await self.heartbeats.beat(task.id, self.config.heartbeat_ttl_s, worker_uid=worker.uid)

            spec = SandboxSpec(
                run_id=run_id,
                task=task,
                worker=worker,
                run_dir=run_dir,
                env={}, # Not requested
                secrets=secrets_env,
                image=self.config.image,
                deadline_s=self.config.task_deadline_s
            )

            result = await self.sandbox.run(spec, on_heartbeat=hb_callback)
            outcome = await sync_back(
                store=self.store,
                vault=self.vault,
                workspace_dir=self.config.workspace_dir,
                task=task,
                worker=worker,
                result=result
            )

            # Check if status has been updated externally
            curr_task = await self.store.get_task(task.id)

            if curr_task and curr_task.status == TaskStatus.IN_PROGRESS:
                if outcome.status == "completed":
                    await self.service.complete(task.id, outcome.result_payload or {}, actor=f"worker:{worker.uid}")
                    await self.breaker.record_success(worker.uid)
                elif outcome.status == "blocked":
                    await self.service.block(task.id, outcome.reason, actor=f"worker:{worker.uid}")
                else: # failed
                    await self.breaker.record_failure(task.id, worker.uid, outcome.reason, exit_code=result.exit_code)

        except Exception as e:
            self.log.exception(f"Error in _run_worker for {task.id}: {e}")
            await self.breaker.record_failure(task.id, worker.uid, f"Internal error: {e}")
        finally:
            if token is not None:
                await self.tokens.revoke(token)
            await self.heartbeats.clear(task.id)
            await self.locks.release(f"task:{task.id}", self.owner_id)
            await self.locks.release(f"worker:{worker.uid}", self.owner_id)

            # Only switch IDLE if it's currently BUSY (it might have been changed externally)
            curr_worker = await self.store.get_worker(worker.uid)
            if curr_worker and curr_worker.status == WorkerStatus.BUSY:
                await self.store.cas_worker(worker.uid, WorkerStatus.BUSY, {"status": WorkerStatus.IDLE})

            if task.workspace_repo:
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(work_dir)],
                        check=True,
                        capture_output=True
                    )
                except Exception as e:
                    self.log.warning(f"Could not remove git worktree {work_dir}: {e}")

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.tick()
            except Exception as e:
                self.log.error(f"Dispatcher tick error: {e}", exc_info=True)
                # Fail-safe audit
                with contextlib.suppress(Exception):
                    await self.service.ledger.append(
                        actor="system", action="system.dispatcher_error", category="system", payload={"error": str(e)}
                    )

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self.config.tick_s)

    async def cancel(self, task_id: str) -> None:
        task = await self.store.get_task(task_id)
        if task:
            run_id = f"{task_id}-a{task.attempts}"
            await self.sandbox.cancel(run_id)
