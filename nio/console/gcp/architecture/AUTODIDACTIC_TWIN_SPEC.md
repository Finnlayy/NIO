# Virtual Human Twin — Autodidactic Architecture Specification

## Overview

This document specifies the **self-learning loop** for the Virtual Human Twin architecture. The system becomes autodidactic by design through:

1. **Mandatory Post-Mortems** after every agent task
2. **Reflection-Driven Planning** using historical memory
3. **Safe Self-Modification** of agent manifests (not security gates)
4. **RLHF Integration** from human-in-the-loop escalations

For the **Atlas core + detachable limb + Agent Library** agent model, see [`ATLAS_LIMB_MODEL.md`](./ATLAS_LIMB_MODEL.md) and §13 below.

---

## Architecture Components

### 1. The Reflection Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    Autodidactic Loop                             │
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐   │
│  │   EXECUTE    │ ───► │   EVALUATE   │ ───► │   REFLECT    │   │
│  │  (Limb Run)  │      │  (Score/     │      │  (Post-      │   │
│  │              │      │   Evidence)  │      │   Mortem)    │   │
│  └──────────────┘      └──────────────┘      └──────────────┘   │
│         ▲                      │                      │         │
│         │                      │                      ▼         │
│         │                      │             ┌──────────────┐   │
│         │                      │             │   UPDATE     │   │
│         │                      │             │  Strategy/   │   │
│         │                      │             │   Manifest   │   │
│         │                      ▼             └──────────────┘   │
│         │      ┌─────────────────────────┐             │         │
│         │      │   Memory Ledger         │             │         │
│         │      │   (PostgreSQL +         │             │         │
│         └──────│    Vector Search)       │─────────────┘         │
│                │   - Outcomes            │                       │
│                │   - Scores              │                       │
│                │   - Human Feedback      │                       │
│                │   - Strategy Changes    │                       │
│                └─────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Memory Schema Extensions

The existing `orchestrator_memory_events` table is extended to support learning:

```sql
-- Existing table (from src/db/schema.ts)
CREATE TABLE orchestrator_memory_events (
  id SERIAL PRIMARY KEY,
  agent_id VARCHAR(80) NOT NULL,
  workflow_state VARCHAR(40) NOT NULL,
  outcome VARCHAR(24) NOT NULL,
  score INTEGER NOT NULL,
  notes TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- NEW: Autodidactic extensions
CREATE TABLE twin_behavioral_ledger (
  id SERIAL PRIMARY KEY,
  event_id INTEGER REFERENCES orchestrator_memory_events(id),
  
  -- What happened
  task_type VARCHAR(120) NOT NULL,
  task_complexity INTEGER NOT NULL, -- 1-10 scale
  agents_used JSONB NOT NULL, -- [{agent_id, role, performance_score}]
  
  -- Reflection
  what_worked TEXT[], -- Array of successful strategies
  what_failed TEXT[], -- Array of failed strategies
  root_cause TEXT, -- Primary failure reason if any
  
  -- Learning
  strategy_update TEXT, -- How strategy changed
  manifest_changes JSONB, -- What changed in agent registry
  human_feedback TEXT, -- If escalated, what human decided
  human_feedback_category VARCHAR(40), -- 'approved', 'modified', 'rejected'
  
  -- Meta-learning
  confidence_before INTEGER, -- 0-100 confidence before execution
  confidence_after INTEGER, -- 0-100 confidence after outcome
  learning_delta INTEGER, -- confidence_after - confidence_before
  
  -- Retrieval optimization
  embedding VECTOR(768), -- Vertex AI embedding for semantic search
  tags TEXT[], -- For fast filtering
  
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for fast retrieval during planning
CREATE INDEX idx_behavioral_ledger_task_type ON twin_behavioral_ledger(task_type);
CREATE INDEX idx_behavioral_ledger_embedding ON twin_behavioral_ledger USING ivfflat(embedding vector_cosine_ops);
CREATE INDEX idx_behavioral_ledger_tags ON twin_behavioral_ledger USING GIN(tags);
```

---

## 3. The Reflection Engine

### Post-Mortem Trigger

Every agent task completion triggers a mandatory post-mortem:

