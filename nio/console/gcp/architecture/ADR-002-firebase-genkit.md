# ADR-002 — Firebase and GenKit in the Nexus stack

- **Status**: Proposed
- **Date**: 2026-06
- **Deciders**: Platform, Security, Autodidactic-Engine
- **Scope**: Nexus Console, 10-agent registry, autodidactic loop, GCP deployment

---

## Verdict, up front

**GenKit: yes, adopt.** It is a developer framework, not infrastructure — it wraps the Vertex AI + Cloud SQL stack we already provisioned and gives us three things we are currently hand-rolling: type-safe agent flows, a local trace viewer for the reflection loop, and an evaluation harness that replaces the stubs in `src/lib/autodidactic/`.

**Firebase the platform: partial, narrow.** Adopt **App Check** for console API protection and **Firestore only as a real-time fan-out layer for the console UI**. Do not adopt Firestore as the primary data store, Firebase Auth as the identity provider, or Firebase Hosting as the runtime — each of those is already covered by a stronger primitive in our stack (Cloud SQL with pgvector, Cloud IAM, Cloud Run with Next.js SSR).

The rest of this document is the reasoning.

---

## Context

Nexus currently runs on a Google-Cloud-native stack:

- Cloud Run for the Next.js console
- Cloud SQL Postgres + pgvector for the ledger and embeddings
- Vertex AI (Gemini 3.5 Flash / 3.1 Pro) for model inference
- Secret Manager, Cloud IAM, Cloud Workflows, Pub/Sub
- A hand-written reflection engine in `src/lib/autodidactic/`

Two pressure points are pushing us toward a framework layer:

1. The post-mortem, planning-with-memory, and RLHF modules are typed with ad-hoc interfaces. A schema mistake in one module silently corrupts the ledger.
2. Debugging an agent trace today means grepping Cloud Logging. The reflection loop is exactly the kind of multi-step, tool-using flow that GenKit's trace viewer was built to visualise.

Firebase appears on the table because GenKit is published under `firebase/genkit` and the marketing pages present them together. They are not the same thing.

---

## The split

GenKit and Firebase are orthogonal. GenKit runs anywhere Node.js runs — locally, on Cloud Run, on Cloud Functions, on a VM. Firebase is a bundle of managed services. The question decomposes into two independent yes/no decisions.

| Component | Today | GenKit | Firebase piece | Decision |
|---|---|---|---|---|
| Flow orchestration | Hand-rolled TS modules | Adopt — type-safe flows, Zod schemas, retry, plugin system | n/a | **Yes** |
| Trace / debug UI | Cloud Logging grep | Adopt — `genkit start` dev server, full step traces | n/a | **Yes** |
| Evaluation harness | `reflection-engine.ts` stubs | Adopt — built-in datasets + metrics | n/a | **Yes** |
| Model calls | Direct Vertex SDK | Replace with `genkit` + `@genkit-ai/vertexai` plugin | n/a | **Yes** |
| Primary database | Cloud SQL + Drizzle + pgvector | Plugin available for pgvector | Firestore | **Keep Cloud SQL** |
| Console hosting | Cloud Run + Next.js SSR | n/a | Firebase Hosting (static only) | **Keep Cloud Run** |
| Identity | Cloud IAM + Identity Platform | n/a | Firebase Auth | **Keep IAM** (add Identity Platform only if console needs user-level auth) |
| Console API protection | None | n/a | App Check | **Adopt App Check** |
| Real-time UI updates | Polling | n/a | Firestore listeners | **Adopt Firestore, narrow scope only** |
| Background jobs | Cloud Workflows + Cloud Tasks | GenKit flows can be deployed as Cloud Functions | Cloud Functions for Firebase | **Keep Workflows; allow GenKit flows on Cloud Run/Functions** |

---

## Why GenKit wins its column

Three concrete wins for Nexus specifically:

**Schema-validated flows.** Every post-mortem input becomes a Zod schema. A mis-typed `agentsUsed` array from an upstream agent fails at the flow boundary, not three functions deep inside `reflection-engine.ts`. The ledger table `twin_behavioral_ledger` gets a single canonical input shape.

