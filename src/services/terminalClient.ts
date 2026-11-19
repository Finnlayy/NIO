import {
  TimeframeId,
  DataProviderId,
  OHLCVCandle,
  ProviderAttemptTrace,
  StrategyDefinition,
  BacktestResult,
  ScreenerScheduleStatus,
  CmcIntelligencePayload,
} from '../types/terminal';

const LOCAL_STORAGE_KEY = 'omega_nio_terminal_store_v5';

export interface PersistentTerminalStore {
  strategies: StrategyDefinition[];
  lastResults: Record<string, BacktestResult>;
  activeStrategyId: string;
}

export const INITIAL_CLIENT_STRATEGIES: StrategyDefinition[] = [
  {
    id: 'strat_sniper_fusion_v31',
    name: 'SniperFusion v3.1 Long/Short',
    templateType: 'SNIPER_FUSION',
    idea: 'Multi-Source EMA Crossover & VWAP Alignment mit adaptivem Auto-TP MFE-Quantil und cos(φ) Phasen-Wächter',
    symbol: 'BTC/USD',
    timeframe: '15m',
    lookbackBars: 240,
    direction: 'BOTH',
    initialCapital: 1000,
    maxConcurrentTrades: 20,
    riskPerTradePct: 2.0,
    leverage: 5,
    feePct: 0.05,
    slippageBps: 2,
    slAtrMult: 1.6,
    tpRMultiple: 2.4,
    exitMode: 'AUTO_TP_MFE',
    advanced: {
      fastPeriod: 9,
      slowPeriod: 21,
      zScoreThreshold: 1.5,
      cosPhiThreshold: 0.35,
      profitLockGivebackR: 0.65,
      mfeQuantileWindow: 20,
      mfeQuantileTarget: 0.72,
      enableShadowEngine: true,
      maxSpreadBpsGuard: 12,
    },
    updatedAt: Date.now(),
  },
  {
    id: 'strat_mtf_cisd_breakout',
    name: 'MTF CISD Structure Break',
    templateType: 'MTF_CISD',
    idea: 'Change in State of Delivery (CISD) Pullback-Fortsetzung mit Trailing Stop from Top',
    symbol: 'PEPEUSDT.P',
    timeframe: '5m',
    lookbackBars: 300,
    direction: 'BOTH',
    initialCapital: 1000,
    maxConcurrentTrades: 20,
    riskPerTradePct: 2.5,
    leverage: 10,
    feePct: 0.05,
    slippageBps: 3,
    slAtrMult: 1.8,
    tpRMultiple: 3.0,
    exitMode: 'TRAILING_STOP',
    advanced: {
      fastPeriod: 8,
      slowPeriod: 24,
      zScoreThreshold: 1.6,
      cosPhiThreshold: 0.4,
      profitLockGivebackR: 0.6,
      mfeQuantileWindow: 25,
      mfeQuantileTarget: 0.75,
      enableShadowEngine: true,
      maxSpreadBpsGuard: 15,
    },
    updatedAt: Date.now(),
  },
  {
    id: 'strat_1m_flip_sensor',
    name: '1m Flip-Sensor Microstructure',
    templateType: 'FLIP_SENSOR_1M',
    idea: 'Hochfrequenter VWAP-Flip-Sensor mit Fractal-TP Gewinnmitnahme bei Momentum-Umkehr',
    symbol: 'SOL/USD',
    timeframe: '1m',
    lookbackBars: 240,
    direction: 'BOTH',
    initialCapital: 1000,
    maxConcurrentTrades: 20,
    riskPerTradePct: 1.5,
    leverage: 5,
    feePct: 0.04,
    slippageBps: 1.5,
    slAtrMult: 1.4,
    tpRMultiple: 2.0,
    exitMode: 'FRACTAL_TP',
    advanced: {
      fastPeriod: 6,
      slowPeriod: 18,
      zScoreThreshold: 1.3,
      cosPhiThreshold: 0.3,
      profitLockGivebackR: 0.5,
      mfeQuantileWindow: 15,
      mfeQuantileTarget: 0.68,
      enableShadowEngine: true,
      maxSpreadBpsGuard: 10,
    },
    updatedAt: Date.now(),
  },
  {
    id: 'strat_sigma_zscore_reversion',
    name: 'Sigma Z-Score Mean Reversion',
    templateType: 'SIGMA_ZSCORE',
    idea: 'Statistische Mean-Reversion bei ±1.4σ Z-Score Auslenkungen gegen VWAP mit TP-Ladder',
    symbol: 'ZECUSDT.P',
    timeframe: '15m',
    lookbackBars: 240,
    direction: 'BOTH',
    initialCapital: 1000,
    maxConcurrentTrades: 20,
    riskPerTradePct: 2.0,
    leverage: 5,
    feePct: 0.05,
    slippageBps: 2,
    slAtrMult: 1.5,
    tpRMultiple: 2.2,
    exitMode: 'TP_LADDER',
    advanced: {
      fastPeriod: 10,
      slowPeriod: 20,
      zScoreThreshold: 1.4,
      cosPhiThreshold: 0.25,
      profitLockGivebackR: 0.7,
      mfeQuantileWindow: 20,
      mfeQuantileTarget: 0.7,
      enableShadowEngine: true,
      maxSpreadBpsGuard: 14,
    },
    updatedAt: Date.now(),
  },
  {
    id: 'strat_atr_volatility_breakout',
    name: 'ATR Volatility Breakout Trend',
    templateType: 'ATR_BREAKOUT',
    idea: 'Volatilitäts-Ausbruch über Mehrkerzen-Struktur mit hartem 20-Trade-Cap und 1.000 $ Paper-Basis',
    symbol: 'ETH/USD',
    timeframe: '1h',
    lookbackBars: 240,
    direction: 'BOTH',
    initialCapital: 1000,
    maxConcurrentTrades: 20,
    riskPerTradePct: 2.0,
    leverage: 5,
    feePct: 0.05,
    slippageBps: 2,
    slAtrMult: 1.7,
    tpRMultiple: 2.8,
    exitMode: 'TP_LADDER',
    advanced: {
      fastPeriod: 9,
      slowPeriod: 21,
      zScoreThreshold: 1.5,
      cosPhiThreshold: 0.38,
      profitLockGivebackR: 0.65,
      mfeQuantileWindow: 20,
      mfeQuantileTarget: 0.72,
      enableShadowEngine: true,
      maxSpreadBpsGuard: 10,
    },
    updatedAt: Date.now(),
  },
];

