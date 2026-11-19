import React, { useState, useEffect } from 'react';
import {
  Terminal,
  RefreshCw,
  Cpu,
  Layers,
  ShieldCheck,
  Zap,
  TrendingUp,
  Database,
  ArrowRight,
  Code,
  CheckCircle,
  AlertCircle,
  Play,
  Copy,
  ChevronRight,
  Wallet,
  Scale,
  ListOrdered,
  BookOpen,
  RotateCcw,
  Bot,
  Activity,
  History,
  Wrench,
  Search,
  Sliders,
  Eye,
  Check,
  Sparkles,
} from 'lucide-react';
import {
  KrakenCliCommand,
  KrakenAccountSummary,
  KrakenCliExecutionResult,
  KrakenPaperStatusResponse,
  SituationCycleResult,
  KrakenToolDefinition,
} from '../types/krakenCli';
import {
  KRAKEN_COMMAND_REGISTRY,
  KRAKEN_COMMAND_MAP,
  executeKrakenCliCommand,
  fetchKrakenAccountSummary,
  fetchKrakenPaperStatus,
  fetchKrakenPaperHistory,
  executeKrakenPaperBuy,
  executeKrakenPaperSell,
  executeKrakenPaperReset,
  executeSituationCycle,
  formatKrakenCommandLine,
  executeKrakenTool,
  fetchKrakenJournal,
} from '../services/krakenCliRouter';
import { KRAKEN_TOOLS_CATALOG } from '../data/krakenToolsCatalog';

