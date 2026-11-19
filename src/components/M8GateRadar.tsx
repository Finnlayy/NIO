import React, { useState, useMemo } from 'react';
import { Shield, ShieldAlert, CheckCircle2, XCircle, AlertTriangle, Cpu, ArrowRight, Crosshair, Zap } from 'lucide-react';
import { GateResult, JudgeVerdict, JudgeConfig } from '../types/trading';
import { AnimatedNumber, AnimatedCurrency, AnimatedPercent } from './AnimatedNumber';

interface M8GateRadarProps {
  recentVerdicts: JudgeVerdict[];
  config: JudgeConfig;
}

export const M8GateRadar: React.FC<M8GateRadarProps> = ({ recentVerdicts, config }) => {
  const [selectedGate, setSelectedGate] = useState<string | null>(null);
  
  const totalEvaluated = recentVerdicts.length;
  const approvedCount = recentVerdicts.filter((v) => v.status === 'PASSED').length;
  const modifiedCount = recentVerdicts.filter((v) => v.status === 'MODIFIED').length;
  const rejectedCount = recentVerdicts.filter((v) => v.status === 'REJECTED').length;
  const rejectionRate = totalEvaluated > 0 ? (rejectedCount / totalEvaluated) * 100 : 0;

  const gatesMeta = useMemo(() => [
    {
      id: 'M1',
      name: 'Sanity & Latency',
      desc: 'Checks tick freshness & monotonic sequence',
      threshold: `<= ${config.signalMaxLatencyMs}ms`,
      type: 'HARD_REJECT',
      angle: -90, // Top
    },
    {
      id: 'M2',
      name: 'Gross Exposure',
      desc: 'Net & Gross aggregate leverage limit',
      threshold: `<= ${config.maxGrossLeverage}x NAV`,
      type: 'HARD_REJECT',
      angle: -45, // Top-Right
    },
    {
      id: 'M3',
      name: 'Vol Regime Filter',
      desc: 'Parkinson / GARCH volatility dampener',
      threshold: `<= ${config.volatilityCeilingAtrRatio}x ATR`,
      type: 'PROPORTIONAL',
      angle: 0, // Right
    },
    {
      id: 'M4',
      name: 'Kelly Capital Sizer',
      desc: 'Fractional Kelly sizing optimization',
      threshold: `${(config.kellyFraction * 100).toFixed(0)}% Half-Kelly`,
      type: 'SIZING_MOD',
      angle: 45, // Bottom-Right
    },
    {
      id: 'M5',
      name: 'Drawdown Breaker',
      desc: 'Daily limit & peak trailing stop',
      threshold: `Max -${config.maxTotalDrawdownPct}%`,
      type: 'CIRCUIT_BREAK',
      angle: 90, // Bottom
    },
    {
      id: 'M6',
      name: 'ADV & Spread Barrier',
      desc: 'Bid-ask spread & order slice participation',
      threshold: `<= ${config.maxSpreadBpsThreshold} bps`,
      type: 'HARD_REJECT',
      angle: 135, // Bottom-Left
    },
    {
      id: 'M7',
      name: '99% CVaR Barrier',
      desc: 'Cornish-Fisher expected shortfall stress',
      threshold: `<= $${(config.cvarLimitUsd / 1000).toFixed(0)}k CVaR`,
      type: 'RISK_CAP',
      angle: 180, // Left
    },
    {
      id: 'M8',
      name: 'Execution Routing',
      desc: 'DMA, TWAP/VWAP slicer, Iceberg selector',
      threshold: 'Optimal Route',
      type: 'ROUTER',
      angle: 225, // Top-Left
    },
  ], [config]);

  // Count failures by gate
  const gateFailures: Record<string, number> = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const v of recentVerdicts) {
      if (v.failedGate) {
        acc[v.failedGate] = (acc[v.failedGate] || 0) + 1;
      }
    }
    return acc;
  }, [recentVerdicts]);

  // Radar chart mathematical dimensions
  const size = 260;
  const center = size / 2;
  const maxRadius = 96;

  // Compute safety score per gate (1.0 = optimal, lower if recent failures)
  const radarPoints = useMemo(() => {
    return gatesMeta.map((gate) => {
      const fails = gateFailures[gate.id] || 0;
      // Health score between 0.2 and 0.95
      const health = Math.max(0.25, 0.92 - (fails * 0.18));
      const rad = (gate.angle * Math.PI) / 180;
      const r = maxRadius * health;
      const x = center + r * Math.cos(rad);
      const y = center + r * Math.sin(rad);
      const maxX = center + maxRadius * Math.cos(rad);
      const maxY = center + maxRadius * Math.sin(rad);
      return {
        ...gate,
        health,
        x,
        y,
        maxX,
        maxY,
      };
    });
  }, [gatesMeta, gateFailures, center, maxRadius]);

  const polygonPath = useMemo(() => {
    return radarPoints.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  }, [radarPoints]);

  const latestVerdict = recentVerdicts[0];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm space-y-4 gpu-accelerate">
      {/* Header & Overall Statistics */}
      <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>THE JUDGE: M8-GATE INVARIANT RADAR</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-700/40">
                ACTIVE 60FPS
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 font-sans">
              8-tier quantitative risk adjudication pipeline separating Swarm alpha from execution
            </p>
          </div>
        </div>

        {/* Stats Pills with Animated Numbers */}
        <div className="flex items-center gap-2 text-xs font-mono flex-wrap">
          <span className="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300">
            ADJUDICATED: <strong className="text-white"><AnimatedNumber value={totalEvaluated} precision={0} /></strong>
          </span>
          <span className="px-2.5 py-1 rounded bg-emerald-950/40 border border-emerald-800 text-emerald-300">
            PASSED: <strong><AnimatedNumber value={approvedCount} precision={0} /></strong>
          </span>
          <span className="px-2.5 py-1 rounded bg-amber-950/40 border border-amber-800 text-amber-300">
            MODIFIED: <strong><AnimatedNumber value={modifiedCount} precision={0} /></strong>
          </span>
          <span className="px-2.5 py-1 rounded bg-rose-950/40 border border-rose-800 text-rose-300">
            REJECTED: <strong><AnimatedNumber value={rejectedCount} precision={0} /> (<AnimatedPercent value={rejectionRate} precision={0} showSign={false} />)</strong>
          </span>
        </div>
      </div>

      {/* Interactive Visual Radar & 8-Gate Metrics Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
        {/* Polar SVG Radar Visualizer (5 cols) */}
        <div className="lg:col-span-4 flex flex-col items-center justify-center p-3 bg-slate-950/80 rounded-xl border border-slate-800/80 relative overflow-hidden">
          {/* Subtle radar background grid */}
          <div className="text-[10px] font-mono text-cyan-400 font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5 self-start">
            <Crosshair className="w-3.5 h-3.5 text-cyan-400 animate-spin" style={{ animationDuration: '12s' }} />
            <span>REAL-TIME INVARIANT POLAR ENVELOPE</span>
          </div>

          <div className="relative w-[260px] h-[260px] flex items-center justify-center">
            <svg width={size} height={size} className="overflow-visible select-none">
              <defs>
                {/* Radar Fill Gradient */}
                <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgba(6, 182, 212, 0.45)" />
                  <stop offset="60%" stopColor="rgba(16, 185, 129, 0.25)" />
                  <stop offset="100%" stopColor="rgba(16, 185, 129, 0.02)" />
                </radialGradient>
                {/* Sweep Gradient */}
                <linearGradient id="sweepGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="rgba(6, 182, 212, 0.6)" />
                  <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
                </linearGradient>
              </defs>

              {/* Concentric rings */}
              {[0.25, 0.5, 0.75, 1.0].map((frac, idx) => (
                <circle
                  key={idx}
                  cx={center}
                  cy={center}
                  r={maxRadius * frac}
                  fill="none"
                  stroke="#1e293b"
                  strokeWidth="1"
                  strokeDasharray={frac === 1.0 ? 'none' : '2 2'}
                />
              ))}

              {/* Axis rays */}
              {radarPoints.map((pt) => (
                <line
                  key={`ray-${pt.id}`}
                  x1={center}
                  y1={center}
                  x2={pt.maxX}
                  y2={pt.maxY}
                  stroke="#334155"
                  strokeWidth="1"
                />
              ))}

              {/* Active Radar Polygon */}
              <polygon
                points={polygonPath}
                fill="url(#radarGlow)"
                stroke="#06b6d4"
                strokeWidth="2"
                className="transition-all duration-700 ease-out"
                style={{
                  filter: 'drop-shadow(0 0 8px rgba(6, 182, 212, 0.6))',
                }}
              />

              {/* Radar Sweep Rotating Ray */}
              <g className="animate-radar-sweep" style={{ transformOrigin: `${center}px ${center}px` }}>
                <line
                  x1={center}
                  y1={center}
                  x2={center}
                  y2={center - maxRadius}
                  stroke="#22d3ee"
                  strokeWidth="2"
                  strokeLinecap="round"
                  style={{ filter: 'drop-shadow(0 0 6px #06b6d4)' }}
                />
                <path
                  d={`M ${center} ${center} L ${center} ${center - maxRadius} A ${maxRadius} ${maxRadius} 0 0 1 ${center + maxRadius * 0.7} ${center - maxRadius * 0.7} Z`}
                  fill="url(#sweepGradient)"
                  opacity="0.3"
                />
              </g>

              {/* Gate Node Dots and Labels */}
              {radarPoints.map((pt) => {
                const fails = gateFailures[pt.id] || 0;
                const isSelected = selectedGate === pt.id;
                const rad = (pt.angle * Math.PI) / 180;
                const labelX = center + (maxRadius + 18) * Math.cos(rad);
                const labelY = center + (maxRadius + 18) * Math.sin(rad);

                return (
                  <g
                    key={`node-${pt.id}`}
                    className="cursor-pointer"
                    onClick={() => setSelectedGate(selectedGate === pt.id ? null : pt.id)}
                  >
                    {/* Node Dot */}
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r={isSelected ? 5 : 3.5}
                      fill={fails > 0 ? '#f43f5e' : '#10b981'}
                      stroke="#0f172a"
                      strokeWidth="1.5"
                      className="transition-all duration-300"
                      style={{
                        filter: fails > 0
                          ? 'drop-shadow(0 0 6px rgba(244, 63, 94, 0.8))'
                          : 'drop-shadow(0 0 6px rgba(16, 185, 129, 0.8))',
                      }}
                    />
                    {/* Label */}
                    <text
                      x={labelX}
                      y={labelY + 4}
                      textAnchor="middle"
                      className={`text-[10px] font-mono font-bold transition-colors ${
                        isSelected
                          ? 'fill-cyan-300 font-extrabold'
                          : fails > 0
                          ? 'fill-rose-400'
                          : 'fill-slate-400 hover:fill-slate-200'
                      }`}
                    >
                      {pt.id}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div className="text-[10px] font-mono text-slate-400 flex items-center justify-between w-full mt-2 pt-2 border-t border-slate-800">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Safety Target: &gt;90%
            </span>
            <span className="text-cyan-400">Click axis for details</span>
          </div>
        </div>

        {/* 8 Gates Status Grid (8 cols) */}
        <div className="lg:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {gatesMeta.map((gate) => {
            const failCount = gateFailures[gate.id] || 0;
            const hasRecentFailure = failCount > 0;
            const isSelected = selectedGate === gate.id;

            return (
              <div
                key={gate.id}
                onClick={() => setSelectedGate(selectedGate === gate.id ? null : gate.id)}
                className={`p-2.5 rounded-lg border flex flex-col justify-between transition-all cursor-pointer ${
                  isSelected
                    ? 'ring-2 ring-cyan-400 bg-slate-900 border-cyan-400'
                    : hasRecentFailure
                    ? 'bg-rose-950/20 border-rose-500/40 text-rose-200 hover:border-rose-400'
                    : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-cyan-400">{gate.id}</span>
                    {hasRecentFailure ? (
                      <span className="text-[10px] font-mono px-1 py-0.2 bg-rose-900/60 text-rose-300 rounded">
                        <AnimatedNumber value={failCount} precision={0} /> BLOCKED
                      </span>
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    )}
                  </div>
                  <div className="text-xs font-semibold text-white mt-1 truncate">{gate.name}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5 line-clamp-2 leading-tight">{gate.desc}</div>
                </div>

                <div className="mt-2 pt-1.5 border-t border-slate-800/60 text-[10px] font-mono flex items-center justify-between text-slate-400">
                  <span>CUTOFF</span>
                  <span className="text-cyan-300 font-semibold">{gate.threshold}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Latest Adjudication Detail with Animated Numbers */}
      {latestVerdict && (
        <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-3 text-xs font-mono">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="flex items-center gap-1.5 text-cyan-400 font-semibold">
              <Cpu className="w-3.5 h-3.5" /> LATEST ADJUDICATION AUDIT TRAIL
            </span>
            <span>ID: {latestVerdict.signalId}</span>
          </div>
          <div className="flex items-center gap-3 text-xs flex-wrap">
            <span className="text-white font-bold">{latestVerdict.symbol}</span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                latestVerdict.direction === 'LONG' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'
              }`}
            >
              {latestVerdict.direction}
            </span>
            <span className="text-slate-400">
              Raw: <AnimatedCurrency value={latestVerdict.originalSizeUsd} precision={0} />
            </span>
            <ArrowRight className="w-3 h-3 text-slate-500" />
            <span className="text-cyan-400 font-bold">
              Approved: <AnimatedCurrency value={latestVerdict.approvedSizeUsd} precision={0} /> (
              <AnimatedPercent value={latestVerdict.scaleFactor * 100} precision={0} showSign={false} />)
            </span>
            <span className="text-slate-400">Route: <strong className="text-indigo-300">{latestVerdict.executionRoute}</strong></span>
            <span
              className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                latestVerdict.status === 'PASSED'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : latestVerdict.status === 'MODIFIED'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
              }`}
            >
              {latestVerdict.status}
            </span>
          </div>

          {/* Detailed Gate Reasons for Latest */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 mt-2 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400">
            {latestVerdict.gateResults.slice(0, 4).map((gr) => (
              <div key={gr.gateId} className="flex items-center gap-1.5 truncate">
                {gr.passed ? <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" /> : <XCircle className="w-3 h-3 text-rose-400 shrink-0" />}
                <span className="font-semibold text-slate-300">{gr.gateId}:</span>
                <span className="truncate">{gr.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
