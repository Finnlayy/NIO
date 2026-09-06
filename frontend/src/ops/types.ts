/* ================================================================== */
/* MCP hydration protocol — declarative widget blueprints               */
/* ================================================================== */

export type WidgetSpan = 2 | 3 | 4 | 6;
export type WidgetHeight = "compact" | "tall";

/**
 * A WidgetTemplate is a *declarative blueprint*: a JSON-serializable
 * descriptor the NIO Master Twin can dispatch over MCP to materialize a
 * widget. No component references live here — the renderer resolves
 * `componentKey` at hydration time.
 */
export interface WidgetTemplate {
  id: `TPL_${string}`;
  key: string;
  title: string;
  tagline: string;
  category: "Market" | "Execution" | "System" | "Data";
  defaultSymbol?: string;
  defaultSpan: WidgetSpan;
  defaultHeight: WidgetHeight;
  dataFactory: () => Record<string, unknown>;
}

export interface WidgetInstance {
  id: string;
  templateId: WidgetTemplate["id"];
  title: string;
  symbol?: string;
  span: WidgetSpan;
  height: WidgetHeight;
  minimized: boolean;
  pinned: boolean;
  data: Record<string, unknown>;
}

/* JSON-RPC-ish envelope for MCP orchestrator -> UI events */
export interface McpHydrateParams {
  templateKey: WidgetTemplate["key"];
  instanceId?: string;
  title?: string;
  symbol?: string;
  span?: WidgetSpan;
  data?: Record<string, unknown>;
}

export interface McpEvent {
  id: number;
  timestamp: string;
  method: "ui/hydrate_widget_template" | "ui/update_widget_state" | "ui/remove_widget";
  source: string;
  params: Record<string, unknown>;
}
