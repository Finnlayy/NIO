import type { ComponentType } from "react";
import type { WidgetInstance } from "../types";
import { widgetTemplates } from "../widgetRegistry";
import { MarketBreadthRadar } from "./MarketBreadthRadar";
import { EnvelopeChart } from "./EnvelopeChart";
import { PatternScanner } from "./PatternScanner";
import { NewsSentiment } from "./NewsSentiment";
import { LimbMesh } from "./LimbMesh";
import { CvdHeatmap } from "./CvdHeatmap";
import { TradePlan } from "./TradePlan";
import { KeyLevelsTable } from "./KeyLevelsTable";
import { TechnicalGauge } from "./TechnicalGauge";
import { CompositeRankings } from "./CompositeRankings";

type Renderer = ComponentType<{ data: Record<string, unknown>; symbol?: string }>;

const renderers: Record<string, Renderer> = {
  "market-breadth-radar": MarketBreadthRadar,
  "quantum-envelope-chart": EnvelopeChart,
  "gpm-incubation-arena": PatternScanner,
  "macro-catalyst-timeline": NewsSentiment,
  "limb-mindmap-node": LimbMesh,
  "orderflow-cvd-heatmap": CvdHeatmap,
  "vault-earn-arbitrage": TradePlan,
  "custom-dynamic-table": KeyLevelsTable,
  "technical-signal-gauge": TechnicalGauge,
  "composite-score-ranking": CompositeRankings,
};

const keyById = Object.fromEntries(widgetTemplates.map((t) => [t.id, t.key]));

export function renderWidget(widget: WidgetInstance) {
  const Cmp = renderers[keyById[widget.templateId] ?? widget.templateId];
  if (!Cmp) {
    return (
      <p className="text-[12px] text-slate-500 p-2">
        Unknown template <code>{widget.templateId}</code> — awaiting renderer registration.
      </p>
    );
  }
  return <Cmp data={widget.data} symbol={widget.symbol} />;
}