export interface SystemMemoryTelemetry {
  timestamp: number;
  uptimeSec: number;
  rssMb: number;
  heapUsedMb: number;
  heapTotalMb: number;
  heapLimitMb: number;
  externalMb: number;
  arrayBuffersMb: number;
  wsClientsCount: number;
  swarmWsClientsCount: number;
  sseClientsCount: number;
  krakenWsStatus: string;
  autoSweepsCount: number;
  lastSweepAt: number | null;
  status: 'HEALTHY' | 'ELEVATED' | 'CRITICAL';
  history: Array<{
    timestamp: number;
    timeFormatted: string;
    rssMb: number;
    heapUsedMb: number;
  }>;
}

export async function fetchSystemMemoryStatus(): Promise<SystemMemoryTelemetry> {
  const res = await fetch('/api/system/memory', { signal: AbortSignal.timeout(4000) });
  if (!res.ok) {
    throw new Error('Memory status fetch failed');
  }
  return res.json();
}

export async function triggerSystemGcSweep(): Promise<SystemMemoryTelemetry> {
  const res = await fetch('/api/system/gc-sweep', {
    method: 'POST',
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    throw new Error('Memory GC sweep failed');
  }
  return res.json();
}

export function loadLocalStore(): PersistentTerminalStore | null {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && Array.isArray(parsed.strategies) && parsed.strategies.length > 0) {
      return parsed;
    }
  } catch {
    // ignore storage parse issue
  }
  return null;
}

export function saveLocalStore(store: PersistentTerminalStore): void {
  try {
    const cappedStrategies = (store.strategies || []).slice(0, 20);
    const keepIds = new Set(cappedStrategies.slice(0, 5).map((s) => s.id));
    if (store.activeStrategyId) keepIds.add(store.activeStrategyId);

    const prunedResults: Record<string, BacktestResult> = {};
    for (const [id, res] of Object.entries(store.lastResults || {})) {
      if (keepIds.has(id) && res) {
        prunedResults[id] = {
          ...res,
          candles: Array.isArray(res.candles) ? res.candles.slice(-200) : [],
          equityCurve: Array.isArray(res.equityCurve) ? res.equityCurve.slice(-200) : [],
          trades: Array.isArray(res.trades) ? res.trades.slice(-80) : [],
          pipelineEvents: Array.isArray(res.pipelineEvents) ? res.pipelineEvents.slice(0, 30) : [],
        };
      }
    }

    localStorage.setItem(
      LOCAL_STORAGE_KEY,
      JSON.stringify({
        strategies: cappedStrategies,
        lastResults: prunedResults,
        activeStrategyId: store.activeStrategyId,
      })
    );
  } catch {
    // ignore quota error
  }
}

