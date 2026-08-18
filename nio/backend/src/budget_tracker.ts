import type { ModelManifest, ModelTier } from "../../shared/manifest-schema";

export class BudgetTracker {
  private dailySpendUsd = 0;
  private lastResetDate = new Date().toDateString();

  constructor(private manifest: ModelManifest) {}

  refreshManifest(manifest: ModelManifest): void {
    this.manifest = manifest;
  }

  private maybeReset(): void {
    const today = new Date().toDateString();
    if (today !== this.lastResetDate) {
      this.dailySpendUsd = 0;
      this.lastResetDate = today;
    }
  }

  recordCost(usd: number): void {
    this.maybeReset();
    this.dailySpendUsd += usd;
  }

  getDailySpend(): number {
    this.maybeReset();
    return this.dailySpendUsd;
  }

  getEffectiveTier(requestedTier: ModelTier): ModelTier {
    this.maybeReset();
    const budget = this.manifest.defaults.cost_budget_usd_per_day;
    if (this.dailySpendUsd < budget) {
      return requestedTier;
    }
    if (this.manifest.defaults.on_daily_budget_exceeded === "clamp_to_free_tier") {
      return "free";
    }
    return requestedTier;
  }

  estimateCostUsd(inputTokens: number, costPer1mInput: number): number {
    return (inputTokens / 1_000_000) * costPer1mInput;
  }
}
