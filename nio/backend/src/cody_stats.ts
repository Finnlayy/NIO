import { existsSync, readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';

export interface CodyStatsFile {
  startedAt: string;
  lastHeartbeatAt: string | null;
  lastActivityAt: string | null;
  lastConsoleHeartbeatAt: string | null;
  messagesUser: number;
  messagesAssistant: number;
  nioTasksTotal: number;
  nioTasksSuccess: number;
  nioTasksFailed: number;
  quotaEvents: number;
}

export interface CodyStatsResponse {
  agentId: 'cody';
  displayName: string;
  role: 'supervisor';
  online: boolean;
  startedAt: string | null;
  lastHeartbeatAt: string | null;
  lastActivityAt: string | null;
  uptimeMs: number;
  messagesUser: number;
  messagesAssistant: number;
  messagesTotal: number;
  nioTasksTotal: number;
  nioTasksSuccess: number;
  nioTasksFailed: number;
  quotaEvents: number;
  telegramTelemetryCount: number;
  route: string;
  channels: { telegram: boolean; console: boolean };
  /** Aggregated supervisor view (limbs, gates, budget). */
  supervisor?: {
    nioHealthy: boolean;
    activeLimbCount: number;
    gateFailuresRecent: number;
    persistenceEnabled: boolean;
    summary: string;
  };
}

const DEFAULT_STATS: CodyStatsFile = {
  startedAt: new Date(0).toISOString(),
  lastHeartbeatAt: null,
  lastActivityAt: null,
  lastConsoleHeartbeatAt: null,
  messagesUser: 0,
  messagesAssistant: 0,
  nioTasksTotal: 0,
  nioTasksSuccess: 0,
  nioTasksFailed: 0,
  quotaEvents: 0,
};

export function getWorkspaceRoot(): string {
  if (process.env.WORKSPACE_ROOT?.trim()) {
    return resolve(process.env.WORKSPACE_ROOT.trim());
  }
  return resolve(process.cwd(), '..', '..');
}

export function getCodyStatsPath(): string {
  return resolve(getWorkspaceRoot(), '.cody_stats.json');
}

export function loadCodyStatsFile(): CodyStatsFile | null {
  const path = getCodyStatsPath();
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf-8')) as CodyStatsFile;
  } catch {
    return null;
  }
}

export function saveCodyStatsFile(stats: CodyStatsFile): void {
  writeFileSync(getCodyStatsPath(), JSON.stringify(stats, null, 2), 'utf-8');
}

export function bumpCodyQuotaEvent(): void {
  const stats = loadCodyStatsFile() ?? { ...DEFAULT_STATS, startedAt: new Date().toISOString() };
  stats.quotaEvents += 1;
  stats.lastActivityAt = new Date().toISOString();
  saveCodyStatsFile(stats);
}

function touchStats(mutator: (stats: CodyStatsFile) => void): CodyStatsFile {
  const stats = loadCodyStatsFile() ?? { ...DEFAULT_STATS, startedAt: new Date().toISOString() };
  mutator(stats);
  saveCodyStatsFile(stats);
  return stats;
}

export function recordCodyConsoleHeartbeat(): void {
  touchStats((stats) => {
    const now = new Date().toISOString();
    stats.lastConsoleHeartbeatAt = now;
    stats.lastActivityAt = now;
  });
}

export function recordCodyConsoleMessage(role: 'user' | 'assistant'): void {
  touchStats((stats) => {
    const now = new Date().toISOString();
    if (role === 'user') stats.messagesUser += 1;
    else stats.messagesAssistant += 1;
    stats.lastConsoleHeartbeatAt = now;
    stats.lastActivityAt = now;
  });
}

export function bumpCodyConsoleActivity(): void {
  touchStats((stats) => {
    stats.nioTasksTotal += 1;
    stats.nioTasksSuccess += 1;
    stats.lastActivityAt = new Date().toISOString();
  });
}

function isChannelOnline(iso: string | null | undefined): boolean {
  if (!iso) return false;
  const ts = Date.parse(iso);
  return Number.isFinite(ts) && Date.now() - ts < HEARTBEAT_ONLINE_MS;
}

const HEARTBEAT_ONLINE_MS = 90_000;

export function buildCodyStatsResponse(
  file: CodyStatsFile | null,
  telegramTelemetryCount: number,
  supervisor?: CodyStatsResponse['supervisor'],
): CodyStatsResponse {
  const now = Date.now();
  const lastHeartbeat = file?.lastHeartbeatAt ? Date.parse(file.lastHeartbeatAt) : NaN;
  const telegramOnline = Number.isFinite(lastHeartbeat) && now - lastHeartbeat < HEARTBEAT_ONLINE_MS;
  const consoleOnline = isChannelOnline(file?.lastConsoleHeartbeatAt);
  const online = telegramOnline || consoleOnline;
  const startedAt = file?.startedAt ?? null;
  const uptimeMs = startedAt ? Math.max(0, now - Date.parse(startedAt)) : 0;

  return {
    agentId: 'cody',
    displayName: 'Cody — Supervisor',
    role: 'supervisor',
    online,
    startedAt,
    lastHeartbeatAt: file?.lastHeartbeatAt ?? null,
    lastActivityAt: file?.lastActivityAt ?? null,
    uptimeMs,
    messagesUser: file?.messagesUser ?? 0,
    messagesAssistant: file?.messagesAssistant ?? 0,
    messagesTotal: (file?.messagesUser ?? 0) + (file?.messagesAssistant ?? 0),
    nioTasksTotal: file?.nioTasksTotal ?? 0,
    nioTasksSuccess: file?.nioTasksSuccess ?? 0,
    nioTasksFailed: file?.nioTasksFailed ?? 0,
    quotaEvents: file?.quotaEvents ?? 0,
    telegramTelemetryCount,
    route: 'Cody supervisor → user · orchestrator · limbs · PostgreSQL',
    channels: { telegram: telegramOnline, console: consoleOnline },
    supervisor,
  };
}
