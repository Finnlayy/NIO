import React, { useState, useMemo } from 'react';
import {
  Bot,
  Zap,
  TrendingUp,
  DollarSign,
  Activity,
  Plus,
  SlidersHorizontal,
  CheckCircle2,
  ShieldCheck,
  Search,
  Sliders,
  Sparkles,
  ArrowRight,
  Radio,
  ExternalLink,
  Filter,
  Trophy,
  Clock,
  Receipt,
} from 'lucide-react';
import { WorkerBotData } from '../types/trading';
import { WorkerBotCard } from './WorkerBotCard';
import { AnimatedNumber, AnimatedCurrency, AnimatedPercent } from './AnimatedNumber';
import { useBotStream } from '../hooks/useBotStream';
import { useBotHistory } from '../hooks/useBotHistory';
import { INITIAL_WORKER_BOTS } from '../data/workerBots';
import { spawnBotFromHistory } from '../services/krakenCliRouter';

// Fallback-/Initial-Daten, bis der WebSocket feuert
const initialSwarm: WorkerBotData[] = INITIAL_WORKER_BOTS;

interface WorkerBotsViewProps {
  bots?: WorkerBotData[];
  onToggleBotStatus?: (botId: string) => void;
  onUpdateParameters?: (
    botId: string,
    updates: { leverage?: number; dcaRangeMin?: number; dcaRangeMax?: number }
  ) => void;
  onAddBot?: (newBot: WorkerBotData) => void;
  onSelectBot?: (botId: string) => void;
}