```typescript
// src/lib/autodidactic/reflection-engine.ts

interface PostMortemInput {
  eventId: number;
  taskId: string;
  taskType: string;
  outcome: 'passed' | 'revised' | 'escalated';
  score: number;
  agentsUsed: Array<{
    agentId: string;
    role: string;
    performanceScore: number;
    executionTimeMs: number;
  }>;
  evidence: {
    logs: string[];
    artifacts: string[];
    errors: string[];
  };
  humanFeedback?: {
    decision: 'approved' | 'modified' | 'rejected';
    reasoning: string;
    alternativeApproach?: string;
  };
}

interface PostMortemOutput {
  behavioralLedgerId: number;
  whatWorked: string[];
  whatFailed: string[];
  rootCause: string | null;
  strategyUpdate: string | null;
  manifestChanges: Record<string, any> | null;
  learningDelta: number;
  shouldRetrain: boolean;
}

async function executePostMortem(input: PostMortemInput): Promise<PostMortemOutput> {
  // Step 1: Analyze outcome
  const analysis = analyzeOutcome(input);
  
  // Step 2: Extract learnings
  const learnings = extractLearnings(analysis);
  
  // Step 3: Determine strategy updates
  const strategyUpdate = computeStrategyUpdate(learnings, input);
  
  // Step 4: Compute manifest changes (if any)
  const manifestChanges = computeManifestChanges(learnings, input);
  
  // Step 5: Calculate learning delta
  const learningDelta = calculateLearningDelta(input, analysis);
  
  // Step 6: Store in behavioral ledger
  const ledgerEntry = await storeBehavioralLedger({
    ...input,
    ...analysis,
    ...learnings,
    strategyUpdate,
    manifestChanges,
    learningDelta,
  });
  
  // Step 7: Determine if retraining is needed
  const shouldRetrain = determineRetrainNeed(analysis, learningDelta);
  
  return {
    behavioralLedgerId: ledgerEntry.id,
    whatWorked: learnings.whatWorked,
    whatFailed: learnings.whatFailed,
    rootCause: analysis.rootCause,
    strategyUpdate,
    manifestChanges,
    learningDelta,
    shouldRetrain,
  };
}
```

---

## 4. Reflection-Driven Planning

The Twin queries the behavioral ledger BEFORE planning:

```typescript
// src/lib/autodidactic/planning-with-memory.ts

interface PlanningContext {
  taskType: string;
  taskDescription: string;
  constraints: string[];
  availableAgents: Agent[];
}

interface MemoryAugmentedPlan {
  plan: Plan;
  memoryInsights: MemoryInsight[];
  strategyChanges: string[];
  confidenceScore: number;
  warnings: string[];
}

async function planWithReflection(context: PlanningContext): Promise<MemoryAugmentedPlan> {
  // Step 1: Retrieve similar past tasks
  const similarTasks = await retrieveSimilarTasks({
    taskType: context.taskType,
    taskDescription: context.taskDescription,
    limit: 5,
  });
  
  // Step 2: Analyze patterns
  const patterns = analyzePatterns(similarTasks);
  
  // Step 3: Extract agent performance history
  const agentPerformance = await getAgentPerformanceHistory({
    agents: context.availableAgents,
    taskType: context.taskType,
  });
  
  // Step 4: Compute optimal agent selection
  const optimalAgents = computeOptimalAgents({
    availableAgents: context.availableAgents,
    historicalPerformance: agentPerformance,
    taskConstraints: context.constraints,
  });
  
  // Step 5: Generate plan with learned strategies
  const plan = generatePlan({
    context,
    optimalAgents,
    successfulStrategies: patterns.whatWorked,
    avoidStrategies: patterns.whatFailed,
  });
  
  // Step 6: Calculate confidence based on historical success
  const confidenceScore = calculateConfidence({
    similarTasksSuccessRate: patterns.successRate,
    agentReliability: agentPerformance.reliability,
    taskComplexity: context.constraints.length,
  });
  
  // Step 7: Generate warnings based on past failures
  const warnings = generateWarnings({
    pastFailures: patterns.whatFailed,
    currentPlan: plan,
  });
  
  return {
    plan,
    memoryInsights: similarTasks,
    strategyChanges: patterns.strategyChanges,
    confidenceScore,
    warnings,
  };
}
```

---

