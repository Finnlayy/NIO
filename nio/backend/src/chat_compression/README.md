# Predictive Delta Compression (PDC)

Brain-inspired chat compression for the NIO neural orchestrator, mapped from [Jancke lab primary visual cortex research](https://jancke-lab.de/in-the-media/detail/the-brains-data-compression-mechanisms:248).

## Brain → Chat Mapping

| Neural principle | PDC component | Chat behavior |
|------------------|---------------|---------------|
| Dual coding (short vs long intervals) | **HotWindow** vs **DeltaEncoder** | Recent turns sent verbatim; older turns encoded as deltas |
| Predictive coding | **SessionBaseline** | Model receives expectations + error signals, not repeated full state |
| Redundancy suppression | **stripFiller**, **suppressRedundant** | Filler words and baseline-known facts stripped early |
| Temporal tiers | Hot / warm / cold | Hot = full fidelity; warm = compact deltas; cold = folded into baseline |

## Architecture

```
messages[] ──► CompressionTrigger ──► SessionBaseline (predictive state)
                      │                      ▲
                      ▼                      │ mergeDeltaIntoBaseline
                 DeltaEncoder ───────────────┘
                      │
                      ▼
              hotWindow (verbatim)
                      │
                      ▼
                 Rehydrator ──► LLM userPrompt (within tokenBudget)
```

## Modules

- `types.ts` — SessionBaseline, TurnDelta, ConversationCompression
- `baseline_store.ts` — predictive state merge + summary rendering
- `delta_encoder.ts` — heuristic delta extraction (no LLM on hot path)
- `compression_trigger.ts` — budget check + cold-tier compression
- `rehydrator.ts` — reconstruct prompt from baseline + deltas + hot window

## API Integration

Pass `conversationCompression` on `POST /api/task`:

```json
{
  "taskDescription": "Reply as Cody to the latest user message.",
  "isComplexWorkflow": false,
  "source": "telegram",
  "conversationCompression": {
    "baseline": { "topics": [], "decisions": [], "openTasks": [], "entities": [], "summaryVersion": 1 },
    "hotWindow": [{ "role": "user", "content": "..." }],
    "deltas": [],
    "tokenBudget": 2000
  }
}
```

Optional standalone compression: `POST /api/chat/compress` (Phase 2 adds PostgreSQL persistence).

## Phase 2

### PostgreSQL `conversation_sessions`

Optional persistence when `DATABASE_URL` is set. Schema in `migrations/001_conversation_sessions.sql`.

```bash
# optional
DATABASE_URL=postgresql://user:pass@localhost:5432/nio
CODY_SESSION_ID=cody-telegram   # stable session key for Cody
```

`POST /api/chat/compress` accepts `sessionId`, `source`, and persists when configured.
`GET /api/chat/sessions/:sessionId` retrieves stored compression state.

### LLM summarization (cold path)

When heuristic baseline exceeds `tokenBudget`, `compressSessionAsync` calls `ManifestLlmAdapter` provider chain (LM Studio first when `LMSTUDIO_ENABLED=true`), falling back to heuristics.

Post-task summarization runs best-effort after `POST /api/task` when `conversationCompression` is present.

### Cody supervisor

Cody mediates user ↔ orchestrator ↔ limbs. See `inter_agent/README.md` and `cody_supervisor.py`.

## Cody Telegram (single-process)

Cody routes Telegram messages through `POST /api/task` with `source: "telegram"` and optional `conversationCompression`. When you run `npm start` in `nio/backend`, Cody's `telegram_notify.py serve` poller starts automatically after NIO listens — no separate manual process. See `nio/backend/README.md` for env vars (`CODY_ENABLED`, `CODY_PYTHON`, `WORKSPACE_ROOT`).
