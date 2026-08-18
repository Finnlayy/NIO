# Inter-Agent Communication (Orchestrator ↔ Subagents)

Hard-gated messaging between the NIO orchestrator and subagent limbs, with **Cody as supervisor** mediating status to the user.

## Architecture

```
User (Telegram)
      ↕ Cody supervisor (telegram_notify.py + cody_supervisor.py)
      ↕ POST /api/task (source=telegram) · GET /api/agents/cody/supervisor
NIO Orchestrator
      ↕ hard gates (budget · policy · telemetry · parent approval)
      ↕ InterAgentMessageBus
Subagent Limbs (deployed via limb_lifecycle)
      ↕
PostgreSQL conversation_sessions (optional)
```

Cody is not just a bridge — he **monitors** orchestrator health, active limbs, gate pass/fail, budget, and persistence; **mediates** user messages → orchestrator and gate failures → user alerts; and answers status queries ("what are agents doing?").

## Hard Gate Specs

| Gate ID | Kind | Required | Blocks dispatch when |
|---------|------|----------|----------------------|
| `gate-budget` | `budget_check` | yes | Daily spend ≥ budget (unless clamp_to_free_tier) |
| `gate-policy` | `policy_check` | yes | Empty task or destructive pattern without approval |
| `gate-telemetry` | `telemetry_emit` | yes | Always passes; emits checkpoint telemetry |
| `gate-parent-approval` | `parent_approval` | yes | `isDestructive=true` without `parentApproved=true` |

Gate results flow to:
- `InterAgentMessageBus` (`to: cody` on checkpoint, `to: user` on failure)
- Telemetry (`agentId: gate:<id>`)
- `GET /api/agents/cody/supervisor` for Cody polling

## API Endpoints

### `POST /api/inter-agent/dispatch`
Run gates + deploy limb if all pass.

```json
{
  "taskDescription": "Implement unit tests for PDC",
  "role": "worker",
  "templateId": "python-test-engineer",
  "isDestructive": false
}
```

### `POST /api/inter-agent/gate-check`
Dry-run gates without deploying.

### `GET /api/inter-agent/messages?limit=50&from=orchestrator&to=cody`
Recent message bus events.

### `GET /api/agents/cody/supervisor`
Full supervisor status (limbs, gates, budget, persistence).

### `GET /api/agents/cody/supervisor?format=text`
Human-readable report for Cody → user.

### `GET /api/agents/cody/stats`
Extended with `supervisor` summary block for CodyStatsBoard.

## Cody Supervisor (Python)

`cody_supervisor.py` at workspace root:
- `supervisor_heartbeat()` — poll on each Telegram daemon cycle
- `fetch_supervisor_report()` — status query responses
- Gate failure alerts → Telegram via `send_alert` callback

## Modules

- `types.ts` — GateSpec, InterAgentMessage, DEFAULT_SUBAGENT_GATE_SPECS
- `gate_runner.ts` — sequential gate evaluation + Cody notification
- `orchestrator.ts` — message bus + `dispatchSubagentWithGates`
- `../cody_supervisor.ts` — status aggregation for Cody

## Integration

`middleware.ts` calls `dispatchSubagentWithGates` before non-telegram limb tasks. Telegram tasks skip limb deploy (Cody handles user channel directly) but Cody still monitors all gate events via supervisor polling.