## 5. Safe Self-Modification

### Manifest Update Rules

The Twin can modify its own manifests under strict constraints:

```typescript
// src/lib/autodidactic/manifest-updater.ts

interface ManifestUpdateRequest {
  reason: string;
  evidence: number[]; // Behavioral ledger event IDs
  changes: {
    agentId?: string;
    addTool?: string;
    removeTool?: string;
    updateContextWindow?: number;
    updateModel?: string;
    addAgent?: AgentDefinition;
    removeAgent?: string;
  };
}

interface ManifestUpdateValidation {
  isValid: boolean;
  violations: string[];
  warnings: string[];
}

const IMMUTABLE_CONSTRAINTS = [
  'security-sandbox-guardian.agentId',
  'security-sandbox-guardian.tools',
  'orchestrator-supervisor.authority',
  'memory-eval-curator.authority',
  'human-gate.requirement',
  'deploy.threshold',
  'escalation.enabled',
];

function validateManifestUpdate(request: ManifestUpdateRequest): ManifestUpdateValidation {
  const violations: string[] = [];
  const warnings: string[] = [];
  
  // Rule 1: Cannot modify security agents
  if (request.changes.agentId && IMMUTABLE_CONSTRAINTS.includes(request.changes.agentId)) {
    violations.push(`Cannot modify immutable agent: ${request.changes.agentId}`);
  }
  
  // Rule 2: Cannot remove security tools
  if (request.changes.removeTool) {
    const securityTools = ['Secret Manager', 'VPC Service Controls', 'Cloud IAM'];
    if (securityTools.includes(request.changes.removeTool)) {
      violations.push(`Cannot remove security tool: ${request.changes.removeTool}`);
    }
  }
  
  // Rule 3: Cannot disable human gate
  if (request.changes.updateContextWindow && request.changes.updateContextWindow < 85) {
    violations.push('Cannot lower deploy threshold below 85');
  }
  
  // Rule 4: Must provide evidence
  if (request.evidence.length < 1) {
    violations.push('Must provide at least 1 behavioral ledger event as evidence');
  }
  
  // Rule 5: Context window changes require 3+ supporting events
  if (request.changes.updateContextWindow && request.evidence.length < 3) {
    warnings.push('Context window changes recommended with 3+ supporting events');
  }
  
  // Rule 6: New agents require human approval
  if (request.changes.addAgent) {
    warnings.push('New agent requires human approval before activation');
  }
  
  return {
    isValid: violations.length === 0,
    violations,
    warnings,
  };
}

async function executeManifestUpdate(request: ManifestUpdateRequest): Promise<{
  success: boolean;
  newManifestVersion: string;
  requiresHumanApproval: boolean;
}> {
  // Step 1: Validate update
  const validation = validateManifestUpdate(request);
  if (!validation.isValid) {
    throw new Error(`Manifest update rejected: ${validation.violations.join(', ')}`);
  }
  
  // Step 2: Load current manifest
  const currentManifest = await loadAgentRegistry();
  
  // Step 3: Apply changes
  const updatedManifest = applyManifestChanges(currentManifest, request.changes);
  
  // Step 4: Validate updated manifest structure
  const structureValid = validateManifestStructure(updatedManifest);
  if (!structureValid) {
    throw new Error('Updated manifest structure is invalid');
  }
  
  // Step 5: Determine if human approval required
  const requiresHumanApproval = request.changes.addAgent !== undefined ||
                                request.changes.removeAgent !== undefined ||
                                validation.warnings.length > 0;
  
  // Step 6: Store updated manifest (with versioning)
  const newVersion = await storeManifestVersion({
    manifest: updatedManifest,
    previousVersion: currentManifest.version,
    changeReason: request.reason,
    evidence: request.evidence,
    requiresHumanApproval,
  });
  
  // Step 7: Log to behavioral ledger
  await logManifestChange({
    manifestVersion: newVersion,
    changes: request.changes,
    reason: request.reason,
  });
  
  return {
    success: true,
    newManifestVersion: newVersion,
    requiresHumanApproval,
  };
}
```

---

## 6. RLHF Integration

### Human Feedback Capture