**Trace viewer for the reflection loop.** Run `npx genkit start` locally, execute `planWithMemory`, and see every Vertex call, every pgvector lookup, every Cloud Workflows step as a node in a timeline. Today this trace is reconstructed from three log streams. For an autodidactic system where the post-mortem *is* the product, this is not a convenience — it is the debugging surface.

**Evaluation harness.** GenKit's `defineEval` with datasets plugs directly into our `rlhf_samples` table. We can score prompt versions against historical human overrides without writing another custom runner. Echo stops being a hand-built curator and becomes a GenKit-evaluated agent.

---

## Why Firebase narrows to two pieces

**Firestore is wrong as the primary store.** Our ledger is relational: joins across `twin_behavioral_ledger`, `agent_manifest_versions`, `rlhf_samples`, with pgvector for semantic retrieval. Firestore would force us to denormalise, lose the joins, and rebuild the embedding search with a separate vector store anyway. Cloud SQL stays.

**Firestore is right as a pub/sub layer for the console UI.** The Orchestrator Console currently polls mock data. A Firestore collection `agent_status/{agentId}` with real-time listeners gives us sub-second UI updates without standing up a WebSocket server. This is the only place Firestore earns its keep — as a thin real-time fan-out of state that Pub/Sub + Cloud Run already produce. If we already have Pub/Sub provisioned and don't want two messaging layers, skip Firestore and keep polling; the win is real but optional.

**Firebase Auth is the wrong identity model.** IAM and Identity Platform already give us enterprise SSO, org-policy enforcement, and audit logs that feed Cloud Audit Logs natively. Firebase Auth is consumer-shaped — email + Google + phone — and would create a second identity surface that Security has to review. Reject.

**Firebase Hosting is the wrong runtime.** Next.js SSR on Cloud Run is already in Terraform, has Cloud SQL sidecar access, and supports the image-based deploys Cloud Build produces. Firebase Hosting is static + Cloud Functions rewrites; it would fragment the deployment. Reject.

**App Check is worth it.** It attests that requests to the console API come from a genuine client (web or mobile). Cheap to enable, prevents casual abuse of the orchestrator endpoints, and composes with our existing IAM. Adopt.

---

## GenKit integration sketch

Not code to ship today — the shape of the integration so the next turn can build it.

```typescript
// genkit/flows/echo-post-mortem.ts
import { genkit, z } from 'genkit';
import { vertexAI, gemini35Flash } from '@genkit-ai/vertexai';
import { postgresRetriever } from '@genkit-ai/postgres'; // pgvector plugin

const ai = genkit({
  plugins: [vertexAI({ projectId: process.env.PROJECT_ID, location: 'europe-west3' })],
  model: gemini35Flash,
});

const PostMortemInput = z.object({
  eventId: z.number(),
  taskId: z.string(),
  taskType: z.string(),
  outcome: z.enum(['passed', 'revised', 'escalated']),
  score: z.number().min(0).max(100),
  agentsUsed: z.array(z.object({
    agentId: z.string(),
    performanceScore: z.number(),
    executionTimeMs: z.number(),
  })),
});

const PostMortemOutput = z.object({
  whatWorked: z.array(z.string()),
  whatFailed: z.array(z.string()),
  rootCause: z.string().nullable(),
  strategyUpdate: z.string().nullable(),
  learningDelta: z.number(),
});

export const echoPostMortem = ai.defineFlow(
  { name: 'echoPostMortem', inputSchema: PostMortemInput, outputSchema: PostMortemOutput },
  async (input) => {
    // Step 1: retrieve similar past events from pgvector
    const similar = await ai.retrieve({
      retriever: postgresRetriever({ tableName: 'twin_behavioral_ledger' }),
      query: `${input.taskType} ${input.outcome}`,
      options: { limit: 5 },
    });

    // Step 2: model call with retrieved context
    const { output } = await ai.generate({
      prompt: `Analyse the post-mortem. Past similar events:\n${similar.map(s => s.text).join('\n---\n')}\n\nCurrent event:\n${JSON.stringify(input)}`,
      output: { schema: PostMortemOutput },
    });

    // Step 3: persist (side effect outside the flow return)
    await persistLedger(input, output);
    return output;
  }
);
```

