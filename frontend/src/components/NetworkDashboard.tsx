"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  domainFilters,
  networkEdges,
  networkNodes,
  taskPresets,
  type DomainId,
} from "@/data/network";
import { Header } from "./dashboard/Header";
import { FilterBar } from "./dashboard/FilterBar";
import { KpiStrip } from "./dashboard/KpiStrip";
import { CoreTile } from "./dashboard/CoreTile";
import { TaskConsole } from "./dashboard/TaskConsole";
import { InspectorTile } from "./dashboard/InspectorTile";
import { DomainsGrid } from "./dashboard/DomainsGrid";
import { AgentsTile } from "./dashboard/AgentsTile";
import { ActivityFeed } from "./dashboard/ActivityFeed";
import type { FeedEvent, FeedStatus, RunState } from "./dashboard/types";

// ⚡ Bolt Optimization:
// Extracted static derivations out of the React render loop (`useMemo`).
// Since `networkNodes` is static configuration data, calculating these values once
// at the module level avoids unnecessary Hook overhead and recalculation on mount.
const nodeById = Object.fromEntries(networkNodes.map((node) => [node.id, node]));
const activeDomainCount = new Set(networkNodes.map((node) => node.domain).filter(Boolean)).size;
const agentCount = networkNodes.filter((node) => node.kind === "agent").length;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

type TaskResponse = {
  coreNodeId: string;
  output: string;
  latencyMs: number;
  metadata: Record<string, unknown>;
};

export default function NetworkDashboard() {
  const [selectedId, setSelectedId] = useState("neural-core");
  const [activeFilter, setActiveFilter] = useState<DomainId | "all">("all");
  const [search, setSearch] = useState("");
  const [taskText, setTaskText] = useState("");
  const [isComplex, setIsComplex] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [runState, setRunState] = useState<RunState>("idle");
  const [result, setResult] = useState(
    "Select a module to inspect it, or dispatch a task through the Neural Core.",
  );
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [events, setEvents] = useState<FeedEvent[]>([]);

  const eventId = useRef(0);
  const log = useCallback(
    (event: { label: string; detail?: string; status: FeedStatus }) => {
      eventId.current += 1;
      const entry: FeedEvent = {
        id: eventId.current,
        timestamp: new Date().toLocaleTimeString("en-GB", { hour12: false }),
        label: event.label,
        detail: event.detail ?? "",
        status: event.status,
      };
      setEvents((prev) => [...prev.slice(-39), entry]);
    },
    [],
  );

  useEffect(() => {
    log({
      label: "Monitoring grid initialized",
      detail: `${networkNodes.length} nodes · ${networkEdges.length} links`,
      status: "info",
    });
  }, [log]);

  const selectedNode = nodeById[selectedId] ?? nodeById["neural-core"];
  const selectedPreset = taskPresets[selectedId];

  const visibleIds = useMemo(() => {
    const query = search.trim().toLowerCase();
    return new Set(
      networkNodes
        .filter((node) => {
          const matchesFilter =
            activeFilter === "all" || node.domain === activeFilter || node.kind === "core";
          const matchesSearch =
            query.length === 0 ||
            node.label.toLowerCase().includes(query) ||
            node.description.toLowerCase().includes(query) ||
            (node.tags ?? []).some((tag) => tag.toLowerCase().includes(query));
          return matchesFilter && matchesSearch;
        })
        .map((node) => node.id),
    );
  }, [activeFilter, search]);

  const selectNode = useCallback(
    (nodeId: string) => {
      setSelectedId(nodeId);
      const preset = taskPresets[nodeId];
      if (preset) {
        setTaskText(preset.taskDescription);
        setIsComplex(preset.isComplexWorkflow);
      }
    },
    [],
  );

  function changeFilter(id: DomainId | "all") {
    setActiveFilter(id);
    if (id !== "all") {
      const label = domainFilters.find((filter) => filter.id === id)?.label ?? id;
      log({ label: "Domain filter applied", detail: label, status: "trace" });
    }
  }

  async function runTask() {
    if (!taskText.trim() || isRunning) return;
    setIsRunning(true);
    setRunState("running");
    setResult("Routing task through middleware …");

    const preset = taskPresets[selectedId];
    const body = {
      taskDescription: taskText.trim(),
      isComplexWorkflow: isComplex,
      domainHint: preset?.domainHint,
      algorithmTag: preset?.algorithmTag,
      politenessTier: preset?.politenessTier ?? "neutral",
    };

    log({
      label: "Task dispatched",
      detail: preset?.domainHint ?? "auto domain routing",
      status: "info",
    });

    try {
      const response = await fetch(`${API_URL}/api/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as TaskResponse | { error?: string };
      if (!response.ok) {
        throw new Error("error" in data ? data.error : "Task execution failed");
      }
      const taskResponse = data as TaskResponse;
      setLatencyMs(taskResponse.latencyMs);
      setResult(taskResponse.output);
      setRunState("success");
      log({
        label: "Routing complete",
        detail: `${taskResponse.latencyMs}ms · ${taskResponse.coreNodeId}`,
        status: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not reach API";
      setResult(`API error: ${message}. Start the backend with npm start in the repo root.`);
      setRunState("error");
      log({ label: "Routing failed", detail: message, status: "error" });
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#090b12]">
      <Header
        search={search}
        onSearch={setSearch}
        onMasterSummary={() => selectNode("neural-core")}
      />
      <FilterBar activeFilter={activeFilter} onFilter={changeFilter} />

      <div className="max-w-[1600px] mx-auto p-4 sm:p-6 space-y-4">
        <KpiStrip
          nodeCount={networkNodes.length}
          domainCount={activeDomainCount}
          agentCount={agentCount}
          edgeCount={networkEdges.length}
          latencyMs={latencyMs}
        />

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <CoreTile
            node={nodeById["neural-core"]}
            selected={selectedId === "neural-core"}
            dimmed={!visibleIds.has("neural-core")}
            onSelect={() => selectNode("neural-core")}
          />
          <TaskConsole
            taskText={taskText}
            onTaskText={setTaskText}
            isComplex={isComplex}
            onComplex={setIsComplex}
            isRunning={isRunning}
            runState={runState}
            result={result}
            apiUrl={API_URL}
            onRun={() => void runTask()}
          />
          <div className="md:col-span-2 xl:col-span-1">
            <InspectorTile node={selectedNode} dimmed={false} hasPreset={Boolean(selectedPreset)} />
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="xl:col-span-2">
            <DomainsGrid visibleIds={visibleIds} selectedId={selectedId} onSelectNode={selectNode} />
          </div>
          <div className="space-y-4">
            <AgentsTile visibleIds={visibleIds} selectedId={selectedId} onSelect={selectNode} />
            <ActivityFeed events={events} />
          </div>
        </div>
      </div>
    </main>
  );
}