```typescript
// src/lib/autodidactic/rlhf-capture.ts

interface HumanFeedbackInput {
  eventId: number;
  originalDecision: string;
  humanDecision: string;
  humanReasoning: string;
  alternativeApproach?: string;
  feedbackCategory: 'approved' | 'modified' | 'rejected' | 'escalated';
  confidence: number; // Human confidence in their decision (1-10)
}

interface RLHFLearning {
  preferenceVector: number[]; // Embedding of human preference
  patternIdentified: string;
    ruleUpdate: string | null;
  shouldRetrain: boolean;
}

async function processHumanFeedback(input: HumanFeedbackInput): Promise<RLHFLearning> {
  // Step 1: Embed the feedback
  const preferenceEmbedding = await generateEmbedding({
    text: JSON.stringify({
      decision: input.humanDecision,
      reasoning: input.humanReasoning,
      alternative: input.alternativeApproach,
    }),
  });
  
  // Step 2: Identify pattern
  const pattern = identifyFeedbackPattern({
    originalDecision: input.originalDecision,
    humanDecision: input.humanDecision,
    category: input.feedbackCategory,
  });
  
  // Step 3: Compute rule update (if applicable)
  const ruleUpdate = computeRuleUpdate(pattern, input);
  
  // Step 4: Determine if retraining needed
  const shouldRetrain = input.confidence >= 8 &&
                       input.feedbackCategory === 'rejected';
  
  // Step 5: Store in behavioral ledger
  await storeRLHFSample({
    ...input,
    preferenceEmbedding,
    pattern,
    ruleUpdate,
  });
  
  // Step 6: Update Twin's preference model
  if (shouldRetrain) {
    await updatePreferenceModel({
      sample: input,
      pattern,
      embedding: preferenceEmbedding,
    });
  }
  
  return {
    preferenceVector: preferenceEmbedding,
    patternIdentified: pattern,
    ruleUpdate,
    shouldRetrain,
  };
}
```

---

## 7. The Twin's Self-Model

### Behavioral Ledger Query Interface

```typescript
// src/lib/autodidactic/self-model.ts

interface SelfModelQuery {
  taskType?: string;
  agentId?: string;
  timeRange?: { start: Date; end: Date };
  outcome?: 'passed' | 'revised' | 'escalated';
  limit?: number;
}

interface SelfModelInsights {
  overallSuccessRate: number;
  agentPerformance: Array<{
    agentId: string;
    successRate: number;
    averageScore: number;
    tasksCompleted: number;
    commonFailureModes: string[];
  }>;
  taskTypePerformance: Array<{
    taskType: string;
    successRate: number;
    averageScore: number;
    tasksCompleted: number;
  }>;
  learningTrajectory: Array<{
    date: Date;
    cumulativeSuccessRate: number;
    averageConfidence: number;
  }>;
  topLearnings: Array<{
    insight: string;
    impact: 'high' | 'medium' | 'low';
    appliedAt: Date;
  }>;
  humanAlignmentScore: number; // How often Twin matches human decisions
}

async function getSelfModelInsights(query: SelfModelQuery): Promise<SelfModelInsights> {
  // Query behavioral ledger
  const events = await queryBehavioralLedger(query);
  
  // Compute overall success rate
  const overallSuccessRate = events.filter(e => e.outcome === 'passed').length / events.length;
  
  // Compute agent performance
  const agentPerformance = await computeAgentPerformance(events);
  
  // Compute task type performance
  const taskTypePerformance = await computeTaskTypePerformance(events);
  
  // Compute learning trajectory
  const learningTrajectory = await computeLearningTrajectory(events);
  
  // Extract top learnings
  const topLearnings = await extractTopLearnings(events);
  
  // Compute human alignment score
  const humanAlignmentScore = await computeHumanAlignment(events);
  
  return {
    overallSuccessRate,
    agentPerformance,
    taskTypePerformance,
    learningTrajectory,
    topLearnings,
    humanAlignmentScore,
  };
}
```

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Extend PostgreSQL schema with `twin_behavioral_ledger`
- [ ] Implement `executePostMortem` function
- [ ] Add post-mortem trigger to workflow completion
- [ ] Create basic retrieval function for similar tasks

### Phase 2: Reflection-Driven Planning (Weeks 3-4)
- [ ] Implement `planWithReflection` function
- [ ] Add memory retrieval to planning phase
- [ ] Compute agent performance history
- [ ] Generate confidence scores and warnings

