# Nexus Console — Google AI Platform Migration Guide

## The three-platform pipeline

These are not alternatives. They are sequential stages for the same system.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│   AI Studio     │ ──► │  Antigravity 2.0 │ ──► │ Gemini Enterprise Agent │
│   (Prototype)   │     │  (Develop)       │     │ Platform (Production)   │
│                 │     │                  │     │                         │
│ • Prompt test   │     │ • Multi-agent    │     │ • VPC-scoped access     │
│ • Agent sketch  │     │   orchestration  │     │ • Cloud Audit Logs      │
│ • Export button │     │ • CLI for CI/CD  │     │ • IAM + Secret Manager  │
│ • Playground    │     │ • SDK hosting    │     │ • Data residency        │
└─────────────────┘     └──────────────────┘     └─────────────────────────┘
```

**Recommendation for Nexus**: Use all three. AI Studio for agent prompt iteration, Antigravity for development and CI/CD, Gemini Enterprise for the production deployment we already provisioned in Terraform.

---

## ⚠️ Forced migration deadline: June 18, 2026

Gemini CLI access ends for AI Pro, AI Ultra, and free-tier users on **June 18, 2026**. The replacement is Antigravity CLI (written in Go, faster startup, lower memory).

If you have `gemini` commands in scripts, CI pipelines, or muscle memory:

```bash
# Run this before June 18 to preserve Agent Skills, Hooks, and Subagents
antigravity migrate --from-gemini-cli
```

Enterprise customers on Gemini Code Assist Standard/Enterprise retain access beyond that date, but the direction is clear.

---

## Platform 1: Google AI Studio (Prototype stage)

### What it's for

Rapid prompt iteration, agent behavior sketching, and Managed Agents API testing. The new "Export to Antigravity" button carries full conversation context into local development.

### Migration steps for Nexus

1. **Create agent playgrounds** for each of the 10 Nexus agents:
   - Open AI Studio → New Project → "Nexus Agent Registry"
   - For each agent (Atlas, Aegis, Echo, Nova, Delta, etc.), create a prompt template
   - Test with sample tasks from `src/data/mock-orchestrator.ts`

2. **Export to Antigravity**:
   - When a prompt template is stable, click "Export to Antigravity"
   - This creates a `.gemini/` directory with agent skills, hooks, and subagent definitions
   - The export preserves conversation context so Antigravity picks up where you left off

3. **Managed Agents API** (optional):
   - If you want to test the Antigravity agent harness directly:
   ```bash
   curl -X POST https://generativelanguage.googleapis.com/v1beta/interactions \
     -H "Authorization: Bearer $GEMINI_API_KEY" \
     -d '{
       "model": "gemini-3.5-flash",
       "instructions": "You are Atlas, the GCP bootstrap agent...",
       "tools": ["code_execution", "file_search"]
     }'
   ```

### What to prototype in AI Studio

| Agent | Prompt focus | Test input |
|-------|-------------|------------|
| Atlas | Terraform plan generation | "Create a Cloud Run service with Secret Manager integration" |
| Aegis | IAM diff review | "Review this IAM policy binding for least privilege" |
| Echo | Post-mortem analysis | "Task scored 62/100. Root cause: timeout. Generate learning." |
| Nova | UI component generation | "Build a React component showing agent performance history" |
| Delta | Architecture decision memo | "Compare Option A vs Option B for a 10-agent system" |

---

## Platform 2: Google Antigravity 2.0 (Development stage)

### What it's for

Multi-agent orchestration during development. The desktop app provides a "Manager Surface" for supervising parallel agents. The CLI (`agy`) replaces Gemini CLI in CI/CD. The SDK lets you host custom agents on your own infrastructure.

### Migration steps for Nexus

1. **Install Antigravity 2.0**:
   - Download from https://antigravity.google (macOS/Linux/Windows)
   - Or install CLI: `brew install google-antigravity` (or `npm install -g @google/antigravity-cli`)

2. **Import from AI Studio**:
   - Open Antigravity → File → Import from AI Studio
   - Select the exported `.gemini/` directory
   - All agent skills, hooks, and subagent definitions are preserved

3. **Map our multiagent handoff to Antigravity subagents**:

   Our `multiagent/HANDOFF.yaml` defines 5 agents. In Antigravity, these become **dynamic subagents**:

   ```markdown
   <!-- .gemini/agents/atlas.md -->
   ---
   name: Atlas
   model: gemini-3.5-flash
   tools: [terminal, file_edit, browser]
   hooks:
     - pre_execute: verify_no_serviceUsageAdmin_on_runtime
   ---
   You are Atlas, the GCP bootstrap agent.
   Owns: gcp/terraform/, gcp/deploy.sh, gcp/cloudbuild.yaml
   Forbidden: granting serviceUsageAdmin to runtime identities
   ```

   Repeat for Aegis, Echo, Nova, Delta.

4. **Set up scheduled tasks** (Antigravity 2.0 feature):
   ```bash
   agy schedule create \
     --name "nexus-daily-health-check" \
     --cron "0 9 * * *" \
     --agent atlas \
     --task "Run terraform plan and report drift"
   ```

5. **CI/CD with Antigravity CLI**:
   Replace `gemini` commands in your CI with `agy`:
   ```bash
   # Before (Gemini CLI, deprecated)
   gemini -p "Review this PR for security issues"

   # After (Antigravity CLI)
   agy -p "Review this PR for security issues" --agent aegis
   ```

6. **SDK hosting** (if you want agents on your own infra):
   ```typescript
   import { AntigravityAgent } from '@google/antigravity-sdk';

   const echo = new AntigravityAgent({
     model: 'gemini-3.5-flash',
     instructions: 'You are Echo, the autodidactic Twin engineer...',
     tools: ['code_execution', 'database_query'],
     host: 'your-infrastructure', // Cloud Run, GKE, etc.
   });

   await echo.execute({
     task: 'Generate post-mortem for task-842',
     context: { score: 62, errors: ['timeout'], agents: ['forge', 'vector'] }
   });
   ```

### Antigravity ↔ Nexus Console integration

Our Nexus Console (`src/components/OrchestratorConsole.tsx`) can display Antigravity agent status:

- **Agent canvas**: Show live Antigravity subagent states (working/idle/blocked)
- **Activity feed**: Stream Antigravity CLI output as mock activities
- **Memory ledger**: Store Antigravity execution results in `twin_behavioral_ledger`

This requires a webhook or polling endpoint from Antigravity → Nexus. Antigravity 2.0 supports custom integrations via the SDK.

---

## Platform 3: Gemini Enterprise Agent Platform (Production stage)

### What it's for

Production deployment with enterprise security: VPC-scoped model access, Cloud Audit Logs on every agent action, IAM-controlled permissions, data residency commitments.

**This is what we already built.** Our Terraform (`gcp/terraform/main.tf`) provisions Vertex AI Agent Engine, Cloud Workflows, Cloud Run, Cloud SQL, Secret Manager, and IAM roles. The multiagent handoff maps directly to this platform.

### Migration steps for Nexus

1. **Deploy Terraform infrastructure** (already prepared):
   ```bash
   export PROJECT_ID="your-gcp-project"
   export BOOTSTRAP_PRINCIPAL="user:you@example.com"
   ./gcp/bootstrap-service-usage.sh grant
   cd gcp/terraform && ./deploy-infra.sh
   cd ../.. && ./gcp/bootstrap-service-usage.sh revoke
   ```

2. **Register agents in Vertex AI Agent Engine**:
   Our `gcp/vertex-ai/agent-registry.json` defines 10 agents. Deploy them:
   ```bash
   gcloud ai reasoning-engines create \
     --project=$PROJECT_ID \
     --region=europe-west3 \
     --display-name="Nexus Agent Registry" \
     --spec-file=gcp/vertex-ai/agent-registry.json
   ```

3. **Connect Antigravity to Gemini Enterprise**:
   In Antigravity 2.0: Settings → Enterprise → Connect to Google Cloud → Select project
   This allows Antigravity agents to invoke Vertex AI Agent Engine endpoints directly.

4. **Enable Cloud Audit Logs**:
   Already configured in Terraform. Every agent action (tool use, state transition, memory write) is logged to Cloud Logging with full IAM context.

5. **VPC Service Controls** (optional, for regulated workloads):
   ```bash
   gcloud access-context-manager perimeters create nexus-perimeter \
     --title="Nexus VPC Perimeter" \
     --resources=projects/$PROJECT_NUMBER \
     --restricted-services=aiplatform.googleapis.com,run.googleapis.com
   ```

---

## Decision matrix: which platform for which task

| Task | AI Studio | Antigravity | Gemini Enterprise |
|------|-----------|-------------|-------------------|
| Test a prompt template | ✅ Best | ⚠️ Overkill | ❌ Too slow |
| Build a new agent from scratch | ✅ Good start | ✅ Best | ❌ Too slow |
| Orchestrate 5+ agents in parallel | ❌ No multi-agent | ✅ Best | ✅ Production |
| Run agents in CI/CD pipeline | ❌ No CLI | ✅ Best (agy) | ✅ Via Cloud Build |
| Deploy to production with IAM | ❌ No enterprise | ⚠️ Via Enterprise | ✅ Best |
| Audit every agent action | ❌ No audit logs | ⚠️ Local only | ✅ Cloud Audit Logs |
| Data residency (RBI, HIPAA, etc.) | ❌ No guarantees | ⚠️ Depends on host | ✅ VPC + perimeters |
| Cost for prototyping | Free tier | Free tier | Pay-per-use |
| Cost for production | N/A | $20-250/mo (Pro/Ultra) | Cloud billing |

---

## Framework layer: GenKit (see ADR-002)

The three Google platforms above are deployment surfaces. GenKit is the orchestration framework that sits underneath all three and is **independent** of which platform you pick. Verdict from `gcp/architecture/ADR-002-firebase-genkit.md`:

- **GenKit**: adopt. Type-safe flows, local trace viewer for the reflection loop, built-in evaluation harness.
- **Firebase App Check**: adopt. Cheap console API attestation.
- **Firestore**: adopt only as a real-time fan-out layer for the console UI; never as the primary store.
- **Firebase Auth, Firebase Hosting**: reject. Cloud IAM and Cloud Run + Next.js SSR already cover those.

Concrete integration plan and the first flow skeleton live in `genkit/INTEGRATION_PLAN.md`.

---

## Recommended Nexus migration sequence

### Week 1: AI Studio prototyping
- Create playgrounds for all 10 agents
- Test prompts against mock tasks
- Export stable agents to Antigravity

### Week 2: Antigravity development
- Import AI Studio exports
- Create `.gemini/` agent definitions
- Set up `agy` CLI in CI/CD (replace any `gemini` commands before June 18)
- Test multi-agent orchestration locally

### Week 3: Gemini Enterprise deployment
- Run Terraform bootstrap (already prepared)
- Deploy agent registry to Vertex AI Agent Engine
- Connect Antigravity to Enterprise project
- Enable Cloud Audit Logs and VPC Service Controls

### Week 4: Integration & monitoring
- Wire Antigravity agent status to Nexus Console
- Stream execution results to behavioral ledger
- Set up Cloud Monitoring dashboards
- Run first production task through the full pipeline

---

## What changes in our codebase

| File | Change | Reason |
|------|--------|--------|
| `gcp/terraform/main.tf` | Add `google_vertex_ai_agent_engine` resource | Register agents in production |
| `gcp/cloudbuild.yaml` | Replace `gemini` with `agy` commands | Gemini CLI retirement |
| `.gemini/agents/*.md` | **New**: Agent skill definitions | Antigravity subagent format |
| `src/lib/autodidactic/reflection-engine.ts` | Add Antigravity SDK integration | Store execution results |
| `src/components/OrchestratorConsole.tsx` | Add live agent status polling | Display Antigravity states |
| `multiagent/HANDOFF.yaml` | Add Antigravity-specific fields | Map to `.gemini/` format |

---

## Cost comparison (monthly, 10-agent system)

| Platform | Prototyping | Development | Production |
|----------|-------------|-------------|------------|
| AI Studio | Free (rate limited) | N/A | N/A |
| Antigravity | Free (20 req/day) | $20 (AI Pro) | N/A |
| Gemini Enterprise | N/A | N/A | ~$300-600 (Cloud billing) |
| **Total** | **$0** | **$20** | **$300-600** |

The production cost is dominated by Vertex AI Agent Engine runtime, Cloud Run, and Cloud SQL — not by the AI platform itself.

---

## Summary

**Don't choose one. Use all three as a pipeline.**

- AI Studio for fast iteration
- Antigravity for development and CI/CD
- Gemini Enterprise for production with enterprise security

The forced Gemini CLI → Antigravity CLI migration on June 18, 2026 is the only hard deadline. Everything else can be done incrementally.

Our existing Terraform, IAM bootstrap, and multiagent handoff package are already aligned with the Gemini Enterprise path. The missing piece is the `.gemini/` agent definitions for Antigravity — which can be generated from our `multiagent/HANDOFF.yaml` with a simple transform.
