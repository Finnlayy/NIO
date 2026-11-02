# WP-03: Decomposer, Dispatcher, Reaper, Circuit-Breaker, Telegram

Lies zuerst `00-README.md`. Du **nutzt** `KanbanStore` (fertig), `KanbanBus`/`LockManager`/
`HeartbeatStore`/`TokenStore` (WP-02), `SandboxRunner`/`SandboxSpec` (WP-04), `sync_back`/
`RunOutcome` (WP-05) und `KanbanService` (WP-06). Sind diese noch nicht da, schreib in
den Tests Fakes gegen die Signaturen aus `00-README.md`. Das ist das sicherheitskritische
Paket: lieber ein stärkeres Modell nehmen.

## `orchestrator/kanban/decomposer.py`
- `@dataclass ChildSpec(title, description="", required_skills=[], depends_on=[])`.
  `depends_on` enthält Indizes in der Kinderliste.
- `class Decomposer(Protocol): async def decompose(self, task: KanbanTask) -> list[ChildSpec]`
- `ChecklistDecomposer`:
  - Zeilen mit `- [ ] text` oder `* [ ] text` werden **parallele** Kinder.
  - Zeilen mit `1. text` oder `1) text` werden **sequenzielle** Kinder: Kind *i* hängt
    von Kind *i−1* ab.
  - Tokens `#skill` im Zeilentext werden zu `required_skills` und aus dem Titel entfernt.
    Ohne `#`-Token erbt das Kind die `required_skills` des Elternteils.
  - Keine passenden Zeilen ergibt `[]`.
- `LLMDecomposer(llm, fallback=ChecklistDecomposer())`:
  - `llm` ist ein Ciel-`LLMClient` (`apollo/ciel/sandbox_agent.py`, Methode
    `complete(system=, messages=, tools=[])`, die `AssistantMessage` mit `.content` liefert).
  - Der System-Prompt verlangt reines JSON `{"children":[{"title","description","required_skills","depends_on"}]}`.
  - Parse-Fehler, Timeout (`asyncio.wait_for`, 60 s) oder mehr als 20 Kinder führen zum
    Fallback.

## `orchestrator/kanban/notify.py`
- `TelegramNotifier(token, chat_id, *, timeout_s=10)`:
  - `alert(text)` läuft per `asyncio.to_thread` mit `urllib.request`:
    POST `https://api.telegram.org/bot{token}/sendMessage`, JSON
    `{"chat_id","text","disable_web_page_preview":true}`.
  - Gibt `True` bei HTTP 200 und `"ok":true` zurück, sonst `False`.
  - **Fail-silent**: keine Exception nach außen. Der Token taucht nie in Logs oder
    Fehlermeldungen auf; die URL beim Loggen maskieren.
- `NullNotifier` gibt immer `False` zurück. Fabrik:
  `build_notifier(config) -> Notifier` (Telegram nur, wenn Token **und** Chat-ID gesetzt sind).

## `orchestrator/kanban/breaker.py`
`CircuitBreaker(store, ledger, notifier, bus_service, *, threshold, cooldown_s)`
- `async record_failure(task_id, worker_uid, reason, *, exit_code=None) -> bool`
  (Rückgabe: ausgelöst ja/nein):
  1. Task neu laden, `attempts = task.attempts + 1`.
  2. Bei `attempts >= threshold`:
     - CAS `in_progress → blocked` mit `block_reason=f"circuit breaker: {reason}"`,
       `assigned_worker_uid=None` und `attempts`.
     - Audit `action="task.circuit_open"`, `category="task"`, Payload
       `{reason, exit_code, attempts, worker_uid}`.
     - `notifier.alert(...)` mit Task-ID, Titel, Worker, Grund und Exit-Code.
     - Event `task.blocked`.
  3. Sonst: CAS `in_progress → ready` mit `assigned_worker_uid=None`, `attempts`,
     `started_at=None`; Audit `task.retry`; Event `task.reset`.
  4. Worker: `fail_count += 1` und `status=idle`.
     Bei `fail_count >= threshold`: `breaker_open_until = now + cooldown_s` (ISO),
     `fail_count = 0`, Audit `worker.circuit_open`.
  5. Schlägt das CAS fehl (Task inzwischen woanders), nichts weiter tun und `False` liefern.