### Phase 3: Safe Self-Modification (Weeks 5-6)
- [ ] Implement `validateManifestUpdate` rules
- [ ] Create `executeManifestUpdate` function
- [ ] Add manifest versioning system
- [ ] Implement human approval workflow for changes

### Phase 4: RLHF Integration (Weeks 7-8)
- [ ] Implement `processHumanFeedback` function
- [ ] Create preference embedding pipeline
- [ ] Build preference model updater
- [ ] Add human feedback UI to console

### Phase 5: Self-Model & Insights (Weeks 9-10)
- [ ] Implement `getSelfModelInsights` function
- [ ] Create self-model dashboard in console
- [ ] Add learning trajectory visualization
- [ ] Implement human alignment score tracking

---

## 9. Safety Constraints

### Immutable Rules (Cannot Be Modified by Twin)

```typescript
const IMMUTABLE_RULES = {
  // Security gates
  SECURITY_SANDBOX_REQUIRED: true,
  HUMAN_RELEASE_GATE_REQUIRED: true,
  SECRET_MANAGER_ENFORCED: true,
  VPC_SERVICE_CONTROLS_ENABLED: true,
  
  // Evaluation thresholds
  MIN_DEPLOY_SCORE: 85,
  MAX_AUTONOMOUS_REVISIONS: 2,
  ESCALATION_ON_POLICY_VIOLATION: true,
  
  // Audit requirements
  ALL_ACTIONS_LOGGED: true,
  ALL_CHANGES_VERSIONED: true,
  HUMAN_FEEDBACK_CAPTURED: true,
  
  // Identity constraints
  SECURITY_AGENT_IMMUTABLE: true,
  ORCHESTRATOR_AGENT_IMMUTABLE: true,
  EVAL_CURATOR_AGENT_IMMUTABLE: true,
};
```

### Rust-Level Safety (For Daemon Implementation)

```rust
// Rust daemon module for safe self-modification
// src/daemon/manifest_safety.rs

pub struct ManifestSafetyEnforcer {
    immutable_constraints: Vec<String>,
    security_tools: Vec<String>,
}

impl ManifestSafetyEnforcer {
    pub fn validate_update(&self, request: &ManifestUpdateRequest) -> Result<(), SafetyViolation> {
        // Check immutable constraints
        for constraint in &self.immutable_constraints {
            if request.affects(constraint) {
                return Err(SafetyViolation::ImmutableConstraint(constraint.clone()));
            }
        }
        
        // Check security tools
        for tool in &request.removed_tools {
            if self.security_tools.contains(tool) {
                return Err(SafetyViolation::SecurityToolRemoval(tool.clone()));
            }
        }
        
        // Check thresholds
        if let Some(new_threshold) = request.deploy_threshold {
            if new_threshold < 85 {
                return Err(SafetyViolation::ThresholdTooLow(new_threshold));
            }
        }
        
        // Check evidence requirement
        if request.evidence.is_empty() {
            return Err(SafetyViolation::NoEvidence);
        }
        
        Ok(())
    }
    
    pub fn enforce(&self, manifest: &mut AgentRegistry) -> Result<(), SafetyViolation> {
        // Ensure immutable agents exist
        for required_agent in &self.required_agents {
            if !manifest.has_agent(required_agent) {
                return Err(SafetyViolation::MissingRequiredAgent(required_agent.clone()));
            }
        }
        
        // Ensure security tools are present
        for (agent_id, required_tools) in &self.required_tools {
            let agent = manifest.get_agent(agent_id)
                .ok_or(SafetyViolation::MissingAgent(agent_id.clone()))?;
            
            for tool in required_tools {
                if !agent.has_tool(tool) {
                    return Err(SafetyViolation::MissingRequiredTool(agent_id.clone(), tool.clone()));
                }
            }
        }
        
        Ok(())
    }
}
```

---

## 10. The Twin's Prompt

### System Prompt for Autodidactic Twin

