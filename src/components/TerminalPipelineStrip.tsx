import React from 'react';
import { DataProviderId, PipelineLogEvent } from '../types/terminal';
import { Activity, ShieldCheck, DollarSign, Zap, Terminal, AlertTriangle } from 'lucide-react';

interface TerminalPipelineStripProps {
  isRunning: boolean;
  activeProvider: DataProviderId;
  activeSymbol: string;
  activeTimeframe: string;
  activeConcurrentTrades: number;
  maxConcurrentTrades: number;
  paperCapital: number;
  filteredByMax20Count: number;
  filteredByChopCount: number;
  latestLog?: PipelineLogEvent | null;
}

const PROVIDER_COLORS: Record<DataProviderId, string> = {
  KRAKEN: 'text-[#00E5FF] border-[#00E5FF]/40 bg-[#00E5FF]/10',
  CCXT: 'text-[#10B981] border-[#10B981]/40 bg-[#10B981]/10',
  MEXC: 'text-[#00C087] border-[#00C087]/50 bg-[#00C087]/15',
  CMC: 'text-[#3861FB] border-[#3861FB]/50 bg-[#3861FB]/15',
  GAINIUM: 'text-[#A855F7] border-[#A855F7]/40 bg-[#A855F7]/10',
  BINANCE: 'text-[#F59E0B] border-[#F59E0B]/40 bg-[#F59E0B]/10',
  ALPACA: 'text-[#3B82F6] border-[#3B82F6]/40 bg-[#3B82F6]/10',
  ALPHAVANTAGE: 'text-[#EC4899] border-[#EC4899]/40 bg-[#EC4899]/10',
};

export const TerminalPipelineStrip: React.FC<TerminalPipelineStripProps> = React.memo(({
  isRunning,
  activeProvider,
  activeSymbol,
  activeTimeframe,
  activeConcurrentTrades,
  maxConcurrentTrades,
  paperCapital,
  filteredByMax20Count,
  filteredByChopCount,
  latestLog,
}) => {
  const isAtCap = activeConcurrentTrades >= maxConcurrentTrades;

  const stages = [
    {
      id: 'SCANNER',
      title: '1. SCANNER',
      subtitle: `${activeSymbol} · ${activeTimeframe}`,
      badge: activeProvider,
      badgeClass: PROVIDER_COLORS[activeProvider] || PROVIDER_COLORS.KRAKEN,
      icon: Activity,
      activeColor: 'border-[#00E5FF]/60',
    },
    {
      id: 'CHECK',
      title: '2. RISK CHECK',
      subtitle: `Slots: ${activeConcurrentTrades}/${maxConcurrentTrades} (Cap ≤20)`,
      badge: isAtCap ? 'CAP 20 REACHED' : `FILTERED: ${filteredByMax20Count + filteredByChopCount}`,
      badgeClass: isAtCap
        ? 'text-[#F23645] border-[#F23645]/50 bg-[#F23645]/15'
        : 'text-[#089981] border-[#089981]/40 bg-[#089981]/10',
      icon: ShieldCheck,
      activeColor: isAtCap ? 'border-[#F23645]/60' : 'border-[#089981]/60',
    },
    {
      id: 'SIZER',
      title: '3. SIZER',
      subtitle: `Paper Basis: $${paperCapital.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      badge: 'ATR-RISK',
      badgeClass: 'text-[#00E5FF] border-[#00E5FF]/40 bg-[#00E5FF]/10',
      icon: DollarSign,
      activeColor: 'border-[#00E5FF]/60',
    },
    {
      id: 'EXECUTOR',
      title: '4. EXECUTOR',
      subtitle: latestLog ? `${latestLog.action} ${latestLog.side || ''}` : 'IDLE / READY',
      badge: latestLog?.action || 'READY',
      badgeClass:
        latestLog?.action === 'ENTER'
          ? 'text-[#00E5FF] border-[#00E5FF]/50 bg-[#00E5FF]/15'
          : latestLog?.action === 'EXIT'
          ? (latestLog.pnlUsd ?? 0) >= 0
            ? 'text-[#089981] border-[#089981]/50 bg-[#089981]/15'
            : 'text-[#F23645] border-[#F23645]/50 bg-[#F23645]/15'
          : 'text-[#F59E0B] border-[#F59E0B]/40 bg-[#F59E0B]/10',
      icon: Zap,
      activeColor: 'border-[#A855F7]/60',
    },
    {
      id: 'LOGGER',
      title: '5. LOGGER',
      subtitle: latestLog ? latestLog.reason.slice(0, 32) : 'Awaiting tick...',
      badge: latestLog?.sizePctEquity ? `${latestLog.sizePctEquity.toFixed(1)}%` : 'SOT',
      badgeClass: 'text-[#8B95A5] border-[#263042] bg-[#131924]',
      icon: Terminal,
      activeColor: 'border-[#089981]/60',
    },
  ];

  return (
    <div className="bg-[#0C1017] border-b border-[#1B2230] px-2.5 py-1.5 select-none">
      <div className="grid grid-cols-5 gap-1.5 items-center">
        {stages.map((st, idx) => {
          const Icon = st.icon;
          return (
            <div key={st.id} className="relative flex items-center">
              <div
                className={`flex-1 bg-[#07090E] border ${
                  isRunning ? st.activeColor : 'border-[#1B2230]'
                } px-2 py-1 transition-colors duration-200`}
              >
                <div className="flex items-center justify-between gap-1">
                  <div className="flex items-center gap-1 min-w-0">
                    <Icon className="w-3 h-3 text-[#8B95A5] shrink-0" />
                    <span className="text-[10px] font-semibold tracking-wider text-[#E6EDF3] truncate">
                      {st.title}
                    </span>
                  </div>
                  <span
                    className={`text-[9px] font-mono tabular-nums px-1 py-0.2 border uppercase shrink-0 ${st.badgeClass}`}
                  >
                    {st.badge}
                  </span>
                </div>
                <div className="text-[10px] font-mono tabular-nums text-[#8B95A5] truncate mt-0.5">
                  {st.subtitle}
                </div>
              </div>

              {idx < stages.length - 1 && (
                <div className="w-2.5 h-0.5 bg-[#1B2230] relative overflow-hidden shrink-0 mx-0.5">
                  <div
                    className={`absolute inset-y-0 w-2 bg-gradient-to-r from-transparent via-[#00E5FF] to-transparent ${
                      isRunning ? 'animate-pipeline-packet' : 'opacity-40'
                    }`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {filteredByMax20Count > 0 && (
        <div className="mt-1 flex items-center justify-between bg-[#F59E0B]/10 border border-[#F59E0B]/30 px-2 py-0.5 text-[10px] font-mono tabular-nums text-[#F59E0B]">
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3 shrink-0" />
            <span>
              M2 HARD-CAP AKTIV: {filteredByMax20Count} Signale als FILTERED blockiert (Max {maxConcurrentTrades} gleichzeitige Trades erreicht)
            </span>
          </div>
          <span>CosPhi-Chop gefiltert: {filteredByChopCount}</span>
        </div>
      )}
    </div>
  );
});
