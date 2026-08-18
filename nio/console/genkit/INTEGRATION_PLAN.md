# GenKit integration plan

Companion to `ADR-002-firebase-genkit.md`. This file is the concrete to-do for the next engineering turn — not a design document.

## Package additions

```json
{
  "dependencies": {
    "genkit": "^1.0.0",
    "@genkit-ai/vertexai": "^1.0.0",
    "@genkit-ai/postgres": "^1.0.0",
    "zod": "^3.23.0"
  }
}
```

Zod is already transitively present; pin the version so GenKit's schema inference and our Drizzle validation agree.

## New directory layout

```
genkit/
├── genkit.config.ts            # dev server + plugin registration
├── flows/
│   ├── echo-post-mortem.ts     # replaces reflection-engine.ts
│   ├── atlas-plan.ts           # replaces planning-with-memory.ts
│   └── delta-review.ts         # RLHF dataset evaluator
├── retrievers/
│   └── ledger-pgvector.ts      # thin wrapper around @genkit-ai/postgres
├── evaluators/
│   └── post-mortem-quality.ts  # defineEval over rlhf_samples
└── datasets/
    └── human-overrides.jsonl   # seeded from rlhf_samples on first run
```

## What gets deleted

- `src/lib/autodidactic/reflection-engine.ts` → replaced by `genkit/flows/echo-post-mortem.ts`
- `src/lib/autodidactic/planning-with-memory.ts` → replaced by `genkit/flows/atlas-plan.ts`
- `src/lib/autodidactic/rlhf-capture.ts` → split into a flow + a dataset

`src/db/schema.ts` is untouched. The ledger tables remain the source of truth; GenKit reads and writes them through Drizzle.

## Local developer workflow

```bash
# one-time
npm install

# every day
npx genkit start           # boots trace viewer at http://localhost:4000
npm run dev                 # boots Next.js console at http://localhost:3000
```

The trace viewer at :4000 is the primary debug surface for the autodidactic loop. On-call uses Cloud Logging for production; engineers use GenKit traces for local iteration.

## Cloud Build change

One step added after the existing `build` step:

```yaml
- name: 'node:20-alpine'
  id: 'genkit-deploy'
  entrypoint: 'npx'
  args: ['genkit', 'build']
  waitFor: ['build']
```

The flows are bundled into the same Cloud Run image. No separate deployment target.

## Telemetry

GenKit emits OpenTelemetry spans. Route them to Cloud Trace with:

```typescript
import { CloudTraceExporter } from '@genkit-ai/google-cloud';

const ai = genkit({
  plugins: [
    vertexAI({ projectId: process.env.PROJECT_ID, location: 'europe-west3' }),
    new CloudTraceExporter({ projectId: process.env.PROJECT_ID }),
  ],
});
```

This replaces the manual `console.log` calls currently scattered through the autodidactic modules.

## First acceptance test

After Phase 1 lands, the following must pass:

1. `npx genkit start` opens the trace viewer without errors.
2. Invoking `echoPostMortem` with a mock event writes exactly one row to `twin_behavioral_ledger` with a non-null `embedding`.
3. The trace viewer shows three steps: retrieve, generate, persist — in order.
4. Cloud Trace receives the same span tree within 30 seconds.

If any of those fail, Phase 2 is blocked.
