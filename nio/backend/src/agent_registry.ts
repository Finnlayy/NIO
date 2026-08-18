import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';
import type { AgentRegistryEntry, AgentRole } from '../../shared/manifest-schema';
import { buildCoreRegistry } from './core_registry';
import type { LimbInstance } from './limb_instance_store';
import { loadLibraryTemplates } from './library_templates';
import { consoleAgentRoleMap, ModelRouter, resolveConsoleAgentRole } from './model_router';

/**
 * Backend agent registry — Atlas core + dynamic limb instances.
 *
 * See `nio/console/gcp/architecture/ATLAS_LIMB_MODEL.md`.
 */

interface RoleManifest {
  name: string;
  description?: string;
  domains?: string[];
}

export function loadRoleManifests(agentsDir: string): RoleManifest[] {
  const rolesDir = join(agentsDir, 'roles');
  try {
    return readdirSync(rolesDir)
      .filter((f) => f.endsWith('.json'))
      .map((file) => JSON.parse(readFileSync(join(rolesDir, file), 'utf-8')) as RoleManifest);
  } catch {
    return [];
  }
}

function buildLimbRegistryEntry(
  router: ModelRouter,
  instance: LimbInstance,
  agentsDir: string,
): AgentRegistryEntry {
  const roleManifests = loadRoleManifests(agentsDir);
  const byName = new Map(roleManifests.map((r) => [r.name, r]));
  const template = loadLibraryTemplates().find((t) => t.template_id === instance.template_id);
  const roleKey = instance.mock_id;
  const role = (consoleAgentRoleMap[roleKey] ?? 'worker') as AgentRole;
  const resolvedModel = router.resolveRole(role);
  const pydanticRole = byName.get(roleKey.replace(/-/g, '_')) ?? byName.get(roleKey);

  return {
    agentId: instance.mock_id,
    displayName: instance.display_name,
    role,
    modelTier: resolvedModel.tier,
    resolvedModel,
    description: pydanticRole?.description ?? template?.description,
  };
}

/** Backward-compatible registry: core + interface + active limb instances. */
export function buildAgentRegistry(
  router: ModelRouter,
  agentsDir: string,
  activeLimbs: LimbInstance[] = [],
): AgentRegistryEntry[] {
  const core = buildCoreRegistry(router);
  const limbEntries = activeLimbs.map((instance) =>
    buildLimbRegistryEntry(router, instance, agentsDir),
  );
  return [...core, ...limbEntries];
}

/** Full legacy list for clients that still expect all template personas. */
export function buildLegacyAgentRegistry(router: ModelRouter, agentsDir: string): AgentRegistryEntry[] {
  const templates = loadLibraryTemplates();
  const roleManifests = loadRoleManifests(agentsDir);
  const byName = new Map(roleManifests.map((r) => [r.name, r]));

  const templateEntries = templates.map((template) => {
    const role = (consoleAgentRoleMap[template.mock_id] ?? 'worker') as AgentRole;
    const resolvedModel = router.resolveRole(role);
    const pydanticRole = byName.get(template.mock_id.replace(/-/g, '_')) ?? byName.get(template.mock_id);
    return {
      agentId: template.mock_id,
      displayName: template.display_name,
      role,
      modelTier: resolvedModel.tier,
      resolvedModel,
      description: pydanticRole?.description ?? template.description,
    };
  });

  return [...buildCoreRegistry(router), ...templateEntries];
}

export { resolveConsoleAgentRole };
