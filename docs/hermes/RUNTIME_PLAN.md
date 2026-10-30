# Hermes-Runtime — angepasster Umsetzungsplan (Stand 2026-10-30, Branch `feat/hermes-kanban`)

Dieser Plan ersetzt den ursprünglichen 6-Phasen-Plan „Hermes-Klasse". Er ist gegen den
tatsächlichen Code abgeglichen: falsche Annahmen sind korrigiert, vorhandene Kanban-Bausteine
werden wiederverwendet statt neu gebaut, und die Reihenfolge folgt dem Risiko (Kapital-Sicherheit
zuerst, KV-Cache-Optimierung zuletzt).

## 1. Ist-Stand (verifiziert)

Fünf Runtime-Schichten, nicht vier:

| Schicht | Ort | Relevanz für diesen Plan |
|---|---|---|
| NEU Core & Orchestrator | `orchestrator/runner.py`, `core/job.py`, `core/policy.py` | `human_only_globs` + `approved_by == "human"` = Vorläufer eines Approval-Gates |
| Apollo Ciel | `apollo/ciel/*` | Ziel der meisten Phasen; **nirgends produktiv verdrahtet** (nur `orchestrator/kanban/tools.py` registriert Tools in die Registry) |
| Sigma | `workspace/sigma/app/*` | Kapitalrelevante LLM-Tools in `app/llm/tool_executor.py` (synchron!) |
| Apollo Frontend | `frontend/src/apollo/*` | Spricht nur über Next-Proxy-Routen (`/api/apollo`, `/api/sandbox`) mit Backends |
| **Hermes-Kanban** (neu) | `orchestrator/kanban/*` | Sandbox, Bus, Locks, Tokens, Audit-Ledger, Breaker, Telegram, FastAPI mit Operator-Auth |

### Korrekturen am alten Plan

1. **`state` in `messages[1]` bricht den Cache nicht pro Turn.** `SandboxAgent._reasoning_loop`
   setzt die Message einmal pro `run()`; innerhalb der Schleife ändert sie sich nicht.
2. **`loaded.insert(0, …)` ist Absicht**, kein Bug: Es hält die per Test
   `test_prompt_payload_max_3_plus_meta_with_150_tools` abgesicherte Garantie „≤ 3 Skills + 1 Meta-Tool".
   Append-only bricht diese Garantie → Design-Entscheidung (siehe Phase 5).
3. Die Testdatei `tests/test_ciel_orchestrator.py` existiert nicht. Bestehende Ciel-Tests:
   `tests/test_ciel_integration.py`, `tests/test_ciel_mcp_nodes.py` (22 Tests, pytest-Stil, grün).
4. `frontend/src/apollo/commands.ts` nutzt Einträge `{ command, usage, detail }` und eine
   `ParsedCommand`-Union mit `kind` — nicht `{ name, description, category }`.
5. `LlmToolExecutor` in Sigma ist **synchron**; ein async Policy-Engine-Aufruf passt dort nicht direkt hinein.
6. `apollo/ciel` importiert ausschließlich aus `apollo` (keine Abhängigkeit auf `orchestrator` oder `core`).
   Diese Richtung bleibt so: `orchestrator` darf `apollo.ciel` importieren, nicht umgekehrt.
   Kopplung an Kanban (Audit, Notifier, Experiences) läuft über injizierte Callables/Protokolle.
7. Für Steuer-Endpunkte existiert bereits die Kanban-FastAPI (`orchestrator/kanban/api.py`) mit
   Operator-Bearer-Auth (503 ohne Token). Neue Runtime-Routen gehören dorthin, nicht in die
   2900-Zeilen-`workspace/sigma/app/server/main.py`.

### Was bereits erledigt bzw. wiederverwendbar ist

| Plan-Baustein | Vorhanden in | Nutzung |
|---|---|---|
| Prozessgruppen-Kill SIGTERM → Grace → SIGKILL | `orchestrator/kanban/sandbox.py` (`SubprocessSandbox._stop_proc`, `start_new_session=True`) | Muster für Ciel-`SubprocessExecutionEnv` und MCP-Transport übernehmen |
| Docker-Isolation (`--network none`, `--pids-limit`, CPU/Mem) | `DockerSandbox.build_argv` | Kein eigenes `DockerExecutionEnv` in Ciel nötig (YAGNI) |
| Abbruch per ID | `SandboxRunner.cancel(run_id)` | Vorbild für `CancellationToken` |
| Kurzlebige Tokens / Claims in Redis | `TokenStore` / `RedisTokenStore` (`orchestrator/kanban/bus.py`, `redis_resp.py`) | Vorbild für Approval-Tickets |
| Manipulationssicheres Protokoll | `AuditLedger.append(actor=, action=, category=, subject=, payload=)` | Jede Ticket-Entscheidung loggen |
| Operator-Benachrichtigung | `TelegramNotifier` (`orchestrator/kanban/notify.py`) | Pending-Ticket melden |
| Stdlib-Redis inkl. `EVAL` | `orchestrator/kanban/redis_resp.RedisClient.execute(...)` | Lua-Gate ohne `redis`-Paket ausführbar |
| Erfahrungs-Datensätze | `Experience` (`orchestrator/kanban/models.py`), Obsidian-Vault | Quelle für den FTS5-Index |
| Wilson-Score | `Architect/core/learning/skill_profiles.py` | Formel stdlib-only nach Ciel kopieren |

