import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ReferenceLine,
  LabelList,
} from 'recharts';
import {
  TrendingUp,
  Award,
  Zap,
  ArrowUpDown,
  Layers,
  Sparkles,
  BarChart3,
  ShieldCheck,
} from 'lucide-react';
import { StrategyAgent, RawSignal } from '../types/trading';
import { AnimatedNumber, AnimatedPercent } from './AnimatedNumber';

interface StrategyAlphaChartProps {
  strategies: StrategyAgent[];
  signals: RawSignal[];
}

interface StrategyAlphaMetric {
  id: string;
  name: string;
  shortName: string;
  type: string;
  avgAlphaBps: number;
  minAlphaBps: number;
  maxAlphaBps: number;
  signalCount: number;
  shareOfSignalsPct: number;
  winRate: number;
  sharpeRatio: number;
  weight: number;
  isTopPerformer: boolean;
  alphaVsSwarmBps: number;
}

export const StrategyAlphaChart: React.FC<StrategyAlphaChartProps> = ({
  strategies,
  signals,
}) => {
  const [sortMode, setSortMode] = useState<'alpha_desc' | 'allocation' | 'sharpe'>('alpha_desc');

  // Compute average expectedAlphaBps and stats per strategy
  const { strategyMetrics, swarmAvgAlpha, topPerformer } = useMemo(() => {
    const totalSignals = signals.length;
    const swarmTotalAlpha = signals.reduce((acc, s) => acc + s.expectedAlphaBps, 0);
    const swarmAvg = totalSignals > 0 ? Math.round((swarmTotalAlpha / totalSignals) * 10) / 10 : 0;

    // Aggregate by strategy
    const rawMetrics: StrategyAlphaMetric[] = strategies.map((strat) => {
      const stratSignals = signals.filter((s) => s.strategyId === strat.id);
      const count = stratSignals.length;

      let avgAlpha = 0;
      let minAlpha = 0;
      let maxAlpha = 0;

      if (count > 0) {
        const sumAlpha = stratSignals.reduce((acc, s) => acc + s.expectedAlphaBps, 0);
        avgAlpha = Math.round((sumAlpha / count) * 10) / 10;
        minAlpha = Math.round(Math.min(...stratSignals.map((s) => s.expectedAlphaBps)) * 10) / 10;
        maxAlpha = Math.round(Math.max(...stratSignals.map((s) => s.expectedAlphaBps)) * 10) / 10;
      }

      // Compact display name
      const shortName = strat.name.split('(')[0].trim();

      return {
        id: strat.id,
        name: strat.name,
        shortName,
        type: strat.type,
        avgAlphaBps: avgAlpha,
        minAlphaBps: minAlpha,
        maxAlphaBps: maxAlpha,
        signalCount: count,
        shareOfSignalsPct: totalSignals > 0 ? Math.round((count / totalSignals) * 100) : 0,
        winRate: strat.winRate,
        sharpeRatio: strat.sharpeRatio,
        weight: strat.weight,
        isTopPerformer: false,
        alphaVsSwarmBps: Math.round((avgAlpha - swarmAvg) * 10) / 10,
      };
    });

    // Determine top performer by average alpha
    const highestAlpha = Math.max(...rawMetrics.map((m) => m.avgAlphaBps), 0);
    rawMetrics.forEach((m) => {
      if (m.avgAlphaBps === highestAlpha && highestAlpha > 0) {
        m.isTopPerformer = true;
      }
    });

    const top = rawMetrics.find((m) => m.isTopPerformer) || rawMetrics[0];

    // Sort according to selected sort mode
    const sorted = [...rawMetrics].sort((a, b) => {
      if (sortMode === 'alpha_desc') {
        return b.avgAlphaBps - a.avgAlphaBps;
      }
      if (sortMode === 'sharpe') {
        return b.sharpeRatio - a.sharpeRatio;
      }
      return b.weight - a.weight;
    });

    return {
      strategyMetrics: sorted,
      swarmAvgAlpha: swarmAvg,
      topPerformer: top,
    };
  }, [strategies, signals, sortMode]);

  // Color palette based on alpha ranking & status
  const getBarColor = (item: StrategyAlphaMetric) => {
    if (item.isTopPerformer) {
      return '#10b981'; // Vibrant Emerald for #1 Top Generator
    }
    if (item.avgAlphaBps >= swarmAvgAlpha) {
      return '#38bdf8'; // Sky Blue for above-average alpha
    }
    if (item.avgAlphaBps > 0) {
      return '#818cf8'; // Indigo for baseline positive alpha
    }
    return '#475569'; // Slate for inactive/pending
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider">
                Average Expected Alpha per Strategy
              </h3>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 font-semibold">
                BASIS POINTS (BPS)
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono">
              Comparative alpha expectancy to identify the most performant signal generators
            </p>
          </div>
        </div>

        {/* Sort / View controls */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-md border border-slate-800 text-xs font-mono">
          <span className="text-[10px] text-slate-500 px-1.5 flex items-center gap-1">
            <ArrowUpDown className="w-3 h-3" />
            Sort:
          </span>
          <button
            type="button"
            onClick={() => setSortMode('alpha_desc')}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              sortMode === 'alpha_desc'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Highest Alpha
          </button>
          <button
            type="button"
            onClick={() => setSortMode('sharpe')}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              sortMode === 'sharpe'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sharpe Ratio
          </button>
          <button
            type="button"
            onClick={() => setSortMode('allocation')}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              sortMode === 'allocation'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Portfolio Weight
          </button>
        </div>
      </div>

      {/* Top Generator Callout Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 font-mono text-xs">
        {/* Top Performer Card */}
        <div className="bg-slate-950 p-2.5 rounded border border-emerald-500/30 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <Award className="w-3 h-3 text-emerald-400" />
              TOP ALPHA GENERATOR
            </div>
            <div className="text-xs font-bold text-slate-100 mt-0.5 truncate max-w-[170px]" title={topPerformer?.name}>
              {topPerformer?.shortName || 'None'}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Type: <span className="text-slate-200">{topPerformer?.type}</span>
            </div>
          </div>
          <div className="text-right pl-2 tabular-nums">
            <div className="text-sm font-bold text-emerald-400">
              <AnimatedNumber value={topPerformer?.avgAlphaBps || 0} precision={1} showSign={true} suffix=" bps" />
            </div>
            <div className="text-[10px] text-emerald-500/80">
              SR <AnimatedNumber value={topPerformer?.sharpeRatio || 0} precision={2} />
            </div>
          </div>
        </div>

        {/* Swarm Benchmark Average */}
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-400" />
              SWARM BENCHMARK MEAN
            </div>
            <div className="text-sm font-bold text-amber-400 mt-0.5 tabular-nums">
              <AnimatedNumber value={swarmAvgAlpha} precision={1} showSign={true} suffix=" bps" />
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Sample: <AnimatedNumber value={signals.length} precision={0} /> live signals
            </div>
          </div>
          <div className="text-right text-[10px] text-slate-400 tabular-nums">
            <div>Alpha Spread:</div>
            <div className="font-bold text-slate-200">
              <AnimatedNumber
                value={Math.max(0, (topPerformer?.avgAlphaBps || 0) - Math.min(...strategyMetrics.map(s => s.avgAlphaBps)))}
                precision={1}
                showSign={true}
                suffix=" bps"
              />
            </div>
          </div>
        </div>

        {/* High Conviction Share */}
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Layers className="w-3 h-3 text-sky-400" />
              ABOVE SWARM MEAN
            </div>
            <div className="text-sm font-bold text-sky-400 mt-0.5 tabular-nums">
              <AnimatedNumber value={strategyMetrics.filter(s => s.avgAlphaBps >= swarmAvgAlpha).length} precision={0} /> of {strategies.length}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5 tabular-nums">
              <AnimatedPercent
                value={strategies.length > 0 ? (strategyMetrics.filter(s => s.avgAlphaBps >= swarmAvgAlpha).length / strategies.length) * 100 : 0}
                precision={0}
                showSign={false}
              /> outperforming
            </div>
          </div>
          <div className="text-right text-[10px] text-slate-400 tabular-nums">
            <div>Allocation:</div>
            <div className="font-bold text-slate-200">
              <AnimatedPercent
                value={strategyMetrics.filter(s => s.avgAlphaBps >= swarmAvgAlpha).reduce((acc, s) => acc + s.weight, 0) * 100}
                precision={0}
                showSign={false}
              /> cap
            </div>
          </div>
        </div>

        {/* Signals Cadence / Activity */}
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Zap className="w-3 h-3 text-emerald-400" />
              ACTIVE GENERATORS
            </div>
            <div className="text-sm font-bold text-emerald-400 mt-0.5 tabular-nums">
              <AnimatedNumber value={strategyMetrics.filter(s => s.signalCount > 0).length} precision={0} /> / {strategies.length} Active
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Continuous L2 telemetry
            </div>
          </div>
          <div className="text-right text-[10px] text-slate-400 tabular-nums">
            <div>Buffer Depth:</div>
            <div className="font-bold text-slate-200">
              <AnimatedNumber value={signals.length} precision={0} suffix=" ticks" />
            </div>
          </div>
        </div>
      </div>

      {/* Main Bar Chart Container */}
      <div className="h-64 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={strategyMetrics}
            margin={{ top: 20, right: 30, left: 0, bottom: 25 }}
          >
            <defs>
              <linearGradient id="topAlphaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#059669" stopOpacity={0.7} />
              </linearGradient>
              <linearGradient id="aboveAvgGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#0284c7" stopOpacity={0.7} />
              </linearGradient>
              <linearGradient id="standardGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#818cf8" stopOpacity={0.8} />
                <stop offset="100%" stopColor="#4f46e5" stopOpacity={0.6} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

            <XAxis
              dataKey="shortName"
              stroke="#64748b"
              interval={0}
              tick={({ x, y, payload }) => {
                const item = strategyMetrics.find((m) => m.shortName === payload.value);
                const isTop = item?.isTopPerformer;
                return (
                  <g transform={`translate(${x},${y})`}>
                    <text
                      x={0}
                      y={0}
                      dy={14}
                      textAnchor="middle"
                      fill={isTop ? '#34d399' : '#94a3b8'}
                      fontSize={11}
                      fontFamily="monospace"
                      fontWeight={isTop ? 'bold' : 'normal'}
                    >
                      {payload.value}
                    </text>
                    {isTop && (
                      <text
                        x={0}
                        y={0}
                        dy={26}
                        textAnchor="middle"
                        fill="#10b981"
                        fontSize={9}
                        fontFamily="monospace"
                        fontWeight="bold"
                      >
                        ★ TOP
                      </text>
                    )}
                  </g>
                );
              }}
              tickLine={{ stroke: '#334155' }}
              axisLine={{ stroke: '#334155' }}
            />

            <YAxis
              stroke="#64748b"
              domain={[0, (dataMax: number) => Math.max(25, Math.ceil(dataMax * 1.25))]}
              tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
              tickFormatter={(v) => `+${v} bps`}
              tickLine={{ stroke: '#334155' }}
              axisLine={{ stroke: '#334155' }}
              label={{
                value: 'Expected Alpha (bps)',
                angle: -90,
                position: 'insideLeft',
                offset: 15,
                fill: '#94a3b8',
                fontSize: 10,
                fontFamily: 'monospace',
              }}
            />

            {/* Reference Line for Swarm Average */}
            {swarmAvgAlpha > 0 && (
              <ReferenceLine
                y={swarmAvgAlpha}
                stroke="#f59e0b"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{
                  value: `Swarm Mean: +${swarmAvgAlpha} bps`,
                  fill: '#f59e0b',
                  fontSize: 10,
                  position: 'top',
                  fontFamily: 'monospace',
                }}
              />
            )}

            <Tooltip
              cursor={{ fill: 'rgba(255, 255, 255, 0.04)' }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const data = payload[0]?.payload as StrategyAlphaMetric;
                if (!data) return null;

                return (
                  <div className="bg-slate-950/95 border border-slate-700 p-3 rounded shadow-2xl font-mono text-xs text-slate-200 z-50 backdrop-blur-md min-w-[240px]">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                      <div>
                        <span className="text-slate-400 text-[10px] block uppercase tracking-wider">STRATEGY</span>
                        <span className="font-bold text-slate-100 text-sm">{data.name}</span>
                      </div>
                      {data.isTopPerformer && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 text-[10px] font-bold">
                          #1 TOP ALPHA
                        </span>
                      )}
                    </div>

                    <div className="space-y-1.5 text-[11px]">
                      <div className="flex justify-between items-center py-1 bg-emerald-500/10 px-2 rounded border border-emerald-500/20">
                        <span className="text-slate-300 font-semibold">Mean Expected Alpha:</span>
                        <span className="font-bold text-emerald-400 text-sm">+{data.avgAlphaBps} bps</span>
                      </div>

                      <div className="flex justify-between text-slate-400">
                        <span>Alpha vs. Swarm Benchmark:</span>
                        <span className={`font-bold ${data.alphaVsSwarmBps >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {data.alphaVsSwarmBps >= 0 ? `+${data.alphaVsSwarmBps}` : data.alphaVsSwarmBps} bps
                        </span>
                      </div>

                      {data.signalCount > 0 && (
                        <div className="flex justify-between text-slate-400">
                          <span>Alpha Range (Min / Max):</span>
                          <span className="text-slate-200">
                            +{data.minAlphaBps} / +{data.maxAlphaBps} bps
                          </span>
                        </div>
                      )}

                      <div className="border-t border-slate-800 pt-1.5 flex justify-between text-slate-400">
                        <span>Signals in Current Buffer:</span>
                        <span className="text-slate-200 font-bold">{data.signalCount} ({data.shareOfSignalsPct}%)</span>
                      </div>

                      <div className="flex justify-between text-slate-400">
                        <span>Current Portfolio Weight:</span>
                        <span className="text-amber-400 font-bold">{Math.round(data.weight * 100)}%</span>
                      </div>

                      <div className="flex justify-between text-slate-400">
                        <span>Historical Sharpe Ratio:</span>
                        <span className="text-slate-200 font-bold">{data.sharpeRatio.toFixed(2)}</span>
                      </div>

                      <div className="flex justify-between text-slate-400">
                        <span>Backtested Win Rate:</span>
                        <span className="text-slate-200 font-bold">{(data.winRate * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                );
              }}
            />

            <Bar
              dataKey="avgAlphaBps"
              radius={[4, 4, 0, 0]}
              barSize={32}
            >
              <LabelList
                dataKey="avgAlphaBps"
                position="top"
                formatter={(val: number) => (val > 0 ? `+${val}` : '')}
                style={{
                  fill: '#e2e8f0',
                  fontSize: 10,
                  fontFamily: 'monospace',
                  fontWeight: 600,
                }}
              />
              {strategyMetrics.map((entry) => (
                <Cell
                  key={`cell-${entry.id}`}
                  fill={
                    entry.isTopPerformer
                      ? 'url(#topAlphaGrad)'
                      : entry.avgAlphaBps >= swarmAvgAlpha
                      ? 'url(#aboveAvgGrad)'
                      : 'url(#standardGrad)'
                  }
                  stroke={
                    entry.isTopPerformer
                      ? '#10b981'
                      : entry.avgAlphaBps >= swarmAvgAlpha
                      ? '#38bdf8'
                      : '#818cf8'
                  }
                  strokeWidth={entry.isTopPerformer ? 2 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend & Performance Legend */}
      <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block"></span>
            <span className="text-slate-300">Top Alpha Performer</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-sky-400 inline-block"></span>
            <span className="text-slate-300">Above Benchmark</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-indigo-400 inline-block"></span>
            <span className="text-slate-300">Standard Horizon Alpha</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="border-t-2 border-dashed border-amber-400 w-3.5 inline-block"></span>
            <span className="text-amber-400">Swarm Mean (+{swarmAvgAlpha} bps)</span>
          </div>
        </div>

        <div className="text-[10px] text-slate-500 mt-1 sm:mt-0">
          Rankings dynamically updated with live tick buffer
        </div>
      </div>
    </div>
  );
};
