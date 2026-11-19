import React, { useState } from 'react';
import {
  Cpu,
  TrendingUp,
  Activity,
  Sliders,
  Zap,
  BarChart2,
  Clock,
  CheckCircle2,
  Percent,
  SlidersHorizontal,
  Bot,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { StrategyAgent, RawSignal, WorkerBot } from '../types/trading';
import { SignalChart } from './SignalChart';
import { StrategyAlphaChart } from './StrategyAlphaChart';
import { WorkerBotCard } from './WorkerBotCard';

interface SwarmViewProps {
  strategies: StrategyAgent[];
  signals: RawSignal[];
  onUpdateWeights: (strategyId: string, newWeight: number) => void;
  workerBots?: WorkerBot[];
  onToggleBotStatus?: (botId: string) => void;
  onNavigateToBotsTab?: () => void;
}

export const SwarmView: React.FC<SwarmViewProps> = ({
  strategies,
  signals,
  onUpdateWeights,
  workerBots = [],
  onToggleBotStatus,
  onNavigateToBotsTab,
}) => {
  const [showWorkerBots, setShowWorkerBots] = useState<boolean>(true);
  const [selectedBotId, setSelectedBotId] = useState<string>(workerBots[0]?.id || 'BOT-7742');

  const currentBot = workerBots.find((b) => b.id === selectedBotId) || workerBots[0];

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-tight">
                THE SWARM: SPECULATIVE ALPHA GENERATION
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-3xl">
              Independent algorithmic agents continuously mining microsecond market data for statistical anomalies, orderbook toxicity (VPIN), and Ornstein-Uhlenbeck drift. Signals carry zero authority until adjudicated by The Judge.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="bg-slate-950 px-3 py-1.5 rounded border border-slate-800">
              <span className="text-slate-400">ACTIVE AGENTS:</span>{' '}
              <span className="text-emerald-400 font-bold">{strategies.length}</span>
            </div>
            <div className="bg-slate-950 px-3 py-1.5 rounded border border-slate-800">
              <span className="text-slate-400">SIGNALS (LAST 50):</span>{' '}
              <span className="text-amber-400 font-bold">{signals.length}</span>
            </div>
          </div>
        </div>

        {/* Strategy Agent Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3 mt-4">
          {strategies.map((strat) => (
            <div
              key={strat.id}
              className="bg-slate-950 p-3 rounded-lg border border-slate-800 flex flex-col justify-between hover:border-slate-700 transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-800 text-amber-400">
                    {strat.type}
                  </span>
                  <span className="text-[11px] font-mono text-emerald-400 font-semibold">
                    SR {strat.sharpeRatio.toFixed(2)}
                  </span>
                </div>

                <h3 className="text-xs font-bold text-slate-100 font-mono line-clamp-1">
                  {strat.name}
                </h3>
                <p className="text-[11px] text-slate-400 mt-1 leading-snug line-clamp-2">
                  {strat.description}
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-800/80 space-y-2">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-400">
                  <span>Win Rate: <strong className="text-slate-200">{(strat.winRate * 100).toFixed(0)}%</strong></span>
                  <span>Weight: <strong className="text-amber-400">{Math.round(strat.weight * 100)}%</strong></span>
                </div>

                {/* Weight slider */}
                <input
                  type="range"
                  min="0"
                  max="50"
                  value={Math.round(strat.weight * 100)}
                  onChange={(e) => onUpdateWeights(strat.id, parseInt(e.target.value) / 100)}
                  className="w-full accent-amber-400 h-1 bg-slate-800 rounded cursor-pointer"
                />

                {/* Parameter Snippet */}
                <div className="bg-slate-900/90 p-1.5 rounded text-[9px] font-mono text-slate-400 space-y-0.5">
                  {Object.entries(strat.parameters).slice(0, 2).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-slate-500">{k}:</span>
                      <span className="text-slate-300 font-semibold">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Strategy Alpha Performance Bar Chart (Recharts) */}
      <StrategyAlphaChart strategies={strategies} signals={signals} />

      {/* Etablierte Worker & DCA Bots Widget Showcase */}
      {workerBots.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-400">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider">
                    Etablierte Worker / Bots (Live Widgets)
                  </h3>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-purple-500/10 border border-purple-500/30 text-purple-300 font-semibold">
                    DCA &amp; PERPETUAL FUTURES
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 font-mono">
                  Live-Synchronisation mit Marktdaten, Realized/Unrealized P&amp;L, Hebel und Liquidations-Abstand
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {onNavigateToBotsTab && (
                <button
                  type="button"
                  onClick={onNavigateToBotsTab}
                  className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
                >
                  <span>Alle Worker verwalten</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowWorkerBots(!showWorkerBots)}
                className="px-2.5 py-1 rounded bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 text-xs font-mono font-medium transition-colors"
              >
                {showWorkerBots ? 'Widget einklappen' : 'Widget einblenden'}
              </button>
            </div>
          </div>

          {showWorkerBots && (
            <div className="space-y-4">
              {/* Bot Selector Pills */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-mono text-slate-500">Worker wählen:</span>
                {workerBots.map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => setSelectedBotId(b.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 ${
                      b.id === selectedBotId
                        ? 'bg-purple-600 text-white font-bold shadow-md shadow-purple-500/20'
                        : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200 hover:border-slate-700'
                    }`}
                  >
                    <Bot className="w-3.5 h-3.5" />
                    <span>{b.name}</span>
                    <span className="text-[10px] opacity-75">
                      ({(b.pair || b.symbol || '').split('/')[0]} {b.leverage}×)
                    </span>
                  </button>
                ))}
              </div>

              {/* Bot Widget Container */}
              <div className="flex flex-col lg:flex-row items-center lg:items-start justify-center gap-6 pt-2">
                {currentBot && (
                  <WorkerBotCard
                    bot={currentBot}
                    onToggleStatus={onToggleBotStatus}
                  />
                )}

                {/* Companion Quant Telemetry Panel */}
                <div className="w-full lg:flex-1 bg-slate-950 border border-slate-800/90 rounded-2xl p-4 font-mono text-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <span className="font-bold text-slate-200 uppercase tracking-wider">
                        Worker Telemetrie &amp; M8-Audit ({currentBot.id})
                      </span>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      LIVE STREAM
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
                    <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 space-y-1">
                      <div className="text-slate-400 text-[10px]">VERBINDUNGS-ROUTING</div>
                      <div className="text-slate-200 font-bold">{currentBot.exchange} DMA Gateway</div>
                      <div className="text-slate-500 text-[10px]">Latenz: &lt;1.2 ms Direct Webhook</div>
                    </div>

                    <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 space-y-1">
                      <div className="text-slate-400 text-[10px]">RISIKO-PUFFER / LIQUIDATION</div>
                      <div className="text-rose-400 font-bold">
                        {(currentBot.metrics?.liquidationPrice ?? currentBot.liquidationPrice ?? 0).toFixed(2)} $ (
                        {(currentBot.metrics?.liquidationDistancePct ?? currentBot.liquidationDistancePct ?? 0).toFixed(2)}%)
                      </div>
                      <div className="text-slate-500 text-[10px]">M8-Stoploss bei -0.50% Distanz</div>
                    </div>

                    <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 space-y-1">
                      <div className="text-slate-400 text-[10px]">KUMULIERTE ZYKLEN</div>
                      <div className="text-purple-400 font-bold">
                        {currentBot.runtime?.cycles ?? currentBot.cyclesCompleted ?? 0} Zyklen abgeschlossen
                      </div>
                      <div className="text-slate-500 text-[10px]">
                        Zyklusfortschritt: {currentBot.runtime?.cycleProgressPct ?? currentBot.cycleProgressPct ?? 50}%
                      </div>
                    </div>

                    <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 space-y-1">
                      <div className="text-slate-400 text-[10px]">EFFEKTIVER ROI &amp; APR</div>
                      <div className="text-emerald-400 font-bold">
                        +{(currentBot.roi ?? currentBot.roiPct ?? 0).toFixed(2)}% ROI / +
                        {(currentBot.apr ?? currentBot.aprPct ?? 0).toLocaleString('en-US')}% APR
                      </div>
                      <div className="text-slate-500 text-[10px]">
                        Laufzeit: {currentBot.runtime?.days ?? currentBot.runtimeDays ?? 0}d{' '}
                        {currentBot.runtime?.hours ?? currentBot.runtimeHours ?? 0}h
                      </div>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-purple-950/20 border border-purple-500/20 text-slate-300 text-[11px] leading-relaxed">
                    <strong className="text-purple-300 block mb-1">DCA-Stufen &amp; Order-Ausführung:</strong>
                    Der Worker auf dem Kontrakt <span className="text-slate-100 font-bold">{currentBot.pair || currentBot.symbol}</span> hat im Bereich von{' '}
                    <span className="text-slate-100 font-bold">
                      {(currentBot.metrics?.dcaRangeMin ?? currentBot.dcaRangeLow ?? 0).toFixed(2)} –{' '}
                      {(currentBot.metrics?.dcaRangeMax ?? currentBot.dcaRangeHigh ?? 0).toFixed(2)} $
                    </span>{' '}
                    insgesamt{' '}
                    <span className="text-emerald-400 font-bold">
                      {currentBot.metrics?.dcaOrdersTriggered ?? currentBot.dcaOrdersTriggered ?? 0}
                    </span>{' '}
                    limit-basierte Einstiegsorders gestaffelt. Alle Positionen werden über das M8-Gate risikoadjustiert abgesichert.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Signal Frequency & Confidence Recharts Visualization */}
      <SignalChart signals={signals} strategies={strategies} />

      {/* Live Raw Signals Stream */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              Live Swarm Emissions (Pre-Adjudication Buffer)
            </h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            SHOWING LATEST {signals.length} TICKS
          </span>
        </div>

        {signals.length === 0 ? (
          <div className="p-8 text-center text-slate-500 font-mono text-xs">
            Awaiting tick cycle for Swarm signal emission...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                  <th className="pb-2 font-medium">TIMESTAMP</th>
                  <th className="pb-2 font-medium">SIGNAL ID</th>
                  <th className="pb-2 font-medium">STRATEGY</th>
                  <th className="pb-2 font-medium">SYMBOL</th>
                  <th className="pb-2 font-medium">DIR</th>
                  <th className="pb-2 font-medium">CONFIDENCE</th>
                  <th className="pb-2 font-medium">ALPHA BPS</th>
                  <th className="pb-2 font-medium">SUGGESTED SIZE</th>
                  <th className="pb-2 font-medium">HORIZON</th>
                  <th className="pb-2 font-medium">MODEL METRICS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {signals.slice(0, 15).map((sig) => (
                  <tr key={`${sig.id}-${sig.timestamp}`} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2 text-slate-500 text-[10px]">
                      {new Date(sig.timestamp).toLocaleTimeString()}.{String(sig.timestamp % 1000).padStart(3, '0')}
                    </td>
                    <td className="py-2 text-amber-400 font-bold">{sig.id}</td>
                    <td className="py-2 text-slate-300 text-[11px]">{sig.strategyName.split('(')[0]}</td>
                    <td className="py-2 font-bold text-slate-100">{sig.symbol}</td>
                    <td className="py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          sig.direction === 'LONG'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-rose-500/20 text-rose-300'
                        }`}
                      >
                        {sig.direction}
                      </span>
                    </td>
                    <td className="py-2">
                      <div className="flex items-center gap-1.5">
                        <div className="w-12 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-emerald-400 h-full rounded-full"
                            style={{ width: `${Math.round(sig.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-300 font-semibold">
                          {Math.round(sig.confidence * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-2 text-emerald-400 font-semibold">+{sig.expectedAlphaBps} bps</td>
                    <td className="py-2 font-bold text-slate-200">${sig.suggestedSizeUsd.toLocaleString()}</td>
                    <td className="py-2 text-slate-400 text-[10px]">{sig.timeHorizonSec}s</td>
                    <td className="py-2 text-[10px] text-slate-400">
                      {Object.entries(sig.rawMetrics)
                        .map(([k, v]) => `${k}:${v}`)
                        .join(' | ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