- `async record_success(worker_uid)`: `fail_count = 0`.
- `is_open(worker) -> bool`: `breaker_open_until` liegt in der Zukunft.

## `orchestrator/kanban/dispatcher.py`
`Dispatcher(*, store, service, locks, heartbeats, tokens, sandbox, breaker, vault, decomposer, config, owner_id)`
- `async tick() -> TickReport`. Der Report enthält Zähler für `decomposed`, `promoted`,
  `rolled_up`, `assigned` und `spawned`. Ablauf:
  1. **Triage**: für jeden `triage`-Task `decomposer.decompose(task)`.
     - Daraus `KanbanTask`s bauen: `status=backlog`, `parent_id=task.id`, `board_id`
       erben, `dependencies` aus `depends_on` auf die neuen IDs abbilden. Kinder ohne
       `depends_on` erben die `dependencies` des Elternteils.
     - Dann `store.apply_decomposition(parent_id, children)`. Bei leerer Liste geht der
       Task nur nach `backlog`.
     - Audit `task.decomposed`.
  2. **Promote**: `store.promotable_tasks()` → CAS `backlog → ready`, Event.
  3. **Roll-up**: `store.rollup_candidates()` → CAS `backlog → completed` mit
     `result_payload={"children": {child_id: child.result_payload}}`.
  4. **Assign**: für jeden `ready`-Task, solange die Semaphore frei ist:
     - Worker-Wahl: `status == idle`, nicht `breaker.is_open`, `set(required_skills) <= set(worker.skills)`.
       Bei mehreren passenden Workern den mit den wenigsten `fail_count` nehmen, bei
       Gleichstand nach `uid`.
     - `locks.acquire(f"worker:{uid}", owner_id, ttl=deadline+60)` und
       `locks.acquire(f"task:{id}", …)`. Scheitert einer, beide freigeben und weiter.
     - `store.cas_worker(uid, IDLE, {"status": BUSY})` und
       `store.cas_task(id, READY, {"status": IN_PROGRESS, "assigned_worker_uid": uid, "started_at": now})`.
       Scheitert eines, zurückrollen (Worker wieder IDLE) und Locks freigeben.
     - `heartbeats.beat(task_id, ttl)` als Startpuls.
     - `asyncio.create_task(self._run_worker(task, worker))`, gemerkt in `self._active[task_id]`.
  5. `tick(wait=True)` (CLI-Modus) wartet, bis alle in diesem Tick gestarteten Läufe fertig sind.
- `async _run_worker(task, worker)`:
  1. `run_dir = config.workspace_dir / "runs" / run_id` mit `in/`, `out/`, `work/`.
     - In `in/` liegen `task.json`, `SOUL.md` (`worker.soul_md`) und `history.md` aus
       `workspace_dir/workers/{uid}/history.md`, falls vorhanden.
     - Ist `task.workspace_repo` gesetzt, wird `work/` ein Git-Worktree:
       `git -C <repo> worktree add <run_dir>/work -b kanban/{run_id}`.
  2. Task-Token: `secrets.token_urlsafe(32)` → `tokens.put(token, {"task_id","worker_uid"}, ttl=deadline+60)`.
     Dazu `secrets_env = {"NIO_KANBAN_TASK_TOKEN": token, **{n: os.environ[n] for n in config.secret_allowlist if n in os.environ}}`.
     Audit `worker.spawn` **nur mit Secret-Namen**, nie mit Werten.
  3. `result = await sandbox.run(spec, on_heartbeat=lambda: heartbeats.beat(task.id, config.heartbeat_ttl_s, worker_uid=uid))`
  4. `outcome = await sync_back(...)`
     - `completed` → `service.complete(...)` mit CAS von `in_progress`, dann `breaker.record_success`.
     - `blocked` (Worker hat bewusst blockiert) → `service.block(...)`, **kein** Breaker.
     - `failed`, Exit ≠ 0 oder Timeout → `breaker.record_failure(...)`.
     - Hat ein Tool den Task schon abgeschlossen oder blockiert (Status ≠ `in_progress`),
       nur noch Experience und Seele übernehmen.
  5. `finally`: `tokens.revoke`, `heartbeats.clear`, beide Locks freigeben, Worker auf
     `idle` setzen, falls noch `busy`. Worktree: `git worktree remove --force`; der Branch
     bleibt erhalten.
