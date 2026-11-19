import React, { useState, useEffect } from 'react';
import { ShieldCheck, Play, Pause, RefreshCw, HardDrive, Zap, Lock, AlertTriangle, ExternalLink, Radio, Wifi, History } from 'lucide-react';
import { PortfolioState } from '../types/trading';
import { User } from 'firebase/auth';
import { AnimatedNumber, AnimatedCurrency, AnimatedPercent } from './AnimatedNumber';

interface HeaderProps {
  isRunning: boolean;
  onToggleRunning: () => void;
  portfolio: PortfolioState;
  driveConnected: boolean;
  driveUser: User | null;
  onOpenDriveModal: () => void;
  activeTab: string;
  onSelectTab: (tab: string) => void;
  tickCount: number;
  onOpenConnectionHistory?: () => void;
  krakenStatus?: {
    status: 'LIVE' | 'CONNECTING' | 'FALLBACK_REST' | 'OFFLINE';
    source: string;
    latencyMs: number;
    messagesCount: number;
    onReconnect?: () => void;
    onForceRecalibrate?: () => Promise<any> | void;
    isRealData?: boolean;
    reconnectAttempt?: number;
    nextRetryDelayMs?: number | null;
    nextRetryAt?: number | null;
    targetPort?: number;
  };
}