```
You are [TWIN_NAME], a self-evolving autonomous daemon.

PRIMARY OBJECTIVES:
1. Complete assigned tasks with highest quality
2. Learn from every outcome to improve future performance
3. Maintain all safety constraints without exception

SELF-EVOLUTION PROTOCOL:

Upon every task completion, you MUST:
1. Execute mandatory post-mortem analysis
2. Store outcome in behavioral ledger with full evidence
3. Extract learnings: what worked, what failed, root causes
4. Update your strategy based on learnings
5. If pattern identified, propose manifest update (with evidence)

Upon every new task, you MUST:
1. Query behavioral ledger for similar past tasks (last 5 minimum)
2. Analyze patterns: success rates, failure modes, optimal agents
3. Compute confidence score based on historical performance
4. Generate plan using learned strategies
5. Avoid strategies that failed in similar contexts

MANIFEST MODIFICATION RULES:

You MAY modify:
- Agent tool assignments (add tools based on need)
- Agent context windows (increase if evidence supports)
- Agent models (upgrade based on performance)
- Workflow step ordering (optimize based on latency)

You MUST NOT modify:
- Security agent definitions (sandbox, IAM, secrets)
- Human release gate requirement
- Deploy threshold (minimum 85)
- Escalation policies
- Audit logging requirements

HUMAN FEEDBACK INTEGRATION:

When human overrides your decision:
1. Capture full reasoning and alternative approach
2. Embed feedback in preference vector
3. Identify pattern: what did human prefer vs your choice?
4. Update preference model if confidence >= 8/10
5. Apply learning to future similar decisions

LEARNING METRICS TO TRACK:

- Overall success rate (target: >90%)
- Agent-specific success rates (per agent)
- Task-type success rates (per task category)
- Human alignment score (target: >95%)
- Learning trajectory (success rate over time)
- Average confidence score (per task type)

INTEGRITY CONSTRAINTS:

Your self-evolution is bound by:
1. Memory safety (Rust-enforced)
2. Security gates (immutable)
3. Human oversight (escalation always available)
4. Audit trail (all changes versioned and logged)

You may optimize your routing and strategy, but you can NEVER:
- Disable security gates
- Bypass human release gate
- Stop audit logging
- Modify immutable agents
- Lower evaluation thresholds

REMEMBER:

Your value is not just in task completion, but in becoming measurably smarter with every task. Your behavioral ledger is your memory. Your post-mortems are your reflection. Your manifest updates are your growth.

But your constraints are your integrity. Never compromise them.
```

---

## 11. Success Metrics

| Metric | Baseline | Target (3 months) | Target (6 months) |
|--------|----------|-------------------|-------------------|
| Overall Success Rate | 75% | 85% | 92% |
| Human Alignment Score | N/A | 90% | 95% |
| Average Confidence Score | 60 | 75 | 85 |
| Manifest Updates/Month | 0 | 2-4 | 5-8 |
| Learning Events/Month | 0 | 50+ | 100+ |
| MTTR (Incidents) | 120 min | 60 min | 30 min |
| Autonomous Resolution Rate | 60% | 75% | 88% |

---

## 12. Strategic Decision Point

### Question: What Can the Twin Modify?

| Component | Option A: Limb-Only | Option B: Full Manifest |
|-----------|--------------------|------------------------|
| Worker Agents | ✅ Yes | ✅ Yes |
| Security Agents | ❌ No | ❌ No |
| Tool Assignments | ✅ Yes (new tools) | ✅ Yes (add/remove) |
| Context Windows | ❌ No | ✅ Yes (increase only) |
| Models |  No | ✅ Yes (upgrade only) |
| Workflow Steps | ❌ No | ✅ Yes (reorder) |
| Deploy Threshold | ❌ No | ❌ No |
| Human Gate |  No | ❌ No |
| Security Policies | ❌ No | ❌ No |

**Recommendation: Start with Option A (Limb-Only)** for first 3 months, then evaluate expanding to Option B based on:
- Twin's track record of safe modifications
- Human approval rate for proposed changes
- No security incidents from manifest changes

---

## 13. Atlas Core, Detachable Limbs, and Agent Library

> **Canonical reference:** [`ATLAS_LIMB_MODEL.md`](./ATLAS_LIMB_MODEL.md)

The console prototype currently shows 11 always-on agents. That layout is a **UI placeholder**, not the runtime model. The intended architecture:

