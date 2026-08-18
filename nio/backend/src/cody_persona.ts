import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';
import { getWorkspaceRoot } from './cody_stats';

const PERSONA_FILES = ['AGENTS.md', 'SOUL.md', 'IDENTITY.md', 'USER.md'] as const;
const MAX_PERSONA_CHARS_PER_FILE = 8000;

function readPersonaFile(name: string): string {
  const path = resolve(getWorkspaceRoot(), name);
  if (!existsSync(path)) return '';
  try {
    const text = readFileSync(path, 'utf-8').trim();
    return text.slice(0, MAX_PERSONA_CHARS_PER_FILE);
  } catch {
    return '';
  }
}

/** Load workspace persona files (mirrors telegram_notify.py). */
export function loadCodyPersonaContext(): string {
  const parts: string[] = [];
  for (const file of PERSONA_FILES) {
    const content = readPersonaFile(file);
    if (content) parts.push(`## ${file}\n${content}`);
  }
  return parts.join('\n\n');
}

/** Build Cody system prompt for console chat. */
export function buildCodySystemPrompt(personaContext: string): string {
  return (
    'You are Cody, a relaxed but precise assistant in the NIO console. ' +
    'Follow the workspace persona and boundaries below. ' +
    'Reply directly to the user\'s latest message, keep it concise unless detail is asked, ' +
    'and do not expose secrets.\n\n' +
    personaContext
  );
}

export const STATUS_QUERY_PATTERNS: RegExp[] = [
  /\b(what are agents doing|agent status|status report|system status)\b/i,
  /\b(what('s| is) running|active limbs|orchestrator status)\b/i,
];

export function isStatusQuery(text: string): boolean {
  return STATUS_QUERY_PATTERNS.some((p) => p.test(text));
}
