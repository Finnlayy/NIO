import { existsSync, readdirSync, readFileSync } from 'fs';
import { join } from 'path';
import type { ModelTier } from '../../shared/manifest-schema';
import { getTemplatesDir } from './workspace_paths';

export interface LimbTemplate {
  template_id: string;
  mock_id: string;
  display_name: string;
  role: string;
  tools: string[];
  model_tier: ModelTier;
  limb_runtime: string;
  output_contract?: string;
  routing_weight?: number;
  requires_cross_review?: boolean;
  review_reason?: string;
  description?: string;
}

let cachedTemplates: LimbTemplate[] | null = null;

export function loadLibraryTemplates(force = false): LimbTemplate[] {
  if (cachedTemplates && !force) return cachedTemplates;

  const dir = getTemplatesDir();
  if (!existsSync(dir)) {
    cachedTemplates = [];
    return cachedTemplates;
  }

  cachedTemplates = readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .map((file) => JSON.parse(readFileSync(join(dir, file), 'utf-8')) as LimbTemplate)
    .sort((a, b) => a.template_id.localeCompare(b.template_id));

  return cachedTemplates;
}

export function getTemplateById(templateId: string): LimbTemplate | undefined {
  return loadLibraryTemplates().find((t) => t.template_id === templateId);
}

export function getTemplateByMockId(mockId: string): LimbTemplate | undefined {
  return loadLibraryTemplates().find((t) => t.mock_id === mockId);
}

export function resolveTemplateForTask(params: {
  templateId?: string;
  role?: string;
  domainHint?: string;
}): LimbTemplate {
  const templates = loadLibraryTemplates();
  if (params.templateId) {
    const found = getTemplateById(params.templateId);
    if (found) return found;
  }

  if (params.role === 'judge') {
    return getTemplateById('quant-auditor') ?? templates[0]!;
  }
  if (params.role === 'coordinator') {
    return getTemplateById('pr-review-synthesizer') ?? templates[0]!;
  }
  if (params.domainHint?.includes('ci') || params.domainHint?.includes('build')) {
    return getTemplateById('ci-evidence-runner') ?? templates[0]!;
  }

  return getTemplateById('python-test-engineer') ?? templates[0]!;
}