- `async run(stop: asyncio.Event)`: Endlosschleife `tick()` + `asyncio.sleep(config.tick_s)`.
  Exceptions eines Ticks loggen (stderr) und Audit `system.dispatcher_error`; nie abbrechen.
- `async cancel(task_id)`: `sandbox.cancel(run_id)` für einen aktiven Lauf.

## `orchestrator/kanban/reaper.py`
`Reaper(*, store, heartbeats, breaker, dispatcher=None, vault, config)`, `async tick() -> list[str]` (geerntete Task-IDs):
- Für jeden `in_progress`-Task gilt er als verwaist, wenn alle drei zutreffen:
  - `not await heartbeats.alive(id)`
  - `now - started_at > reaper_grace_s`
  - der Task ist nicht in `dispatcher._active` mit frischem Heartbeat
- Verwaiste Tasks: zuerst `dispatcher.cancel(id)` (falls lokal), dann
  `breaker.record_failure(id, uid, "heartbeat lost")`.
- Danach `store.pending_vault_experiences()` erneut in den Vault spiegeln
  (`vault.write_experience`, WP-05) und `mark_vault_synced`.
- `async run(stop)`: Schleife mit `max(config.heartbeat_ttl_s / 2, 1)`.

## Tests: `tests/test_kanban_dispatcher.py`, `test_kanban_reaper.py`, `test_kanban_breaker.py`, `test_kanban_decomposer.py`
Store ist `SqliteKanbanStore(":memory:")`, Bus/Locks sind die In-Memory-Varianten, dazu
`FakeSandbox`, `FakeNotifier` und `FakeVault`.
- Checkliste mit drei Zeilen ergibt drei Kinder. Eine nummerierte Liste ergibt eine Kette.
  Nach der Abarbeitung ist der Elternteil per Roll-up `completed`.
- Ein Task mit einer offenen Abhängigkeit wird nicht `ready`.
- Skill-Matching: Ein Task mit `#rust` geht nicht an einen Worker ohne `rust`.
- **Konkurrenz**: Zwei `Dispatcher` teilen Store und Locks und rufen gleichzeitig
  `tick()` (`asyncio.gather`). Erwartet: genau ein Spawn.
- `FakeSandbox` liefert dreimal Exit 1. Erwartet: zweimal zurück auf `ready`, beim dritten
  Mal `blocked`, ein Audit-Eintrag `task.circuit_open` und ein Telegram-Aufruf.
- Reaper: `in_progress` ohne Heartbeat und älter als die Grace-Zeit geht zurück auf
  `ready`, `attempts == 1`.
- `TelegramNotifier` gegen einen lokalen `http.server` (`api_base` als Konstruktor-Parameter
  für Tests): Erfolg ergibt `True`, HTTP 500 ergibt `False`, beides ohne Exception.

## Fertig, wenn
Die Abnahme ist grün. Es gibt keinen Pfad, auf dem ein Lauf seine Locks, Tokens oder den
Worker-Status `busy` behält. Prüfe das mit einem Test, der in `sandbox.run` eine Exception wirft.
