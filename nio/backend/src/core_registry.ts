import type { AgentRegistryEntry, AgentRole } from '../../shared/manifest-schema';
import type { ModelRouter } from './model_router';
import { resolveConsoleAgentRole } from './model_router';

/** Immutable Tier-1 core agents (canonical IDs). */
export const CORE_CANONICAL_IDS = {
  orchestrator: 'atlas-orchestrator',
  sandbox: 'aegis-security',
  memory: 'echo-memory',
} as const;

export const INTERFACE_AGENT_ID = 'cody';

const coreAgents: Array<{
  agentId: string;
  canonicalId: string;
  displayName: string;
  description: string;
  roleKey: string;
}> = [
  {
    agentId: 'orchestrator',
    canonicalId: CORE_CANONICAL_IDS.orchestrator,
    displayName: 'Atlas - Supervisor Orchestrator',
    description: 'Coordinates workflows and state transitions',
    roleKey: 'orchestrator',
  },
  {
    agentId: 'sandbox',
    canonicalId: CORE_CANONICAL_IDS.sandbox,
    displayName: 'Aegis - Security Guardian',
    description: 'Enforces sandbox and secret policies',
    roleKey: 'sandbox',
  },
  {
    agentId: 'memory',
    canonicalId: CORE_CANONICAL_IDS.memory,
    displayName: 'Echo - Memory & Eval Curator',
    description: 'Curates behavioral ledger and retrieval',
    roleKey: 'memory',
  },
];

const interfaceAgent = {
  agentId: INTERFACE_AGENT_ID,
  canonicalId: INTERFACE_AGENT_ID,
  displayName: 'Cody - Telegram Bridge',
  description: 'Human-facing Telegram assistant routed through NIO middleware',
  roleKey: 'cody',
};

export function buildCoreRegistry(router: ModelRouter): AgentRegistryEntry[] {
  return [...coreAgents, interfaceAgent].map((agent) => {
    const role = resolveConsoleAgentRole(agent.roleKey) as AgentRole;
    const resolvedModel = router.resolveRole(role);
    return {
      agentId: agent.agentId,
      displayName: agent.displayName,
      role,
      modelTier: resolvedModel.tier,
      resolvedModel,
      description: agent.description,
    };
  });
}

export function isCoreAgentId(agentId: string): boolean {
  return (
    agentId === 'orchestrator' ||
    agentId === 'sandbox' ||
    agentId === 'memory' ||
    Object.values(CORE_CANONICAL_IDS).includes(agentId as (typeof CORE_CANONICAL_IDS)[keyof typeof CORE_CANONICAL_IDS])
  );
}