What changes in the repo when this lands:

- `src/lib/autodidactic/reflection-engine.ts` is replaced by a thin wrapper that invokes `echoPostMortem`.
- `src/lib/autodidactic/planning-with-memory.ts` becomes a second flow `atlasPlan`.
- `src/lib/autodidactic/rlhf-capture.ts` becomes a dataset definition plus a `defineEval`.
- A new `genkit/` directory holds flows, evaluators, and the dev config.
- Cloud Build gets one extra step: `npx genkit deploy` (or the flows are bundled into the Cloud Run image; either works).

What does not change:

- Terraform. GenKit runs inside Cloud Run; no new GCP resources.
- Database schema. GenKit reads and writes the existing tables.
- IAM. GenKit uses the runtime service account; no new bindings.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GenKit schema churn breaks ledger writes | Medium | High | Pin GenKit major; gate schema changes behind the manifest-versioning table |
| Two messaging layers (Pub/Sub + Firestore) confuse operators | Medium | Low | Pick one for UI fan-out; document the decision in `gcp/README.md` |
| App Check blocks legitimate internal tooling | Low | Medium | Maintain a server-to-server bypass via App Check debug tokens in staging only |
| Team learning curve for GenKit flows vs plain TS | Medium | Low | Pair-programming one flow (Echo) as the reference; ADR-003 to follow if patterns diverge |
| GenKit plugin for pgvector lags Postgres version | Low | Medium | Pin Cloud SQL to Postgres 15; track plugin release notes |

---

## Migration path

**Phase 1 — GenKit scaffolding (this week, no infra change)**
Add `genkit` and `@genkit-ai/vertexai` to `package.json`. Add `genkit/flows/echo-post-mortem.ts` as the first flow, running against the existing `twin_behavioral_ledger` table. Run `genkit start` locally to verify the trace viewer against five sample events from the mock data.

**Phase 2 — Flow migration (next two weeks)**
Port `planning-with-memory` and `rlhf-capture` to flows. Replace direct Vertex SDK calls in `src/lib/autodidactic/` with `ai.generate` calls. Add one `defineEval` over the `rlhf_samples` table.

**Phase 3 — Firebase narrow adoption (after Phase 2 is stable)**
Enable App Check on the console API. If real-time UI is wanted, add a Firestore collection `agent_status` fed by a GenKit flow post-step hook. Document the scope in `gcp/IAM_BOOTSTRAP.md` and add the App Check enforcement to `gcp/terraform/main.tf` as a `google_firebase_app_check_service_config` resource.

**Phase 4 — No-op**
Do not adopt Firebase Auth, Firebase Hosting, or Firestore-as-primary-store. If a future requirement surfaces that genuinely needs one of them, raise a new ADR.

---

## What this ADR does not decide

- Whether to expose GenKit's dev server in staging. Default: no; revisit if on-call needs live traces.
- Whether to migrate the five-agent multiagent handoff (`multiagent/HANDOFF.yaml`) into GenKit subagent definitions. Default: keep the handoff as the source of truth; GenKit flows are the implementation. A separate ADR if that inverts.
- Whether Gemini 3.5 Flash or 3.1 Pro is the default model per flow. That belongs in the registry manifest, not here.

---

## References

- GenKit repository: `github.com/firebase/genkit`
- GenKit Vertex AI plugin docs: `genkit.dev/docs/plugins/vertex-ai`
- Firebase App Check overview: `firebase.google.com/docs/app-check`
- Internal: `gcp/architecture/AUTODIDACTIC_TWIN_SPEC.md`, `gcp/MIGRATION_GUIDE.md`, `gcp/terraform/main.tf`
