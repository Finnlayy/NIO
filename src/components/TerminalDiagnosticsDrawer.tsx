import React from 'react';
import {
  DataProviderId,
  ProviderAttemptTrace,
  ScreenerScheduleStatus,
  BacktestResult,
} from '../types/terminal';
import { SystemMemoryTelemetry } from '../services/terminalClient';
import { X, Server, CheckCircle2, Terminal, Cpu, RefreshCw, Activity } from 'lucide-react';

interface TerminalDiagnosticsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeProvider: DataProviderId;
  cascadeTrace: ProviderAttemptTrace[];
  screenerStatus: ScreenerScheduleStatus | null;
  backtestResult: BacktestResult | null;
  wsConnected: boolean;
  systemLogs: string[];
  memoryTelemetry?: SystemMemoryTelemetry | null;
  onTriggerGcSweep?: () => void;
}

const CASCADE_ORDER: Array<{
  id: DataProviderId;
  rank: number;
  name: string;
  scope: string;
  endpoint: string;
}> = [
  {
    id: 'KRAKEN',
    rank: 1,
    name: 'Kraken Spot & Futures',
    scope: 'Primary Crypto Spot & Perpetuals (BTC/USD, ETH/USD, SOL/USD, AVAX/USD)',
    endpoint: 'api.kraken.com / demo-futures.kraken.com',
  },
  {
    id: 'CCXT',
    rank: 2,
    name: 'CCXT Unified Exchange Aggregator',
    scope: 'Perpetual Futures & Altcoins (PEPEUSDT.P, BTCUSDT.P, HYPE/USD)',
    endpoint: 'ccxt.pro multi-exchange router',
  },
  {
    id: 'MEXC',
    rank: 3,
    name: 'MEXC Global OpenAPI v3 & Contract',
    scope: 'Spot & Inverse/Linear Perpetuals (BTCUSDT, PEPE_USDT, KAS/USDT)',
    endpoint: 'api.mexc.com/api/v3/klines / contract.mexc.com/api/v1/contract',
  },
  {
    id: 'CMC',
    rank: 4,
    name: 'CoinMarketCap Pro & DEXscan Engine',
    scope: 'Ranked Crypto Assets, DEX On-Chain Pools & Global Liquidity (TON/USD, RENDER/USD, BONK/SOL, WIF/SOL, BRETT/ETH)',
    endpoint: 'pro-api.coinmarketcap.com / api.coinmarketcap.com/data-api/v3',
  },
  {
    id: 'GAINIUM',
    rank: 5,
    name: 'Gainium DCA & Grid Feed',
    scope: 'Bot-optimierte Liquiditäts-Paare (LINK/USD, DOGE/USD)',
    endpoint: 'api.gainium.io/v1/market',
  },
  {
    id: 'BINANCE',
    rank: 6,
    name: 'Binance USD-M & Spot',
    scope: 'High-Velocity Perps & Spot (ZECUSDT.P, SUIUSDT.P, XRP/USD)',
    endpoint: 'fapi.binance.com / data-api.binance.vision',
  },
  {
    id: 'ALPACA',
    rank: 7,
    name: 'Alpaca Markets SIP/IEX',
    scope: 'US-Aktien & Tech-Leader (NVDA, AAPL)',
    endpoint: 'data.alpaca.markets/v2/stocks',
  },
  {
    id: 'ALPHAVANTAGE',
    rank: 8,
    name: 'Alpha Vantage FX & Commodities',
    scope: 'Forex & Rohstoffe (EUR/USD, XAU/USD)',
    endpoint: 'alphavantage.co/query',
  },
];

function formatUptime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
}

