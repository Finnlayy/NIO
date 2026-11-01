"use client";

import { useEffect } from "react";
import Link from "next/link";
import { BrainCircuit, Download, GitBranch, Library, Radio, Zap } from "lucide-react";
import { GridCanvas } from "@/ops/GridCanvas";
import { GalleryDrawer } from "@/ops/GalleryDrawer";
import { McpConsole } from "@/ops/McpConsole";
import { startLayout } from "@/ops/layout";
import { useGridStore } from "@/ops/store";
import { useDataSourceStatus } from "@/ops/hooks/useMarketData";
import { isTypingTarget, opsHotkey } from "@/ops/hotkeys";


export default function OpsGridPage() {
  const setGalleryOpen = useGridStore((s) => s.setGalleryOpen);
  const setConsoleOpen = useGridStore((s) => s.setConsoleOpen);
  const consoleOpen = useGridStore((s) => s.consoleOpen);
  const dataSource = useDataSourceStatus();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;
      const action = opsHotkey(e);
      if (!action) return;
      const s = useGridStore.getState();
      if (action === "toggle-console") {
        e.preventDefault();
        s.setConsoleOpen(!s.consoleOpen);
        return;
      }
      if (action === "toggle-gallery") {
        e.preventDefault();
        s.setGalleryOpen(!s.galleryOpen);
        return;
      }
      if (action === "close-panels") {
        if (s.consoleOpen || s.galleryOpen) {
          e.preventDefault();
          s.setConsoleOpen(false);
          s.setGalleryOpen(false);
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => startLayout(), []);

  /* Simulated live-tick telemetry: direct (virtualized) data binding —
     streams into the store without flooding the MCP control log. */
  useEffect(() => {
    const timer = setInterval(() => {
      useGridStore.getState().widgets.forEach((w) => {
        if (w.templateId === "TPL_02" && Array.isArray(w.data.spark)) {
          const spark = w.data.spark as number[];
          const last = spark[spark.length - 1] ?? 0.5;
          const next = Math.min(0.98, Math.max(0.02, last + (Math.random() - 0.48) * 0.08));
          useGridStore.getState().mergeData(w.id, { spark: [...spark.slice(1), next] });
        }
      });
    }, 2200);
    return () => clearInterval(timer);
  }, []);

  function exportLayout() {
    const widgets = useGridStore.getState().widgets;
    const payload = {
      exportedAt: new Date().toISOString(),
      widgets: widgets.map((w) => ({
        templateId: w.templateId,
        title: w.title,
        symbol: w.symbol,
        span: w.span,
        height: w.height,
        pinned: w.pinned,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "nio-widget-layout.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="min-h-screen bg-[#080a10] pb-10">
      {/* Header */}
      <header className="sticky top-0 z-30 h-14 border-b border-white/[0.06] bg-[#080a10]/90 backdrop-blur-xl px-4 sm:px-6 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 via-blue-500 to-violet-600 grid place-items-center shrink-0">
          <BrainCircuit className="w-4 h-4 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-white leading-tight truncate">
            <span className="sm:hidden">NIO OPS GRID</span>
            <span className="hidden sm:inline">NIO COMPOSABLE OPS GRID</span>
          </p>
          <p className="hidden sm:block text-[10px] uppercase tracking-[0.16em] text-slate-400 leading-tight truncate">
            Widget gallery · MCP hydration
          </p>
        </div>

        <div className="ml-auto flex items-center gap-2 shrink-0">
          <span
            className={`hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold uppercase tracking-wide border ${
              dataSource === "live"
                ? "text-emerald-300 border-emerald-400/25 bg-emerald-400/10"
                : dataSource === "sim"
                  ? "text-amber-300 border-amber-400/25 bg-amber-400/10"
                  : "text-slate-400 border-white/10 bg-white/[0.04]"
            }`}
            title={
              dataSource === "live"
                ? "Live TradingView data via tvremix MCP"
                : dataSource === "sim"
                  ? "tvremix unreachable — showing simulated data"
                  : "Checking tvremix connection…"
            }
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                dataSource === "live" ? "bg-emerald-400 pulse-dot" : dataSource === "sim" ? "bg-amber-400" : "bg-slate-500 animate-pulse"
              }`}
            />
            {dataSource === "live" ? "tvremix · Live" : dataSource === "sim" ? "Simulated" : "Connecting"}
          </span>
          <Link
            href="/apollo"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-cyan-400/25 bg-cyan-400/[0.07] text-cyan-200 hover:bg-cyan-400/15 transition-colors"
            title="Apollo orchestrator stage — orb, neural graph, FreeLLMAPI router"
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Apollo stage</span>
          </Link>
          <button
            onClick={() => setConsoleOpen(!consoleOpen)}
            aria-label="MCP Bus"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              consoleOpen
                ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-200"
                : "border-white/[0.08] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">MCP Bus <kbd className="ml-1 opacity-50 font-sans">Ctrl/⌘K</kbd></span>
          </button>
          <button
            onClick={exportLayout}
            aria-label="Export layout"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.08] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button
            onClick={() => setGalleryOpen(true)}
            aria-label="Add widget"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 text-white hover:brightness-110 transition-colors"
          >
            <Library className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Add widget <kbd className="ml-1 opacity-50 font-sans">Ctrl/⌘G</kbd></span>
            <Zap className="hidden sm:block w-3 h-3 opacity-80" />
          </button>
        </div>
      </header>

      {/* Canvas */}
      <div className="max-w-[1680px] mx-auto p-4 sm:p-5">
        <GridCanvas />

        <p className="text-center text-[10px] text-slate-700 mt-6">
          AI can make mistakes. Not financial advice — simulated telemetry for orchestration demos.
          Drag widgets by their grip to reorder · pin to lock · resize from the options menu.
        </p>
      </div>

      <GalleryDrawer />
      <McpConsole />
    </main>
  );
}
