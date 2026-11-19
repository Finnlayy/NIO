import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts';
import { Activity, Zap, TrendingUp, Filter, BarChart3, Gauge, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { RawSignal, StrategyAgent } from '../types/trading';
import { AnimatedNumber, AnimatedPercent } from './AnimatedNumber';

interface SignalChartProps {
  signals: RawSignal[];
  strategies?: StrategyAgent[];
}

interface BucketDataPoint {
  timeStr: string;
  timestamp: number;
  totalSignals: number;
  longSignals: number;
  shortSignals: number;
  avgConfidence: number | null;
  minConfidence: number | null;
  maxConfidence: number | null;
  avgAlphaBps: number | null;
}

export const SignalChart: React.FC<SignalChartProps> = ({ signals, strategies }) => {
  const [viewMode, setViewMode] = useState<'combined' | 'directional' | 'conviction'>('combined');
  const [bucketWindowSec, setBucketWindowSec] = useState<number>(3); // 3 seconds per bucket
  const [maxBuckets] = useState<number>(20); // show last 20 buckets (approx 60s)

  // Accumulate historical bucket tracking so the chart streams smoothly
  const bucketHistoryRef = useRef<Map<number, { count: number; longs: number; shorts: number; confidences: number[]; alphas: number[] }>>(new Map());

  // Aggregate signals into discrete time buckets
  const chartData = useMemo(() => {
    const bucketMs = bucketWindowSec * 1000;
    const now = Date.now();
    const map = bucketHistoryRef.current;

    // Process all current signals into the rolling map
    signals.forEach((sig) => {
      const bKey = Math.floor(sig.timestamp / bucketMs) * bucketMs;
      if (!map.has(bKey)) {
        map.set(bKey, { count: 0, longs: 0, shorts: 0, confidences: [], alphas: [] });
      }
      const item = map.get(bKey)!;
      // Prevent duplicate counting of the same signal id in a bucket if we already processed it
      // but simpler: if item doesn't have it, register metrics
      item.count += 1;
      if (sig.direction === 'LONG') item.longs += 1;
      else if (sig.direction === 'SHORT') item.shorts += 1;
      item.confidences.push(sig.confidence);
      item.alphas.push(sig.expectedAlphaBps);
    });

    // Prune buckets older than 3 minutes to prevent memory leak
    const cutoff = now - 180 * 1000;
    for (const key of map.keys()) {
      if (key < cutoff) {
        map.delete(key);
      }
    }

    // Build ordered timeline of the most recent `maxBuckets` time slices
    const latestBucketKey = Math.floor(now / bucketMs) * bucketMs;
    const result: BucketDataPoint[] = [];

    // Derive raw signal metrics per bucket strictly from signals in memory
    // to ensure accuracy without duplicate accumulation
    const cleanMap = new Map<number, { longs: number; shorts: number; confs: number[]; alphas: number[] }>();
    
    signals.forEach((sig) => {
      const bKey = Math.floor(sig.timestamp / bucketMs) * bucketMs;
      if (!cleanMap.has(bKey)) {
        cleanMap.set(bKey, { longs: 0, shorts: 0, confs: [], alphas: [] });
      }
      const b = cleanMap.get(bKey)!;
      if (sig.direction === 'LONG') b.longs += 1;
      else if (sig.direction === 'SHORT') b.shorts += 1;
      b.confs.push(sig.confidence);
      b.alphas.push(sig.expectedAlphaBps);
    });

    let lastKnownConfidence: number | null = null;

    for (let i = maxBuckets - 1; i >= 0; i--) {
      const bucketTime = latestBucketKey - i * bucketMs;
      const bucketDate = new Date(bucketTime);
      const timeStr = bucketDate.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });

      const entry = cleanMap.get(bucketTime);

      if (entry && (entry.longs + entry.shorts) > 0) {
        const total = entry.longs + entry.shorts;
        const avgConf = Math.round((entry.confs.reduce((a, b) => a + b, 0) / entry.confs.length) * 1000) / 10;
        const minConf = Math.round(Math.min(...entry.confs) * 1000) / 10;
        const maxConf = Math.round(Math.max(...entry.confs) * 1000) / 10;
        const avgAlpha = Math.round((entry.alphas.reduce((a, b) => a + b, 0) / entry.alphas.length) * 10) / 10;
        lastKnownConfidence = avgConf;

        result.push({
          timeStr,
          timestamp: bucketTime,
          totalSignals: total,
          longSignals: entry.longs,
          shortSignals: entry.shorts,
          avgConfidence: avgConf,
          minConfidence: minConf,
          maxConfidence: maxConf,
          avgAlphaBps: avgAlpha,
        });
      } else {
        result.push({
          timeStr,
          timestamp: bucketTime,
          totalSignals: 0,
          longSignals: 0,
          shortSignals: 0,
          avgConfidence: lastKnownConfidence, // smooth continuation for line
          minConfidence: null,
          maxConfidence: null,
          avgAlphaBps: null,
        });
      }
    }

    return result;
  }, [signals, bucketWindowSec, maxBuckets]);

  // Overall statistics across active signals
  const stats = useMemo(() => {
    if (signals.length === 0) {
      return {
        avgConf: 0,
        highConvictionRate: 0,
        longRatio: 0,
        shortRatio: 0,
        frequencyPerSec: 0,
        avgAlpha: 0,
      };
    }

    const confSum = signals.reduce((acc, s) => acc + s.confidence, 0);
    const avgConf = Math.round((confSum / signals.length) * 1000) / 10;
    const highConvictionCount = signals.filter((s) => s.confidence >= 0.75).length;
    const highConvictionRate = Math.round((highConvictionCount / signals.length) * 100);

    const longs = signals.filter((s) => s.direction === 'LONG').length;
    const shorts = signals.filter((s) => s.direction === 'SHORT').length;
    const longRatio = Math.round((longs / signals.length) * 100);
    const shortRatio = Math.round((shorts / signals.length) * 100);

    // Frequency estimate: signals count over time span
    const oldest = signals[signals.length - 1]?.timestamp || Date.now();
    const newest = signals[0]?.timestamp || Date.now();
    const spanSec = Math.max(1, (newest - oldest) / 1000);
    const frequencyPerSec = Math.round((signals.length / spanSec) * 10) / 10;

    const alphaSum = signals.reduce((acc, s) => acc + s.expectedAlphaBps, 0);
    const avgAlpha = Math.round((alphaSum / signals.length) * 10) / 10;

    return {
      avgConf,
      highConvictionRate,
      longRatio,
      shortRatio,
      frequencyPerSec,
      avgAlpha,
    };
  }, [signals]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
      {/* Header & Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider">
                Swarm Emission Frequency & Conviction Trajectory
              </h3>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-semibold animate-pulse">
                LIVE TELEMETRY
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono">
              Real-time signal density per {bucketWindowSec}s interval vs. continuous model confidence
            </p>
          </div>
        </div>

        {/* View mode toggle controls */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-md border border-slate-800 text-xs font-mono">
          <button
            type="button"
            onClick={() => setViewMode('combined')}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              viewMode === 'combined'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Combined
          </button>
          <button
            type="button"
            onClick={() => setViewMode('directional')}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              viewMode === 'directional'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Long vs Short
          </button>
          <button
            type="button"
            onClick={() => setViewMode('conviction')}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              viewMode === 'conviction'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Confidence Band
          </button>
        </div>
      </div>

      {/* KPI Stats Pill Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-1 font-mono">
        <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
          <div className="text-[10px] text-slate-500">SIGNAL CADENCE</div>
          <div className="text-xs font-bold text-amber-400 flex items-center gap-1 mt-0.5 tabular-nums">
            <Zap className="w-3 h-3" />
            <AnimatedNumber value={stats.frequencyPerSec} precision={1} suffix=" sig/sec" />
          </div>
        </div>

        <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
          <div className="text-[10px] text-slate-500">SWARM CONVICTION</div>
          <div className="text-xs font-bold text-emerald-400 flex items-center gap-1 mt-0.5 tabular-nums">
            <Gauge className="w-3 h-3" />
            <AnimatedPercent value={stats.avgConf} precision={0} showSign={false} />
          </div>
        </div>

        <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
          <div className="text-[10px] text-slate-500">HIGH CONVICTION (≥75%)</div>
          <div className="text-xs font-bold text-slate-200 flex items-center gap-1 mt-0.5 tabular-nums">
            <TrendingUp className="w-3 h-3 text-emerald-400" />
            <AnimatedPercent value={stats.highConvictionRate} precision={0} showSign={false} />
          </div>
        </div>

        <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
          <div className="text-[10px] text-slate-500">DIRECTIONAL SKEW</div>
          <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5 mt-0.5 tabular-nums">
            <span className="text-emerald-400 flex items-center">
              <ArrowUpRight className="w-3 h-3" />
              <AnimatedPercent value={stats.longRatio} precision={0} showSign={false} />
            </span>
            <span className="text-slate-600">/</span>
            <span className="text-rose-400 flex items-center">
              <ArrowDownRight className="w-3 h-3" />
              <AnimatedPercent value={stats.shortRatio} precision={0} showSign={false} />
            </span>
          </div>
        </div>

        <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
          <div className="text-[10px] text-slate-500">EXP ALPHA SPREAD</div>
          <div className="text-xs font-bold text-emerald-400 mt-0.5 tabular-nums">
            <AnimatedNumber value={stats.avgAlpha} precision={1} showSign={true} suffix=" bps" />
          </div>
        </div>

        <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
          <div className="text-[10px] text-slate-500">SAMPLE BUFFER</div>
          <div className="text-xs font-bold text-slate-300 mt-0.5 tabular-nums">
            <AnimatedNumber value={signals.length} precision={0} suffix=" Signals" />
          </div>
        </div>
      </div>

      {/* Main Recharts Visualization Canvas */}
      <div className="h-64 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <defs>
              {/* Glowing frequency gradient */}
              <linearGradient id="freqGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="longGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0.2} />
              </linearGradient>
              <linearGradient id="shortGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.8} />
                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.2} />
              </linearGradient>
              <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.05} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

            {/* X-Axis: Time buckets */}
            <XAxis
              dataKey="timeStr"
              stroke="#64748b"
              tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'monospace' }}
              tickLine={{ stroke: '#334155' }}
              axisLine={{ stroke: '#334155' }}
            />

            {/* Left Y-Axis: Signal Frequency (Count per bucket) */}
            <YAxis
              yAxisId="frequency"
              orientation="left"
              stroke="#f59e0b"
              domain={[0, (dataMax: number) => Math.max(4, Math.ceil(dataMax * 1.2))]}
              allowDecimals={false}
              tick={{ fill: '#d97706', fontSize: 10, fontFamily: 'monospace' }}
              tickLine={{ stroke: '#334155' }}
              axisLine={{ stroke: '#334155' }}
              label={{
                value: 'Freq (sigs/bucket)',
                angle: -90,
                position: 'insideLeft',
                offset: 15,
                fill: '#d97706',
                fontSize: 9,
                fontFamily: 'monospace',
              }}
            />

            {/* Right Y-Axis: Confidence Level (0% to 100%) */}
            <YAxis
              yAxisId="confidence"
              orientation="right"
              stroke="#10b981"
              domain={[30, 100]}
              tick={{ fill: '#10b981', fontSize: 10, fontFamily: 'monospace' }}
              tickFormatter={(v) => `${v}%`}
              tickLine={{ stroke: '#334155' }}
              axisLine={{ stroke: '#334155' }}
              label={{
                value: 'Confidence (%)',
                angle: 90,
                position: 'insideRight',
                offset: 15,
                fill: '#10b981',
                fontSize: 9,
                fontFamily: 'monospace',
              }}
            />

            {/* Threshold References */}
            <ReferenceLine
              yAxisId="confidence"
              y={75}
              stroke="#10b981"
              strokeDasharray="4 4"
              strokeOpacity={0.6}
              label={{
                value: '75% M8-Cutoff',
                fill: '#10b981',
                fontSize: 9,
                position: 'right',
                fontFamily: 'monospace',
              }}
            />
            <ReferenceLine
              yAxisId="confidence"
              y={50}
              stroke="#475569"
              strokeDasharray="2 2"
              strokeOpacity={0.5}
            />

            {/* Tooltip */}
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null;
                const point = payload[0]?.payload as BucketDataPoint;
                if (!point) return null;

                return (
                  <div className="bg-slate-950/95 border border-slate-700 p-2.5 rounded shadow-2xl font-mono text-xs text-slate-200 z-50 backdrop-blur-sm">
                    <div className="flex items-center justify-between gap-4 border-b border-slate-800 pb-1.5 mb-1.5">
                      <span className="text-slate-400 font-semibold">TICK INTERVAL</span>
                      <span className="text-amber-400 font-bold">{label}</span>
                    </div>
                    <div className="space-y-1 text-[11px]">
                      <div className="flex justify-between gap-4">
                        <span className="text-slate-400">Total Signal Count:</span>
                        <span className="font-bold text-slate-100">{point.totalSignals} sigs</span>
                      </div>
                      <div className="flex justify-between gap-4">
                        <span className="text-slate-400">Directional Split:</span>
                        <span className="font-bold">
                          <span className="text-emerald-400">{point.longSignals} Long</span> /{' '}
                          <span className="text-rose-400">{point.shortSignals} Short</span>
                        </span>
                      </div>
                      <div className="flex justify-between gap-4 pt-1 border-t border-slate-800/80">
                        <span className="text-slate-400">Avg Swarm Confidence:</span>
                        <span className="font-bold text-emerald-400">
                          {point.avgConfidence !== null ? `${point.avgConfidence}%` : 'N/A'}
                        </span>
                      </div>
                      {point.minConfidence !== null && point.maxConfidence !== null && (
                        <div className="flex justify-between gap-4 text-[10px] text-slate-400">
                          <span>Confidence Range:</span>
                          <span>
                            {point.minConfidence}% - {point.maxConfidence}%
                          </span>
                        </div>
                      )}
                      {point.avgAlphaBps !== null && (
                        <div className="flex justify-between gap-4 text-[10px] text-slate-400">
                          <span>Avg Expected Alpha:</span>
                          <span className="text-emerald-400">+{point.avgAlphaBps} bps</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              }}
            />

            <Legend
              verticalAlign="top"
              height={28}
              wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace', paddingBottom: '4px' }}
              formatter={(value) => {
                const labels: Record<string, string> = {
                  totalSignals: 'Signal Frequency',
                  longSignals: 'Long Frequency',
                  shortSignals: 'Short Frequency',
                  avgConfidence: 'Mean Confidence (%)',
                  maxConfidence: 'Max Conviction Peak',
                };
                return <span className="text-slate-300">{labels[value] || value}</span>;
              }}
            />

            {/* Visuals rendered according to viewMode */}
            {viewMode === 'combined' && (
              <>
                <Bar
                  yAxisId="frequency"
                  dataKey="totalSignals"
                  fill="url(#freqGradient)"
                  stroke="#f59e0b"
                  strokeWidth={1}
                  radius={[3, 3, 0, 0]}
                  barSize={14}
                />
                <Line
                  yAxisId="confidence"
                  type="monotone"
                  dataKey="avgConfidence"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 2.5, fill: '#10b981', strokeWidth: 1, stroke: '#064e3b' }}
                  activeDot={{ r: 5, fill: '#34d399', stroke: '#fff', strokeWidth: 1.5 }}
                  connectNulls
                />
              </>
            )}

            {viewMode === 'directional' && (
              <>
                <Bar
                  yAxisId="frequency"
                  dataKey="longSignals"
                  stackId="signals"
                  fill="url(#longGradient)"
                  stroke="#10b981"
                  strokeWidth={1}
                  barSize={14}
                />
                <Bar
                  yAxisId="frequency"
                  dataKey="shortSignals"
                  stackId="signals"
                  fill="url(#shortGradient)"
                  stroke="#f43f5e"
                  strokeWidth={1}
                  radius={[3, 3, 0, 0]}
                  barSize={14}
                />
                <Line
                  yAxisId="confidence"
                  type="monotone"
                  dataKey="avgConfidence"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={{ r: 2.5, fill: '#38bdf8' }}
                  activeDot={{ r: 5, fill: '#7dd3fc' }}
                  connectNulls
                />
              </>
            )}

            {viewMode === 'conviction' && (
              <>
                <Area
                  yAxisId="confidence"
                  type="monotone"
                  dataKey="maxConfidence"
                  fill="url(#bandGradient)"
                  stroke="#38bdf8"
                  strokeWidth={1.5}
                  strokeDasharray="2 2"
                  connectNulls
                />
                <Bar
                  yAxisId="frequency"
                  dataKey="totalSignals"
                  fill="#1e293b"
                  stroke="#475569"
                  strokeWidth={1}
                  radius={[2, 2, 0, 0]}
                  barSize={10}
                />
                <Line
                  yAxisId="confidence"
                  type="monotone"
                  dataKey="avgConfidence"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: '#10b981' }}
                  connectNulls
                />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom Sub-legend / Quick Explanation */}
      <div className="flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-500 pt-1 border-t border-slate-800/60">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded bg-amber-400 inline-block"></span> Frequency: Left Axis
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded bg-emerald-400 inline-block"></span> Confidence: Right Axis (30-100%)
          </span>
          <span className="flex items-center gap-1 text-slate-400">
            <span className="border-t border-dashed border-emerald-400 w-3 inline-block"></span> M8 Gate Hurdle (75%)
          </span>
        </div>
        <div>
          <span>Updated dynamically every tick cycle</span>
        </div>
      </div>
    </div>
  );
};
