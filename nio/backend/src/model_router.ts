import type { AgentRole, ModelManifest, ModelTier, ResolvedModel } from "../../shared/manifest-schema";
import { BudgetTracker } from "./budget_tracker";
import { loadManifest } from "./manifest_loader";
import { isLmStudioEnabled, lmStudioResolvedModel } from "./providers/lmstudio";

const tierOrder: ModelTier[] = ["frontier", "standard", "economy", "free"];

export function tierPriority(tier: ModelTier, manifest: ModelManifest): number {
  return manifest.tiers[tier]?.priority ?? 99;
}

export function isTierUpgrade(from: ModelTier, to: ModelTier, manifest: ModelManifest): boolean {
  return tierPriority(to, manifest) < tierPriority(from, manifest);
}

export class ModelRouter {
  private manifest: ModelManifest;
  private readonly budget: BudgetTracker;

  constructor(manifest?: ModelManifest) {
    this.manifest = manifest ?? loadManifest();
    this.budget = new BudgetTracker(this.manifest);
  }

  reload(): void {
    this.manifest = loadManifest(true);
    this.budget.refreshManifest(this.manifest);
  }

  getManifest(): ModelManifest {
    return this.manifest;
  }

  resolveRole(role: string): ResolvedModel {
    const tier = this.manifest.role_overrides[role] ?? "standard";
    return this.resolveTier(tier);
  }

  resolveTier(requestedTier: ModelTier): ResolvedModel {
    if (isLmStudioEnabled()) {
      const local = lmStudioResolvedModel();
      return {
        tier: requestedTier,
        provider: local.provider,
        model_id: local.model_id,
        cost_per_1m_input: local.cost_per_1m_input,
      };
    }

    const effectiveTier = this.budget.getEffectiveTier(requestedTier);
    const tierDef = this.manifest.tiers[effectiveTier];
    const primary = tierDef?.models[0];
    if (!primary) {
      throw new Error(`No models configured for tier: ${effectiveTier}`);
    }
    return {
      tier: effectiveTier,
      provider: primary.provider,
      model_id: primary.model_id,
      cost_per_1m_input: primary.cost_per_1m_input,
    };
  }

  recordUsage(estimatedInputTokens: number, model: ResolvedModel): number {
    const cost = this.budget.estimateCostUsd(estimatedInputTokens, model.cost_per_1m_input);
    this.budget.recordCost(cost);
    return cost;
  }

  getBudgetStatus() {
    return {
      dailySpendUsd: this.budget.getDailySpend(),
      dailyBudgetUsd: this.manifest.defaults.cost_budget_usd_per_day,
      swarmBudgetUsd: this.manifest.defaults.cost_budget_usd_per_swarm,
      onExceeded: this.manifest.defaults.on_daily_budget_exceeded,
    };
  }
}

export const consoleAgentRoleMap: Record<string, AgentRole> = {
  orchestrator: "coordinator",
  "review-synth": "judge",
  "quant-auditor": "judge",
  sandbox: "gate",
  cartographer: "worker",
  "python-tester": "worker",
  "ci-runner": "worker",
  "c-reviewer": "worker",
  "ui-designer": "worker",
  memory: "aggregator",
  cody: "heartbeat",
};

export function resolveConsoleAgentRole(agentId: string): AgentRole {
  return consoleAgentRoleMap[agentId] ?? "worker";
}

export { tierOrder };
