import React, { useState, useMemo } from 'react';
import { EquityCurvePoint } from '../types/terminal';
import { 
  AlertTriangle, 
  Flame, 
  TrendingDown, 
  Activity, 
  Eye, 
  Layers, 
  Clock, 
  ShieldAlert,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

interface EquityDrawdownHeatmapProps {
  equityCurve: EquityCurvePoint[];
  initialCapital?: number;
  symbol?: string;
  timeframe?: string;
  showShadowCurve?: boolean;
}

interface DrawdownEpisode {
  id: number;
  peakIdx: number;
  peakTime: number;
  peakEquity: number;
  troughIdx: number;
  troughTime: number;
  troughEquity: number;
  troughDrawdownPct: number;
  troughDrawdownUsd: number;
  recoveredIdx: number | null;
  recoveryTime: number | null;
  durationBars: number;
  isRecovered: boolean;
}

export const EquityDrawdownHeatmap: React.FC<EquityDrawdownHeatmapProps> = React.memo(({
  equityCurve,
  initialCapital = 1000,
  symbol = 'BTC/USDT',
  timeframe = '1h',
  showShadowCurve = false,
}) => {
  const [sensitivity, setSensitivity] = useState<'STANDARD' | 'STRICT' | 'DYNAMIC'>('STANDARD');
  const [showUnderwaterFill, setShowUnderwaterFill] = useState(true);
  const [showPeakLine, setShowPeakLine] = useState(true);
  const [showHeatBands, setShowHeatBands] = useState(true);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<number | null>(null);
  const [showEpisodesDrawer, setShowEpisodesDrawer] = useState(false);

  // Compute thresholds based on sensitivity mode
  const thresholds = useMemo(() => {
    if (!equityCurve.length) {
      return { low: 1.5, mod: 3.5, severe: 6.0 };
    }
    if (sensitivity === 'STRICT') {
      return { low: 1.0, mod: 2.5, severe: 4.5 };
    }
    if (sensitivity === 'DYNAMIC') {
      const dds = equityCurve.map((p) => p.drawdownPct).filter((d) => d > 0.05).sort((a, b) => a - b);
      if (dds.length < 5) return { low: 1.0, mod: 2.5, severe: 5.0 };
      const q50 = dds[Math.floor(dds.length * 0.5)] || 1.5;
      const q75 = dds[Math.floor(dds.length * 0.75)] || 3.0;
      const q90 = dds[Math.floor(dds.length * 0.9)] || 5.0;
      return { low: Number(q50.toFixed(2)), mod: Number(q75.toFixed(2)), severe: Number(q90.toFixed(2)) };
    }
    // STANDARD default
    return { low: 1.5, mod: 3.5, severe: 6.0 };
  }, [equityCurve, sensitivity]);

  // Compute Running High Water Mark (Peak) and Drawdown Data
  const { enrichedData, overallMaxDd, totalUnderwaterPct, avgDrawdown } = useMemo(() => {
    if (!equityCurve.length) {
      return { enrichedData: [], overallMaxDd: 0, totalUnderwaterPct: 0, avgDrawdown: 0 };
    }

    let runningPeak = initialCapital;
    let maxDd = 0;
    let underwaterCount = 0;
    let sumDd = 0;

    const enriched = equityCurve.map((pt, idx) => {
      if (pt.equity > runningPeak) {
        runningPeak = pt.equity;
      }
      const ddPct = runningPeak > 0 ? ((runningPeak - pt.equity) / runningPeak) * 100 : 0;
      const ddUsd = runningPeak - pt.equity;
      if (ddPct > maxDd) maxDd = ddPct;
      if (ddPct > 0.1) underwaterCount++;
      sumDd += ddPct;

      return {
        ...pt,
        idx,
        runningPeak,
        ddPctCalc: ddPct,
        ddUsdCalc: ddUsd,
      };
    });

    return {
      enrichedData: enriched,
      overallMaxDd: maxDd,
      totalUnderwaterPct: (underwaterCount / Math.max(equityCurve.length, 1)) * 100,
      avgDrawdown: sumDd / Math.max(equityCurve.length, 1),
    };
  }, [equityCurve, initialCapital]);

  // Detect Drawdown Episodes (Peak to Trough to Recovery)
  const episodes = useMemo<DrawdownEpisode[]>(() => {
    if (enrichedData.length < 2) return [];

    const detected: DrawdownEpisode[] = [];
    let currentEpisode: Partial<DrawdownEpisode> | null = null;
    let epCount = 0;

    for (let i = 0; i < enrichedData.length; i++) {
      const pt = enrichedData[i];
      const isUnder = pt.ddPctCalc >= 0.2; // at least 0.2% drawdown to qualify as episode

      if (isUnder) {
        if (!currentEpisode) {
          // Find peak index (last point at peak before this drop)
          const peakIdx = Math.max(0, i - 1);
          currentEpisode = {
            id: ++epCount,
            peakIdx,
            peakTime: enrichedData[peakIdx].time,
            peakEquity: enrichedData[peakIdx].equity,
            troughIdx: i,
            troughTime: pt.time,
            troughEquity: pt.equity,
            troughDrawdownPct: pt.ddPctCalc,
            troughDrawdownUsd: pt.ddUsdCalc,
            recoveredIdx: null,
            recoveryTime: null,
            isRecovered: false,
            durationBars: 1,
          };
        } else {
          // Update trough if deeper
          if (pt.ddPctCalc > (currentEpisode.troughDrawdownPct || 0)) {
            currentEpisode.troughIdx = i;
            currentEpisode.troughTime = pt.time;
            currentEpisode.troughEquity = pt.equity;
            currentEpisode.troughDrawdownPct = pt.ddPctCalc;
            currentEpisode.troughDrawdownUsd = pt.ddUsdCalc;
          }
          currentEpisode.durationBars = i - currentEpisode.peakIdx!;
        }
      } else if (currentEpisode) {
        // Recovered back to peak!
        currentEpisode.recoveredIdx = i;
        currentEpisode.recoveryTime = pt.time;
        currentEpisode.isRecovered = true;
        currentEpisode.durationBars = i - currentEpisode.peakIdx!;
        if ((currentEpisode.troughDrawdownPct || 0) >= 0.5) {
          detected.push(currentEpisode as DrawdownEpisode);
        }
        currentEpisode = null;
      }
    }

    if (currentEpisode && (currentEpisode.troughDrawdownPct || 0) >= 0.5) {
      currentEpisode.durationBars = enrichedData.length - 1 - currentEpisode.peakIdx!;
      detected.push(currentEpisode as DrawdownEpisode);
    }

    // Sort by largest drawdown percentage descending
    return detected.sort((a, b) => b.troughDrawdownPct - a.troughDrawdownPct);
  }, [enrichedData]);

  // Color mapping helper based on drawdown severity
  const getDrawdownColor = (ddPct: number, alpha = 1) => {
    if (ddPct < thresholds.low) {
      return `rgba(8, 153, 129, ${alpha * 0.15})`; // Normal / safe
    }
    if (ddPct < thresholds.mod) {
      return `rgba(245, 158, 11, ${alpha * 0.4})`; // Low DD (Amber)
    }
    if (ddPct < thresholds.severe) {
      return `rgba(249, 115, 22, ${alpha * 0.65})`; // Moderate DD (Orange)
    }
    // Severe DD (Crimson Flame)
    return `rgba(242, 54, 69, ${alpha * 0.85})`;
  };

  const getSeverityBadge = (ddPct: number) => {
    if (ddPct < thresholds.low) {
      return { text: 'GERING', color: 'text-[#089981] bg-[#089981]/10 border-[#089981]/30' };
    }
    if (ddPct < thresholds.mod) {
      return { text: 'MILD (WARNUNG)', color: 'text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/30' };
    }
    if (ddPct < thresholds.severe) {
      return { text: 'ERHÖHT (VOLATIL)', color: 'text-[#F97316] bg-[#F97316]/10 border-[#F97316]/30' };
    }
    return { text: 'KRITISCHER DRAWDOWN', color: 'text-[#F23645] bg-[#F23645]/20 border-[#F23645]/40 animate-pulse' };
  };

  if (!enrichedData.length) {
    return (
      <div className="bg-[#07090E] border border-[#1B2230] p-4 text-center text-xs text-[#8B95A5]">
        Keine Equity-Kurvendaten verfügbar. Führe einen Backtest aus, um die Drawdown-Heatmap zu visualisieren.
      </div>
    );
  }

  // Dimensions for Chart
  const W = 900;
  const H = 220;
  const PAD_L = 10;
  const PAD_R = 64;
  const PAD_T = 16;
  const PAD_B = 26;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  // Min and Max for Equity
  let minEquity = initialCapital;
  let maxEquity = initialCapital;
  for (const p of enrichedData) {
    minEquity = Math.min(minEquity, p.equity);
    maxEquity = Math.max(maxEquity, p.equity, p.runningPeak);
    if (showShadowCurve && p.shadowEquity) {
      minEquity = Math.min(minEquity, p.shadowEquity);
      maxEquity = Math.max(maxEquity, p.shadowEquity);
    }
  }
  const equityMargin = Math.max((maxEquity - minEquity) * 0.12, initialCapital * 0.03);
  const eqMinBounded = minEquity - equityMargin;
  const eqMaxBounded = maxEquity + equityMargin;
  const eqRange = Math.max(eqMaxBounded - eqMinBounded, 0.001);

  const xForIdx = (idx: number) => {
    if (enrichedData.length <= 1) return PAD_L;
    return PAD_L + (idx / (enrichedData.length - 1)) * plotW;
  };

  const yForEquity = (val: number) => {
    return PAD_T + (1 - (val - eqMinBounded) / eqRange) * plotH;
  };

  // Build SVG Path for Equity Line
  const equityPointsStr = enrichedData
    .map((pt, i) => `${xForIdx(i).toFixed(1)},${yForEquity(pt.equity).toFixed(1)}`)
    .join(' ');

  // Build SVG Path for Running High Water Mark (Peak)
  const peakPointsStr = enrichedData
    .map((pt, i) => `${xForIdx(i).toFixed(1)},${yForEquity(pt.runningPeak).toFixed(1)}`)
    .join(' ');

  // Build SVG Path for Shadow Inverse Equity (if enabled)
  const shadowPointsStr = showShadowCurve
    ? enrichedData
        .map((pt, i) => `${xForIdx(i).toFixed(1)},${yForEquity(pt.shadowEquity).toFixed(1)}`)
        .join(' ')
    : '';

  // Build Underwater Polygon: Top is Peak, Bottom is Equity
  const underwaterPath = useMemo(() => {
    if (!showUnderwaterFill || enrichedData.length < 2) return '';
    // Forward along peak line
    let path = `M ${xForIdx(0).toFixed(1)},${yForEquity(enrichedData[0].runningPeak).toFixed(1)}`;
    for (let i = 1; i < enrichedData.length; i++) {
      path += ` L ${xForIdx(i).toFixed(1)},${yForEquity(enrichedData[i].runningPeak).toFixed(1)}`;
    }
    // Backward along equity line
    for (let i = enrichedData.length - 1; i >= 0; i--) {
      path += ` L ${xForIdx(i).toFixed(1)},${yForEquity(enrichedData[i].equity).toFixed(1)}`;
    }
    path += ' Z';
    return path;
  }, [enrichedData, showUnderwaterFill, eqMinBounded, eqRange]);

  // Selected or Hovered Point
  const activePt = hoveredIdx !== null && enrichedData[hoveredIdx] ? enrichedData[hoveredIdx] : enrichedData[enrichedData.length - 1];
  const severityBadge = getSeverityBadge(activePt.ddPctCalc);

  return (
    <div className="bg-[#07090E] border border-[#1B2230] rounded-none p-3 space-y-2.5 font-mono select-none">
      {/* Header Bar with Telemetry, Volatility Risk Badge, and Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1B2230] pb-2">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-[#00E5FF] font-bold text-xs uppercase tracking-wider">
            <Flame className="w-3.5 h-3.5 text-[#F23645]" />
            <span>EQUITY DRAWDOWN HEATMAP</span>
          </div>
          <span className="text-[10px] text-[#8B95A5] px-1.5 py-0.5 bg-[#0C1017] border border-[#1B2230]">
            {symbol} · {timeframe}
          </span>
          <div className={`text-[10px] font-bold px-2 py-0.5 border ${severityBadge.color}`}>
            STATUS: {severityBadge.text} (-{activePt.ddPctCalc.toFixed(2)}%)
          </div>
        </div>

        {/* Action Controls & Sensitivity Toggles */}
        <div className="flex items-center gap-2">
          {/* Sensitivity Preset */}
          <div className="flex items-center bg-[#0C1017] border border-[#1B2230] p-0.5 text-[10px]">
            <span className="text-[#8B95A5] px-1.5 text-[9px]">SENSITIVITÄT:</span>
            {(['STANDARD', 'STRICT', 'DYNAMIC'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setSensitivity(mode)}
                className={`px-1.5 py-0.5 uppercase transition-colors ${
                  sensitivity === mode
                    ? 'bg-[#1B2230] text-[#00E5FF] font-bold'
                    : 'text-[#8B95A5] hover:text-[#E6EDF3]'
                }`}
              >
                {mode === 'DYNAMIC' ? 'DYN (Q90)' : mode}
              </button>
            ))}
          </div>

          {/* Toggle Heat Bands */}
          <button
            type="button"
            onClick={() => setShowHeatBands((prev) => !prev)}
            className={`flex items-center gap-1 px-1.5 py-0.5 text-[10px] border transition-colors ${
              showHeatBands
                ? 'bg-[#F23645]/15 border-[#F23645]/40 text-[#F23645]'
                : 'bg-[#0C1017] border-[#1B2230] text-[#8B95A5]'
            }`}
            title="Schattiert vertikale Hitze-Zonen im Hintergrund"
          >
            <Layers className="w-2.5 h-2.5" />
            <span>HITZE-BÄNDER</span>
          </button>

          {/* Toggle Underwater Fill */}
          <button
            type="button"
            onClick={() => setShowUnderwaterFill((prev) => !prev)}
            className={`flex items-center gap-1 px-1.5 py-0.5 text-[10px] border transition-colors ${
              showUnderwaterFill
                ? 'bg-[#00E5FF]/15 border-[#00E5FF]/40 text-[#00E5FF]'
                : 'bg-[#0C1017] border-[#1B2230] text-[#8B95A5]'
            }`}
            title="Schattiert den Bereich zwischen High-Water-Mark und Equity"
          >
            <TrendingDown className="w-2.5 h-2.5" />
            <span>UNDERWATER-ZONE</span>
          </button>

          {/* Toggle Episodes Table */}
          <button
            type="button"
            onClick={() => setShowEpisodesDrawer((prev) => !prev)}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] bg-[#0C1017] border border-[#1B2230] hover:border-[#00E5FF]/50 text-[#E6EDF3]"
          >
            <ShieldAlert className="w-2.5 h-2.5 text-[#F59E0B]" />
            <span>EPISODEN ({episodes.length})</span>
            {showEpisodesDrawer ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
          </button>
        </div>
      </div>

      {/* Primary SVG Heatmap Chart */}
      <div className="relative w-full overflow-hidden bg-[#05070B] border border-[#141A24]">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto block select-none"
          onMouseLeave={() => setHoveredIdx(null)}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const svgX = (mouseX / rect.width) * W;
            const relativeX = Math.max(0, Math.min(plotW, svgX - PAD_L));
            const calculatedIdx = Math.round((relativeX / plotW) * (enrichedData.length - 1));
            if (calculatedIdx >= 0 && calculatedIdx < enrichedData.length) {
              setHoveredIdx(calculatedIdx);
            }
          }}
        >
          <defs>
            {/* Underwater Depth Gradient (Peak to Equity) */}
            <linearGradient id="underwaterGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F23645" stopOpacity="0.32" />
              <stop offset="60%" stopColor="#F97316" stopOpacity="0.16" />
              <stop offset="100%" stopColor="#F23645" stopOpacity="0.04" />
            </linearGradient>

            {/* Severe Heat Glow */}
            <linearGradient id="severeGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F23645" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#F23645" stopOpacity="0.08" />
            </linearGradient>
          </defs>

          {/* Background Grid Lines (Equity Values) */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const val = eqMinBounded + pct * eqRange;
            const y = yForEquity(val);
            return (
              <g key={i}>
                <line
                  x1={PAD_L}
                  y1={y}
                  x2={W - PAD_R}
                  y2={y}
                  stroke="#121722"
                  strokeDasharray="2 2"
                />
                <text
                  x={W - PAD_R + 6}
                  y={y + 3}
                  fill="#566173"
                  fontSize="8"
                  fontFamily="JetBrains Mono, monospace"
                >
                  ${val.toFixed(0)}
                </text>
              </g>
            );
          })}

          {/* Initial Capital Reference Line ($1,000) */}
          <line
            x1={PAD_L}
            y1={yForEquity(initialCapital)}
            x2={W - PAD_R}
            y2={yForEquity(initialCapital)}
            stroke="#3B4252"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
          <text
            x={W - PAD_R + 6}
            y={yForEquity(initialCapital) - 3}
            fill="#8B95A5"
            fontSize="8"
            fontFamily="JetBrains Mono, monospace"
          >
            BASE $1K
          </text>

          {/* 1. VERTICAL HEATMAP BANDS (Colored columns based on drawdown severity) */}
          {showHeatBands &&
            enrichedData.map((pt, i) => {
              if (pt.ddPctCalc < thresholds.low) return null; // do not crowd low/zero drawdown
              const xLeft = i === 0 ? PAD_L : (xForIdx(i - 1) + xForIdx(i)) / 2;
              const xRight = i === enrichedData.length - 1 ? PAD_L + plotW : (xForIdx(i) + xForIdx(i + 1)) / 2;
              const width = Math.max(1.2, xRight - xLeft);

              // Color based on severity
              let fillColor = 'rgba(245, 158, 11, 0.16)'; // Low DD (Amber)
              if (pt.ddPctCalc >= thresholds.severe) {
                fillColor = 'rgba(242, 54, 69, 0.38)'; // Severe DD (Red Heat)
              } else if (pt.ddPctCalc >= thresholds.mod) {
                fillColor = 'rgba(249, 115, 22, 0.26)'; // Moderate DD (Orange)
              }

              return (
                <rect
                  key={`band-${i}`}
                  x={xLeft}
                  y={PAD_T}
                  width={width}
                  height={plotH}
                  fill={fillColor}
                  className="transition-opacity duration-150"
                />
              );
            })}

          {/* 2. UNDERWATER AREA FILL (Between High Water Mark and Equity) */}
          {showUnderwaterFill && underwaterPath && (
            <path d={underwaterPath} fill="url(#underwaterGrad)" />
          )}

          {/* 3. RUNNING HIGH WATER MARK (Peak Equity) */}
          {showPeakLine && (
            <polyline
              fill="none"
              stroke="#00E5FF"
              strokeWidth="1.2"
              strokeDasharray="3 2"
              strokeOpacity="0.7"
              points={peakPointsStr}
            />
          )}

          {/* 4. SHADOW INVERSE ENGINE CURVE (Counter-strategy) */}
          {showShadowCurve && shadowPointsStr && (
            <polyline
              fill="none"
              stroke="#A855F7"
              strokeWidth="1.2"
              strokeDasharray="2 2"
              strokeOpacity="0.8"
              points={shadowPointsStr}
            />
          )}

          {/* 5. PRIMARY EQUITY CURVE */}
          <polyline
            fill="none"
            stroke="#089981"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={equityPointsStr}
          />

          {/* 6. HIGHLIGHTED DRAWDOWN EPISODE (If selected from drawer) */}
          {selectedEpisodeId !== null && (() => {
            const ep = episodes.find((e) => e.id === selectedEpisodeId);
            if (!ep) return null;
            const x1 = xForIdx(ep.peakIdx);
            const x2 = xForIdx(ep.recoveredIdx ?? enrichedData.length - 1);
            return (
              <g>
                <rect
                  x={x1}
                  y={PAD_T}
                  width={Math.max(x2 - x1, 4)}
                  height={plotH}
                  fill="rgba(242, 54, 69, 0.22)"
                  stroke="#F23645"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
                {/* Trough Marker */}
                <circle
                  cx={xForIdx(ep.troughIdx)}
                  cy={yForEquity(ep.troughEquity)}
                  r="4"
                  fill="#F23645"
                  stroke="#FFFFFF"
                  strokeWidth="1.5"
                />
              </g>
            );
          })()}

          {/* 7. HOVER CROSSHAIR & DATA POINT MARKERS */}
          {hoveredIdx !== null && (
            <g>
              <line
                x1={xForIdx(hoveredIdx)}
                y1={PAD_T}
                x2={xForIdx(hoveredIdx)}
                y2={PAD_T + plotH}
                stroke="#E6EDF3"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              {/* Point on Equity Line */}
              <circle
                cx={xForIdx(hoveredIdx)}
                cy={yForEquity(activePt.equity)}
                r="4"
                fill="#089981"
                stroke="#E6EDF3"
                strokeWidth="1.5"
              />
              {/* Point on Peak Line */}
              {showPeakLine && (
                <circle
                  cx={xForIdx(hoveredIdx)}
                  cy={yForEquity(activePt.runningPeak)}
                  r="3"
                  fill="#00E5FF"
                />
              )}
            </g>
          )}
        </svg>

        {/* Floating Telemetry Tooltip on Hover */}
        {hoveredIdx !== null && (
          <div
            className="absolute top-2 pointer-events-none bg-[#0C1017]/95 border border-[#1B2230] p-2 text-[10px] space-y-0.5 shadow-xl backdrop-blur-sm z-20"
            style={{
              left: Math.min(Math.max(12, (xForIdx(hoveredIdx) / W) * 100), 75) + '%',
            }}
          >
            <div className="flex justify-between gap-4 text-[#8B95A5] border-b border-[#1B2230] pb-1 font-bold">
              <span>BAR #{activePt.idx + 1}</span>
              <span className="text-[#E6EDF3]">{new Date(activePt.time).toLocaleTimeString()}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-[#8B95A5]">Equity:</span>
              <span className="font-bold text-[#E6EDF3]">${activePt.equity.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-[#8B95A5]">High Water Mark:</span>
              <span className="text-[#00E5FF]">${activePt.runningPeak.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-[#8B95A5]">Drawdown:</span>
              <span
                className={`font-bold ${
                  activePt.ddPctCalc >= thresholds.severe
                    ? 'text-[#F23645]'
                    : activePt.ddPctCalc >= thresholds.mod
                    ? 'text-[#F97316]'
                    : activePt.ddPctCalc >= thresholds.low
                    ? 'text-[#F59E0B]'
                    : 'text-[#089981]'
                }`}
              >
                -{activePt.ddPctCalc.toFixed(2)}% (-${activePt.ddUsdCalc.toFixed(2)})
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-[#8B95A5]">Offene Trades:</span>
              <span className="text-[#E6EDF3]">{activePt.openTradesCount ?? 0}</span>
            </div>
          </div>
        )}
      </div>

      {/* CONTINUOUS DRAWDOWN HEATMAP RIBBON (Micro Timeline Bar) */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[9px] text-[#8B95A5]">
          <span className="flex items-center gap-1">
            <Activity className="w-2.5 h-2.5 text-[#00E5FF]" />
            <span>DRAWDOWN INTENSITÄTS-TIMELINE (ALLE BALKEN)</span>
          </span>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-xs bg-[#089981]" />
              <span>&lt;{thresholds.low}% Peak</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-xs bg-[#F59E0B]" />
              <span>{thresholds.low}-{thresholds.mod}% Mild</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-xs bg-[#F97316]" />
              <span>{thresholds.mod}-{thresholds.severe}% Mod</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-xs bg-[#F23645] animate-pulse" />
              <span>&gt;{thresholds.severe}% Severe DD</span>
            </span>
          </div>
        </div>

        {/* Heatmap Ribbon Strip */}
        <div className="h-2.5 w-full bg-[#0C1017] border border-[#141A24] flex overflow-hidden">
          {enrichedData.map((pt, i) => {
            let color = '#089981'; // Peak/Safe
            if (pt.ddPctCalc >= thresholds.severe) {
              color = '#F23645';
            } else if (pt.ddPctCalc >= thresholds.mod) {
              color = '#F97316';
            } else if (pt.ddPctCalc >= thresholds.low) {
              color = '#F59E0B';
            }
            return (
              <div
                key={`ribbon-${i}`}
                style={{ backgroundColor: color, flex: 1 }}
                className={`h-full cursor-pointer hover:opacity-80 transition-opacity ${
                  hoveredIdx === i ? 'ring-1 ring-white' : ''
                }`}
                onMouseEnter={() => setHoveredIdx(i)}
                title={`Bar #${i + 1} | DD: -${pt.ddPctCalc.toFixed(2)}% ($${pt.equity.toFixed(2)})`}
              />
            );
          })}
        </div>
      </div>

      {/* QUICK SUMMARY TELEMETRY GRID */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 text-[11px] font-mono tabular-nums">
        <div className="bg-[#0C1017] border border-[#1B2230] p-1.5 flex flex-col justify-between">
          <span className="text-[9px] text-[#8B95A5]">MAX DRAWDOWN (HISTORISCH)</span>
          <span className="text-[#F23645] font-bold text-xs">
            -{overallMaxDd.toFixed(2)}%
          </span>
        </div>
        <div className="bg-[#0C1017] border border-[#1B2230] p-1.5 flex flex-col justify-between">
          <span className="text-[9px] text-[#8B95A5]">DURCHSCHN. DRAWDOWN</span>
          <span className="text-[#F59E0B] font-bold text-xs">
            -{avgDrawdown.toFixed(2)}%
          </span>
        </div>
        <div className="bg-[#0C1017] border border-[#1B2230] p-1.5 flex flex-col justify-between">
          <span className="text-[9px] text-[#8B95A5]">ZEIT UNTERWASSER (% DER BALKEN)</span>
          <span className="text-[#00E5FF] font-bold text-xs">
            {totalUnderwaterPct.toFixed(1)}%
          </span>
        </div>
        <div className="bg-[#0C1017] border border-[#1B2230] p-1.5 flex flex-col justify-between">
          <span className="text-[9px] text-[#8B95A5]">IDENTIFIZIERTE DRAWDOWN-EPISODEN</span>
          <span className="text-[#E6EDF3] font-bold text-xs">
            {episodes.length} Phasen ({episodes.filter((e) => !e.isRecovered).length} aktiv)
          </span>
        </div>
      </div>

      {/* EXPANDABLE DRAWDOWN EPISODES DRAWER */}
      {showEpisodesDrawer && (
        <div className="border border-[#1B2230] bg-[#0A0D14] p-2 space-y-2 text-[10px]">
          <div className="flex items-center justify-between border-b border-[#1B2230] pb-1">
            <span className="font-bold text-[#E6EDF3] uppercase flex items-center gap-1.5">
              <ShieldAlert className="w-3 h-3 text-[#F23645]" />
              <span>TOP DRAWDOWN-PHASEN & VOLATILITÄTS-ANALYSE (PEAK-TO-TROUGH)</span>
            </span>
            <span className="text-[9px] text-[#8B95A5]">
              Klicke eine Zeile, um die Zone auf der Heatmap zu isolieren
            </span>
          </div>

          {episodes.length === 0 ? (
            <div className="py-2 text-center text-[#8B95A5]">
              Keine signifikanten Drawdown-Episoden (&gt;0.5%) in diesem Zeitraum aufgezeichnet.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-36 overflow-y-auto">
              <table className="w-full text-left border-collapse tabular-nums">
                <thead className="text-[8px] text-[#8B95A5] uppercase border-b border-[#1B2230]">
                  <tr>
                    <th className="py-1">#</th>
                    <th className="py-1">Peak Equity</th>
                    <th className="py-1">Tiefpunkt (Trough)</th>
                    <th className="py-1">Max Verlust</th>
                    <th className="py-1">Dauer (Bars)</th>
                    <th className="py-1">Erholung</th>
                    <th className="py-1 text-right">Aktion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#141A24]">
                  {episodes.slice(0, 6).map((ep) => {
                    const isSelected = selectedEpisodeId === ep.id;
                    return (
                      <tr
                        key={ep.id}
                        onClick={() => setSelectedEpisodeId(isSelected ? null : ep.id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-[#F23645]/20 text-[#FFFFFF]'
                            : 'hover:bg-[#141A24] text-[#E2E8F0]'
                        }`}
                      >
                        <td className="py-1 font-bold">#{ep.id}</td>
                        <td className="py-1 text-[#00E5FF]">${ep.peakEquity.toFixed(2)}</td>
                        <td className="py-1 text-[#E6EDF3]">${ep.troughEquity.toFixed(2)}</td>
                        <td className="py-1 text-[#F23645] font-bold">
                          -{ep.troughDrawdownPct.toFixed(2)}% (-${ep.troughDrawdownUsd.toFixed(2)})
                        </td>
                        <td className="py-1 text-[#8B95A5]">{ep.durationBars} Bars</td>
                        <td className="py-1">
                          {ep.isRecovered ? (
                            <span className="text-[#089981] font-semibold">Erholt</span>
                          ) : (
                            <span className="text-[#F23645] font-semibold animate-pulse">Aktiv</span>
                          )}
                        </td>
                        <td className="py-1 text-right">
                          <button
                            type="button"
                            className="px-1.5 py-0.5 text-[8px] border border-[#1B2230] hover:border-[#00E5FF] text-[#00E5FF]"
                          >
                            {isSelected ? 'RESET' : 'ZEIGEN'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
