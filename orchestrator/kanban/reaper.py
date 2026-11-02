from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from .breaker import CircuitBreaker
from .bus import HeartbeatStore
from .config import KanbanConfig
from .dispatcher import Dispatcher
from .models import TaskStatus
from .store import KanbanStore
from .vault import ObsidianVault

__all__ = ["Reaper"]


class Reaper:
    def __init__(
        self,
        *,
        store: KanbanStore,
        heartbeats: HeartbeatStore,
        breaker: CircuitBreaker,
        vault: ObsidianVault,
        config: KanbanConfig,
        dispatcher: Dispatcher | None = None,
    ) -> None:
        self.store = store
        self.heartbeats = heartbeats
        self.breaker = breaker
        self.vault = vault
        self.config = config
        self.dispatcher = dispatcher
        self.log = logging.getLogger(__name__)

    async def tick(self) -> list[str]:
        reaped_task_ids = []
        in_progress_tasks = await self.store.list_tasks(status=TaskStatus.IN_PROGRESS)
        now = datetime.now(UTC)

        for task in in_progress_tasks:
            # 1. Missing heartbeat
            is_alive = await self.heartbeats.alive(task.id)
            if is_alive:
                continue

            # 2. Grace time exceeded
            if not task.started_at:
                continue

            try:
                started_at = datetime.fromisoformat(task.started_at)
                if (now - started_at).total_seconds() <= self.config.reaper_grace_s:
                    continue
            except ValueError:
                self.log.warning("Invalid started_at for task %s", task.id)
                continue

            # 3. Lokal laufender, aber stummer Worker: nur abbrechen. Der Lauf endet
            # dann als ``cancelled`` und der Dispatcher verbucht den Fehlschlag selbst --
            # zaehlte der Reaper zusaetzlich, kaeme jeder Absturz doppelt in den Breaker.
            if self.dispatcher and task.id in self.dispatcher._active:
                try:
                    await self.dispatcher.cancel(task.id)
                except Exception as e:
                    self.log.warning("Failed to cancel local run for %s: %s", task.id, e)
                reaped_task_ids.append(task.id)
                continue

            # Verwaist (Prozess abgestuerzt, Lauf gehoert keinem lebenden Dispatcher)

            # Record failure
            await self.breaker.record_failure(
                task.id,
                task.assigned_worker_uid or "unknown",
                "heartbeat lost",
            )
            reaped_task_ids.append(task.id)

        # Sync vault experiences
        pending = await self.store.pending_vault_experiences()
        for exp in pending:
            try:
                exp_task = await self.store.get_task(exp.task_id)
                if exp_task:
                    self.vault.write_experience(exp, exp_task)
                await self.store.mark_vault_synced(exp.id)
            except Exception as e:
                self.log.error("Failed to sync experience %s to vault: %s", exp.id, e)

        return reaped_task_ids

    async def run(self, stop: asyncio.Event) -> None:
        sleep_time = max(self.config.heartbeat_ttl_s / 2, 1.0)
        while not stop.is_set():
            try:
                await self.tick()
            except Exception as e:
                self.log.error("Reaper tick error: %s", e, exc_info=True)

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=sleep_time)
