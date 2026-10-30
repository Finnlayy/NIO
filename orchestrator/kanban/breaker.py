from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .audit import AuditLedger
from .bus import KanbanBus
from .models import KanbanEvent, TaskStatus, Worker, WorkerStatus
from .notify import Notifier
from .store import KanbanStore

__all__ = ["CircuitBreaker"]


class CircuitBreaker:
    def __init__(
        self,
        store: KanbanStore,
        ledger: AuditLedger,
        notifier: Notifier,
        bus_service: KanbanBus,
        *,
        threshold: int,
        cooldown_s: float,
    ) -> None:
        self.store = store
        self.ledger = ledger
        self.notifier = notifier
        self.bus_service = bus_service
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.log = logging.getLogger(__name__)

    async def record_failure(
        self, task_id: str, worker_uid: str, reason: str, *, exit_code: int | None = None
    ) -> bool:
        task = await self.store.get_task(task_id)
        if not task:
            return False

        attempts = task.attempts + 1
        triggered = attempts >= self.threshold

        if triggered:
            # Triggered
            task_updated = await self.store.cas_task(
                task_id,
                TaskStatus.IN_PROGRESS,
                {
                    "status": TaskStatus.BLOCKED,
                    "block_reason": f"circuit breaker: {reason}",
                    "assigned_worker_uid": None,
                    "attempts": attempts,
                },
            )
            if not task_updated:
                return False

            await self.ledger.append(
                actor="system",
                action="task.circuit_open",
                category="task",
                payload={"reason": reason, "exit_code": exit_code, "attempts": attempts, "worker_uid": worker_uid},
            )
            await self.notifier.alert(
                f"Circuit breaker opened for task {task_id} ({task.title})\nWorker: {worker_uid}\nReason: {reason}\nExit code: {exit_code}"
            )
            await self.bus_service.publish(KanbanEvent("task.blocked", task_id))
        else:
            # Retry
            task_updated = await self.store.cas_task(
                task_id,
                TaskStatus.IN_PROGRESS,
                {
                    "status": TaskStatus.READY,
                    "assigned_worker_uid": None,
                    "attempts": attempts,
                    "started_at": None,
                },
            )
            if not task_updated:
                return False

            await self.ledger.append(
                actor="system",
                action="task.retry",
                category="task",
                payload={"reason": reason, "exit_code": exit_code, "attempts": attempts, "worker_uid": worker_uid},
            )
            await self.bus_service.publish(KanbanEvent("task.reset", task_id))

        # Handle Worker
        worker = await self.store.get_worker(worker_uid)
        if worker:
            fail_count = worker.fail_count + 1
            worker_changes = {"status": WorkerStatus.IDLE, "fail_count": fail_count}

            if fail_count >= self.threshold:
                now_utc = datetime.now(UTC)
                open_until = (now_utc + timedelta(seconds=self.cooldown_s)).isoformat()
                worker_changes["breaker_open_until"] = open_until
                worker_changes["fail_count"] = 0
                await self.ledger.append(
                    actor="system",
                    action="worker.circuit_open",
                    category="worker",
                    payload={"worker_uid": worker_uid, "until": open_until},
                )

            await self.store.cas_worker(worker_uid, None, worker_changes)

        return triggered

    async def record_success(self, worker_uid: str) -> None:
        await self.store.cas_worker(worker_uid, None, {"fail_count": 0})

    def is_open(self, worker: Worker) -> bool:
        if not worker.breaker_open_until:
            return False
        try:
            until_dt = datetime.fromisoformat(worker.breaker_open_until)
            return datetime.now(UTC) < until_dt
        except ValueError:
            return False