### Bestätigte Lücken

- Sigma-API ohne jede Authentifizierung (auch `POST /api/v1/safety/release` ist offen).
- Sigma: LLM kann `confirmation_confirmed=true` selbst setzen; `update_risk_settings` und
  `control_bot START` sind gar nicht gegated; `SafetyGuard._daily_pnl_usd` lebt nur im Prozess-RAM.
- `StdioMCPTransport.start` ohne `start_new_session`; Timeout verwirft nur das Future; `stop()`
  beendet nur den direkten Prozess, nicht die Gruppe.
- `OpenAICompatLLMClient.complete` (`urlopen` in `to_thread`) ist nicht abbrechbar.
- Kein DAG, kein `/undo`/`/retry`, kein FTS5 irgendwo im Repo; `KnowledgeBase` liest JSON linear.
- Keine Micro-Compaction, keine Sub-Agent-Delegation in der LLM-Runtime, keine prozeduralen Skills.
- Frontend kennt nur `/spawn /dispatch /failover /router /config /sandbox /clear /help`.

## 2. Neue Reihenfolge

| Phase | Inhalt | Abhängig von | Aufwand |
|---|---|---|---|
| **0** | Sicherheits-Hotfixes: Sigma-Approval-Gate, MCP-Prozessgruppen | — | klein |
| **1** | Ciel Pre-Execution Policy Engine (Lua + Fallback, Tickets, Tiers) | 0 | mittel |
| **2** | DAG-Checkpointing + episodisches Gedächtnis (FTS5, Kanban-Experiences) | — | mittel |
| **3** | CancellationToken, ExecutionEnv, Sub-Agent-Delegation | 1, 2 | mittel |
| **4** | Control Plane: Kanban-API-Routen, Next-Proxy, Apollo-CLI | 1, 2, 3 | mittel |
| **5** | Micro-Compaction + Cache-stabile Tools + prozedurale Skills (`load_skill`) | 2 | groß |

Phase 0 und 2 können parallel laufen (keine gemeinsamen Dateien).

## 3. Gemeinsame Regeln für alle Phasen (in jeden Prompt mitgeben)

