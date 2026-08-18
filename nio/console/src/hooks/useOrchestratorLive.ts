"use client";

import { useCallback, useEffect, useState } from "react";
import {
  mockActivity,
  mockAgents,
  mockMemory,
  mockMetrics,
  mockPolicies,
  mockRuns,
  googleCloudAgentRegistry,
  type MockActivity,
  type MockAgent,
  type MockMetric,
  type MockMemory,
} from "@/data/mock-orchestrator";
import { buildCanvasAgents, mapTemplateToLibraryRow } from "@/data/atlas-limb";
import {
  buildMetricsFromTelemetry,
  buildPoliciesFromManifest,
  mapRegistryToAgents,
  mapRegistryToGoogleCloudEntries,
  applyCodyLiveStatus,
} from "@/data/orchestrator-live";
import type {
  AgentRegistryEntry,
  ArchiveEntry,
  CodyStats,
  LimbInstance,
  LimbTemplate,
} from "@/lib/manifest-types";
import {
  checkBackendHealth,
  fetchActiveLimbs,
  fetchAgentRegistry,
  fetchCodyStats,
  fetchLibraryArchive,
  fetchLibraryTemplates,
  fetchManifest,
  fetchTelemetry,
  runTask,
} from "@/lib/nio-client";

const agentRoleMap: Record<string, string> = {
  orchestrator: "coordinator",
  "review-synth": "judge",
  "quant-auditor": "judge",
  sandbox: "gate",
  memory: "aggregator",
};

