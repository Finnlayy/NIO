"use client";

import { emitMcp, restoreWidgets, useGridStore } from "./store";
import type { WidgetInstance, WidgetSpan } from "./types";
import { widgetTemplates } from "./widgetRegistry";

export const LAYOUT_STORAGE_KEY = "nio.ops.layout.v1";

export type SavedWidget = Omit<WidgetInstance, "id" | "data">;

/* Boot layout the Master Twin hydrates on session start */
const BOOT_LAYOUT: Array<{ key: string; span?: WidgetSpan; title?: string }> = [
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
const BOOT_STEP_MS = 180;

const SPANS: readonly number[] = [2, 3, 4, 6];

/** Everything the operator arranged. Market data is left out: it is rebuilt on load. */
export function serializeLayout(widgets: readonly WidgetInstance[]): string {
  const saved: SavedWidget[] = widgets.map((w) => ({
    templateId: w.templateId,
    title: w.title,
    symbol: w.symbol,
    span: w.span,
    height: w.height,
    minimized: w.minimized,
    pinned: w.pinned,
    takenAt: w.takenAt,
  }));
  return JSON.stringify(saved);
}

/** Null means "nothing usable saved", which boots the default layout. */
export function parseLayout(raw: string | null): SavedWidget[] | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed.flatMap((entry: Partial<SavedWidget> | null) => {
      if (!entry || typeof entry.templateId !== "string" || typeof entry.title !== "string") return [];
      if (!widgetTemplates.some((t) => t.id === entry.templateId)) return [];
      return [
        {
          templateId: entry.templateId,
          title: entry.title,
          symbol: typeof entry.symbol === "string" ? entry.symbol : undefined,
          span: SPANS.includes(entry.span as number) ? (entry.span as WidgetSpan) : 3,
          height: entry.height === "compact" ? ("compact" as const) : ("tall" as const),
          minimized: entry.minimized === true,
          pinned: entry.pinned === true,
          takenAt: typeof entry.takenAt === "string" ? entry.takenAt : undefined,
        },
      ];
    });
  } catch {
    return null;
  }
}

function readSaved(): string | null {
  try {
    return window.localStorage.getItem(LAYOUT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeSaved(value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(LAYOUT_STORAGE_KEY);
    else window.localStorage.setItem(LAYOUT_STORAGE_KEY, value);
  } catch {
    /* Blocked storage only costs persistence; the grid keeps working. */
  }
}

/* Master Twin boot: hydrate the default monitoring layout as a sequence of MCP
   events so each widget spring-inserts into the auto-layout grid. */
function bootDefaultLayout(): ReturnType<typeof setTimeout>[] {
  return BOOT_LAYOUT.flatMap((entry, index) => {
    const tpl = widgetTemplates.find((t) => t.key === entry.key);
    if (!tpl) return [];
    const timer = setTimeout(() => {
      emitMcp("ui/hydrate_widget_template", "master-twin/boot", {
        templateKey: entry.key,
        title: entry.title ?? (tpl.defaultSymbol ? `${tpl.title} · ${tpl.defaultSymbol}` : tpl.title),
        symbol: tpl.defaultSymbol,
        span: entry.span ?? tpl.defaultSpan,
      });
    }, index * BOOT_STEP_MS);
    return [timer];
  });
}

/**
 * Bring the canvas up and keep the saved layout in step with it. A canvas that
 * already holds widgets (client-side navigation back to /ops) is left alone.
 * Returns the teardown for the page effect.
 */
export function startLayout(): () => void {
  let booting = false;
  let bootTimers: ReturnType<typeof setTimeout>[] = [];

  if (useGridStore.getState().widgets.length === 0) {
    const saved = parseLayout(readSaved());
    if (saved) {
      restoreWidgets(saved);
    } else {
      booting = true;
      bootTimers = bootDefaultLayout();
      bootTimers.push(setTimeout(() => (booting = false), BOOT_LAYOUT.length * BOOT_STEP_MS));
    }
  }

  let last = serializeLayout(useGridStore.getState().widgets);
  const unsubscribe = useGridStore.subscribe((state) => {
    if (booting) return;
    const next = serializeLayout(state.widgets);
    if (next === last) return;
    last = next;
    writeSaved(next);
  });

  return () => {
    bootTimers.forEach(clearTimeout);
    unsubscribe();
  };
}

/** Forget the saved arrangement and re-run the Master Twin boot. */
export function resetLayout() {
  useGridStore.setState({ widgets: [] });
  writeSaved(null);
  bootDefaultLayout();
}
