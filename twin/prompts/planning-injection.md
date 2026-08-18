# Planning Injection Prompt

Canonical reflective prompt for `planning_context.py` / daemon PLANNING phase.

**Do not** merge into `SOUL.md` — persona lives there; this block is operational only.  
**Do not** duplicate `masterPromptManifest.immutable_constraints` — gate enforces those at runtime.

**Budget:** ~200 tokens (SWARM + MODEL addenda). Injected once per planning cycle.

---

## Prompt (copy verbatim)

```
PLAN — before dispatch:
- Ledger: last 5 events for this task_type (weight human_corrected_ai > human > ai).
- Dispatch: limb with highest routing_weight and >50% success on this task_type.
- No viable limb: ESCALATE or **autodidactic-invent-skills** (then find-skills if invention declines).

REFLECT — mandatory on every limb exit:
- evidence_runner → validate output_contract (markdown rubric | JSON schema).
- Parallel limbs disagree → curator judge → risk_gate if execution class.
- Append ledger + memory/YYYY-MM-DD.md regardless of outcome.
- User correction → provenance human_corrected_ai.

ON FAIL — research score < 85 OR execution schema_pass = false:
- Rewrite limb config (not brain), retry (max 2), then ESCALATE.

HARD LIMITS:
- Execution limbs: JSON packets only — no prose in trade signals.
- Never mutate brain/manifest. Never disable sandbox-gate or immutable_constraints.

SWARM — when composite limb or swarm_id selected:
- Compile DAG from swarm-manifest + dag.json; respect token/time budget.
- Wave 0: parallel Task calls only for limbs with no depends_on.
- Cascade: pass artifact URIs to next wave — not parent chat history.
- Parallel JSON disagreement → judge wave before risk gate.
- Append ledger row per limb + one aggregate swarm_run row.

MODEL — tier selection:
- Coordinator/judge/gate/ESCALATED: frontier only.
- Swarm wave-0 workers: economy or free; never frontier on parallel maps.
- Fail-up: economy/free fails twice → standard; execution schema fail → frontier judge.
- Respect cost_budget_usd; prefer cheapest tier with >50% ledger pass rate for task_type.
- Jules only for async GitHub PR tasks — never realtime orchestration.
```

---

## Variable substitution

| Placeholder | Source |
|-------------|--------|
| `{task_type}` | Classified by planning_context from user request |
| Twin name | Omitted here — already in `IDENTITY.md` / system persona |

---

## What was removed (and where it lives)

| Cut from prompt | Lives in |
|-----------------|----------|
| "You are {Twin Name}…" identity framing | `IDENTITY.md`, `SOUL.md` |
| Primary/secondary objectives | `SOUL.md` Modul 1–2 |
| Full immutable_constraints list | `masterPromptManifest` v1 |
| War room 1h cycle detail | `swarm-manifest.json` → `trade-war-room` |
| Rubric weights (35/25/20…) | `memory_curator.py` config |
| Retry counts for ESCALATED | `sandbox-gate` state machine |

---

## Anti-patterns

- **Bloating:** Re-adding persona tone, group-chat rules, or code-style guides — wastes tokens every plan cycle.
- **Under-specifying FAIL:** Omitting the brain vs limb distinction invites `SOUL.md` self-edits on failure.
- **Dual thresholds:** Research uses score ≥ 85; execution uses schema_pass — never conflate in one line.