export async function fetchStrategyStore(): Promise<PersistentTerminalStore> {
  const local = loadLocalStore();
  try {
    const res = await fetch('/api/strategies');
    if (res.ok) {
      const serverStore: PersistentTerminalStore = await res.json();
      if (local && local.strategies.length > 0) {
        // Merge local user edits with server store
        const mergedMap = new Map<string, StrategyDefinition>();
        for (const s of serverStore.strategies) mergedMap.set(s.id, s);
        for (const s of local.strategies) {
          const existing = mergedMap.get(s.id);
          if (!existing || (s.updatedAt || 0) >= (existing.updatedAt || 0)) {
            mergedMap.set(s.id, s);
          }
        }
        const merged: PersistentTerminalStore = {
          strategies: Array.from(mergedMap.values()),
          lastResults: { ...serverStore.lastResults, ...local.lastResults },
          activeStrategyId: local.activeStrategyId || serverStore.activeStrategyId,
        };
        saveLocalStore(merged);
        return merged;
      }
      saveLocalStore(serverStore);
      return serverStore;
    }
  } catch {
    // Server offline fallback to local
  }

  if (local) return local;
  return {
    strategies: INITIAL_CLIENT_STRATEGIES,
    lastResults: {},
    activeStrategyId: INITIAL_CLIENT_STRATEGIES[0].id,
  };
}

export async function persistStrategyToBackend(
  strategy: StrategyDefinition,
  lastResult?: BacktestResult,
  currentStore?: PersistentTerminalStore
): Promise<PersistentTerminalStore> {
  const baseStore = currentStore || loadLocalStore() || {
    strategies: INITIAL_CLIENT_STRATEGIES,
    lastResults: {},
    activeStrategyId: strategy.id,
  };

  const idx = baseStore.strategies.findIndex((s) => s.id === strategy.id);
  const updatedStrategies = [...baseStore.strategies];
  const stamped = { ...strategy, updatedAt: Date.now() };
  if (idx >= 0) {
    updatedStrategies[idx] = stamped;
  } else {
    updatedStrategies.unshift(stamped);
  }

  const updatedResults = { ...baseStore.lastResults };
  if (lastResult) {
    updatedResults[strategy.id] = lastResult;
  }

  const nextStore: PersistentTerminalStore = {
    strategies: updatedStrategies,
    lastResults: updatedResults,
    activeStrategyId: strategy.id,
  };
  saveLocalStore(nextStore);

  try {
    const res = await fetch('/api/strategies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy: stamped,
        lastResult,
        activeStrategyId: strategy.id,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.store) {
        saveLocalStore(data.store);
        return data.store;
      }
    }
  } catch {
    // LocalStorage already persisted
  }

  return nextStore;
}

export async function deleteStrategyFromBackend(
  strategyId: string,
  currentStore?: PersistentTerminalStore
): Promise<PersistentTerminalStore> {
  const baseStore = currentStore || loadLocalStore() || {
    strategies: INITIAL_CLIENT_STRATEGIES,
    lastResults: {},
    activeStrategyId: INITIAL_CLIENT_STRATEGIES[0].id,
  };

  const filtered = baseStore.strategies.filter((s) => s.id !== strategyId);
  const nextStrategies = filtered.length > 0 ? filtered : [INITIAL_CLIENT_STRATEGIES[0]];
  const updatedResults = { ...baseStore.lastResults };
  delete updatedResults[strategyId];

  const nextStore: PersistentTerminalStore = {
    strategies: nextStrategies,
    lastResults: updatedResults,
    activeStrategyId: nextStrategies[0].id,
  };
  saveLocalStore(nextStore);

  try {
    await fetch(`/api/strategies/${encodeURIComponent(strategyId)}`, { method: 'DELETE' });
  } catch {
    // LocalStorage already updated
  }

  return nextStore;
}

export async function fetchOhlcvCascade(
  symbol: string,
  timeframe: TimeframeId,
  limit: number = 240,
  signal?: AbortSignal
): Promise<{
  symbol: string;
  activeProvider: DataProviderId;
  candles: OHLCVCandle[];
  cascadeTrace: ProviderAttemptTrace[];
}> {
  const url = `/api/market/ohlc?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`;
  const res = await fetch(url, { signal });
  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.error || `Marktdaten für ${symbol} (${timeframe}) nicht verfügbar.`);
  }
  return data;
}