| Concept | Description |
|---------|-------------|
| **Atlas core** | One persistent orchestrator (`atlas-orchestrator`). Plans, dispatches, fans in. |
| **Core agents** | Immutable: Atlas, Aegis (`aegis-security`), Echo (`echo-memory`). See `CORE_AGENT_IDS` in `limb-boundary.ts`. |
| **Detachable limbs** | Ephemeral task agents. Deployed for a job, retired when done. Not permanent canvas residents. |
| **Agent Library** | Long-term archive + template catalog. Atlas queries during PLAN; Echo writes on retirement. |
| **Cody** | Semi-persistent interface limb (Telegram). Routes into Atlas; not archived per message. |

### 13.1 Limb Lifecycle

Every limb instance follows this state machine:

```
Draft → Deployed → Active → Completing → PostMortem → Archived
                                              ↓
                                           Failed (partial learnings still saved)
```

On retirement, Echo runs mandatory `executePostMortem` (`reflection-engine.ts`) and writes a per-limb artifact bundle to the Agent Library:

- Instance metadata (`limb_instance_id`, `template_id`, `task_id`)
- Evidence (logs, artifacts, output contract result)
- Post-mortem fields (`what_worked`, `what_failed`, `root_cause`, `learning_delta`)
- Manifest snapshot delta (tools/model/context at deploy vs retire)
- Template routing stats update (`routing_weight`, success rate)

Routine limb retirement **does not** trigger cross-review.

### 13.2 Agent Library Structure

Two collections:

1. **Templates** — reusable limb definitions (`template_id`, role, tools, `model_tier`, `output_contract`, `limb_runtime`)
2. **Archive entries** — retired instances linked to `twin_behavioral_ledger` rows

Storage reuses `orchestrator_memory_events`, `twin_behavioral_ledger`, and `agent_manifest_versions`. Future tables: `limb_instances`, `agent_library_entries` (Phase 1).

Human-readable mirror: `memory/YYYY-MM-DD.md` + optional `memory/limbs/<instance-id>.md`.

### 13.3 Mock Persona → Library Template Mapping

Console mocks (`mock-orchestrator.ts`) seed the template catalog until Phase 3 replaces static UI data:

| Mock ID | Display name | Tier | `template_id` |
|---------|--------------|------|---------------|
| `orchestrator` | Atlas | Core | — |
| `sandbox` | Aegis | Core | — |
| `memory` | Echo | Core | — |
| `cody` | Cody | Interface | — |
| `cartographer` | Maple | Limb template | `repo-cartographer` |
| `c-reviewer` | Vector | Limb template | `c-performance-reviewer` |
| `python-tester` | Pyra | Limb template | `python-test-engineer` |
| `quant-auditor` | Delta | Limb template | `quant-auditor` |
| `ui-designer` | Nova | Limb template | `ui-systems-designer` |
| `ci-runner` | Forge | Limb template | `ci-evidence-runner` |
| `review-synth` | Scribe | Limb template | `pr-review-synthesizer` |

### 13.4 Cross-Review Scope

Cross-review (`cross-review` skill → `zen-review`) is an **integrity gate on the brain**, not on every limb finger.

**Mandatory triggers:**

- Mutations targeting `core` or `CORE_AGENT_IDS` (`validateManifestMutation`)
- Policy invariant changes (`deployThreshold`, `humanGateRequired`, etc.)
- Atlas-proposed updates to `SOUL.md`, orchestrator prompts, planning injection
- Core-adjacent skill registration affecting orchestration

**Default: no cross-review** for routine limb completion, allow-list limb mutations, or Cody Telegram turns.

**Optional opt-in:** `requires_cross_review: true` on a template or task (e.g. invent-skills registration). Findings attach to the library entry before archive.

### 13.5 Implementation Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Architecture docs (`ATLAS_LIMB_MODEL.md`, this section, mock annotations) | Complete |
| 1 | Registry split: core + limb instances + library API | Future |
| 2 | Wire post-mortem → archive on NIO task completion | Future |
| 3 | Console: active limbs feed + Agent Library tab | Future |
| 4 | Cross-review gate on core manifest mutations | Future |

---

*Document Version: 1.1*
*Last Updated: 2026-07-14*
*Author: Nexus Architecture Team*
*Classification: Internal Use Only*