export const KrakenCliView: React.FC = () => {
  const [summary, setSummary] = useState<KrakenAccountSummary | null>(null);
  const [paperStatus, setPaperStatus] = useState<KrakenPaperStatusResponse | null>(null);
  const [paperHistory, setPaperHistory] = useState<any[]>([]);
  const [loadingSummary, setLoadingSummary] = useState<boolean>(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Command Runner State
  const [selectedCommand, setSelectedCommand] = useState<KrakenCliCommand>('paper');
  const [commandArgs, setCommandArgs] = useState<string>('status');
  const [workspace, setWorkspace] = useState<string>('default');
  const [outputFormat, setOutputFormat] = useState<'json' | 'table'>('json');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<KrakenCliExecutionResult | null>(null);
  const [activeTab, setActiveTab] = useState<
    'paper-book' | 'balances' | 'positions' | 'situation-cycle' | 'terminal' | 'routing-table' | 'tools-catalog'
  >('paper-book');
  const [copiedNotification, setCopiedNotification] = useState<boolean>(false);

  // 150+ Tools Catalog & Skills State
  const [toolSearch, setToolSearch] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedToolForExec, setSelectedToolForExec] = useState<KrakenToolDefinition | null>(null);
  const [toolParams, setToolParams] = useState<Record<string, any>>({
    pair: 'BTC/USD',
    volume: 0.01,
    price: 80250,
    investment: 100,
    dcaSteps: 60,
    name: 'DCA Bot Alpha (Custom)',
    direction: 'LONG',
    leverage: 1,
  });
  const [isExecutingTool, setIsExecutingTool] = useState<boolean>(false);
  const [toolExecResult, setToolExecResult] = useState<any | null>(null);

  // Situation-Cycle State
  const [isCycling, setIsCycling] = useState<boolean>(false);
  const [cycleHistory, setCycleHistory] = useState<SituationCycleResult[]>([]);
  const [cycleError, setCycleError] = useState<string | null>(null);

  // Paper order form
  const [orderPair, setOrderPair] = useState<string>('BTC/USD');
  const [orderVol, setOrderVol] = useState<number>(0.05);

  // Load initial account summary from CLI (Source of Truth)
  const loadSummary = async () => {
    setLoadingSummary(true);
    setSummaryError(null);
    try {
      const [sumData, paperData, histData] = await Promise.all([
        fetchKrakenAccountSummary(),
        fetchKrakenPaperStatus(),
        fetchKrakenPaperHistory(),
      ]);
      setSummary(sumData);
      setPaperStatus(paperData);
      setPaperHistory(histData || []);
    } catch (err: any) {
      setSummaryError(err.message || 'Fehler beim Abrufen der Kraken CLI Kontodaten');
    } finally {
      setLoadingSummary(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  const handleRunCommand = async (cmdToRun?: KrakenCliCommand) => {
    const targetCmd = cmdToRun || selectedCommand;
    setIsExecuting(true);
    setExecutionResult(null);

    const splitArgs = commandArgs
      .trim()
      .split(/\s+/)
      .filter((s) => s.length > 0);

    try {
      const result = await executeKrakenCliCommand({
        command: targetCmd,
        args: splitArgs,
        options: {
          output: outputFormat,
          workspace,
        },
        internalContext: {
          initiatedBy: 'ORCHESTRATOR',
          timestamp: Date.now(),
        },
      });

      setExecutionResult(result);
      loadSummary();
    } catch (err: any) {
      setExecutionResult({
        command: targetCmd,
        fullCommandLine: `kraken -o ${outputFormat} --workspace ${workspace} ${targetCmd} ${commandArgs}`.trim(),
        executedAt: new Date().toISOString(),
        durationMs: 0,
        exitCode: 1,
        isRealBinary: false,
        data: null,
        rawStdout: '',
        error: err.message,
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const handleExecutePaperOrder = async (side: 'buy' | 'sell') => {
    setIsExecuting(true);
    try {
      if (side === 'buy') {
        await executeKrakenPaperBuy(orderPair, orderVol);
      } else {
        await executeKrakenPaperSell(orderPair, orderVol);
      }
      await loadSummary();
    } catch (err: any) {
      alert(`Fehler bei Paper Order: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleResetPaper = async () => {
    if (!confirm('Soll das Paper-Ledger der Kraken CLI wirklich auf 100,000 USD zurückgesetzt werden?')) return;
    setIsExecuting(true);
    try {
      await executeKrakenPaperReset(100000);
      await loadSummary();
    } catch (err: any) {
      alert(`Fehler beim Reset: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleTriggerSituationCycle = async () => {
    setIsCycling(true);
    setCycleError(null);
    try {
      const cycleRes = await executeSituationCycle();
      setCycleHistory((prev) => [cycleRes, ...prev].slice(0, 20));
      await loadSummary();
    } catch (err: any) {
      setCycleError(err.message || 'Situation-Cycle Ausführung fehlgeschlagen');
    } finally {
      setIsCycling(false);
    }
  };

  const handleCopyCommand = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedNotification(true);
    setTimeout(() => setCopiedNotification(false), 2000);
  };

  const currentCommandLine = formatKrakenCommandLine(
    selectedCommand,
    commandArgs ? commandArgs.trim().split(/\s+/) : [],
    { output: outputFormat, workspace }
  );

  return (
    <div className="space-y-4">
      {/* Top Banner: Orchestrator Mode & Kraken Startup Status */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-bold font-mono text-slate-100">Kraken CLI 0.3.2 Engine (Master-Plan SoT)</h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />
                  CLI IST SOURCE OF TRUTH
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                  AKTIVES BUCH: {summary?.active_book || 'PAPER'}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  WORKSPACE: {summary?.workspace.active_workspace || workspace}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 max-w-3xl">
                Reine Orchestrierungs-Schicht ohne selbstgemachte Paper-Ledger oder 50k-Seeds. Paper-Kapital entstammt exklusiv{' '}
                <code className="text-amber-300 font-mono">kraken paper status</code>, Live-Kapital aus{' '}
                <code className="text-emerald-300 font-mono">kraken balance / trade-balance</code>.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start lg:self-center shrink-0">
            <button
              id="trigger-situation-cycle-btn"
              onClick={handleTriggerSituationCycle}
              disabled={isCycling}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 transition shadow-sm"
            >
              <Activity className={`w-3.5 h-3.5 ${isCycling ? 'animate-spin' : ''}`} />
              <span>{isCycling ? 'Zyklus läuft...' : 'Situation-Cycle ausführen'}</span>
            </button>
            <button
              id="refresh-kraken-summary-btn"
              onClick={loadSummary}
              disabled={loadingSummary}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingSummary ? 'animate-spin' : ''}`} />
              <span>CLI Sync</span>
            </button>
          </div>
        </div>

        {/* Diagnostic Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-3 border-t border-slate-800/80 font-mono text-xs">
          <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800/60">
            <span className="text-[10px] text-slate-500 block">KRAKEN TRADING MODE</span>
            <span className="text-slate-200 font-bold mt-0.5 block uppercase">
              {summary?.system_status.trading_mode || 'PAPER'}
            </span>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800/60">
            <span className="text-[10px] text-slate-500 block">SYSTEM STATUS</span>
            <span className="text-emerald-400 font-bold mt-0.5 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              {summary?.system_status.status || 'ONLINE'}
            </span>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800/60">
            <span className="text-[10px] text-slate-500 block">MCP SERVER STATUS</span>
            <span className="text-amber-400 font-bold mt-0.5 flex items-center gap-1">
              <Cpu className="w-3.5 h-3.5" />
              READY (STDIO)
            </span>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800/60">
            <span className="text-[10px] text-slate-500 block">EXECUTION BACKEND</span>
            <span className="text-slate-300 mt-0.5 block truncate">
              {summary?.mode === 'REAL_CLI' ? 'wsl.exe kraken-cli 0.3.2' : 'High-Fidelity CLI 0.3.2'}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-800 pb-2 overflow-x-auto text-xs font-mono">
        <button
          id="kraken-tab-paper"
          onClick={() => setActiveTab('paper-book')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'paper-book'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>Paper-Buch (`kraken paper status`)</span>
        </button>

        <button
          id="kraken-tab-situation"
          onClick={() => setActiveTab('situation-cycle')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'situation-cycle'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Autonomous Situation-Cycle</span>
        </button>

        <button
          id="kraken-tab-balances"
          onClick={() => setActiveTab('balances')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'balances'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Wallet className="w-3.5 h-3.5" />
          <span>Live Balances (`kraken balance`)</span>
        </button>

        <button
          id="kraken-tab-positions"
          onClick={() => setActiveTab('positions')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'positions'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          <span>Live Margin (`kraken trade-balance`)</span>
        </button>

        <button
          id="kraken-tab-terminal"
          onClick={() => setActiveTab('terminal')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'terminal'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>Interaktive CLI Konsole</span>
        </button>

        <button
          id="kraken-tab-routing"
          onClick={() => setActiveTab('routing-table')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'routing-table'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <ListOrdered className="w-3.5 h-3.5" />
          <span>Master Command Map (32+ Befehle)</span>
        </button>

        <button
          id="kraken-tab-tools-catalog"
          onClick={() => setActiveTab('tools-catalog')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition ${
            activeTab === 'tools-catalog'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <Wrench className="w-3.5 h-3.5 text-amber-400" />
          <span>Cursor Skills &amp; 150+ Tools</span>
          <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold border border-amber-500/30">
            150
          </span>
        </button>
      </div>

      {/* TAB: PAPER BOOK (THE SOT FOR PAPER) */}
      {activeTab === 'paper-book' && (
        <div className="space-y-4">
          {/* Key Metrics from kraken paper status */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
              <span className="text-[11px] font-mono text-slate-400 block">Paper NAV (`current_value`)</span>
              <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                ${(paperStatus?.current_value || 100000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] font-mono text-slate-500 mt-0.5 block">
                Initial: ${(paperStatus?.initial_balance || 100000).toLocaleString()}
              </span>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
              <span className="text-[11px] font-mono text-slate-400 block">Verfügbare Liquidität (`cash`)</span>
              <span className="text-xl font-bold font-mono text-emerald-400 mt-1 block">
                ${(paperStatus?.cash || 100000).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] font-mono text-slate-500 mt-0.5 block">
                Trades Gesamt: {paperStatus?.trades_count || 0}
              </span>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
              <span className="text-[11px] font-mono text-slate-400 block">Unrealized P&L</span>
              <span className={`text-xl font-bold font-mono mt-1 block ${(paperStatus?.unrealized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(paperStatus?.unrealized_pnl || 0) >= 0 ? '+' : ''}${(paperStatus?.unrealized_pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] font-mono text-slate-500 mt-0.5 block">
                Realized: ${(paperStatus?.realized_pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg flex flex-col justify-between">
              <div>
                <span className="text-[11px] font-mono text-slate-400 block">Total P&L</span>
                <span className={`text-xl font-bold font-mono mt-1 block ${(paperStatus?.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(paperStatus?.total_pnl || 0) >= 0 ? '+' : ''}${(paperStatus?.total_pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
              <button
                onClick={handleResetPaper}
                disabled={isExecuting}
                className="mt-2 flex items-center justify-center gap-1 text-[10px] font-mono px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 transition"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Paper Ledger Resetten (`kraken paper reset`)</span>
              </button>
            </div>
          </div>

          {/* Quick Order Direct Execution via kraken paper buy / sell */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider mb-2">
              Direkte Paper-Order Platzierung (`kraken paper buy|sell &lt;pair&gt; &lt;vol&gt;`)
            </h3>
            <div className="flex flex-wrap items-center gap-3">
              <div>
                <label className="text-[10px] font-mono text-slate-400 block mb-0.5">Asset Pair</label>
                <select
                  value={orderPair}
                  onChange={(e) => setOrderPair(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200 focus:outline-none"
                >
                  <option value="BTC/USD">BTC/USD</option>
                  <option value="ETH/USD">ETH/USD</option>
                  <option value="SOL/USD">SOL/USD</option>
                  <option value="AVAX/USD">AVAX/USD</option>
                  <option value="XRP/USD">XRP/USD</option>
                  <option value="LINK/USD">LINK/USD</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-slate-400 block mb-0.5">Volumen</label>
                <input
                  type="number"
                  step="0.01"
                  value={orderVol}
                  onChange={(e) => setOrderVol(parseFloat(e.target.value) || 0.01)}
                  className="w-24 bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200 focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2 mt-4">
                <button
                  onClick={() => handleExecutePaperOrder('buy')}
                  disabled={isExecuting}
                  className="px-3 py-1.5 rounded text-xs font-mono font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1"
                >
                  <span>kraken paper buy</span>
                </button>
                <button
                  onClick={() => handleExecutePaperOrder('sell')}
                  disabled={isExecuting}
                  className="px-3 py-1.5 rounded text-xs font-mono font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex items-center gap-1"
                >
                  <span>kraken paper sell</span>
                </button>
              </div>
            </div>
          </div>

          {/* Open Paper Positions */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                  Offene Paper-Positionen (`kraken paper status`)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Gefunden: {paperStatus?.positions?.length || 0}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="py-2.5 px-3">Markt / Pair</th>
                    <th className="py-2.5 px-3">Richtung</th>
                    <th className="py-2.5 px-3 text-right">Volumen</th>
                    <th className="py-2.5 px-3 text-right">Einstiegspreis</th>
                    <th className="py-2.5 px-3 text-right">Aktueller Marktpreis</th>
                    <th className="py-2.5 px-3 text-right">Kosten</th>
                    <th className="py-2.5 px-3 text-right">Unrealized P&L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {paperStatus?.positions && paperStatus.positions.length > 0 ? (
                    paperStatus.positions.map((pos, idx) => (
                      <tr key={`${pos.pair}-${idx}`} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-3 font-bold text-slate-200">{pos.pair}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              pos.type === 'buy'
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            {pos.type.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-200">{pos.vol}</td>
                        <td className="py-2.5 px-3 text-right text-slate-300">
                          ${pos.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-300">
                          ${pos.current_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-300">
                          ${pos.cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td
                          className={`py-2.5 px-3 text-right font-bold ${
                            pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)} ({pos.unrealized_pnl_pct.toFixed(2)}%)
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-slate-500 font-mono">
                        Keine offenen Positionen im CLI-Paper-Ledger
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Paper Trade History */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                  Paper Trade History (`kraken paper history`)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Einträge: {paperHistory.length}
              </span>
            </div>

            <div className="overflow-x-auto max-h-60 overflow-y-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="py-2 px-3">TXID</th>
                    <th className="py-2 px-3">Zeit</th>
                    <th className="py-2 px-3">Pair</th>
                    <th className="py-2 px-3">Typ</th>
                    <th className="py-2 px-3 text-right">Preis</th>
                    <th className="py-2 px-3 text-right">Volumen</th>
                    <th className="py-2 px-3 text-right">Kosten</th>
                    <th className="py-2 px-3 text-right">Realized PnL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {paperHistory.length > 0 ? (
                    paperHistory.map((tr) => (
                      <tr key={tr.txid} className="hover:bg-slate-800/30 transition">
                        <td className="py-2 px-3 text-slate-400 text-[11px]">{tr.txid}</td>
                        <td className="py-2 px-3 text-slate-400">{new Date(tr.time).toLocaleTimeString()}</td>
                        <td className="py-2 px-3 font-semibold text-slate-200">{tr.pair}</td>
                        <td className="py-2 px-3">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tr.type === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                            {tr.type.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-slate-200">${tr.price.toLocaleString()}</td>
                        <td className="py-2 px-3 text-right text-slate-200">{tr.vol}</td>
                        <td className="py-2 px-3 text-right text-slate-300">${tr.cost.toLocaleString()}</td>
                        <td className="py-2 px-3 text-right text-emerald-400">
                          {tr.pnl !== undefined ? `${tr.pnl >= 0 ? '+' : ''}$${tr.pnl}` : '-'}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-4 text-center text-slate-500">
                        Noch keine Paper Trades protokolliert
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB: AUTONOMOUS SITUATION-CYCLE (MASTER-PLAN REQUIREMENT 5) */}
      {activeTab === 'situation-cycle' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold font-mono text-slate-100 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-amber-400" />
                  Autonomer Situation-Cycle (Der Master-Zyklus)
                </h3>
                <p className="text-xs text-slate-400 mt-1 max-w-2xl">
                  Führt den 5-Schritt-Zyklus strikt über die Kraken CLI aus:
                  <br />
                  1. <strong>Observe:</strong> Liest aktives Buch (`kraken paper status` oder `kraken trade-balance`).
                  <br />
                  2. <strong>Universe:</strong> Filtert Paare nach `ordermin`, `costmin` und `liveEligible`.
                  <br />
                  3. <strong>Selection:</strong> Wählt genau 1 (Symbol, Modul) aus dem Swarm.
                  <br />
                  4. <strong>Act:</strong> Führt Order strikt über die CLI Command Map aus (`kraken paper buy|sell` oder `kraken order`).
                  <br />
                  5. <strong>Journal:</strong> Schreibt konsistente Einträge mit TXID und verändertem Buch.
                </p>
              </div>

              <button
                onClick={handleTriggerSituationCycle}
                disabled={isCycling}
                className="flex items-center gap-2 px-4 py-2 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold font-mono text-xs transition shrink-0"
              >
                <Play className={`w-4 h-4 fill-current ${isCycling ? 'animate-pulse' : ''}`} />
                <span>{isCycling ? 'Führe Zyklus aus...' : 'Jetzt Zyklus Starten'}</span>
              </button>
            </div>

            {cycleError && (
              <div className="mt-3 p-3 bg-rose-500/10 border border-rose-500/30 rounded text-rose-300 text-xs font-mono">
                {cycleError}
              </div>
            )}
          </div>

          {/* Cycle Execution Log */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h4 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider mb-3">
              Protokollierte Zyklen ({cycleHistory.length})
            </h4>

            {cycleHistory.length > 0 ? (
              <div className="space-y-3">
                {cycleHistory.map((cycle) => (
                  <div key={cycle.cycleId} className="bg-slate-950 p-3 rounded border border-slate-800/80 font-mono text-xs">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-amber-400">{cycle.cycleId}</span>
                        <span className="text-slate-500 text-[10px]">
                          {new Date(cycle.timestamp).toLocaleTimeString()}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">
                          Modus: {cycle.activeMode}
                        </span>
                      </div>
                      <span className="text-emerald-400 font-bold">
                        NAV: ${cycle.actResult.newCurrentValue.toLocaleString()}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] text-slate-300">
                      <div>
                        <span className="text-slate-500 block">1. Beobachtetes Buch:</span>
                        <span>{cycle.bookObserved.source}</span>
                        <span className="text-slate-400 block font-bold">
                          Freies Kapital: ${cycle.bookObserved.available_capital.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">3. Ausgewähltes Paar & Modul:</span>
                        <span className="font-bold text-slate-100">{cycle.selection.symbol}</span> ({cycle.selection.action})
                        <span className="text-slate-400 block">Modul: {cycle.selection.moduleId}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">4. CLI Ausführung & TXID:</span>
                        <code className="text-amber-300 block">{cycle.actResult.cliCommand}</code>
                        <span className="text-slate-400 block">TXID: {cycle.actResult.txid || 'OK'}</span>
                      </div>
                    </div>

                    <div className="mt-2 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400">
                      <strong>5. Journal:</strong> {cycle.journalEntry.text}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-slate-500 font-mono text-xs">
                Klicke auf "Jetzt Zyklus Starten", um den ersten autonomen Situation-Cycle via Kraken CLI auszuführen.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB: LIVE BALANCES VIEW */}
      {activeTab === 'balances' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Wallet className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                  Kraken Live Spot Balances (`kraken balance -o json`)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Workspace: {summary?.workspace.active_workspace || 'default'}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="py-2.5 px-3">Asset</th>
                    <th className="py-2.5 px-3">Währung</th>
                    <th className="py-2.5 px-3 text-right">Gesamtbestand</th>
                    <th className="py-2.5 px-3 text-right">Verfügbar</th>
                    <th className="py-2.5 px-3 text-right">USD Gegenwert</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {summary?.balances &&
                    Object.entries(summary.balances).map(([assetKey, rawVal]) => {
                      const val = rawVal as { balance: number; currency: string; usd_value?: number; available?: number };
                      return (
                        <tr key={assetKey} className="hover:bg-slate-800/30 transition">
                          <td className="py-2.5 px-3 font-bold text-slate-200 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                            <span>{assetKey}</span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-400">{val.currency}</td>
                          <td className="py-2.5 px-3 text-right text-slate-200 font-semibold">
                            {val.balance.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                          </td>
                          <td className="py-2.5 px-3 text-right text-emerald-400">
                            {val.available !== undefined
                              ? val.available.toLocaleString(undefined, { maximumFractionDigits: 6 })
                              : val.balance.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                          </td>
                          <td className="py-2.5 px-3 text-right text-slate-300 font-medium">
                            ${(val.usd_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB: LIVE MARGIN & POSITIONS */}
      {activeTab === 'positions' && (
        <div className="space-y-4">
          {summary?.trade_balance && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
                <span className="text-[11px] font-mono text-slate-400 block">Total Equity (`trade-balance`)</span>
                <span className="text-xl font-bold font-mono text-slate-100 mt-1 block">
                  ${summary.trade_balance.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
                <span className="text-[11px] font-mono text-slate-400 block">Free Margin (Verfügbar)</span>
                <span className="text-xl font-bold font-mono text-emerald-400 mt-1 block">
                  ${summary.trade_balance.free_margin.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
                <span className="text-[11px] font-mono text-slate-400 block">Unrealized P&L</span>
                <span className={`text-xl font-bold font-mono mt-1 block ${summary.trade_balance.unrealized_profit_loss >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {summary.trade_balance.unrealized_profit_loss >= 0 ? '+' : ''}${summary.trade_balance.unrealized_profit_loss.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
                <span className="text-[11px] font-mono text-slate-400 block">Margin Level Ratio</span>
                <span className="text-xl font-bold font-mono text-amber-400 mt-1 block">
                  {summary.trade_balance.margin_level_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          )}

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider mb-3">
              Aktive Margin & Perpetuals Positionen (`kraken positions -o json`)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="py-2.5 px-3">Position ID</th>
                    <th className="py-2.5 px-3">Markt / Pair</th>
                    <th className="py-2.5 px-3">Typ</th>
                    <th className="py-2.5 px-3 text-right">Volumen</th>
                    <th className="py-2.5 px-3 text-right">Hebel</th>
                    <th className="py-2.5 px-3 text-right">Positionswert</th>
                    <th className="py-2.5 px-3 text-right">Net P&L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {summary?.positions.positions && summary.positions.positions.length > 0 ? (
                    summary.positions.positions.map((pos) => (
                      <tr key={pos.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">{pos.id}</td>
                        <td className="py-2.5 px-3 font-bold text-slate-200">{pos.pair}</td>
                        <td className="py-2.5 px-3">{pos.type.toUpperCase()}</td>
                        <td className="py-2.5 px-3 text-right text-slate-200">{pos.vol}</td>
                        <td className="py-2.5 px-3 text-right text-amber-400 font-bold">{pos.leverage}x</td>
                        <td className="py-2.5 px-3 text-right text-slate-200 font-semibold">${pos.value.toLocaleString()}</td>
                        <td className={`py-2.5 px-3 text-right font-bold ${pos.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          ${pos.net_pnl.toFixed(2)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-slate-500 font-mono">
                        Keine aktiven Live-Positionen auf Kraken gemeldet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB: INTERACTIVE TERMINAL */}
      {activeTab === 'terminal' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider mb-3">
              Kraken CLI Befehls-Ausführer (Interactive Command Runner)
            </h3>

            {/* Command Configuration Bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">Kraken CLI Command</label>
                <select
                  id="kraken-cli-command-select"
                  value={selectedCommand}
                  onChange={(e) => setSelectedCommand(e.target.value as KrakenCliCommand)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500"
                >
                  <optgroup label="Paper Trading (Master-Plan)">
                    <option value="paper">paper (Subcommands: status, buy, sell, history, reset)</option>
                  </optgroup>
                  <optgroup label="Account & Balances">
                    <option value="balance">balance (Spot Balances)</option>
                    <option value="extended-balance">extended-balance (Credits & Holds)</option>
                    <option value="trade-balance">trade-balance (Margin/Equity)</option>
                    <option value="positions">positions (Open Margin Positions)</option>
                    <option value="open-orders">open-orders (Pending Orders)</option>
                    <option value="closed-orders">closed-orders (Order History)</option>
                  </optgroup>
                  <optgroup label="System & Mode">
                    <option value="status">status (Trading Mode & Health)</option>
                    <option value="server-time">server-time (Server Synchronisation)</option>
                    <option value="workspace">workspace (Strategy Environment)</option>
                    <option value="mcp">mcp (Model Context Protocol stdio)</option>
                  </optgroup>
                  <optgroup label="Market Data">
                    <option value="ticker">ticker (Snapshot & 24h Stats)</option>
                    <option value="orderbook">orderbook (L2 Microstructure Depth)</option>
                    <option value="pairs">pairs (Tradable Symbols)</option>
                    <option value="ohlc">ohlc (Candles)</option>
                  </optgroup>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">Argumente</label>
                <input
                  id="kraken-cli-args-input"
                  type="text"
                  placeholder="z. B. status, buy BTC/USD 0.1"
                  value={commandArgs}
                  onChange={(e) => setCommandArgs(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">Workspace (--workspace)</label>
                <input
                  id="kraken-cli-workspace-input"
                  type="text"
                  value={workspace}
                  onChange={(e) => setWorkspace(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">Ausgabeformat (-o)</label>
                <select
                  id="kraken-cli-output-select"
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value as 'json' | 'table')}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500"
                >
                  <option value="json">json (Strict Machine Parsed)</option>
                  <option value="table">table (Terminal Grid)</option>
                </select>
              </div>
            </div>

            {/* Generated Shell Command Preview */}
            <div className="flex items-center justify-between bg-slate-950 p-2.5 rounded border border-slate-800 font-mono text-xs text-amber-400 mb-3">
              <div className="flex items-center gap-2 overflow-x-auto">
                <span className="text-slate-500 select-none">$</span>
                <span className="text-slate-200 font-semibold">{currentCommandLine}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  id="copy-cli-command-btn"
                  onClick={() => handleCopyCommand(currentCommandLine)}
                  title="In die Zwischenablage kopieren"
                  className="text-slate-400 hover:text-slate-200 p-1"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copiedNotification && (
                  <span className="text-[10px] text-emerald-400 animate-fade-in">Kopiert!</span>
                )}
                <button
                  id="execute-cli-command-btn"
                  onClick={() => handleRunCommand()}
                  disabled={isExecuting}
                  className="flex items-center gap-1.5 px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded transition"
                >
                  <Play className={`w-3.5 h-3.5 fill-current ${isExecuting ? 'animate-pulse' : ''}`} />
                  <span>{isExecuting ? 'Wird ausgeführt...' : 'Befehl Ausführen'}</span>
                </button>
              </div>
            </div>

            {/* Terminal Response Box */}
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-xs overflow-hidden">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 mb-2">
                <div className="flex items-center gap-2 text-slate-400 text-[11px]">
                  <Terminal className="w-3.5 h-3.5 text-amber-400" />
                  <span>CLI Output Stream</span>
                  {executionResult && (
                    <span className="text-slate-500">
                      · {executionResult.durationMs}ms · Exit: {executionResult.exitCode}
                    </span>
                  )}
                </div>
                {executionResult && (
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      executionResult.exitCode === 0
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    {executionResult.exitCode === 0 ? 'SUCCESS 200' : 'ERROR'}
                  </span>
                )}
              </div>

              <pre className="text-slate-300 max-h-80 overflow-y-auto overflow-x-auto whitespace-pre leading-relaxed scrollbar-thin scrollbar-thumb-slate-800">
                {isExecuting ? (
                  <span className="text-amber-400">
                    Routing command to kraken-cli engine...
                  </span>
                ) : executionResult ? (
                  executionResult.rawStdout || JSON.stringify(executionResult.data, null, 2)
                ) : (
                  <span className="text-slate-600">
                    Wähle einen Befehl oben aus und klicke auf "Befehl Ausführen".
                  </span>
                )}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* TAB: MASTER COMMAND MAP (32+ BEFEHLE) */}
      {activeTab === 'routing-table' && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                Kraken CLI 0.3.2 Master Command Map (32+ Kommandos)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Vollständige Registrierung aller CLI-Fähigkeiten inkl. Book-Reading/Writing und Danger-Level.
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
              ZERO-DUMMY COMPLIANT
            </span>
          </div>

          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-left font-mono text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40 sticky top-0">
                  <th className="py-2.5 px-3">Kommando</th>
                  <th className="py-2.5 px-3">Kategorie</th>
                  <th className="py-2.5 px-3">Liest Buch</th>
                  <th className="py-2.5 px-3">Verändert Buch</th>
                  <th className="py-2.5 px-3">Danger Level</th>
                  <th className="py-2.5 px-3">Beschreibung</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {Object.values(KRAKEN_COMMAND_MAP).map((cmd) => (
                  <tr key={cmd.name} className="hover:bg-slate-800/30 transition">
                    <td className="py-2 px-3 font-bold text-slate-200">
                      kraken {cmd.name}
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                        {cmd.category}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      {cmd.readsBook ? (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/20 text-blue-300">
                          {cmd.readsBook}
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {cmd.writesBook && cmd.writesBook !== 'NONE' ? (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 font-bold">
                          {cmd.writesBook}
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          cmd.dangerous
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}
                      >
                        {cmd.dangerous ? 'CRITICAL (LIVE ORDERS)' : 'SAFE (READ/PAPER)'}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-300 text-[11px]">{cmd.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB: CURSOR SKILLS & 150+ TOOLS CATALOG */}
      {activeTab === 'tools-catalog' && (
        <div className="space-y-4">
          {/* Header Banner */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0 mt-0.5">
                  <Wrench className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-wider">
                      Kraken CLI &amp; Cursor AI Skills (150 Tools Katalog)
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      VOLLSTÄNDIG VERDRAHTET
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                      150 / 150 TOOLS AKTIV
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Jedes Tool, von DCA-Bot-Generierung (<code className="text-amber-300 font-mono">create_dca_bot</code>) bis zur HFT-Reallokation, sendet direkt Kraken CLI Befehle ab, mutiert das aktive Buch und erzeugt echte TXIDs.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => {
                    const dcaTool = KRAKEN_TOOLS_CATALOG.find((t) => t.id === 'create_dca_bot');
                    if (dcaTool) {
                      setSelectedToolForExec(dcaTool);
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-mono font-bold transition shadow-sm"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>DCA Bot Skill starten</span>
                </button>
              </div>
            </div>

            {/* Filter and Search Bar */}
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-col md:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 text-[11px] font-mono">
                {['ALL', 'DCA & Algorithmic Bots', 'Order Execution', 'Paper Trading', 'Balances & Margin', 'Market Data', 'MCP & Workspaces', 'Situation & Risk'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-2.5 py-1 rounded whitespace-nowrap transition ${
                      selectedCategory === cat
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
                    }`}
                  >
                    {cat === 'ALL' ? `Alle (150)` : cat}
                  </button>
                ))}
              </div>

              <div className="relative w-full md:w-72 shrink-0">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={toolSearch}
                  onChange={(e) => setToolSearch(e.target.value)}
                  placeholder="Tool, Skill oder CLI-Befehl suchen..."
                  className="w-full bg-slate-950 border border-slate-800 rounded pl-8 pr-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
                />
              </div>
            </div>
          </div>

          {/* Interactive Tool Execution Drawer if tool selected */}
          {selectedToolForExec && (
            <div className="bg-slate-900 border-2 border-amber-500/40 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-xs font-mono font-bold">
                    TOOL AUSFÜHREN: {selectedToolForExec.name} ({selectedToolForExec.id})
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    Kategorie: {selectedToolForExec.category}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setSelectedToolForExec(null);
                    setToolExecResult(null);
                  }}
                  className="text-xs font-mono text-slate-400 hover:text-slate-200"
                >
                  Schließen ✕
                </button>
              </div>

              <p className="text-xs font-mono text-slate-300">
                {selectedToolForExec.description}
              </p>

              <div className="bg-slate-950 p-2 rounded border border-slate-800 text-xs font-mono text-amber-400">
                <span className="text-slate-500">Template: </span>
                {selectedToolForExec.cliCommandTemplate}
              </div>

              {/* Dynamic Parameter Form */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">Pair / Symbol</label>
                  <input
                    type="text"
                    value={toolParams.pair}
                    onChange={(e) => setToolParams({ ...toolParams, pair: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">Volumen / Menge</label>
                  <input
                    type="number"
                    step="0.001"
                    value={toolParams.volume}
                    onChange={(e) => setToolParams({ ...toolParams, volume: parseFloat(e.target.value) || 0.01 })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">Limit Preis ($)</label>
                  <input
                    type="number"
                    value={toolParams.price}
                    onChange={(e) => setToolParams({ ...toolParams, price: parseFloat(e.target.value) || 80000 })}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200"
                  />
                </div>

                {selectedToolForExec.id === 'create_dca_bot' && (
                  <>
                    <div>
                      <label className="block text-[10px] font-mono text-slate-400 mb-1">Bot Name</label>
                      <input
                        type="text"
                        value={toolParams.name}
                        onChange={(e) => setToolParams({ ...toolParams, name: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono text-slate-400 mb-1">Investment ($)</label>
                      <input
                        type="number"
                        value={toolParams.investment}
                        onChange={(e) => setToolParams({ ...toolParams, investment: parseFloat(e.target.value) || 100 })}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono text-slate-400 mb-1">DCA Stufen</label>
                      <input
                        type="number"
                        value={toolParams.dcaSteps}
                        onChange={(e) => setToolParams({ ...toolParams, dcaSteps: parseInt(e.target.value) || 60 })}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-200"
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={async () => {
                    setIsExecutingTool(true);
                    setToolExecResult(null);
                    try {
                      const res = await executeKrakenTool(selectedToolForExec.id, toolParams);
                      setToolExecResult(res);
                      loadSummary();
                    } catch (err: any) {
                      setToolExecResult({ error: err.message });
                    } finally {
                      setIsExecutingTool(false);
                    }
                  }}
                  disabled={isExecutingTool}
                  className="flex items-center gap-1.5 px-4 py-2 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-mono font-bold transition shadow-sm disabled:opacity-50"
                >
                  <Play className={`w-3.5 h-3.5 ${isExecutingTool ? 'animate-spin' : ''}`} />
                  <span>{isExecutingTool ? 'Wird ausgeführt...' : 'Befehl über Kraken CLI absenden'}</span>
                </button>
              </div>

              {toolExecResult && (
                <div className="mt-3 p-3 rounded bg-slate-950 border border-slate-800 font-mono text-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-emerald-400 font-bold">Ergebnis der Ausführung:</span>
                    <span className="text-slate-500">{new Date().toLocaleTimeString()}</span>
                  </div>
                  <pre className="text-slate-300 overflow-x-auto text-[11px]">
                    {JSON.stringify(toolExecResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Tools Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {KRAKEN_TOOLS_CATALOG.filter((t) => {
              const matchesCat =
                selectedCategory === 'ALL' ||
                t.category.toLowerCase().includes(selectedCategory.toLowerCase()) ||
                (selectedCategory === 'DCA & Algorithmic Bots' && t.category === 'DCA & Algorithmic Bots') ||
                (selectedCategory === 'Order Execution' && t.category === 'Order Execution & Management') ||
                (selectedCategory === 'Paper Trading' && t.category === 'Paper Trading & Simulation') ||
                (selectedCategory === 'Balances & Margin' && t.category === 'Balances, Margin & Risk') ||
                (selectedCategory === 'Market Data' && t.category === 'Market Data & Orderbook') ||
                (selectedCategory === 'MCP & Workspaces' && t.category === 'MCP & Workspaces') ||
                (selectedCategory === 'Situation & Risk' && t.category === 'Situation-Cycle & Meta Orchestration');

              const matchesSearch =
                !toolSearch ||
                t.name.toLowerCase().includes(toolSearch.toLowerCase()) ||
                t.id.toLowerCase().includes(toolSearch.toLowerCase()) ||
                t.description.toLowerCase().includes(toolSearch.toLowerCase()) ||
                t.cliCommandTemplate.toLowerCase().includes(toolSearch.toLowerCase());

              return matchesCat && matchesSearch;
            }).map((tool) => (
              <div
                key={tool.id}
                className="bg-slate-900 border border-slate-800 hover:border-amber-500/30 rounded-lg p-3.5 flex flex-col justify-between transition group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-mono font-bold text-xs text-amber-300 group-hover:text-amber-200">
                        {tool.name}
                      </span>
                    </div>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 shrink-0">
                      {tool.category.split(' ')[0]}
                    </span>
                  </div>

                  <p className="text-[11px] font-mono text-slate-400 mb-2 line-clamp-2">
                    {tool.description}
                  </p>

                  <div className="bg-slate-950 p-1.5 rounded border border-slate-800/80 text-[10px] font-mono text-slate-300 mb-2 truncate">
                    <span className="text-slate-500">$ </span>
                    {tool.cliCommandTemplate}
                  </div>

                  <div className="flex items-center gap-1.5 flex-wrap text-[9px] font-mono mb-3">
                    <span className="px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      READ: {tool.readsBook}
                    </span>
                    <span
                      className={`px-1.5 py-0.2 rounded ${
                        tool.writesBook !== 'NONE'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      WRITE: {tool.writesBook}
                    </span>
                    <span
                      className={`px-1.5 py-0.2 rounded ${
                        tool.dangerous
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}
                    >
                      {tool.dangerous ? 'LIVE' : 'SAFE'}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setSelectedToolForExec(tool);
                    window.scrollTo({ top: 300, behavior: 'smooth' });
                  }}
                  className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-200 text-xs font-mono font-medium transition"
                >
                  <Play className="w-3 h-3" />
                  <span>Konfigurieren &amp; Testen</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
