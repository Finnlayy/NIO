# Atlas Core + Detachable Limbs — Target Architecture

**Status:** Canonical architecture spec (Phase 0)  
**Related:** [`AUTODIDACTIC_TWIN_SPEC.md`](./AUTODIDACTIC_TWIN_SPEC.md), [`limb-boundary.ts`](../../src/lib/autodidactic/limb-boundary.ts)  
**Last updated:** 2026-07-14

---

## Problem Statement

The console and backend currently present **11 always-on agents** (10 GCP-themed mocks + Cody) as if they were a fixed fleet. That layout came from a placeholder count, not from the intended design:

- **One Atlas core** — persistent orchestrator brain
- **Detachable limbs** — spawned for a task, retired when done
- **Per-limb memory** — post-mortem learnings saved individually
- **Agent Library** — archive of retired limbs (templates + history)
- **Cross-review** — quality gate for **Atlas/core changes only** (unless a limb is explicitly flagged)

Existing autodidactic specs already describe much of this loop; the gap is **conceptual alignment** and a **migration map** from today's static mocks.

---

## Current State vs Target

| Layer | Today | Target |
|-------|-------|--------|
| Console canvas | 11 fixed nodes in `OrchestratorConsole.tsx` + `mock-orchestrator.ts` | Atlas (center) + **active limbs only** + optional Cody interface node |
| Backend registry | Hardcoded `consoleAgents` in `agent_registry.ts` | **Core registry** (immutable) + **limb instance pool** (dynamic) + **library** (archived) |
| GCP manifest | Static `agent-registry.json` | **Limb template catalog** / library seed, not live runtime fleet |
| Learning loop | `reflection-engine.ts` + `twin_behavioral_ledger` exist but are **not wired** to live task completion | Mandatory post-mortem on **every limb retirement** |
| Self-modification | `limb-boundary.ts` + `BoundaryPanel.tsx` (demo) | Core mutations blocked or **cross-reviewed**; limb mutations validated via boundary rules |
| Cross-review | Cursor skill only | Invoked when **core/policy** changes are proposed; optional flag for high-risk limbs |

---

## Target Mental Model

```
                    ┌─────────────────────────────────────┐
                    │         Persistent Core             │
                    │  Atlas · Aegis · Echo               │
                    └──────────────┬──────────────────────┘
                                   │ deploy
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        Limb Instance A      Limb Instance B     Cody (interface)
              │                    │
              └────────┬───────────┘
                       ▼
              Echo: post-mortem + ledger
                       │
                       ▼
              Agent Library (templates + archive)
                       ▲
                       │ plan / redeploy
                       │
                    Atlas ──► cross-review (core mutations only)
```

**Key principle:** Limbs are **instances**, not permanent residents. The 10 named GCP personas (Maple, Vector, Pyra, etc.) become **library templates / archetypes** — useful starting points Atlas can instantiate, not agents that always appear on the canvas.

---

## Agent Taxonomy

### Tier 1 — Core (immutable, always present)

Aligned with `CORE_AGENT_IDS` in `limb-boundary.ts`:

| Mock ID | Canonical ID | Display name | Role | Mutable? | Cross-review |
|---------|--------------|--------------|------|----------|--------------|
| `orchestrator` | `atlas-orchestrator` | Atlas | PLAN, dispatch, fan-in | Strategy/routing only via governed proposals | **Required** on manifest/policy changes |
| `sandbox` | `aegis-security` | Aegis | Sandbox, secrets, IAM | Never | N/A (immutable) |
| `memory` | `echo-memory` | Echo | Ledger, retrieval, post-mortem orchestration | Tooling within allow-list | **Required** on curator logic changes |

### Tier 2 — Interface limb (semi-persistent)

| Mock ID | Canonical ID | Display name | Notes |
|---------|--------------|--------------|-------|
| `cody` | `cody` | Cody | Human-facing Telegram bridge. Routes into Atlas. Stays visible in UI as the **human limb**; not archived after each message. Session learnings aggregate into daily memory instead. |

### Tier 3 — Task limbs (ephemeral)

Spawned from templates or ad-hoc specs. **Do not occupy the canvas unless currently deployed.**