```markdown
KONVENTIONEN NIO
- Sprache von Kommentaren/Docstrings: Deutsch, wie im umgebenden Code.
- `apollo/ciel/*` importiert nur aus `apollo` und der Stdlib (+ optionale Extras mit Fallback).
  Kein Import aus `orchestrator`, `core`, `workspace`. Kopplung nach außen nur über injizierte
  Callables/Protocols.
- Pydantic-Modelle in Ciel über `from .models import BaseModel, ConfigDict, Field` (enthält den
  Stdlib-Fallback) — NICHT direkt aus `pydantic` importieren.
- Redis: entweder `redis.asyncio`-kompatibler Client ODER `orchestrator.kanban.redis_resp.RedisClient`
  (`await client.execute("CMD", ...)`). Code dagegen über ein kleines Protocol abstrahieren und
  immer einen In-Memory-Fallback mit identischer Semantik anbieten (Tests laufen ohne Redis).
- Tests: pytest-Stil (`def test_...`), Dateien unter `tests/` (bzw. `workspace/sigma/tests/` für Sigma).
- Bestehende Tests müssen grün bleiben: `python3 -m pytest -q tests/test_ciel_integration.py tests/test_ciel_mcp_nodes.py tests/test_kanban_*.py`
- Keine neuen Pflicht-Dependencies.
```

---

## PHASE 0 — Sicherheits-Hotfixes

```markdown
ROLE & TASK: NIO PHASE 0 — SIGMA APPROVAL-GATE + MCP-PROZESSGRUPPEN

(Gemeinsame Konventionen siehe oben.)

TEIL A — Sigma: LLM darf sich nicht selbst freigeben
Ist: `workspace/sigma/app/llm/tool_executor.py` → `LlmToolExecutor._emergency` prüft nur
`p.confirmation_confirmed`, das das LLM selbst setzen kann. `_update_risk_settings` und
`_control_bot` haben gar kein Gate. Der Executor ist synchron.

Umsetzen:
1. CREATE `workspace/sigma/app/llm/approval_gate.py`:
   - `ApprovalTicket` (Pydantic): ticket_id, tool_name, arguments, arguments_sha256,
     status ("PENDING"|"APPROVED"|"REJECTED"|"EXPIRED"|"CONSUMED"), created_at_ms, expires_at_ms,
     operator_id, decision_reason.
   - `ApprovalGate` (synchron, thread-safe via `threading.Lock`, In-Memory-Dict, TTL Default 300 s):
     `require(tool_name, arguments) -> ApprovalTicket`, `resolve(ticket_id, approved, operator_id, reason)`,
     `consume(ticket_id, tool_name, arguments) -> bool` (prüft APPROVED, gleicher Tool-Name,
     gleicher `arguments_sha256` über `json.dumps(args, sort_keys=True, default=str)` ohne das Feld
     `approval_ticket_id`, nicht abgelaufen; danach Status CONSUMED → Einmalverwendung),
     `pending() -> list[ApprovalTicket]`.
2. Tier-Einstufung im Executor (Konstante `TOOL_TIERS`):
   - Risiko-ERHÖHEND → Ticket Pflicht: `update_risk_settings` (alle Änderungen),
     `control_bot` mit `START`.
   - Risiko-SENKEND → kein Ticket (Schutzaktionen dürfen nie durch Warten blockiert werden):
     `trigger_emergency_action` (KILL_SWITCH, CANCEL_ALL_ORDERS, FLIGHT_TO_CASH),
     `control_bot` mit PAUSE/STOP/QUARANTINE.
   - Read-only: `query_kausal_autopsy`. `edit_pine_strategy_code` → Ticket Pflicht.
3. Ablauf im Executor: Ticket-pflichtiger Call ohne gültiges `approval_ticket_id` in den Argumenten
   → Status `APPROVAL_REQUIRED` mit `{"ticket_id", "expires_at_ms", "arguments_sha256"}`; Tool
   wird NICHT ausgeführt. Mit gültigem Ticket → `consume()` und ausführen.
   `approval_ticket_id` vor `validate_arguments` aus den Argumenten herausnehmen.
4. `confirmation_confirmed` aus `TriggerEmergencyActionParams` entfernen (bzw. ignorieren und
   als deprecated markieren) — Schutzaktionen laufen direkt.
5. Operator-Auth für Sigma: Die Sigma-API hat derzeit KEINE Authentifizierung (auch
   `POST /api/v1/safety/release` ist offen). CREATE eine FastAPI-Dependency `require_operator`
   (Bearer gegen `SIGMA_OPERATOR_TOKEN`; ohne gesetztes Token 503 statt offen — Muster:
   `operator` in `orchestrator/kanban/api.py`). Anwenden auf die neuen Routen
   `GET /api/v1/approvals` und `POST /api/v1/approvals/{ticket_id}/resolve` (`approved`, `reason`;
   `operator_id` = Auth-Actor) sowie auf `POST /api/v1/safety/release`. Schutzaktionen
   (`/safety/kill`, `/safety/pause`) bleiben ohne Token erreichbar. Frontend-Aufrufer von
   `/safety/release` prüfen und das Token server-seitig (Next-Proxy) mitgeben.
   Kein LLM-Tool darf `resolve` aufrufen können.
6. `SafetyGuard._daily_pnl_usd`: Wenn `self.redis` gesetzt ist, Tages-PnL zusätzlich atomar per
   `INCRBYFLOAT sigma:daily_pnl_usd:{YYYY-MM-DD}` (TTL 2 Tage) führen und beim Lesen von dort nehmen;
   In-RAM bleibt Fallback. Prüfen, ob der Redis-Client dort sync oder async ist, und passend umsetzen.
   Diesen Key liest das Lua-Gate in Phase 1.
7. `workspace/sigma/tests/test_llm_contracts.py` anpassen: Die bisherigen Asserts auf
   `CONFIRMATION_REQUIRED`/`confirm_field` ersetzen.

Tests (CREATE `workspace/sigma/tests/test_approval_gate.py`):
- update_risk_settings ohne Ticket → APPROVAL_REQUIRED, `risk_overrides` unverändert.
- LLM setzt selbst `approval_ticket_id` auf ein PENDING-Ticket → abgelehnt.
- Nach `resolve(approved=True)` mit identischen Args → genau 1x ausgeführt; zweiter Aufruf mit
  demselben Ticket → abgelehnt (CONSUMED).
- Approved Ticket, aber andere Args (`max_daily_loss_usd` erhöht) → abgelehnt (Hash-Mismatch).
- Abgelaufenes Ticket → abgelehnt.
- KILL_SWITCH ohne jede Bestätigung → läuft sofort.

TEIL B — MCP-Stdio-Transport: hängende Prozesse wirklich beenden
Ist: `apollo/ciel/mcp_nodes.py`, `StdioMCPTransport.start` ohne `start_new_session`;
`request()` verwirft bei Timeout nur das Future; `stop()` beendet nur den direkten Prozess.

Umsetzen (Muster: `orchestrator/kanban/sandbox.py`, `SubprocessSandbox._stop_proc`, nur abschreiben,
nicht importieren):
1. In `start()` auf POSIX `start_new_session=True` übergeben.
2. `async def terminate_process_group(self, grace_s: float = 0.25) -> None`: `os.killpg(pgid, SIGTERM)`,
   bis `grace_s` auf `proc.wait()` warten, dann `SIGKILL`; `ProcessLookupError` schlucken; alle
   offenen Futures in `self._pending` mit `MCPTransportError` auflösen. Auf Nicht-POSIX auf
   `terminate()/kill()` zurückfallen.
3. `stop()` nutzt `terminate_process_group`.
4. Neuer Konstruktor-Parameter `kill_on_timeout: bool = True`: Bei Request-Timeout wird der Node
   per `terminate_process_group` beendet und als nicht laufend markiert (Neustart beim nächsten
   `start()`), weil ein hängender Server den JSON-RPC-Stream sonst dauerhaft blockiert.

Tests (ergänzen in `tests/test_ciel_mcp_nodes.py`):
- Fake-MCP-Server (Python-Einzeiler), der einen Kindprozess startet und nie antwortet; nach
  Request-Timeout existieren weder Eltern- noch Kindprozess (`os.kill(pid, 0)` → ProcessLookupError).
- `stop()` räumt Kindprozesse ebenfalls ab.

Verifikation:
python3 -m pytest -q tests/test_ciel_mcp_nodes.py tests/test_ciel_integration.py
(cd workspace/sigma && python3 -m pytest -q tests/test_approval_gate.py tests/test_llm_contracts.py)
```

---

## PHASE 1 — Ciel Pre-Execution Policy Engine

```markdown
ROLE & TASK: NIO PHASE 1 — PRE-EXECUTION POLICY ENGINE FÜR APOLLO CIEL

(Gemeinsame Konventionen siehe oben. Phase 0 ist gemergt; das Ticket-Konzept aus
`workspace/sigma/app/llm/approval_gate.py` ist das fachliche Vorbild, wird aber nicht importiert.)

Ziel: Vor JEDEM Tool-Call in `SandboxAgent.execute_tool` entscheidet eine Policy-Engine
deterministisch: ausführen, ablehnen oder auf Operator-Freigabe warten.

1. CREATE `apollo/ciel/policy_gate.py`
   - `PermissionTier(StrEnum)`: TIER_0_AUTO, TIER_1_GUARD, TIER_2_APPROVAL.
   - `PolicyVerdictCode(StrEnum)`: OK, KILL_SWITCH_ACTIVE, DRAWDOWN_CIRCUIT_BREAKER, SYMBOL_HALTED,
     RATE_LIMIT_EXCEEDED, BOUNDS_VIOLATION, WAITING_APPROVAL, APPROVAL_REJECTED, APPROVAL_INVALID.
   - `ApprovalTicket`, `PolicyDecision` (allowed, code, reason, tier, ticket) als Ciel-Modelle.
   - `LUA_PRE_EXECUTION_GATE` (ein Roundtrip): KEYS = kill switch `nio:policy:kill_switch`,
     `m8:state:{strategy_id}`, `halt:symbol:{symbol}`, `nio:ratelimit:{session_id}:{tool}`,
     `sigma:daily_pnl_usd:{YYYY-MM-DD}`; ARGV = now_ms, window_ms, max_calls, max_daily_loss_usd, tier.
     Reihenfolge: Kill-Switch (gilt für alle Tiers außer TIER_0) → Strategie-Status → Tagesverlust
     → Symbol-Halt → Rate-Limit (INCR + PEXPIRE bei 1). Rückgabe JSON.
     ACHTUNG — tatsächliche M8-Felder (`M8StateEngine.py`, `LUA_IDEMPOTENT_POST_TRADE_SCRIPT`):
     Hash `m8:state:{id}` mit `status` (ACTIVE | THROTTLED | QUARANTINED | RETIRED),
     `budget_multiplier`, `current_budget_usd`, `base_budget_usd`, `consecutive_losses`.
     Es gibt KEIN `daily_loss_lock`/`daily_dd_pct`. Regel: `status` QUARANTINED/RETIRED oder
     `budget_multiplier == 0` → DRAWDOWN_CIRCUIT_BREAKER. Tagesverlust kommt aus dem in Phase 0
     eingeführten Key `sigma:daily_pnl_usd:{date}` (≤ −max_daily_loss_usd → DRAWDOWN_CIRCUIT_BREAKER).
     `halt:symbol:{symbol}` ist ein String mit TTL 300 s (existiert → SYMBOL_HALTED).
   - `_eval_fallback(...)`: Python-Äquivalent mit identischer Semantik für In-Memory/fakeredis.
   - `PolicyStore`-Protocol mit zwei Adaptern: In-Memory und Redis (funktioniert sowohl mit
     `redis.asyncio` als auch mit `orchestrator.kanban.redis_resp.RedisClient` über ein
     `eval(script, keys, args)`-Shim, das der Aufrufer übergibt).
   - `PreExecutionPolicyEngine(store, *, tool_tiers, default_rate_limit=30, window_ms=60_000,
     max_daily_loss_usd=250.0, approval_ttl_ms=300_000, on_audit=None, on_ticket=None)`:
     `register_tool_tier(name, tier, bounds_validator=None)`,
     `async evaluate(session_id, tool_name, arguments, *, strategy_id="default", symbol=None, approval_ticket_id=None)`,
     `async resolve_ticket(ticket_id, *, approved, operator_id, reason="")`,
     `async pending_tickets(session_id=None)`.
     `on_audit(action: str, payload: dict)` und `on_ticket(ticket)` sind optionale Callables — hier
     hängt später das Kanban-`AuditLedger` bzw. der `TelegramNotifier` ein.
     Unbekannte Tools sind standardmäßig TIER_1_GUARD (nicht TIER_0).
   - Ticket-Freigabe: `arguments_sha256` gebunden, Einmalverwendung (CONSUMED), Ablauf, Tool-Name.

2. MODIFY `apollo/ciel/sandbox_agent.py`
   - Optionaler Parameter `policy_engine: PreExecutionPolicyEngine | None = None` und
     `session_id` in `run(...)` (Default: generierte ID).
   - In `execute_tool` vor der Ausführung `evaluate(...)`. Ablehnung → `ToolResult(ok=False,
     error="POLICY:<code>: <reason>")`. WAITING_APPROVAL → Schleife beenden, `AgentResult` mit
     `final_answer="WAITING_APPROVAL:<ticket_id>"`; den bis dahin aufgebauten Lauf-Zustand
     (intent, state, loaded, messages, ausstehender Call) in einem In-Memory-Dict des Agents ablegen.
   - `async resume_after_approval(session_id, ticket_id) -> AgentResult`: führt den ausstehenden Call
     mit Ticket aus und setzt die Schleife fort. (Persistenz übernimmt Phase 2 über den DAG.)
   - Ohne `policy_engine` verhält sich alles exakt wie bisher.

3. Verdrahtung Kanban (MODIFY `orchestrator/kanban/runtime.py`): Factory, die eine
   `PreExecutionPolicyEngine` mit `on_audit` → `AuditLedger.append(actor="policy", category="approval", ...)`
   und `on_ticket` → Notifier baut. Nur bauen, noch nicht global einschalten.

Tests (CREATE `tests/test_ciel_policy_gate.py`):
- TIER_0 läuft durch; mit Kill-Switch blockiert.
- TIER_1 blockiert bei `status=QUARANTINED`, bei Tagesverlust über Limit, bei Symbol-Halt, ab Call max_calls+1.
- Lua-Skript und Python-Fallback liefern für dieselben 8 Szenarien identische Ergebnisse
  (Lua-Teil nur, wenn ein echter Redis erreichbar ist → sonst `pytest.skip`).
- TIER_2 im SandboxAgent: Tool nicht ausgeführt, Ticket PENDING; nach resolve + resume genau 1x
  ausgeführt; Resume mit veränderten Args → APPROVAL_INVALID; zweites Resume → abgelehnt.
- `on_audit` wird für create/approve/reject/consume aufgerufen.

Verifikation: python3 -m pytest -q tests/test_ciel_policy_gate.py tests/test_ciel_integration.py tests/test_kanban_*.py
```

---

## PHASE 2 — DAG-Checkpointing & episodisches Gedächtnis

```markdown
ROLE & TASK: NIO PHASE 2 — DAG-TURN-CHECKPOINTS (/undo, /retry) + FTS5-GEDÄCHTNIS

(Gemeinsame Konventionen siehe oben.)

1. CREATE `apollo/ciel/dag_state.py`
   - `TurnStatus(StrEnum)`: COMPLETED, ABORTED_CLEAN, WAITING_APPROVAL, FAILED.
   - `DAGTurnNode` (turn_id, session_id, parent_turn_id, branch_name, depth, created_at_ms, status,
     user_input, messages_delta, tool_calls_summary, working_state_hash, working_state,
     pending: dict | None — für WAITING_APPROVAL den ausstehenden Call + ticket_id).
   - `DAGLineageView` (session_id, branch_name, head_turn_id, ordered_turn_ids, messages, working_state).
   - `DAGStateManager(store=None, ttl_seconds=86400)` mit In-Memory-Store (asyncio.Lock) und
     Redis-Store (Keys `nio:dag:{sid}:nodes` Hash, `:branches` Hash, `:active_branch` String;
     Schreiben als MULTI/EXEC bzw. `pipeline(transaction=True)`).
     Methoden: `commit_turn(...)`, `get_node`, `checkout_lineage(session_id, target_turn_id=None, branch_name=None)`,
     `undo(session_id, steps=1)` (verschiebt nur den Head, löscht nichts), `retry_from_parent(session_id, new_branch_name=None)`,
     `list_branches`. Zyklenschutz über `visited`. `working_state_hash` =
     sha256(json.dumps(state, sort_keys=True, default=str))[:16].

2. CREATE `apollo/ciel/memory_tier.py`
   - `WorkingMemoryPin(max_chars=1600).render(state) -> str`: deterministisch sortiert, hart gekappt,
     wird als LETZTE Message angehängt (nie in den Prefix).
   - `EpisodicMemoryStore(db_path=":memory:")`: SQLite WAL, Tabelle `episodic_memories` +
     FTS5-Tabelle `episodic_memories_fts` (`tokenize='porter unicode61'`). Ohne FTS5-Modul
     (`sqlite3.OperationalError`) → BM25-Fallback in Python über `episodic_memories`.
     `store_episode(...) -> memory_id`, `recall(query, top_k=5, session_id=None, category=None)`,
     `_sanitize_fts5_query(raw)` (alphanumerische Tokens, gequotet, mit OR verknüpft).
   - `register_recall_tool(registry: ColdStorageRegistry, store)` registriert
     `recall_episodic_memory` als normales Ciel-Tool (ToolSchema + Handler).

3. MODIFY `apollo/ciel/sandbox_agent.py`
   - Optional `dag_manager`. Wenn gesetzt: jeden abgeschlossenen Turn committen;
     `resume_after_approval` aus Phase 1 liest den ausstehenden Call aus dem WAITING_APPROVAL-Knoten
     statt aus dem In-Memory-Dict (Fallback bleibt für Läufe ohne DAG).

4. CREATE `orchestrator/kanban/memory_bridge.py` (Kanban → Gedächtnis, Importrichtung erlaubt):
   indiziert `Experience`-Datensätze (summary, lessons, skills_delta, outcome) aus dem Kanban-Store
   in `EpisodicMemoryStore` (category="kanban_experience"), idempotent über die Experience-ID.

5. MODIFY `apollo/ciel/__init__.py` (Exporte).

Tests (CREATE `tests/test_ciel_dag_and_memory.py`):
- Linearer Commit von 3 Turns → Lineage [t1, t2, t3], Messages vollständig in Reihenfolge.
- `undo` stellt den Working State von t1 wieder her; t2 bleibt über `get_node` lesbar.
- `retry_from_parent` + neuer Commit: `main` → t2, `fix-branch` → t2b, gemeinsamer Parent t1.
- `WorkingMemoryPin` überschreitet nie `max_chars`.
- Recall mit Sonderzeichen (`SOL/USDC`, `halt:symbol:BTC`) wirft keinen FTS5-Syntaxfehler und rankt
  die relevante Episode auf Platz 1; derselbe Test läuft auch erzwungen über den BM25-Fallback.
- Recall-Tool über `RegistryFunctionExecutor` ausführbar.
- Kanban-Bridge: zweimal indizieren → keine Duplikate.
- Phase-1-Resume funktioniert nach Neuaufbau des Agents allein aus dem DAG.

Verifikation: python3 -m pytest -q tests/test_ciel_dag_and_memory.py tests/test_ciel_*.py
```

---

## PHASE 3 — Abbruch, Ausführungsumgebung, Sub-Agenten

```markdown
ROLE & TASK: NIO PHASE 3 — CANCELLATIONTOKEN, EXECUTION-ENV, delegate_task

(Gemeinsame Konventionen siehe oben. Phasen 0–2 sind gemergt.)

1. CREATE `apollo/ciel/execution_env.py`
   - `AbortReason(StrEnum)`, `ExecutionAbortedError`, `CancellationToken` (asyncio.Event,
     `cancel(reason, detail)`, `on_cancel(cb)`, `wait_cancelled()`, `raise_if_cancelled()`,
     `child()` → verknüpftes Kind-Token, das mit dem Eltern-Token mitfeuert).
   - `ExecutionEnvironment`-Protocol: `async execute(call, *, token, timeout_s) -> ToolResult`.
   - `LocalExecutionEnv` (umhüllt den bestehenden `ToolExecutor`; Race gegen `token.wait_cancelled()`).
   - `SubprocessExecutionEnv` (`start_new_session=True`, Abbruch/Timeout → killpg SIGTERM → Grace
     0.25 s → SIGKILL; Logik wie `SubprocessSandbox._stop_proc` in `orchestrator/kanban/sandbox.py`).
   - KEIN eigenes Docker-Backend: Container-Isolation läuft über `orchestrator/kanban/sandbox.DockerSandbox`.
   - Optional: `KanbanSandboxEnv`-Adapter gehört NICHT nach Ciel, sondern bei Bedarf nach `orchestrator/kanban/`.

2. Abbrechbarer LLM-Call: `OpenAICompatLLMClient.complete` bekommt `token`; der Thread-Aufruf läuft
   als Task und wird gegen `token.wait_cancelled()` geraced. Bei Abbruch sofort zurückkehren
   (der Hintergrund-Thread endet über das bestehende HTTP-Timeout; Ergebnis wird verworfen).

3. MODIFY `apollo/ciel/sandbox_agent.py`
   - `run(..., token: CancellationToken | None = None)`. Abbruch während LLM- oder Tool-Call →
     Schleife sofort beenden, Turn mit `TurnStatus.ABORTED_CLEAN` committen (nur vollständige
     Assistant/Tool-Paare in `messages_delta`; ein halber Tool-Call wird nicht persistiert),
     `final_answer="[ABORTED_CLEAN]"`.
   - Registry der laufenden Tokens pro session_id (`SandboxAgent.abort(session_id, reason)`), damit
     Phase 4 per API abbrechen kann.

4. CREATE `apollo/ciel/subagent_delegator.py`
   - `DELEGATE_TOOL_NAME = "delegate_task"`, `SubAgentTaskSpec` (objective, allowed_tools,
     max_turns 1–12, timeout_s 0.1–120, context_slice), `SubAgentReceipt` (status COMPLETED|TIMEOUT|
     ABORTED|FAILED, turns_used, executed_tools, summary ≤ 1200 Zeichen, extracted_data).
   - Kind-Agent sieht nur `allowed_tools` (Scoped-Executor lehnt alles andere ab), niemals
     `delegate_task` (keine Rekursion), läuft mit `copy.deepcopy(parent_state) | context_slice`,
     Kind-Token vom Eltern-Token, `asyncio.wait_for(timeout_s)`. Dieselbe Policy-Engine (Phase 1) gilt
     auch im Kind — TIER_2 im Kind → Receipt `FAILED` mit Hinweis, kein eigenes Ticket.
   - Nur der Receipt landet im Eltern-Buffer; Kind-Turns optional als eigener DAG-Branch
     `sub/<task_id>` archiviert.
   - `delegate_task` wird als Meta-Tool im SandboxAgent angeboten, wenn ein Delegator übergeben ist.

Tests (CREATE `tests/test_ciel_exec_abort_and_delegation.py`):
- SubprocessExecutionEnv: Eltern + Enkelprozess sind nach `cancel()` innerhalb < 0.6 s weg.
- SandboxAgent mit hängendem Tool: `abort()` nach 50 ms → Rückkehr, DAG-Knoten ABORTED_CLEAN,
  keine verwaisten Tool-Messages.
- Abbruch während des LLM-Calls (Fake-Client mit `asyncio.sleep(10)`).
- Delegation: Kind ruft `nuke_account` (nicht erlaubt) → abgelehnt; `read_market` → ok;
  `parent_state` unverändert; Kind kann `delegate_task` nicht aufrufen.
- Timeout 0.15 s → Receipt TIMEOUT.

Verifikation: python3 -m pytest -q tests/test_ciel_exec_abort_and_delegation.py tests/test_ciel_*.py
```

---

## PHASE 4 — Control Plane & Apollo-CLI

```markdown
ROLE & TASK: NIO PHASE 4 — RUNTIME-ROUTEN, NEXT-PROXY, APOLLO-CLI

(Gemeinsame Konventionen siehe oben. Phasen 1–3 sind gemergt.)

1. MODIFY `orchestrator/kanban/api.py` + `orchestrator/kanban/runtime.py`
   Neuer Router `/api/runtime`, ALLE Routen mit der bestehenden `operator`-Dependency (Bearer
   `NIO_KANBAN_API_TOKEN`, 503 ohne Token):
   - `GET  /api/runtime/session/{sid}/dag` → Lineage + Branches
   - `POST /api/runtime/session/{sid}/undo` `{steps: 1..50}`
   - `POST /api/runtime/session/{sid}/retry` `{branch_name?}`
   - `POST /api/runtime/session/{sid}/abort` `{reason}` → `SandboxAgent.abort` + Publish auf dem
     Kanban-Bus (Event-Typ `runtime.abort`), Antwort `{"ok": true, "status": "ABORT_SIGNAL_SENT"}`
   - `GET  /api/runtime/approvals/pending?session_id=`
   - `POST /api/runtime/approvals/{ticket_id}/resolve` `{approved, reason}` — `operator_id` kommt
     aus der Auth (`actor`), NICHT aus dem Body.
   Runtime-Singletons (DAGStateManager, PreExecutionPolicyEngine, SandboxAgent-Registry) werden in
   `build_runtime` erzeugt. Neue `*Out`-Modelle in die Paritätsprüfung von `tests/test_kanban_api.py` aufnehmen.

2. CREATE `frontend/src/app/api/runtime/[...path]/route.ts`
   Server-seitiger Proxy auf die Kanban-API; liest `NIO_KANBAN_API_URL` und `NIO_KANBAN_API_TOKEN`
   aus der Server-Umgebung. Das Token gelangt nie in den Browser. Nur die oben gelisteten Pfade
   durchlassen (Allowlist). Vorbild: `frontend/src/app/api/sandbox`.

3. MODIFY `frontend/src/apollo/commands.ts`
   - `ParsedCommand` um `{kind:"undo";steps}`, `{kind:"retry";branch?}`, `{kind:"abort";reason}`,
     `{kind:"approve";ticketId}`, `{kind:"reject";ticketId;reason}`, `{kind:"approvals"}` erweitern.
   - `COMMANDS`-Einträge im bestehenden Format `{ command, usage, detail }`.
   - `parseCommand` + `suggestCommand` ergänzen.

4. MODIFY `frontend/src/apollo/store.ts` + `frontend/src/apollo/client.ts`
   - State: `sessionId`, `activeBranch`, `headTurnId`, `dagLineage`, `pendingApprovals`.
   - `runCommand`-Switch um die neuen `kind`s erweitern; Client-Funktionen rufen `/api/runtime/...`.
   - `/abort`: laufenden `fetch` per AbortController kappen UND Backend-Abort senden; bei
     Offline/Mock nur lokal abbrechen und `[ABORTED_CLEAN]` in die History schreiben.
   - Pending-Approvals per Polling (5 s) oder über den bestehenden Telemetrie-SSE, falls dort ein
     passender Kanal existiert.

Tests:
- CREATE `tests/test_runtime_control_plane.py` (FastAPI TestClient; skip ohne fastapi):
  ohne Token 503/401; undo/retry/abort/approve-Lebenszyklus; `operator_id` = Auth-Actor.
- Frontend hat kein Test-Skript (nur `typecheck`): `npm --prefix frontend run typecheck` muss grün sein;
  `parseCommand` ist rein — Parser-Fälle als kleine Tabelle in einem Node-Skript oder via `tsx` prüfen.
- Manuell im Browser (Dev-Server `frontend`, Port 4001): `/approvals`, `/approve <id>`, `/abort`.

Verifikation: python3 -m pytest -q tests/test_runtime_control_plane.py tests/test_kanban_api.py
              npm --prefix frontend run typecheck
```

---

## PHASE 5 — Compaction, Cache-stabile Tools, prozedurale Skills

**Vorab zu entscheiden:** Soll die Garantie „≤ 3 Skills + 1 Meta-Tool pro Turn" bleiben?

- **Option A (empfohlen):** Neue Invariante „stabiler Prefix + append-only, gedeckelt auf N
  dynamische Tools pro Session". `test_prompt_payload_max_3_plus_meta_with_150_tools` wird bewusst
  auf die neue Invariante umgeschrieben. Lohnt sich nur, wenn das Routing auf einen Provider mit
  Prefix-Caching festgelegt ist (beim FreeLLMAPI-Failover ist der Gewinn gering).
- **Option B:** MRU-Fenster bleibt; nur Micro-Compaction und `load_skill` werden umgesetzt.

```markdown
ROLE & TASK: NIO PHASE 5 — MICRO-COMPACTION, PROMPT-ASSEMBLER, PROZEDURALE SKILLS

(Gemeinsame Konventionen siehe oben. Entscheidung Option A/B: <HIER EINTRAGEN>.)

1. CREATE `apollo/ciel/compactor.py`
   `StateReceipt` + `MicroCompactor(byte_threshold=1024, keep_recent_tool_turns=1, blob_store=None)`:
   Ältere `role=="tool"`-Messages > Schwelle werden durch ein Receipt-JSON ersetzt (`tool_call_id`
   und `role` bleiben unverändert). Original unter `nio:blob:{sid}:{tool_call_id}` im Blob-Store
   (Dict oder Redis). Strukturierte Extraktion für JSON (Skalare wie status/ok/error/count/symbol/price,
   `<key>_count` für Listen). Idempotent (vorhandene Receipts werden übersprungen).
   Blobs sind über ein Tool `fetch_blob(blob_ref)` (TIER_0) zurückholbar.

2. CREATE `apollo/ciel/prompt_assembler.py` (nur bei Option A)
   Prefix pro Session einfrieren (System-Prompt + kanonisch sortierte Basis-Tools + Skill-Header-Index),
   `prefix_sha256`; dynamische Tools nur anhängen; Working-Memory-Pin aus Phase 2 als letzte Message.
   In `SandboxAgent` `loaded.insert(0, …)` durch Append ersetzen und den Deckel N einführen.

3. CREATE `apollo/ciel/procedural_skills.py`
   `SkillStepSpec` (input_bindings `arg -> "step_<j>.<key>"`), `ProceduralSkillSpec`
   (`to_markdown_playbook()` mit YAML-Frontmatter), `ProceduralSkillRegistry` (SQLite,
   `record_outcome` mit Wilson-Lower-Bound z=1.96, Formel aus `Architect/core/learning/skill_profiles.py`
   stdlib-only übernehmen), `build_compact_header_index`, `load_skill_payload`;
   `TrajectorySkillDistiller` (erkennt Datenfluss: Argumentwert == Top-Level-Output eines früheren Schritts).
   Meta-Tool `load_skill(skill_id)`: Playbook als Tool-Result, `required_tools` werden aktiviert.

4. MODIFY `apollo/ciel/synthesizer.py`: `MacroSkillSynthesizer` bleibt für Rückwärtskompatibilität;
   Post-Run-Hook ruft zusätzlich den Distiller auf (nur bei Erfolg und ≥ 2 verschiedenen Tools).
   Distillierte Skills werden zusätzlich als Episode (Phase 2) gespeichert.

5. MODIFY `apollo/ciel/sandbox_agent.py`: `compactor` (ab Turn 2 vor jedem LLM-Call),
   `skill_registry`, `load_skill`.

Tests (CREATE `tests/test_ciel_cache_and_compaction.py`, `tests/test_ciel_procedural_skills.py`):
- Compaction: zwei 8-KB-Ergebnisse → < 600 Bytes, gleiche `tool_call_id`, Blob verlustfrei,
  letztes Ergebnis unangetastet, zweimal compacten → keine verschachtelten Receipts.
- (Option A) 4 Turns mit `request_additional_skill`: `messages[0]` und die ersten K Tools byte-identisch.
- Distiller erkennt `token_address ← step_0.mint_address`, `depth` in `static_args`.
- Wilson-Ranking: 15/1 vor 1/0.
- `load_skill`: Playbook im Buffer, benötigte Tools am Ende von `tools`.

Verifikation: python3 -m pytest -q tests/test_ciel_*.py
```

## 4. Offene Entscheidungen

1. Phase 5: Option A oder B (siehe oben).
2. Sigma: Sollen Approval-Tickets aus Phase 0 später auf die Ciel-Policy-Engine (Phase 1) migriert
   werden, oder bleibt Sigma bewusst eigenständig (eigener Prozess, synchroner Executor)?
3. Phase 4: Reicht Polling für Pending-Approvals, oder soll der Kanban-Bus per SSE ins Frontend?
