import { z } from "zod";

export const modelTierNames = ["frontier", "standard", "economy", "free"] as const;
export type ModelTier = (typeof modelTierNames)[number];

export const agentRoles = [
  "coordinator",
  "judge",
  "gate",
  "worker",
  "aggregator",
  "heartbeat",
  "invent-skills-draft",
] as const;
export type AgentRole = (typeof agentRoles)[number];

const modelEntrySchema = z.object({
  provider: z.string(),
  model_id: z.string(),
  cost_per_1m_input: z.number(),
});

const tierSchema = z.object({
  priority: z.number(),
  models: z.array(modelEntrySchema),
  rate_limit_rpm: z.number().optional(),
});

export const modelManifestSchema = z.object({
  version: z.number(),
  defaults: z.object({
    fallback_chain: z.array(z.enum(modelTierNames)),
    cost_budget_usd_per_swarm: z.number(),
    cost_budget_usd_per_day: z.number(),
    on_daily_budget_exceeded: z.string(),
    daily_budget_reset: z.string(),
  }),
  providers: z.record(
    z.string(),
    z.record(z.string(), z.union([z.string(), z.record(z.string(), z.string())])),
  ),
  tiers: z.record(z.enum(modelTierNames), tierSchema),
  role_overrides: z.record(z.string(), z.enum(modelTierNames)),
});

export type ModelManifest = z.infer<typeof modelManifestSchema>;

export interface ResolvedModel {
  tier: ModelTier;
  provider: string;
  model_id: string;
  cost_per_1m_input: number;
}

export interface AgentRegistryEntry {
  agentId: string;
  displayName: string;
  role: AgentRole;
  modelTier: ModelTier;
  resolvedModel: ResolvedModel;
  description?: string;
}