export function useOrchestratorLive() {
  const [apiLive, setApiLive] = useState(false);
  const [agents, setAgents] = useState<MockAgent[]>(mockAgents);
  const [canvasAgents, setCanvasAgents] = useState<MockAgent[]>(
    mockAgents.filter((a) => a.id === "orchestrator" || a.id === "cody"),
  );
  const [coreAgents, setCoreAgents] = useState<MockAgent[]>(
    mockAgents.filter((a) => ["orchestrator", "sandbox", "memory"].includes(a.id)),
  );
  const [activeLimbs, setActiveLimbs] = useState<LimbInstance[]>([]);
  const [libraryTemplates, setLibraryTemplates] = useState<LimbTemplate[]>([]);
  const [libraryArchive, setLibraryArchive] = useState<ArchiveEntry[]>([]);
  const [registry, setRegistry] = useState<AgentRegistryEntry[]>([]);
  const [registryEntries, setRegistryEntries] = useState(googleCloudAgentRegistry);
  const [metrics, setMetrics] = useState<MockMetric[]>(mockMetrics);
  const [policies, setPolicies] = useState(mockPolicies);
  const [activities, setActivities] = useState<MockActivity[]>(mockActivity);
  const [memoryItems, setMemoryItems] = useState<MockMemory[]>(mockMemory);
  const [runs, setRuns] = useState(mockRuns);
  const [isRunning, setIsRunning] = useState(false);
  const [codyStats, setCodyStats] = useState<CodyStats | null>(null);

  const refresh = useCallback(async () => {
    const healthy = await checkBackendHealth();
    setApiLive(healthy);
    if (!healthy) {
      setCanvasAgents(mockAgents.filter((a) => a.id === "orchestrator" || a.id === "cody"));
      setCoreAgents(mockAgents.filter((a) => ["orchestrator", "sandbox", "memory"].includes(a.id)));
      return;
    }

    try {
      const [registryData, telemetry, manifest, cody, limbsData, templatesData, archiveData] =
        await Promise.all([
          fetchAgentRegistry(),
          fetchTelemetry(20),
          fetchManifest(),
          fetchCodyStats().catch(() => null),
          fetchActiveLimbs().catch(() => ({ limbs: [] as LimbInstance[] })),
          fetchLibraryTemplates().catch(() => ({ templates: [] as LimbTemplate[] })),
          fetchLibraryArchive(30).catch(() => ({ entries: [] as ArchiveEntry[] })),
        ]);

      setCodyStats(cody);
      setActiveLimbs(limbsData.limbs);
      setLibraryTemplates(templatesData.templates);
      setLibraryArchive(archiveData.entries);

      const mappedAgents = applyCodyLiveStatus(mapRegistryToAgents(registryData.agents), cody);
      setAgents(mappedAgents);
      setRegistry(registryData.agents);
      setRegistryEntries(mapRegistryToGoogleCloudEntries(registryData.agents));
      setMetrics(buildMetricsFromTelemetry(telemetry, registryData.budget));
      setPolicies(buildPoliciesFromManifest(manifest));

      const atlasView = buildCanvasAgents({
        registry: registryData.agents,
        activeLimbs: limbsData.limbs,
        templates: templatesData.templates,
        codyStats: cody,
      });
      setCanvasAgents(atlasView.canvasAgents);
      setCoreAgents(atlasView.coreAgents);

      if (telemetry.length > 0) {
        setActivities(
          telemetry.slice(0, 8).map((event, index) => ({
            id: event.eventId ?? `tel-${index}`,
            timestamp: new Intl.DateTimeFormat("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            }).format(new Date(event.timestamp)),
            agent:
              event.agentId === "cody" || event.source === "telegram"
                ? "Cody"
                : event.limbInstanceId
                  ? `Limb ${event.limbInstanceId}`
                  : "Atlas",
            action: event.isComplex ? "Complex task classified" : "Task executed",
            detail: `${event.domain} · ${event.promptVariant} · ${event.latencyMs ?? 0}ms`,
            type: (event.isComplex ? "review" : "success") as MockActivity["type"],
          })),
        );
      }
    } catch {
      setApiLive(false);
    }

    try {
      const memoryRes = await fetch("/api/orchestrator/memory");
      if (memoryRes.ok) {
        const data = (await memoryRes.json()) as {
          events: Array<{ id: number; agentId: string; notes: string; score: number; outcome: string }>;
        };
        if (data.events?.length) {
          setMemoryItems(
            data.events.map((event) => ({
              id: String(event.id),
              title: `${event.agentId} · ${event.outcome}`,
              summary: event.notes,
              tags: [event.outcome, event.agentId],
              score: event.score / 100,
              source: "PostgreSQL ledger",
              age: "recent",
            })),
          );
        }
      }
    } catch {
      // memory store optional
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const runWorkflow = useCallback(async () => {
    if (isRunning) return;
    setIsRunning(true);

    const taskDescription =
      "Review orderbook merge for race conditions and validate DP recurrence correctness.";
    const role = agentRoleMap["python-tester"] ?? "worker";

    try {
      if (apiLive) {
        const result = await runTask({
          taskDescription,
          isComplexWorkflow: true,
          role,
          domainHint: "dev_dp",
          politenessTier: "neutral",
          source: "console",
          templateId: "python-test-engineer",
        });

        setRuns((current) =>
          current.map((run) =>
            run.id === "run-842"
              ? {
                  ...run,
                  progress: 100,
                  currentStage: "NIO middleware complete",
                  status: "passed",
                  updated: "just now",
                }
              : run,
          ),
        );

        setActivities((current) => [
          {
            id: `live-${Date.now()}`,
            timestamp: new Intl.DateTimeFormat("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            }).format(new Date()),
            agent: "Atlas",
            action: "NIO task completed",
            detail: result.output.slice(0, 120),
            type: "success" as MockActivity["type"],
          },
          ...current,
        ].slice(0, 8));

        await refresh();
      } else {
        setRuns((current) =>
          current.map((run) =>
            run.id === "run-842" ? { ...run, progress: 86, status: "review", updated: "offline fallback" } : run,
          ),
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Task failed";
      setActivities((current) => [
        {
          id: `err-${Date.now()}`,
          timestamp: new Intl.DateTimeFormat("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }).format(new Date()),
          agent: "NIO",
          action: "Task error",
          detail: message,
          type: "warning" as MockActivity["type"],
        },
        ...current,
      ].slice(0, 8));
    } finally {
      setIsRunning(false);
    }
  }, [apiLive, isRunning, refresh]);

  const templateRows = libraryTemplates.map(mapTemplateToLibraryRow);

  return {
    apiLive,
    agents,
    canvasAgents,
    coreAgents,
    activeLimbs,
    libraryTemplates,
    libraryArchive,
    templateRows,
    setAgents,
    registry,
    registryEntries,
    metrics,
    policies,
    activities,
    setActivities,
    memoryItems,
    runs,
    setRuns,
    isRunning,
    runWorkflow,
    refresh,
    codyStats,
  };
}
