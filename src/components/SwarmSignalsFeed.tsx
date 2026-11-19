import React from 'react';
import { Radio, ArrowUpRight, ArrowDownRight, CheckCircle, AlertOctagon, RefreshCcw, Zap } from 'lucide-react';
import { RawSignal, JudgeVerdict, StrategyAgent } from '../types/trading';
import { AnimatedNumber, AnimatedCurrency, AnimatedPercent } from './AnimatedNumber';

interface SwarmSignalsFeedProps {
  signals: RawSignal[];
  verdicts: Map<string, JudgeVerdict>;
  strategies: StrategyAgent[];
}

export const SwarmSignalsFeed: React.FC<SwarmSignalsFeedProps> = ({ signals, verdicts, strategies }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm flex flex-col h-[460px]">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
            THE SWARM: REAL-TIME ALPHA SIGNALS FEED
          </h3>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
          <span>5 QUANT AGENTS ONLINE</span>
        </div>
      </div>

      {/* Strategies Summary Bar */}
      <div className="px-4 py-2 bg-slate-950/40 border-b border-slate-800/80 flex items-center gap-2 overflow-x-auto text-[11px] font-mono">
        {strategies.map((strat) => (
          <div key={strat.id} className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-900 border border-slate-800 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
            <span className="text-slate-300 font-semibold">{strat.name.split(' ')[0]}</span>
            <span className="text-slate-500">{(strat.weight * 100).toFixed(0)}%</span>
            <span className="text-emerald-400">SR {strat.sharpeRatio.toFixed(1)}</span>
          </div>
        ))}
      </div>

      {/* Signal Stream List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {signals.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 text-xs">
            <Radio className="w-6 h-6 mb-2 text-slate-600 animate-pulse" />
            <span>Awaiting swarm signal generation across asset books...</span>
          </div>
        ) : (
          signals.map((sig) => {
            const verdict = verdicts.get(sig.id);
            const isLong = sig.direction === 'LONG';

            return (
              <div
                key={sig.id}
                className={`p-3 rounded-lg border text-xs font-mono transition-all gpu-accelerate ${
                  verdict?.status === 'PASSED'
                    ? 'bg-slate-950/70 border-emerald-900/40 hover:border-emerald-700/60'
                    : verdict?.status === 'MODIFIED'
                    ? 'bg-slate-950/70 border-amber-900/40 hover:border-amber-700/60'
                    : verdict?.status === 'REJECTED'
                    ? 'bg-slate-950/50 border-rose-900/30 opacity-75'
                    : 'bg-slate-950/50 border-slate-800'
                }`}
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  {/* Left: Strategy & Symbol */}
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-sm">{sig.symbol}</span>
                    <span
                      className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-[10px] font-bold ${
                        isLong
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                      }`}
                    >
                      {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {sig.direction}
                    </span>
                    <span className="text-slate-400 text-[11px] truncate max-w-[150px]">
                      {sig.strategyName}
                    </span>
                  </div>

                  {/* Right: The Judge Verdict */}
                  {verdict ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-slate-400">JUDGE:</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          verdict.status === 'PASSED'
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : verdict.status === 'MODIFIED'
                            ? 'bg-amber-950 text-amber-400 border border-amber-800'
                            : 'bg-rose-950 text-rose-400 border border-rose-800'
                        }`}
                      >
                        {verdict.status}
                      </span>
                    </div>
                  ) : (
                    <span className="text-[10px] text-slate-500 flex items-center gap-1">
                      <RefreshCcw className="w-3 h-3 animate-spin" /> Adjudicating...
                    </span>
                  )}
                </div>

                {/* Metrics Row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2 pt-2 border-t border-slate-900 text-[11px] text-slate-400 tabular-nums">
                  <div>
                    <span className="text-slate-500">CONFIDENCE: </span>
                    <strong className="text-cyan-400">
                      <AnimatedPercent value={sig.confidence * 100} precision={0} />
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500">EXP ALPHA: </span>
                    <strong className="text-emerald-400">
                      +<AnimatedNumber value={sig.expectedAlphaBps} precision={0} /> bps
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500">REQUESTED: </span>
                    <strong className="text-slate-200">
                      <AnimatedCurrency value={sig.suggestedSizeUsd} precision={0} />
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500">APPROVED: </span>
                    <strong className={verdict?.approvedSizeUsd ? 'text-white' : 'text-rose-400'}>
                      {verdict ? <AnimatedCurrency value={verdict.approvedSizeUsd} precision={0} /> : '-'}
                    </strong>
                  </div>
                </div>

                {/* Verdict Detail Note */}
                {verdict && (
                  <div className="mt-1.5 text-[10px] text-slate-500 flex items-center justify-between">
                    <span>
                      Route: <strong className="text-indigo-400">{verdict.executionRoute}</strong>
                      {verdict.executionParams.sliceCount > 1 && ` (${verdict.executionParams.sliceCount} slices)`}
                    </span>
                    {verdict.failedGate && (
                      <span className="text-rose-400">
                        Halted by Gate {verdict.failedGate}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
