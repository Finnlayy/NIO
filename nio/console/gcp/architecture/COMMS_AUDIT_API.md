# Comms Audit API Contract

**Status:** Spec only — backend follow-up  
**Consumers:** NIO Console `CommsAuditPage`, Cody pet, Telegram supervisor  
**Date:** 2026-07-15

---

## Overview

The inter-agent message bus (`InterAgentMessageBus`) is the canonical audit trail for orchestrator ↔ limb ↔ Cody traffic. This contract extends existing endpoints so the console can:

1. Filter to **user-relevant** messages by default
2. Optionally surface **Cody-mediated actions** on the bus for a full conversational audit trail
3. Close the loop on **gate approval requests** via `approval_response`

---

## 1. Extended comms endpoint

### Request

```
GET /api/agents/cody/comms?since=<messageId>&filter=relevant|all&limit=50
```

| Param | Default | Description |
|-------|---------|-------------|
| `since` | — | Return only messages newer than this `messageId` (delta cursor) |
| `filter` | `relevant` | `relevant` applies user-visibility rules; `all` returns full bus slice |
| `limit` | `50` | Max messages to consider from ring buffer (1–500) |

### Response

```typescript
interface CodyCommsResponse {
  timeline: FormattedInterAgentLine[];
  latestMessageId: string | null;
  filter: "relevant" | "all";
  totalAvailable: number;
}
```

### Relevant filter logic

Apply in `buildCodyCommsResponse()` (`nio/backend/src/cody_supervisor.ts`):

```typescript
function isRelevantForUser(msg: InterAgentMessage, formatted: FormattedInterAgentLine): boolean {
  if (isUserVisibleInterAgentMessage(msg)) return true;
  if (formatted.severity === "warning" || formatted.severity === "error") return true;
  return false;
}
```

`isUserVisibleInterAgentMessage()` (already in `format.ts`):

- `msg.to === 'cody'` or `msg.to === 'user'`
- `msg.type === 'approval_request'`

Supervisor aggregation (`buildCodySupervisorStatus().interAgentTimeline`) should use the same `filter=relevant` default for consistency with notification bell counts.

---

## 2. Extended timeline line shape

```typescript
type AgentChannel = "orchestrator" | "subagent" | "limb" | "cody" | "user";

type InterAgentMessageType =
  | "dispatch"
  | "gate_checkpoint"
  | "task_result"
  | "approval_request"
  | "approval_response"
  | "user_message"   // new
  | "cody_relay";    // new

interface FormattedInterAgentLine {
  messageId: string;
  timestamp: string;
  severity: "info" | "success" | "warning" | "error";
  headline: string;
  body: string;
  actors: { from: string; to: string };
  // extensions
  type?: InterAgentMessageType;
  isUserVisible?: boolean;
  channel?: { from: AgentChannel; to: AgentChannel };
  requiresAction?: boolean;
  actionPayload?: {
    gateId?: string;
    taskId?: string;
    blockedBy?: string;
  };
}
```

Populate `isUserVisible`, `type`, `channel`, `requiresAction` in `formatInterAgentMessage()`.

`requiresAction: true` when `type === 'approval_request'` and no matching `approval_response` exists for the same gate/task.

---

## 3. Cody publish-back

### Configuration

| Env / flag | Effect |
|------------|--------|
| `CODY_PUBLISH_TO_BUS=true` | Server always publishes Cody chat turns to bus |
| `publishToBus: true` on chat POST | Per-request override (client preference) |

### Chat request extension

```
POST /api/agents/cody/chat
```

```typescript
{
  message: string;
  sessionId?: string;
  history?: Array<{ role: "user" | "assistant"; content: string }>;
  publishToBus?: boolean;
}
```

### Bus messages to publish

| Trigger | Message |
|---------|---------|
| User sends chat (console/Telegram) | `{ type: 'user_message', from: 'user', to: 'cody', payload: { message, sessionId, source } }` |
| Cody returns reply | `{ type: 'cody_relay', from: 'cody', to: 'user', payload: { reply, sessionId, isStatusReport } }` |
| Cody routes task to Atlas | `{ type: 'dispatch', from: 'cody', to: 'orchestrator', payload: { message, taskId? } }` |
| Telegram alert sent | `{ type: 'cody_relay', from: 'cody', to: 'user', payload: { channel: 'telegram', alert } }` |

### Formatters (add to `format.ts`)

**`user_message`:**

- headline: `You → Cody`
- body: truncated user message
- severity: `info`
- isUserVisible: `true`

**`cody_relay`:**

- headline: `Cody → You` (or `Cody → Telegram` when `payload.channel === 'telegram'`)
- body: reply or alert text
- severity: `info` (or `warning` if alert)
- isUserVisible: `true`

---

## 4. Approval loop

### Request

```
POST /api/inter-agent/approve
Content-Type: application/json
```

```typescript
{
  messageId: string;   // approval_request messageId
  approved: boolean;
  reason?: string;
}
```

### Response

```typescript
{
  ok: true;
  responseMessageId: string;
}
```

### Bus publish on success

```typescript
interAgentMessageBus.publish({
  type: "approval_response",
  from: "user",
  to: "orchestrator",
  payload: { approved, messageId, reason },
});
```

Gate runner / orchestrator should consume `approval_response` to unblock deferred dispatches (future work).

### Errors

| Status | Condition |
|--------|-----------|
| 400 | Missing `messageId` or unknown message |
| 409 | Already responded to this approval |
| 404 | Message not found or not an `approval_request` |

---

## 5. Optional publish endpoint (Telegram bridge)

For Python clients that cannot import the in-process bus:

```
POST /api/inter-agent/publish
```

```typescript
{
  type: InterAgentMessageType;
  from: AgentChannel;
  to: AgentChannel;
  targetId?: string;
  payload: Record<string, unknown>;
}
```

Allowed `from` values: `cody`, `user` (server validates token/source).

---

## 6. Frontend fallback (pre-backend)

Until backend ships filter params and extended fields:

- Console calls existing `GET /api/agents/cody/comms` without `filter`
- Applies client-side relevant filter using `actors.from` / `actors.to` labels and severity
- Shows subtle "API upgrade pending" badge when `isUserVisible` is absent from response lines
- Approval buttons call `POST /api/inter-agent/approve` and show disabled/error state on 404

---

## 7. Related files (backend follow-up checklist)

- [ ] `nio/backend/src/cody_supervisor.ts` — filter param, extended response
- [ ] `nio/backend/src/inter_agent/format.ts` — new formatters, populate extended fields
- [ ] `nio/backend/src/inter_agent/types.ts` — `user_message`, `cody_relay` types
- [ ] `nio/backend/src/cody_chat.ts` — publish-back on chat
- [ ] `nio/backend/src/server.ts` — `/api/inter-agent/approve`, optional `/publish`
- [ ] `cody_supervisor.py` — optional publish after Telegram alerts

---

## 8. Out of scope

- SSE `GET /api/agents/cody/events`
- PostgreSQL persistence of bus messages
- Manifest mutation audit trail merge (separate system)
