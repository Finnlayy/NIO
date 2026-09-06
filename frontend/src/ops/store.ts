"use client";

import { create } from "zustand";
import type { McpEvent, McpHydrateParams, WidgetInstance } from "./types";
import { templateById, templateByKey } from "./widgetRegistry";

let seq = 0;
const nextId = () => `w-${(++seq).toString(36)}-${Date.now().toString(36).slice(-4)}`;

/* ------------------------------------------------------------------ */
/* MCP event bus                                                       */
/* Control-plane JSON-RPC events from the NIO Master Twin.             */
/* `emitMcp` is the single entry point: it logs, notifies console      */
/* listeners, and applies the event to the store. UI gestures express  */
/* themselves AS MCP events, so an orchestrated session looks identical */
/* to a user-driven one. Streaming telemetry bypasses the bus (direct  */
/* virtualized data binding) to keep 60fps updates out of the log.     */
/* ------------------------------------------------------------------ */
type Listener = (event: McpEvent) => void;
const listeners = new Set<Listener>();

export function onMcpEvent(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function materialize(params: McpHydrateParams): WidgetInstance | null {
  const tpl = templateByKey(params.templateKey);
  if (!tpl) return null;
  return {
    id: params.instanceId ?? nextId(),
    templateId: tpl.id,
    title: params.title ?? tpl.title,
    symbol: params.symbol ?? tpl.defaultSymbol,
    span: params.span ?? tpl.defaultSpan,
    height: tpl.defaultHeight,
    minimized: false,
    pinned: false,
    data: params.data ?? tpl.dataFactory(),
  };
}

function applyEvent(event: McpEvent) {
  const store = useGridStore.getState();
  if (event.method === "ui/hydrate_widget_template") {
    const params = event.params as unknown as McpHydrateParams;
    const instance = materialize(params);
    if (!instance) return;
    store.upsert(instance);
  } else if (event.method === "ui/update_widget_state") {
    const p = event.params as { instanceId?: string; data?: Record<string, unknown> };
    if (p.instanceId && p.data) store.mergeData(p.instanceId, p.data);
  } else if (event.method === "ui/remove_widget") {
    const p = event.params as { instanceId?: string };
    if (p.instanceId) store.deleteInstance(p.instanceId);
  }
}

export function emitMcp(
  method: McpEvent["method"],
  source: string,
  params: Record<string, unknown>,
): McpEvent {
  const event: McpEvent = {
    id: ++seq,
    timestamp: new Date().toLocaleTimeString("en-GB", { hour12: false }),
    method,
    source,
    params,
  };
  useGridStore.getState().pushLog(event);
  listeners.forEach((l) => l(event));
  applyEvent(event);
  return event;
}

interface GridState {
  widgets: WidgetInstance[];
  mcpLog: McpEvent[];
  consoleOpen: boolean;
  galleryOpen: boolean;

  /* store-internal mutations (no event emission) */
  pushLog: (event: McpEvent) => void;
  upsert: (instance: WidgetInstance) => void;
  deleteInstance: (id: string) => void;
  mergeData: (id: string, data: Record<string, unknown>) => void;

  /* canvas personalization (local state, not control-plane) */
  reorder: (from: number, to: number) => void;
  toggleMinimize: (id: string) => void;
  togglePin: (id: string) => void;
  cycleSpan: (id: string) => void;
  cycleHeight: (id: string) => void;
  setConsoleOpen: (open: boolean) => void;
  setGalleryOpen: (open: boolean) => void;
}

export const useGridStore = create<GridState>((set) => ({
  widgets: [],
  mcpLog: [],
  consoleOpen: false,
  galleryOpen: false,

  pushLog: (event) =>
    set((s) => ({ mcpLog: [...s.mcpLog.slice(-59), event] })),

  upsert: (instance) =>
    set((s) => {
      const existing = s.widgets.some((w) => w.id === instance.id);
      return {
        widgets: existing
          ? s.widgets.map((w) =>
              w.id === instance.id
                ? { ...w, data: instance.data, title: instance.title, symbol: instance.symbol }
                : w,
            )
          : [...s.widgets, instance],
      };
    }),

  deleteInstance: (id) =>
    set((s) => ({ widgets: s.widgets.filter((w) => w.id !== id) })),

  mergeData: (id, data) =>
    set((s) => ({
      widgets: s.widgets.map((w) =>
        w.id === id ? { ...w, data: { ...w.data, ...data } } : w,
      ),
    })),

  reorder: (from, to) =>
    set((s) => {
      if (from === to || from < 0 || to < 0 || from >= s.widgets.length || to >= s.widgets.length) return s;
      const widgets = [...s.widgets];
      const [moved] = widgets.splice(from, 1);
      if (moved.pinned) return s; // pinned widgets resist reordering
      widgets.splice(to, 0, moved);
      return { widgets };
    }),

  toggleMinimize: (id) =>
    set((s) => ({
      widgets: s.widgets.map((w) => (w.id === id ? { ...w, minimized: !w.minimized } : w)),
    })),

  togglePin: (id) =>
    set((s) => ({
      widgets: s.widgets.map((w) => (w.id === id ? { ...w, pinned: !w.pinned } : w)),
    })),

  cycleSpan: (id) =>
    set((s) => ({
      widgets: s.widgets.map((w) => {
        if (w.id !== id) return w;
        const order: WidgetInstance["span"][] = [2, 3, 4, 6];
        const next = order[(order.indexOf(w.span) + 1) % order.length];
        return { ...w, span: next };
      }),
    })),

  cycleHeight: (id) =>
    set((s) => ({
      widgets: s.widgets.map((w) =>
        w.id === id ? { ...w, height: w.height === "compact" ? "tall" : "compact" } : w,
      ),
    })),

  setConsoleOpen: (open) => set({ consoleOpen: open }),
  setGalleryOpen: (open) => set({ galleryOpen: open }),
}));

/* ------------------------------------------------------------------ */
/* High-level control-plane actions (dispatched as MCP events)          */
/* ------------------------------------------------------------------ */

/** Materialize a widget from a gallery template */
export function dispatchHydrateTemplate(templateId: `TPL_${string}`) {
  const tpl = templateById(templateId);
  if (!tpl) return;
  emitMcp("ui/hydrate_widget_template", "gallery", {
    templateKey: tpl.key,
    title: tpl.defaultSymbol ? `${tpl.title} · ${tpl.defaultSymbol}` : tpl.title,
    symbol: tpl.defaultSymbol,
    span: tpl.defaultSpan,
  });
}

/** Re-hydrate a widget (e.g. symbol switch / refresh) with fresh factory data */
export function dispatchRefresh(widget: WidgetInstance) {
  const tpl = templateById(widget.templateId);
  if (!tpl) return;
  emitMcp("ui/hydrate_widget_template", "master-twin", {
    templateKey: tpl.key,
    instanceId: widget.id,
    title: widget.title,
    symbol: widget.symbol,
    span: widget.span,
    data: tpl.dataFactory(),
  });
}

export function dispatchRemove(id: string) {
  emitMcp("ui/remove_widget", "ui-canvas", { instanceId: id });
}

/** Master-Twin scenario injection (e.g. geopolitical shock → liquidity radar) */
export function dispatchOrchestratorScenario() {
  emitMcp("ui/hydrate_widget_template", "master-twin", {
    templateKey: "orderflow-cvd-heatmap",
    title: "Liquidity Radar · Shock Response",
    span: 6,
  });
}