export const TerminalDiagnosticsDrawer: React.FC<TerminalDiagnosticsDrawerProps> = ({
  isOpen,
  onClose,
  activeProvider,
  cascadeTrace,
  screenerStatus,
  wsConnected,
  systemLogs,
  memoryTelemetry,
  onTriggerGcSweep,
}) => {
  if (!isOpen) return null;

  const browserHeapMb =
    typeof window !== 'undefined' && (window.performance as any)?.memory?.usedJSHeapSize
      ? Math.round(((window.performance as any).memory.usedJSHeapSize / (1024 * 1024)) * 10) / 10
      : null;

  return (
    <div className="fixed inset-0 z-50 bg-black/75 flex justify-end select-none">
      <div className="w-full max-w-2xl bg-[#0C1017] border-l border-[#1B2230] h-full flex flex-col text-[#E6EDF3]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1B2230] bg-[#07090E]">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-[#00E5FF]" />
            <span className="text-xs font-bold tracking-wider uppercase">
              SYSTEM-DIAGNOSE, 24/7 RAM-WATCHDOG & 8-STUFEN DATEN-KASKADE
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-[#8B95A5] hover:text-[#E6EDF3] border border-[#1B2230] bg-[#0C1017]"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs">
          {/* 0. 24/7 Memory & Uptime Stability Watchdog */}
          <div className="bg-[#07090E] border border-[#00E5FF]/40 p-3">
            <div className="text-[11px] font-semibold text-[#00E5FF] uppercase mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-[#00E5FF]" />
                <span>0. 24/7 Memory & Uptime Watchdog (Anti-Crash Guard)</span>
              </span>
              <div className="flex items-center gap-2">
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-bold border ${
                    memoryTelemetry?.status === 'CRITICAL'
                      ? 'border-[#F23645] text-[#F23645] bg-[#F23645]/15'
                      : memoryTelemetry?.status === 'ELEVATED'
                      ? 'border-[#F59E0B] text-[#F59E0B] bg-[#F59E0B]/15'
                      : 'border-[#089981] text-[#089981] bg-[#089981]/15'
                  }`}
                >
                  24/7 STATUS: {memoryTelemetry?.status || 'HEALTHY'}
                </span>
                {onTriggerGcSweep && (
                  <button
                    type="button"
                    onClick={onTriggerGcSweep}
                    className="px-2 py-0.5 bg-[#00E5FF]/15 hover:bg-[#00E5FF]/30 border border-[#00E5FF] text-[#00E5FF] text-[10px] font-bold flex items-center gap-1"
                  >
                    <RefreshCw className="w-2.5 h-2.5" />
                    <span>RAM SWEEP</span>
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] tabular-nums">
              <div className="bg-[#0C1017] p-2 border border-[#1B2230]">
                <span className="text-[#8B95A5] text-[10px] block">Server V8 Heap:</span>
                <span className="text-[#00E5FF] font-bold">
                  {memoryTelemetry ? `${memoryTelemetry.heapUsedMb} / ${memoryTelemetry.heapTotalMb} MB` : '—'}
                </span>
              </div>
              <div className="bg-[#0C1017] p-2 border border-[#1B2230]">
                <span className="text-[#8B95A5] text-[10px] block">Server RSS / Limit:</span>
                <span className="text-[#E6EDF3] font-bold">
                  {memoryTelemetry ? `${memoryTelemetry.rssMb} MB` : '—'}
                </span>
              </div>
              <div className="bg-[#0C1017] p-2 border border-[#1B2230]">
                <span className="text-[#8B95A5] text-[10px] block">Browser JS Heap:</span>
                <span className="text-[#089981] font-bold">
                  {browserHeapMb !== null ? `${browserHeapMb} MB` : 'OPTIMIERT (1Hz)'}
                </span>
              </div>
              <div className="bg-[#0C1017] p-2 border border-[#1B2230]">
                <span className="text-[#8B95A5] text-[10px] block">Server Uptime / Sweeps:</span>
                <span className="text-[#E6EDF3] font-bold">
                  {memoryTelemetry
                    ? `${formatUptime(memoryTelemetry.uptimeSec)} (${memoryTelemetry.autoSweepsCount}x)`
                    : '—'}
                </span>
              </div>
            </div>

            {memoryTelemetry && (
              <div className="mt-2 pt-2 border-t border-[#1B2230] flex items-center justify-between text-[10px] text-[#8B95A5]">
                <span>
                  Aktive Streams: WS({memoryTelemetry.wsClientsCount}) · Swarm({memoryTelemetry.swarmWsClientsCount}) · SSE({memoryTelemetry.sseClientsCount})
                </span>
                <span className="text-[#089981] flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  Auto-Hygiene alle 15s aktiv (Max Ring-Buffers: ≤100)
                </span>
              </div>
            )}
          </div>

          {/* 8-Stage Provider Cascade Architecture */}
          <div className="bg-[#07090E] border border-[#1B2230] p-3">
            <div className="text-[11px] font-semibold text-[#00E5FF] uppercase mb-2 flex items-center justify-between">
              <span>1. Deterministische 8-Provider Daten-Kaskade (Inkl. MEXC)</span>
              <span className="text-[#089981]">AKTIV: {activeProvider}</span>
            </div>
            <div className="space-y-1.5">
              {CASCADE_ORDER.map((p) => {
                const isCurrent = p.id === activeProvider;
                return (
                  <div
                    key={p.id}
                    className={`flex items-center justify-between px-2.5 py-1.5 border ${
                      isCurrent
                        ? 'border-[#00E5FF]/60 bg-[#00E5FF]/10 text-[#E6EDF3]'
                        : 'border-[#1B2230] bg-[#0C1017] text-[#8B95A5]'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-[#00E5FF]">#{p.rank}</span>
                        <span className="text-[11px] font-semibold text-[#E6EDF3]">{p.name}</span>
                        <span className="text-[9px] px-1 border border-[#263042] text-[#8B95A5]">
                          {p.id}
                        </span>
                      </div>
                      <div className="text-[10px] text-[#8B95A5] truncate mt-0.5">{p.scope}</div>
                    </div>
                    <div className="text-right shrink-0 ml-2">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 border ${
                          isCurrent
                            ? 'border-[#089981]/50 bg-[#089981]/15 text-[#089981]'
                            : 'border-[#263042] text-[#8B95A5]'
                        }`}
                      >
                        {isCurrent ? 'PRIMÄR AKTIV' : 'BEREIT (SCREENER)'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Last Cascade Trace */}
          <div className="bg-[#07090E] border border-[#1B2230] p-3">
            <div className="text-[11px] font-semibold text-[#E6EDF3] uppercase mb-1.5">
              2. Letzter Kaskaden-Abruf-Trace (Kraken → CCXT → CoinMarketCap → Gainium → Binance → Alpaca → Alpha Vantage)
            </div>
            <div className="space-y-1 text-[11px] text-[#8B95A5]">
              {cascadeTrace.length > 0 ? (
                cascadeTrace.map((trace, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 border-b border-[#1B2230]/50 py-1">
                    <div className="flex items-center gap-2">
                      <CheckCircle2
                        className={`w-3 h-3 shrink-0 ${
                          trace.status === 'SUCCESS' ? 'text-[#089981]' : 'text-[#F59E0B]'
                        }`}
                      />
                      <span className="font-bold text-[#00E5FF]">{trace.provider}</span>
                      <span className="text-[#E6EDF3]">{trace.message}</span>
                    </div>
                    <span className="text-[10px] text-[#8B95A5] shrink-0">
                      {trace.latencyMs}ms · {trace.status}
                    </span>
                  </div>
                ))
              ) : (
                <div>Noch kein Kaskaden-Trace aufgezeichnet.</div>
              )}
            </div>
          </div>

          {/* Scheduled Multi-Source Screener Telemetry */}
          <div className="bg-[#07090E] border border-[#1B2230] p-3">
            <div className="text-[11px] font-semibold text-[#E6EDF3] uppercase mb-1.5 flex items-center justify-between">
              <span>3. Automatisierter Multi-Source Screener (Cron-Schedule)</span>
              <span className="text-[#089981]">
                {screenerStatus?.enabled ? `AKTIV (${screenerStatus.intervalSec}s)` : 'PAUSIERT'}
              </span>
            </div>
            {screenerStatus && (
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="bg-[#0C1017] p-2 border border-[#1B2230]">
                  <span className="text-[#8B95A5] block">Letzter Scan:</span>
                  <span className="text-[#E6EDF3]">
                    {new Date(screenerStatus.lastRunAt).toLocaleTimeString('de-DE')}
                  </span>
                </div>
                <div className="bg-[#0C1017] p-2 border border-[#1B2230]">
                  <span className="text-[#8B95A5] block">Gescannte Symbole (6 Quellen):</span>
                  <span className="text-[#00E5FF]">
                    {screenerStatus.tickers.length} Instrumente · {screenerStatus.totalRuns} Zyklen
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* System & Execution Logs */}
          <div className="bg-[#07090E] border border-[#1B2230] p-3">
            <div className="text-[11px] font-semibold text-[#E6EDF3] uppercase mb-1.5 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-[#00E5FF]" />
                4. Echtzeit-System- & Ausführungs-Protokoll
              </span>
              <span className={wsConnected ? 'text-[#089981]' : 'text-[#F59E0B]'}>
                Kraken WS: {wsConnected ? 'VERBUNDEN' : 'REST-POLLING'}
              </span>
            </div>
            <div className="max-h-56 overflow-y-auto space-y-1 bg-[#0C1017] p-2 border border-[#1B2230] text-[10px]">
              {systemLogs.map((log, index) => (
                <div key={index} className="text-[#8B95A5] border-b border-[#1B2230]/50 pb-0.5">
                  {log}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
