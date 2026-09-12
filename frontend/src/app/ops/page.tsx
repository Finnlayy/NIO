"use client";

import { useEffect, useRef } from "react";
import { BrainCircuit, Download, Library, Radio, Zap } from "lucide-react";
import { GridCanvas } from "@/ops/GridCanvas";
import { GalleryDrawer } from "@/ops/GalleryDrawer";
import { McpConsole } from "@/ops/McpConsole";
import { emitMcp, useGridStore } from "@/ops/store";
import { useDataSourceStatus } from "@/ops/hooks/useMarketData";
import { isTypingTarget, opsHotkey } from "@/ops/hotkeys";
import { widgetTemplates } from "@/ops/widgetRegistry";

/* Boot layout the Master Twin hydrates on session start */
const BOOT_LAYOUT: Array<{ key: string; span?: 2 | 3 | 4 | 6; title?: string }> = [
  { key: "market-breadth-radar", span: 6 },
  { key: "technical-signal-gauge", span: 2 },
  { key: "custom-dynamic-table", span: 2 },
  { key: "quantum-envelope-chart", span: 2 },
  { key: "gpm-incubation-arena", span: 3 },
  { key: "orderflow-cvd-heatmap", span: 3 },
  { key: "vault-earn-arbitrage", span: 3 },
  { key: "macro-catalyst-timeline", span: 3 },
  { key: "limb-mindmap-node", span: 3 },
  { key: "composite-score-ranking", span: 6 },
];

export default function OpsGridPage() {
  const setGalleryOpen = useGridStore((s) => s.setGalleryOpen);
  const setConsoleOpen = useGridStore((s) => s.setConsoleOpen);
  const consoleOpen = useGridStore((s) => s.consoleOpen);
  const dataSource = useDataSourceStatus();
  const booted = useRef(false);

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
      if (s.consoleOpen || s.galleryOpen) {
        e.preventDefault();
        s.setConsoleOpen(false);
        s.setGalleryOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;

    // Master Twin boot: hydrate the default monitoring layout as a sequence
    // of MCP events so each widget spring-inserts into the auto-layout grid.
    let delay = 0;
    for (const entry of BOOT_LAYOUT) {
      const tpl = widgetTemplates.find((t) => t.key === entry.key);
      if (!tpl) continue;
      setTimeout(() => {
        emitMcp("ui/hydrate_widget_template", "master-twin/boot", {
          templateKey: entry.key,
          title: entry.title ?? (tpl.defaultSymbol ? `${tpl.title} · ${tpl.defaultSymbol}` : tpl.title),
          symbol: tpl.defaultSymbol,
          span: entry.span ?? tpl.defaultSpan,
        });
      }, delay);
      delay += 180;
    }
  }, []);

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
            NIO COMPOSABLE OPS GRID
          </p>
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500 leading-tight">
            Widget gallery · MCP hydration
          </p>
        </div>

        <div className="ml-auto flex items-center gap-2">
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
          <button
            onClick={() => setConsoleOpen(!consoleOpen)}
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.08] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button
            onClick={() => setGalleryOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 text-white hover:brightness-110 transition-all"
          >
            <Library className="w-3.5 h-3.5" />
            Add widget <kbd className="ml-1 opacity-50 font-sans">Ctrl/⌘G</kbd>
            <Zap className="w-3 h-3 opacity-80" />
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