export const WorkerBotsView: React.FC<WorkerBotsViewProps> = ({
  bots: propBots,
  onToggleBotStatus,
  onUpdateParameters,
  onAddBot,
}) => {
  // UI State für die Tabs (Live Swarm vs. Historie)
  const [activeTab, setActiveTab] = useState<'live' | 'history'>('live');

  // Verbinde zum Backend (Live-Daten via WS, Historie via REST & DB)
  const initialData = propBots && propBots.length > 0 ? propBots : initialSwarm;
  const liveBots = useBotStream('', initialData);
  const { history, loading: historyLoading, addHistoryItem } = useBotHistory();

  const handleToggleStatus = (botId: string) => {
    // Hier würde ein API-Call oder eine WS-Message ans Backend gehen
    console.log(`Befehl an Engine: Schalte Status für ${botId} um`);
    if (onToggleBotStatus) {
      onToggleBotStatus(botId);
    }
    if (typeof (liveBots as any)?.toggleBotStatus === 'function') {
      (liveBots as any).toggleBotStatus(botId);
    }
  };

  // Lifecycle: Worker Bot stoppen, via WS/REST ins Archiv schieben und in Historie aufnehmen
  const handleStopBot = async (botId: string, reason: string = 'MANUAL_STOP') => {
    console.log(`[Swarm View] Bot stop angefordert: ${botId} (${reason})`);
    const botToStop = liveBots.find((b) => b.id === botId);

    // 1. WebSocket / Hook informieren (filtert bot optimistisch aus liveBots)
    if (typeof (liveBots as any)?.stopWorkerBot === 'function') {
      (liveBots as any).stopWorkerBot(botId, reason);
    }

    // 2. Historie optimistich aktualisieren
    if (botToStop) {
      const finishedBot: WorkerBotData = {
        ...botToStop,
        status: reason === 'LIQUIDATED' ? 'liquidated' : reason === 'TAKE_PROFIT' ? 'completed' : 'stopped',
        finishReason: reason,
        finishedAt: 'Gerade eben',
        statusText: `Beendet · ${reason}`,
        durationFormatted: 'Session beendet',
      };
      addHistoryItem(finishedBot);
    }

    // 3. REST API Call an Backend absetzen
    try {
      await fetch('/api/v1/swarm/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ botId, reason }),
      });
    } catch (err) {
      console.warn('Backend REST Stop Call fehlgeschlagen (WS hat bereits gefeuert):', err);
    }
  };

  const [respawningId, setRespawningId] = useState<string | null>(null);
  const [respawnFeedback, setRespawnFeedback] = useState<string | null>(null);

  const handleRespawnBot = async (historicalBotId: string) => {
    setRespawningId(historicalBotId);
    setRespawnFeedback(null);
    try {
      const res = await spawnBotFromHistory(historicalBotId);
      if (res.success) {
        setRespawnFeedback(`Bot erfolgreich als ${res.newBotId} geklont und im Live-Swarm gestartet!`);
        setTimeout(() => {
          setActiveTab('live');
          setRespawnFeedback(null);
        }, 1200);
      }
    } catch (err: any) {
      setRespawnFeedback(`Fehler beim Klonen: ${err.message}`);
    } finally {
      setRespawningId(null);
    }
  };

  const [selectedBotId, setSelectedBotId] = useState<string>(liveBots[0]?.id || 'BOT-7742');
  const [viewMode, setViewMode] = useState<'featured' | 'grid'>('grid');
  const [filterExchange, setFilterExchange] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'PAUSED'>('ALL');
  const [isDeployModalOpen, setIsDeployModalOpen] = useState<boolean>(false);

  // New bot modal form state
  const [newBotPair, setNewBotPair] = useState<string>('BTC/USD');
  const [newBotName, setNewBotName] = useState<string>('Delta-Neutral Scalper');
  const [newBotExchange, setNewBotExchange] = useState<string>('Kraken Futures');
  const [newBotStrategy, setNewBotStrategy] = useState<string>('KRAKEN FUTURES · VOLATILITY DCA');
  const [newBotDirection, setNewBotDirection] = useState<'LONG' | 'SHORT'>('LONG');
  const [newBotLeverage, setNewBotLeverage] = useState<number>(35);
  const [newBotInvestment, setNewBotInvestment] = useState<number>(150);
  const [newBotDcaLow, setNewBotDcaLow] = useState<number>(24.5);
  const [newBotDcaHigh, setNewBotDcaHigh] = useState<number>(31.0);

  // Active / selected bot
  const selectedBot = liveBots.find((b) => b.id === selectedBotId) || liveBots[0];

  // Aggregate metrics across bots
  const totalInvestment = useMemo(
    () => liveBots.reduce((acc, b) => acc + (b.metrics?.investment ?? b.investmentUsd ?? 0), 0),
    [liveBots]
  );
  const totalUnrealizedPnl = useMemo(
    () => liveBots.reduce((acc, b) => acc + (b.unrealizedPnL?.value ?? b.unrealizedPnlUsd ?? 0), 0),
    [liveBots]
  );
  const totalRealizedProfit = useMemo(
    () => liveBots.reduce((acc, b) => acc + (b.metrics?.realizedProfit ?? b.currentProfitUsd ?? 0), 0),
    [liveBots]
  );
  const totalDcaOrders = useMemo(
    () => liveBots.reduce((acc, b) => acc + (b.metrics?.dcaOrdersTriggered ?? b.dcaOrdersTriggered ?? 0), 0),
    [liveBots]
  );
  const totalTxFees = useMemo(
    () => liveBots.reduce((acc, b) => {
      if (b.metrics?.transactionFees !== undefined) return acc + b.metrics.transactionFees;
      const inv = b.metrics?.investment ?? b.investmentUsd ?? 0;
      const lev = b.leverage > 0 ? b.leverage : 1;
      const nominal = inv * lev;
      const dcaOrders = b.metrics?.dcaOrdersTriggered ?? b.dcaOrdersTriggered ?? 0;
      const steps = b.metrics?.dcaSteps ?? 100;
      const tranche = nominal / Math.max(steps, 1);
      const vol = nominal + (dcaOrders * tranche);
      return acc + (vol * 0.0004);
    }, 0),
    [liveBots]
  );
  const activeBotsCount = useMemo(
    () => liveBots.filter((b) => b.status === 'active' || b.status === 'ACTIVE').length,
    [liveBots]
  );

  const historicalTotalRealized = useMemo(
    () => history.reduce((acc, b) => acc + (b.metrics?.realizedProfit ?? b.totalProfit ?? 0), 0),
    [history]
  );
  const historicalCompletedCount = useMemo(
    () => history.filter((b) => b.status === 'completed' || b.finishReason === 'TAKE_PROFIT').length,
    [history]
  );
  const historicalWinRate = useMemo(
    () => (history.length > 0 ? (historicalCompletedCount / history.length) * 100 : 100),
    [history, historicalCompletedCount]
  );

  const exchanges = useMemo(
    () => ['ALL', ...Array.from(new Set(liveBots.map((b) => b.exchange)))],
    [liveBots]
  );

  // Filtered list
  const filteredBots = useMemo(() => {
    return liveBots.filter((b) => {
      if (filterExchange !== 'ALL' && b.exchange !== filterExchange) return false;
      const isActive = b.status === 'active' || b.status === 'ACTIVE';
      if (statusFilter === 'ACTIVE' && !isActive) return false;
      if (statusFilter === 'PAUSED' && isActive) return false;

      if (searchQuery.trim() !== '') {
        const q = searchQuery.toLowerCase();
        const pair = (b.pair || b.symbol || '').toLowerCase();
        const name = b.name.toLowerCase();
        const id = b.id.toLowerCase();
        const ex = b.exchange.toLowerCase();
        if (!pair.includes(q) && !name.includes(q) && !id.includes(q) && !ex.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [liveBots, filterExchange, statusFilter, searchQuery]);

  // Handle Deploying a new Bot
  const handleDeployBotSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newId = `BOT-${Math.floor(1000 + Math.random() * 9000)}`;
    const nowTime = new Date().toTimeString().split(' ')[0];

    const newBotData: WorkerBotData = {
      id: newId,
      name: newBotName,
      exchange: newBotExchange,
      status: 'active',
      pair: newBotPair.toUpperCase(),
      strategy: newBotStrategy,
      direction: newBotDirection,
      leverage: newBotLeverage,
      unrealizedPnL: {
        value: 0.0,
        percentage: 0.0,
      },
      entryPrice: (newBotDcaLow + newBotDcaHigh) / 2,
      currentPrice: (newBotDcaLow + newBotDcaHigh) / 2,
      metrics: {
        investment: newBotInvestment,
        currency: '$',
        investmentEur: newBotInvestment * 0.915,
        realizedProfit: 0.0,
        profitCycleType: 'Realisiert (Zyklus)',
        dcaRangeMin: newBotDcaLow,
        dcaRangeMax: newBotDcaHigh,
        dcaSteps: 60,
        dcaOrdersTriggered: 1,
        fundingFees: -0.05,
        liquidationPrice:
          newBotDirection === 'LONG'
            ? newBotDcaLow * (1 - 1 / newBotLeverage)
            : newBotDcaHigh * (1 + 1 / newBotLeverage),
        liquidationDistancePct: -100 / newBotLeverage,
      },
      runtime: {
        days: 0,
        hours: 0,
        minutes: 1,
        cycles: 1,
        cycleProgressPct: 15,
      },
      totalProfit: 0.0,
      roi: 0.0,
      apr: 850,
      lastUpdate: nowTime,
      statusText: 'Bot aktiv · Verbunden',
      symbol: newBotPair.toUpperCase(),
      instrumentType: newBotStrategy,
      investmentUsd: newBotInvestment,
      investmentEur: newBotInvestment * 0.915,
      unrealizedPnlUsd: 0.0,
      unrealizedPnlPct: 0.0,
      currentProfitUsd: 0.0,
      totalProfitUsd: 0.0,
      roiPct: 0.0,
      aprPct: 850,
      dcaOrdersTriggered: 1,
      lastUpdated: nowTime,
    };

    if (onAddBot) {
      onAddBot(newBotData);
    }
    setSelectedBotId(newId);
    setIsDeployModalOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Control Bar */}
      <header className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Bot className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold text-emerald-400">
              Worker &amp; DCA Bots
            </h1>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold">
              {activeBotsCount} / {liveBots.length} AKTIV
            </span>
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
              <Radio className="w-2.5 h-2.5 text-emerald-400 animate-pulse" />
              <span>WebSocket &amp; DMA Stream: &lt;1.2ms</span>
            </span>
          </div>
          <p className="text-sm text-gray-400 font-mono mt-1">
            Live Swarm Monitoring · Reale DCA- &amp; Futures-Worker mit dynamischer Marktanbindung &amp; M8-Gate Risikokontrolle
          </p>
        </div>

        {/* Controls: Tabs (Live Swarm vs. Historie), Deploy button & View Mode */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Tab-Navigation: Live Swarm vs. Historie */}
          <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
            <button
              type="button"
              onClick={() => setActiveTab('live')}
              className={`px-3 py-1.5 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'live'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Live Swarm ({liveBots.length})</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('history')}
              className={`px-3 py-1.5 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'history'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Historie ({history.length})</span>
            </button>
          </div>

          {/* Deploy New Bot Button (only in live mode) */}
          {activeTab === 'live' && onAddBot && (
            <button
              type="button"
              onClick={() => setIsDeployModalOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow-md shadow-purple-500/20 transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Neuen Worker bereitstellen</span>
            </button>
          )}

          {/* View Mode Toggle (only in live mode) */}
          {activeTab === 'live' && (
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
              <button
                type="button"
                onClick={() => setViewMode('featured')}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                  viewMode === 'featured'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Fokus-Widget
              </button>
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Multi-Grid ({filteredBots.length})
              </button>
            </div>
          )}
        </div>
      </header>

      {/* CONDITIONALLY RENDER: LIVE SWARM TAB vs. HISTORIE TAB */}
      {activeTab === 'live' ? (
        <>
          {/* Filter & Search Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/60 border border-slate-800 rounded-xl p-3 font-mono text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                <Filter className="w-3 h-3 text-slate-500" />
                Börsen:
              </span>
              {exchanges.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setFilterExchange(ex)}
                  className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                    filterExchange === ex
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {ex}
                </button>
              ))}
            </div>

            {/* Search input */}
            <div className="relative min-w-[200px] flex-1 sm:flex-initial">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Suchen (Symbol, Name, ID)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Aggregate Metrics Header */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 font-mono gpu-accelerate">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <DollarSign className="w-3.5 h-3.5 text-amber-400" />
                DEPLOYSGESAMTKAPITAL
              </div>
              <div className="text-base font-bold text-slate-100 mt-1 tabular-nums">
                <AnimatedNumber value={totalInvestment} precision={2} suffix=" $" />
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 tabular-nums">
                <AnimatedNumber value={totalInvestment * 0.915} precision={2} suffix=" EUR Pool" />
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-emerald-400" />
                GESAMT UNREALIZED P&amp;L
              </div>
              <div className={`text-base font-bold mt-1 tabular-nums ${totalUnrealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                <AnimatedCurrency value={totalUnrealizedPnl} showSign={true} precision={2} />
              </div>
              <div className="text-[10px] text-emerald-500 mt-0.5 tabular-nums">
                {totalInvestment > 0 ? (
                  <>
                    <AnimatedPercent
                      value={(totalUnrealizedPnl / totalInvestment) * 100}
                      showSign={true}
                      precision={2}
                    />{' '}
                    gewichtet
                  </>
                ) : (
                  '0%'
                )}
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
                KUMULIERTER PROFIT
              </div>
              <div className="text-base font-bold text-purple-400 mt-1 tabular-nums">
                <AnimatedCurrency value={totalRealizedProfit} showSign={true} precision={2} />
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                Über alle Zyklen
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-sky-400" />
                DCA BUFFERS &amp; ORDERS
              </div>
              <div className="text-base font-bold text-sky-400 mt-1 tabular-nums">
                <AnimatedNumber value={totalDcaOrders} precision={0} suffix=" Orders" />
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                Ausgelöste DCA-Käufe
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Receipt className="w-3.5 h-3.5 text-amber-400" />
                  GEBÜHREN (MIN 0.04%)
                </span>
                <span className="text-[9px] text-purple-400">≥4 BPS</span>
              </div>
              <div className="text-base font-bold text-amber-400 mt-1 tabular-nums">
                -<AnimatedCurrency value={totalTxFees} precision={2} />
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                Swarm Transaktionsgebühren
              </div>
            </div>
          </div>

          {/* Main Content Area: Featured vs. Multi-Grid */}
          {viewMode === 'featured' ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: The Generic Widget rendering the selected bot */}
              <div className="lg:col-span-5 flex justify-center">
                {selectedBot && (
                  <WorkerBotCard
                    bot={selectedBot}
                    onToggleStatus={handleToggleStatus}
                    onStopBot={handleStopBot}
                    onUpdateParameters={onUpdateParameters}
                  />
                )}
              </div>

              {/* Right Column: Worker Bot Roster & Inspection Table */}
              <div className="lg:col-span-7 space-y-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                        Etablierte Worker &amp; Bot Instanzen
                      </h3>
                      <p className="text-[11px] text-slate-400 font-mono">
                        Wähle einen Worker aus, um das Live-Widget links zu synchronisieren
                      </p>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      {filteredBots.length} Instanzen
                    </span>
                  </div>

                  <div className="space-y-2 font-mono max-h-[480px] overflow-y-auto pr-1">
                    {filteredBots.map((bot) => {
                      const isSelected = bot.id === selectedBotId;
                      const isActive = bot.status === 'active' || bot.status === 'ACTIVE';
                      const unPnl = bot.unrealizedPnL?.value ?? bot.unrealizedPnlUsd ?? 0;
                      const unPnlPct = bot.unrealizedPnL?.percentage ?? bot.unrealizedPnlPct ?? 0;
                      const totProf = bot.totalProfit ?? bot.totalProfitUsd ?? 0;
                      const roiVal = bot.roi ?? bot.roiPct ?? 0;
                      const pairStr = bot.pair || bot.symbol || '';

                      return (
                        <div
                          key={bot.id}
                          onClick={() => setSelectedBotId(bot.id)}
                          className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                            isSelected
                              ? 'bg-purple-950/30 border-purple-500/50 shadow-md shadow-purple-500/5'
                              : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold shrink-0 ${
                                isSelected
                                  ? 'bg-purple-600 text-white'
                                  : 'bg-slate-800 text-slate-300'
                              }`}
                            >
                              <Bot className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-bold text-slate-100">
                                  {bot.name}
                                </span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                                  {bot.id}
                                </span>
                              </div>
                              <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                                <span className="text-slate-300 font-semibold">{pairStr}</span>
                                <span>•</span>
                                <span>{bot.exchange}</span>
                                <span>•</span>
                                <span className="text-purple-300">{bot.leverage}× Leverage</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center justify-between sm:justify-end gap-4 text-right pl-12 sm:pl-0">
                            <div>
                              <div
                                className={`text-xs font-bold ${
                                  unPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                                }`}
                              >
                                {unPnl >= 0 ? `+${unPnl.toFixed(2)}` : unPnl.toFixed(2)} $
                              </div>
                              <div className="text-[10px] text-slate-500">
                                P&amp;L: {unPnlPct >= 0 ? `+${unPnlPct.toFixed(2)}%` : `${unPnlPct.toFixed(2)}%`}
                              </div>
                            </div>

                            <div className="hidden sm:block">
                              <div className="text-xs font-bold text-purple-400">
                                +{totProf.toFixed(2)} $
                              </div>
                              <div className="text-[10px] text-indigo-400/80">
                                ROI +{roiVal.toFixed(1)}%
                              </div>
                            </div>

                            <div className="flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleToggleStatus(bot.id);
                                }}
                                className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase transition-colors ${
                                  isActive
                                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30'
                                    : 'bg-amber-500/20 text-amber-400 border border-amber-500/40 hover:bg-amber-500/30'
                                }`}
                              >
                                {isActive ? 'Aktiv' : 'Pausiert'}
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleStopBot(bot.id, 'MANUAL_STOP');
                                }}
                                className="px-2 py-1 rounded text-[10px] font-bold uppercase bg-slate-800/80 hover:bg-rose-950/40 border border-slate-700 hover:border-rose-500/50 text-slate-400 hover:text-rose-300 transition-colors"
                                title="Worker beenden & archivieren"
                              >
                                Stopp
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Architecture / Template Guarantee Note */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 flex items-start gap-3">
                  <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  <div className="text-xs text-slate-400 space-y-1">
                    <div className="font-bold font-mono text-slate-200">
                      Generische Widget-Architektur &amp; Dynamische Marktanbindung
                    </div>
                    <p className="leading-relaxed">
                      Das Widget fungiert als universelles Template für jegliche Bots im System (z. B. BTC, ETH, SOL, NIO, HYPE oder neu bereitgestellte Worker).
                      Alle Metriken (Einstiegspreis, Marktwert, DCA-Stufen, Funding Fees, Liquidationsabstand und Zyklen) werden strikt aus den dynamischen Props bezogen.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Responsive Grid für die Widgets */
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredBots.map((bot) => (
                <WorkerBotCard
                  key={bot.id}
                  bot={bot}
                  onToggleStatus={handleToggleStatus}
                  onStopBot={handleStopBot}
                  onUpdateParameters={onUpdateParameters}
                />
              ))}
            </div>
          )}
        </>
      ) : (
        /* HISTORIE DER BEENDETEN BOTS */
        <div className="space-y-6">
          {/* Historie Metriken & Analytics Header */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Trophy className="w-3.5 h-3.5 text-amber-400" />
                HISTORISCHER PROFIT
              </div>
              <div className="text-base font-bold text-emerald-400 mt-1">
                +{historicalTotalRealized.toFixed(2)} $
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                Archivierte Zyklen
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                WIN-RATE HISTORISCH
              </div>
              <div className="text-base font-bold text-emerald-400 mt-1">
                {historicalWinRate.toFixed(1)}%
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                {historicalCompletedCount} von {history.length} im Take-Profit
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-400" />
                DURCHSCHN. LAUFZEIT
              </div>
              <div className="text-base font-bold text-indigo-300 mt-1">
                3.4 Tage
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                Pro Trading-Zyklus
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                ARCHIV-STATUS
              </div>
              <div className="text-base font-bold text-purple-300 mt-1">
                REST-API / DB
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                {history.length} Sessions gesichert
              </div>
            </div>
          </div>

          {respawnFeedback && (
            <div className="p-3 rounded-lg bg-purple-950/50 border border-purple-500/40 text-purple-300 font-mono text-xs flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
              <span>{respawnFeedback}</span>
            </div>
          )}

          {/* Grid mit den archivierten Bot-Karten */}
          {historyLoading ? (
            <div className="flex items-center justify-center p-12 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
                <Activity className="w-5 h-5 text-purple-400 animate-spin" />
                <span>Lade Historie aus Datenbank &amp; Engine-Archiv...</span>
              </div>
            </div>
          ) : history.length === 0 ? (
            <div className="p-12 text-center bg-slate-900/40 border border-slate-800 rounded-xl text-slate-400 font-mono">
              Keine beendeten Bots in der Historie vorhanden.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {history.map((bot) => (
                <div
                  key={bot.id}
                  className="flex flex-col gap-2 group"
                >
                  <div className="opacity-80 group-hover:opacity-100 transition-all duration-300">
                    <WorkerBotCard
                      bot={bot}
                      // Ein leerer Callback, da man historische Bots nicht mehr pausieren kann
                      onToggleStatus={() => console.log('Bot ist bereits beendet')}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRespawnBot(bot.id)}
                    disabled={respawningId === bot.id}
                    className="w-full py-2 px-3 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 hover:border-purple-500 text-purple-300 text-xs font-mono font-semibold flex items-center justify-center gap-2 transition shadow-sm"
                  >
                    <Sparkles className={`w-3.5 h-3.5 ${respawningId === bot.id ? 'animate-spin' : ''}`} />
                    <span>{respawningId === bot.id ? 'Orchestrator klont...' : 'Autonom Klonen / Respawn Session'}</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modal: Neuen Worker bereitstellen */}
      {isDeployModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-5 space-y-4 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-purple-500/20 text-purple-400 border border-purple-500/30">
                  <Plus className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                    Neuen Worker / Bot bereitstellen
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Instanziiert einen neuen Bot mit dem universellen Widget-Template
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsDeployModalOpen(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleDeployBotSubmit} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Bot Name</label>
                  <input
                    type="text"
                    required
                    value={newBotName}
                    onChange={(e) => setNewBotName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Handelspaar (Symbol)</label>
                  <input
                    type="text"
                    required
                    value={newBotPair}
                    onChange={(e) => setNewBotPair(e.target.value)}
                    placeholder="z.B. SOL/USDT.P oder AVAX/USDT.P"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Börse / Execution Gateway</label>
                  <select
                    value={newBotExchange}
                    onChange={(e) => setNewBotExchange(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  >
                    <option value="Kraken Futures">Kraken Futures (Multi-Collateral)</option>
                    <option value="Kraken Spot / Margin">Kraken Spot / Margin (DMA)</option>
                    <option value="Kraken Paper Sandbox">Kraken Paper Sandbox (CLI Engine)</option>
                    <option value="Kraken Derivatives">Kraken Derivatives Direct</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Strategie-Typ</label>
                  <input
                    type="text"
                    required
                    value={newBotStrategy}
                    onChange={(e) => setNewBotStrategy(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Richtung</label>
                  <select
                    value={newBotDirection}
                    onChange={(e) => setNewBotDirection(e.target.value as 'LONG' | 'SHORT')}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  >
                    <option value="LONG">▲ LONG</option>
                    <option value="SHORT">▼ SHORT</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Hebel (x)</label>
                  <input
                    type="number"
                    min="1"
                    max="125"
                    value={newBotLeverage}
                    onChange={(e) => setNewBotLeverage(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Kapital ($)</label>
                  <input
                    type="number"
                    min="10"
                    value={newBotInvestment}
                    onChange={(e) => setNewBotInvestment(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">DCA Range Low ($)</label>
                  <input
                    type="number"
                    step="any"
                    value={newBotDcaLow}
                    onChange={(e) => setNewBotDcaLow(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">DCA Range High ($)</label>
                  <input
                    type="number"
                    step="any"
                    value={newBotDcaHigh}
                    onChange={(e) => setNewBotDcaHigh(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-100 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsDeployModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Abbrechen
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold shadow-md shadow-purple-500/20 flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Worker starten</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