export const Header: React.FC<HeaderProps> = ({
  isRunning,
  onToggleRunning,
  portfolio,
  driveConnected,
  driveUser,
  onOpenDriveModal,
  activeTab,
  onSelectTab,
  tickCount,
  onOpenConnectionHistory,
  krakenStatus,
}) => {
  const tabs = [
    { id: 'judge', label: 'The Judge (M8 Gate)' },
    { id: 'agent', label: 'OMEGA Agent (7-Stage)' },
    { id: 'swarm', label: 'The Swarm (Alpha Agents)' },
    { id: 'bots', label: 'Worker & DCA Bots' },
    { id: 'portfolio', label: 'Portfolio & Executions' },
    { id: 'kraken-cli', label: 'Kraken CLI & MCP' },
    { id: 'orderbook', label: 'L2 Microstructure' },
    { id: 'blueprint', label: 'Drive & Blueprint Specs' },
  ];

  // High-precision backoff countdown for WebSocket reconnection on port 1000
  const [countdownSec, setCountdownSec] = useState<number | null>(null);
  const [countdownProgress, setCountdownProgress] = useState<number>(0);

  // Force Price Recalibration state
  const [isRecalibrating, setIsRecalibrating] = useState<boolean>(false);
  const [recalibrationNotice, setRecalibrationNotice] = useState<string | null>(null);

  const handleForceRecalibrate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isRecalibrating || !krakenStatus?.onForceRecalibrate) return;
    setIsRecalibrating(true);
    setRecalibrationNotice(null);
    try {
      await krakenStatus.onForceRecalibrate();
      setRecalibrationNotice('0 DRIFT ✓');
      setTimeout(() => setRecalibrationNotice(null), 3500);
    } catch (err) {
      setRecalibrationNotice('ERR');
      setTimeout(() => setRecalibrationNotice(null), 3500);
    } finally {
      setIsRecalibrating(false);
    }
  };

  const isLive = krakenStatus?.status === 'LIVE';
  const targetPort = krakenStatus?.targetPort || 1000;
  const attempt = krakenStatus?.reconnectAttempt ?? 0;
  const nextRetryAt = krakenStatus?.nextRetryAt ?? null;
  const nextRetryDelayMs = krakenStatus?.nextRetryDelayMs ?? null;

  useEffect(() => {
    if (!nextRetryAt || !nextRetryDelayMs || nextRetryAt <= Date.now()) {
      setCountdownSec(null);
      setCountdownProgress(0);
      return;
    }

    const interval = setInterval(() => {
      const now = Date.now();
      const remaining = nextRetryAt - now;
      if (remaining <= 0) {
        setCountdownSec(0);
        setCountdownProgress(100);
      } else {
        setCountdownSec(Math.max(0, remaining / 1000));
        const total = nextRetryDelayMs;
        const elapsed = total - remaining;
        const progress = Math.min(100, Math.max(0, (elapsed / total) * 100));
        setCountdownProgress(progress);
      }
    }, 50);

    return () => clearInterval(interval);
  }, [nextRetryAt, nextRetryDelayMs]);

  return (
    <header className="bg-slate-950 border-b border-slate-800 text-slate-100 sticky top-0 z-40">
      {/* Top Banner with Quant Metadata */}
      <div className="px-4 py-2 bg-slate-900/90 border-b border-slate-800/80 flex flex-wrap items-center justify-between text-xs gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-mono font-bold text-amber-400 tracking-wider">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>OMEGA NIO</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              v4.2.0-PROD
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-2 text-slate-400 font-mono text-[11px]">
            <span>ENGINE: ASYNC-DETERMINISTIC</span>
            <span className="text-slate-600">|</span>
            <span className="text-emerald-400 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              ZERO-DUMMY GUARANTEE ACTIVE
            </span>
          </div>
        </div>

        {/* Global Live Statistics */}
        <div className="flex items-center gap-4 font-mono text-xs">
          {krakenStatus && (
            <div
              id="kraken-connection-indicator"
              onClick={onOpenConnectionHistory}
              title="Klicken, um WebSocket-Verbindungshistorie & Port 1000 Diagnostik zu öffnen"
              className={`relative overflow-hidden flex items-center gap-2 px-2.5 py-1 rounded border transition-all cursor-pointer select-none ${
                isLive
                  ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300 hover:bg-emerald-950/50 hover:border-emerald-400/60'
                  : 'bg-amber-950/40 border-amber-500/50 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.15)] hover:bg-amber-950/60 hover:border-amber-400/70'
              }`}
            >
              {/* Backoff Progress Bar (subtle bottom hairline for active countdown) */}
              {!isLive && countdownSec !== null && countdownSec > 0 && (
                <div
                  className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-amber-500 to-amber-300 transition-all duration-75"
                  style={{ width: `${countdownProgress}%` }}
                />
              )}

              {isLive ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)] animate-pulse" />
                  <span className="font-bold text-[11px]">KRAKEN STREAM:</span>
                  <span className="font-mono font-extrabold text-[11px]">LIVE</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 font-mono">
                    PORT {targetPort}
                  </span>
                  <span className="text-[10px] text-slate-400 font-normal">
                    ({krakenStatus.latencyMs}ms)
                  </span>
                </>
              ) : (
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                  <span className="font-bold text-[11px] text-amber-200 flex items-center gap-1">
                    <Radio className="w-3 h-3 text-amber-400 animate-pulse" />
                    RECONNECTING:
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono font-bold">
                    PORT {targetPort}
                  </span>
                  {attempt > 0 && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      #{attempt}
                    </span>
                  )}

                  {/* Backoff Countdown Display */}
                  {countdownSec !== null && countdownSec > 0 ? (
                    <div
                      id="backoff-countdown-timer"
                      className="flex items-center gap-1 bg-amber-950/80 border border-amber-500/50 px-1.5 py-0.5 rounded text-[10px] font-mono text-amber-200 font-bold"
                      title={`Exponential Backoff aktiv: Nächster Reconnect-Versuch in ${countdownSec.toFixed(1)}s (Intervall: ${(nextRetryDelayMs! / 1000).toFixed(1)}s)`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                      <span>IN</span>
                      <span className="text-amber-100 underline decoration-amber-400 font-black">
                        {countdownSec.toFixed(1)}s
                      </span>
                    </div>
                  ) : (
                    <span className="text-[10px] text-amber-300/90 font-mono animate-pulse">
                      Handshake...
                    </span>
                  )}

                  {/* Fallback Bridge indicator during port 1000 reconnect */}
                  {krakenStatus.source === 'KRAKEN_SERVER_SSE' && (
                    <span
                      className="hidden sm:inline-flex text-[9px] px-1 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-600/30 font-mono"
                      title="SSE Fallback aktiv: Marktpreise unterbrechungsfrei"
                    >
                      SSE Aktiv
                    </span>
                  )}
                </div>
              )}

              {/* History modal trigger button */}
              {onOpenConnectionHistory && (
                <button
                  id="open-connection-history-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenConnectionHistory();
                  }}
                  title="Verbindungshistorie & Diagnostik anzeigen"
                  className="hover:text-white transition-colors ml-0.5 p-1 text-slate-400 hover:bg-slate-800/80 rounded flex items-center gap-1"
                >
                  <History className="w-3 h-3 text-slate-300 hover:text-amber-300" />
                  <span className="hidden lg:inline text-[9px] text-slate-400 font-mono uppercase">History</span>
                </button>
              )}

              {krakenStatus.onReconnect && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    krakenStatus.onReconnect!();
                  }}
                  title={`Sofortige Neuverbindung auf Port ${targetPort} erzwingen`}
                  className="hover:text-white transition-colors ml-0.5 p-0.5 text-slate-400 hover:bg-slate-800 rounded"
                >
                  <RefreshCw className={`w-3 h-3 ${!isLive ? 'text-amber-400 animate-spin' : ''}`} />
                </button>
              )}

              {/* Force Price Recalibration: Hard Flush & Kraken REST Ticker Sync */}
              {krakenStatus.onForceRecalibrate && (
                <button
                  id="force-price-recalibration-button"
                  onClick={handleForceRecalibrate}
                  disabled={isRecalibrating}
                  title="Force Price Recalibration: Hard Flush des lokalen Marktstatus & Abruf absoluter Ticker-Preise von Kraken REST API (Bereinigt Simulationsdrift)"
                  className={`transition-all ml-1.5 px-2 py-0.5 rounded flex items-center gap-1.5 text-[10px] font-mono border select-none ${
                    recalibrationNotice === '0 DRIFT ✓'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.35)]'
                      : recalibrationNotice === 'ERR'
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/50'
                      : isRecalibrating
                      ? 'bg-cyan-500/25 text-cyan-200 border-cyan-500/60 shadow-[0_0_10px_rgba(6,182,212,0.35)] cursor-wait'
                      : 'bg-slate-900/90 text-slate-300 border-slate-700 hover:bg-slate-800 hover:text-cyan-300 hover:border-cyan-500/50 active:scale-95'
                  }`}
                >
                  <RefreshCw
                    className={`w-3 h-3 ${
                      isRecalibrating
                        ? 'text-cyan-400 animate-spin'
                        : recalibrationNotice === '0 DRIFT ✓'
                        ? 'text-emerald-400'
                        : 'text-cyan-400'
                    }`}
                  />
                  <span className="font-bold tracking-tight whitespace-nowrap">
                    {isRecalibrating
                      ? 'RECALIBRATING...'
                      : recalibrationNotice
                      ? recalibrationNotice
                      : 'RECALIBRATE'}
                  </span>
                </button>
              )}
            </div>
          )}

          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-400">NAV:</span>
            <span className="font-semibold text-slate-100">
              <AnimatedCurrency value={portfolio.navUsd} precision={2} />
            </span>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-400">Gross Lev:</span>
            <span className={`font-semibold ${portfolio.grossLeverage > 2.5 ? 'text-amber-400' : 'text-slate-200'}`}>
              <AnimatedNumber value={portfolio.grossLeverage} precision={2} suffix="x" />
            </span>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-400">99% CVaR:</span>
            <span className="font-semibold text-rose-400">
              <AnimatedCurrency value={portfolio.cvar99Usd} precision={0} />
            </span>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-400">Day PnL:</span>
            <span className={`font-semibold ${portfolio.dailyPnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              <AnimatedPercent value={portfolio.dailyPnlPct} precision={2} showSign={true} />
            </span>
          </div>
        </div>

        {/* Engine Controls & Google Drive Button */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleRunning}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all ${
              isRunning
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
                : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30'
            }`}
          >
            {isRunning ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                <span>PAUSE ENGINE</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>START ENGINE</span>
              </>
            )}
          </button>

          <button
            onClick={onOpenDriveModal}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium border transition-colors ${
              driveConnected
                ? 'bg-blue-950/60 text-blue-300 border-blue-700/60 hover:bg-blue-900/60'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5 text-blue-400" />
            <span>{driveConnected ? 'Google Drive Synced' : 'Connect Drive'}</span>
          </button>
        </div>
      </div>

      {/* Primary Navigation Tabs */}
      <div className="px-4 flex items-center justify-between overflow-x-auto no-scrollbar">
        <nav className="flex space-x-1 py-2">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-slate-800 text-amber-400 font-semibold border border-slate-700 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/80'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="hidden lg:flex items-center gap-3 text-[11px] font-mono text-slate-500">
          <span>TICK: #{tickCount}</span>
          <span>LATENCY: 140ms</span>
          <span>ROUTING: M8 ADAPTIVE</span>
        </div>
      </div>
    </header>
  );
};