export async function executeBacktestJob(
  strategy: StrategyDefinition,
  signal?: AbortSignal
): Promise<BacktestResult> {
  const res = await fetch('/api/backtest/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy }),
    signal,
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.error || 'Backtest-Job fehlgeschlagen.');
  }
  return data.result;
}

export async function fetchScreenerSchedule(): Promise<ScreenerScheduleStatus> {
  const res = await fetch('/api/screener/schedule');
  if (!res.ok) {
    throw new Error('Screener-Status konnte nicht abgerufen werden.');
  }
  return res.json();
}

export async function updateScreenerSchedule(options: {
  enabled?: boolean;
  intervalSec?: number;
}): Promise<ScreenerScheduleStatus> {
  const res = await fetch('/api/screener/schedule', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) {
    throw new Error('Screener-Schedule konnte nicht aktualisiert werden.');
  }
  return res.json();
}

export async function triggerScreenerRunNow(): Promise<ScreenerScheduleStatus> {
  const res = await fetch('/api/screener/run-now', { method: 'POST' });
  if (!res.ok) {
    throw new Error('Screener-Lauf konnte nicht ausgelöst werden.');
  }
  return res.json();
}

export async function triggerEmergencyFlatten(): Promise<any> {
  const res = await fetch('/api/terminal/emergency-flatten', { method: 'POST' });
  if (!res.ok) {
    throw new Error('Emergency Flatten fehlgeschlagen.');
  }
  return res.json();
}

export async function fetchCmcIntelligence(force = false): Promise<CmcIntelligencePayload> {
  const res = await fetch(`/api/cmc/intelligence${force ? '?force=1' : ''}`);
  if (!res.ok) {
    throw new Error('CoinMarketCap Intelligence konnte nicht geladen werden.');
  }
  return res.json();
}

export async function refreshCmcIntelligence(): Promise<CmcIntelligencePayload> {
  const res = await fetch('/api/cmc/refresh', { method: 'POST' });
  if (!res.ok) {
    throw new Error('CoinMarketCap Refresh fehlgeschlagen.');
  }
  return res.json();
}

export function exportTradesToCsv(result: BacktestResult): void {
  const headers = [
    'Trade_Nr',
    'Symbol',
    'Provider',
    'Side',
    'Entry_Time',
    'Exit_Time',
    'Entry_Price',
    'Exit_Price',
    'Stop_Loss',
    'Take_Profit',
    'Quantity',
    'Notional_USD',
    'Size_Pct_Eq',
    'Gross_PnL_USD',
    'Fee_USD',
    'Net_PnL_USD',
    'Return_Pct',
    'R_Multiple',
    'MFE_Pct',
    'MAE_Pct',
    'Exit_Reason',
    'Reason_Detail',
    'Cos_Phi',
    'Concurrent_Slot',
  ];

  const rows = result.trades.map((t) => [
    t.tradeNumber,
    t.symbol,
    t.provider,
    t.side,
    new Date(t.entryTime).toISOString(),
    new Date(t.exitTime).toISOString(),
    t.entryPrice,
    t.exitPrice,
    t.stopLossPrice,
    t.takeProfitPrice,
    t.quantity,
    t.notionalUsd,
    t.sizePctEquity,
    t.grossPnlUsd,
    t.feeUsd,
    t.netPnlUsd,
    t.returnPct,
    t.rMultiple,
    t.mfePct,
    t.maePct,
    t.exitReason,
    `"${(t.reasonDetail || '').replace(/"/g, '""')}"`,
    t.cosPhiAtEntry,
    t.concurrentSlot,
  ]);

  const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `omega_trades_${result.symbol.replace('/', '_')}_${result.timeframe}_${Date.now()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function exportStrategyAndResultToJson(
  strategy: StrategyDefinition,
  result: BacktestResult | null
): void {
  const payload = {
    exportedAt: new Date().toISOString(),
    terminalVersion: 'OMEGA_NIO_QUANT_TERMINAL',
    strategy,
    backtestResult: result,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `omega_strategy_${strategy.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_${Date.now()}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function exportPineScriptFile(strategyName: string, symbol: string, pineCode: string): void {
  const blob = new Blob([pineCode], { type: 'text/plain;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${strategyName.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_${symbol.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_v6.pine`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