See [Mock Persona → Library Template Mapping](#mock-persona--library-template-mapping) below.

---

## Mock Persona → Library Template Mapping

This table is the authoritative mapping from today's console mocks to the target Agent Library template catalog. Mock IDs remain in the UI prototype until Phase 3; `template_id` is the future library key.

| Mock ID | Display name | Tier | `template_id` | Typical task |
|---------|--------------|------|---------------|--------------|
| `orchestrator` | Atlas | Core | — (not a template) | Orchestration, dispatch, fan-in |
| `sandbox` | Aegis | Core | — (not a template) | Sandbox, secrets, IAM enforcement |
| `memory` | Echo | Core | — (not a template) | Ledger, retrieval, post-mortem |
| `cody` | Cody | Interface | — (semi-persistent) | Human Telegram interface |
| `cartographer` | Maple | Limb template | `repo-cartographer` | Map repo / dependencies |
| `c-reviewer` | Vector | Limb template | `c-performance-reviewer` | C code performance review |
| `python-tester` | Pyra | Limb template | `python-test-engineer` | Python test execution |
| `quant-auditor` | Delta | Limb template | `quant-auditor` | Domain / risk validation |
| `ui-designer` | Nova | Limb template | `ui-systems-designer` | UI design and validation |
| `ci-runner` | Forge | Limb template | `ci-evidence-runner` | CI evidence collection |
| `review-synth` | Scribe | Limb template | `pr-review-synthesizer` | PR review synthesis |

Future template JSON location (Phase 1): `library/templates/<template_id>.json`, seeded from `gcp/vertex-ai/agent-registry.json` and `mock-orchestrator.ts`.

---

## Limb Lifecycle

```
  [*] ──► Draft ──► Deployed ──► Active ──► Completing ──► PostMortem ──► Archived ──► [*]
                              ▲                                              │
                              └──────────── redeploy from library ───────────┘
```

| State | Description |
|-------|-------------|
| **Draft** | Template selected or ad-hoc spec created by Atlas during PLAN |
| **Deployed** | Instance allocated; manifest snapshot taken |
| **Active** | Limb executing task (Cursor Task, Jules, NIO worker, etc.) |
| **Completing** | Task done or timed out; evidence collected |
| **PostMortem** | Echo runs mandatory `executePostMortem` |
| **Archived** | Instance retired; artifact bundle written to Agent Library |
| **Failed** | Escalated; partial learnings still archived |

### Per-limb artifact bundle on retirement

Stored in Agent Library archive entries:

- `limb_instance_id`, `template_id`, `task_id`, `swarm_run_id` (if any)
- Evidence: logs, artifacts, output contract validation result
- Post-mortem: `what_worked`, `what_failed`, `root_cause`, `learning_delta` (from `PostMortemOutput` in `reflection-engine.ts`)
- Manifest snapshot at deploy vs at retire (tool/model/context deltas)
- Routing stats update for template (`routing_weight`, success rate)
- Optional: human feedback (RLHF sample link)

**No cross-review** on this path unless `requires_cross_review: true` on the template or task.

---

## Agent Library

The Agent Library is **not** the live runtime registry. It is the **long-term archive + template catalog** Atlas queries during PLAN.

### Collections

1. **Templates** — reusable limb definitions
   - Fields: `template_id`, `role`, `tools`, `model_tier`, `output_contract`, `routing_weight`, `limb_runtime` (`cursor_task`, `jules_github`, etc.)

2. **Archive entries** — retired limb instances
   - Fields: full per-limb artifact bundle + link to `twin_behavioral_ledger` row(s)
   - Searchable by task type, tags, embedding (Phase 2 pgvector)

### Console UX (Phase 3 — documented only)

- **Core** panel: Atlas, Aegis, Echo (locked)
- **Active limbs** panel: 0–N dynamic instances
- **Agent Library** panel: templates + archived runs, filter/search
- Neural canvas: Atlas center; edges only to **currently active** limbs; Cody as bottom interface node

### Storage alignment

Reuse existing schema concepts:

- `orchestrator_memory_events` — per-event evidence
- `twin_behavioral_ledger` — post-mortem learnings (`agentsUsed` JSON)
- `agent_manifest_versions` — core mutation audit trail
- **Future (Phase 1+):** `limb_instances`, `agent_library_entries` tables

Human-readable mirror: `memory/YYYY-MM-DD.md` distill + optional `memory/limbs/<instance-id>.md` on retirement.

---

## Cross-Review Scope

Cross-review (`cross-review` skill → `zen-review`) is **not** on the default limb retirement path.

### Triggers cross-review (mandatory)

- Any mutation targeting `core` or `CORE_AGENT_IDS` in `validateManifestMutation`
- Policy invariant changes: `deployThreshold`, `humanGateRequired`, `maxAutonomousRevisions`, `auditLoggingRequired`
- Atlas-proposed updates to `SOUL.md`, orchestrator prompts, or `twin/prompts/planning-injection.md`
- New core-adjacent skill registration that affects orchestration

### Does NOT trigger cross-review (default)

- Routine limb task completion → post-mortem → archive
- Limb tool/context/model changes within allow-list (boundary validator only)
- Cody Telegram turns routed through NIO

### Optional flag (explicit opt-in)

```json
{
  "template_id": "invent-skills-author",
  "requires_cross_review": true,
  "review_reason": "New skill registration affects workspace-wide behavior"
}
```

Flow: limb completes → if flagged → cross-review runs → findings attached to library entry → then archive.

---

## End-to-End Task Flow

```
User ──► Cody ──► Atlas (POST /api/task)
                    │
                    ├── query Agent Library (similar tasks + templates)
                    ├── deploy limb instance(s)
                    │
Limb executes ──► Echo (evidence + post-mortem) ──► Agent Library (archive)
                    │
                    └── result ──► Cody ──► User

Separate path: Atlas core mutation proposal ──► cross-review ──► APPROVE / REQUEST CHANGES
```

Macro loop preserved from `AUTODIDACTIC_TWIN_SPEC.md`: **EXECUTE → EVALUATE → REFLECT → UPDATE**, with cross-review as an **integrity gate on the brain**, not on every finger.

---

## Migration Map

### Phase 0 — Architecture docs (this document)

- [x] `ATLAS_LIMB_MODEL.md` — canonical spec
- [x] `AUTODIDACTIC_TWIN_SPEC.md` §13 — Agent Library + limb lifecycle + cross-review
- [x] Header annotations on `mock-orchestrator.ts` and `agent_registry.ts`

### Phase 1 — Registry split (future)

- Split `agent_registry.ts` into `core_registry` + `limb_instance_store`
- Map mock personas → `library/templates/*.json`
- API: `GET /api/limbs/active`, `GET /api/library/templates`, `GET /api/library/archive`

### Phase 2 — Wire retirement loop (future)

- On NIO task completion: invoke `executePostMortem` → write ledger → archive limb instance
- Connect telemetry `agentId` to instance lifecycle

### Phase 3 — Console realignment (future)

- Replace `mockAgents` consumption in `OrchestratorConsole.tsx` with live active-limb feed
- Add **Agent Library** view tab
- Keep Cody stats board as interface-limb telemetry

### Phase 4 — Cross-review gate (future)

- Hook `BoundaryPanel` / manifest proposal path to cross-review skill for core mutations
- Store review verdict in `agent_manifest_versions`

---

## What Stays From Recent Work

- Cody = interface limb (Tier 2)
- NIO `/api/task` = Atlas dispatch entry point
- Telemetry `source` + `agentId` = limb instance tracking hooks
- Live LLM routing = per-limb `model_tier` foundation (`model_router.ts`)

No rollback needed — only **relabel and rewire** the 10 mocks from "always-on fleet" to "library seed templates."

---

## Open Design Decisions (defer to implementation)

- **Max concurrent active limbs** — budget-driven, not fixed at 10
- **Template promotion** — when does a one-off ad-hoc limb become a library template?
- **Redeploy semantics** — new instance ID vs resume archived instance
- **Cody archival** — never archive per message; aggregate session learnings into daily memory instead

---

*Document Version: 1.0*  
*Classification: Internal Use Only*
