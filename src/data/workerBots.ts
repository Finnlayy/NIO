import { WorkerBotData, OrderbookData } from '../types/trading';

export const INITIAL_WORKER_BOTS: WorkerBotData[] = [
  {
    id: 'BOT-7742',
    name: 'DCA Bot Alpha',
    exchange: 'Kraken Futures',
    status: 'active',
    pair: 'BTC/USD',
    strategy: 'KRAKEN FUTURES · DCA STRATEGY',
    direction: 'LONG',
    leverage: 75,
    unrealizedPnL: {
      value: 162.24,
      percentage: 216.58,
    },
    entryPrice: 75400.0,
    currentPrice: 76767.0,
    metrics: {
      investment: 500.0,
      currency: '$',
      investmentEur: 460.0,
      realizedProfit: 84.2,
      profitCycleType: 'Realisiert (Zyklus)',
      dcaRangeMin: 72000,
      dcaRangeMax: 82000,
      dcaSteps: 160,
      dcaOrdersTriggered: 247,
      fundingFees: -1.14,
      liquidationPrice: 68500.0,
      liquidationDistancePct: -11.7,
    },
    runtime: {
      days: 3,
      hours: 14,
      minutes: 22,
      cycles: 62,
      cycleProgressPct: 62,
    },
    totalProfit: 170.66,
    roi: 337.4,
    apr: 4480,
    lastUpdate: '14:37:02',
    statusText: 'Bot aktiv · Verbunden',
    // Convenience aliases
    symbol: 'BTC/USD',
    instrumentType: 'KRAKEN FUTURES · DCA STRATEGY',
    investmentUsd: 500.0,
    investmentEur: 460.0,
    unrealizedPnlUsd: 162.24,
    unrealizedPnlPct: 216.58,
    currentProfitUsd: 84.2,
    totalProfitUsd: 170.66,
    roiPct: 337.4,
    aprPct: 4480,
    dcaOrdersTriggered: 247,
    lastUpdated: '14:37:02',
  },
  {
    id: 'BOT-9104',
    name: 'Alpha-Momentum Worker',
    exchange: 'Kraken Futures (PF_XBTUSD)',
    status: 'active',
    pair: 'BTC/USD',
    strategy: 'KRAKEN FUTURES · MOMENTUM DCA',
    direction: 'LONG',
    leverage: 25,
    unrealizedPnL: {
      value: 520.84,
      percentage: 52.08,
    },
    entryPrice: 75200.0,
    currentPrice: 76767.0,
    metrics: {
      investment: 1000.0,
      currency: '$',
      investmentEur: 915.0,
      realizedProfit: 74.5,
      profitCycleType: 'Realisiert (Zyklus)',
      dcaRangeMin: 74000,
      dcaRangeMax: 79000,
      dcaSteps: 120,
      dcaOrdersTriggered: 89,
      fundingFees: -6.32,
      liquidationPrice: 71500.0,
      liquidationDistancePct: -6.86,
    },
    runtime: {
      days: 7,
      hours: 6,
      minutes: 41,
      cycles: 45,
      cycleProgressPct: 78,
    },
    totalProfit: 595.34,
    roi: 59.53,
    apr: 1628,
    lastUpdate: '14:37:02',
    statusText: 'Bot aktiv · Verbunden',
    linkedStrategyId: 'strat_alpha_momentum',
    symbol: 'BTC/USD',
    instrumentType: 'KRAKEN FUTURES · MOMENTUM DCA',
    investmentUsd: 1000.0,
    investmentEur: 915.0,
    unrealizedPnlUsd: 520.84,
    unrealizedPnlPct: 52.08,
    currentProfitUsd: 74.5,
    totalProfitUsd: 595.34,
    roiPct: 59.53,
    aprPct: 1628,
    dcaOrdersTriggered: 89,
    lastUpdated: '14:37:02',
  },
  {
    id: 'BOT-3382',
    name: 'Sigma Mean-Reversion Bot',
    exchange: 'Kraken Futures (PF_ETHUSD)',
    status: 'active',
    pair: 'ETH/USD',
    strategy: 'KRAKEN FUTURES · GRID-DCA',
    direction: 'LONG',
    leverage: 50,
    unrealizedPnL: {
      value: 227.46,
      percentage: 75.82,
    },
    entryPrice: 2440.0,
    currentPrice: 2477.0,
    metrics: {
      investment: 300.0,
      currency: '$',
      investmentEur: 274.5,
      realizedProfit: 28.9,
      profitCycleType: 'Realisiert (Zyklus)',
      dcaRangeMin: 2350,
      dcaRangeMax: 2600,
      dcaSteps: 80,
      dcaOrdersTriggered: 112,
      fundingFees: -2.4,
      liquidationPrice: 2280.0,
      liquidationDistancePct: -7.95,
    },
    runtime: {
      days: 5,
      hours: 18,
      minutes: 9,
      cycles: 38,
      cycleProgressPct: 54,
    },
    totalProfit: 256.36,
    roi: 85.45,
    apr: 2250,
    lastUpdate: '14:37:02',
    statusText: 'Bot aktiv · Verbunden',
    linkedStrategyId: 'strat_sigma_mean_reversion',
    symbol: 'ETH/USD',
    instrumentType: 'KRAKEN FUTURES · GRID-DCA',
    investmentUsd: 300.0,
    investmentEur: 274.5,
    unrealizedPnlUsd: 227.46,
    unrealizedPnlPct: 75.82,
    currentProfitUsd: 28.9,
    totalProfitUsd: 256.36,
    roiPct: 85.45,
    aprPct: 2250,
    dcaOrdersTriggered: 112,
    lastUpdated: '14:37:02',
  },
  {
    id: 'BOT-5519',
    name: 'Deep-RL Arbitrage Bot',
    exchange: 'Kraken Futures (PF_SOLUSD)',
    status: 'active',
    pair: 'SOL/USD',
    strategy: 'KRAKEN FUTURES · ADAPTIVE DCA',
    direction: 'LONG',
    leverage: 20,
    unrealizedPnL: {
      value: 90.26,
      percentage: 45.13,
    },
    entryPrice: 97.5,
    currentPrice: 99.7,
    metrics: {
      investment: 200.0,
      currency: '$',
      investmentEur: 183.0,
      realizedProfit: 19.8,
      profitCycleType: 'Realisiert (Zyklus)',
      dcaRangeMin: 92,
      dcaRangeMax: 108,
      dcaSteps: 100,
      dcaOrdersTriggered: 64,
      fundingFees: -1.85,
      liquidationPrice: 88.5,
      liquidationDistancePct: -11.23,
    },
    runtime: {
      days: 2,
      hours: 21,
      minutes: 15,
      cycles: 19,
      cycleProgressPct: 82,
    },
    totalProfit: 110.06,
    roi: 55.03,
    apr: 4910,
    lastUpdate: '14:37:02',
    statusText: 'Bot aktiv · Verbunden',
    linkedStrategyId: 'strat_deep_rl',
    symbol: 'SOL/USD',
    instrumentType: 'KRAKEN FUTURES · ADAPTIVE DCA',
    investmentUsd: 200.0,
    investmentEur: 183.0,
    unrealizedPnlUsd: 90.26,
    unrealizedPnlPct: 45.13,
    currentProfitUsd: 19.8,
    totalProfitUsd: 110.06,
    roiPct: 55.03,
    aprPct: 4910,
    dcaOrdersTriggered: 64,
    lastUpdated: '14:37:02',
  },
  {
    id: 'BOT-1083',
    name: 'Microstructure Scalp Bot',
    exchange: 'Kraken Spot / Margin',
    status: 'active',
    pair: 'BTC/USD',
    strategy: 'KRAKEN SPOT · L2 ORDERBOOK DCA',
    direction: 'LONG',
    leverage: 10,
    unrealizedPnL: {
      value: 24.07,
      percentage: 30.09,
    },
    entryPrice: 75900.0,
    currentPrice: 76767.0,
    metrics: {
      investment: 800.0,
      currency: '$',
      investmentEur: 732.0,
      realizedProfit: 61.5,
      profitCycleType: 'Realisiert (Zyklus)',
      dcaRangeMin: 73000,
      dcaRangeMax: 80000,
      dcaSteps: 50,
      dcaOrdersTriggered: 38,
      fundingFees: -0.45,
      liquidationPrice: 69000.0,
      liquidationDistancePct: -9.79,
    },
    runtime: {
      days: 1,
      hours: 11,
      minutes: 4,
      cycles: 12,
      cycleProgressPct: 40,
    },
    totalProfit: 30.22,
    roi: 37.78,
    apr: 650,
    lastUpdate: '14:37:02',
    statusText: 'Bot aktiv · Verbunden',
    linkedStrategyId: 'strat_orderbook_microstructure',
    symbol: 'BTC/USD',
    instrumentType: 'KRAKEN SPOT · L2 ORDERBOOK DCA',
    investmentUsd: 800.0,
    investmentEur: 732.0,
    unrealizedPnlUsd: 24.07,
    unrealizedPnlPct: 30.09,
    currentProfitUsd: 61.5,
    totalProfitUsd: 30.22,
    roiPct: 37.78,
    aprPct: 650,
    dcaOrdersTriggered: 38,
    lastUpdated: '14:37:02',
  },
  {
    id: 'BOT-6621',
    name: 'Gamma Hedging Worker',
    exchange: 'Kraken Derivatives / Futures',
    status: 'active',
    pair: 'ETH/USD',
    strategy: 'KRAKEN FUTURES · SHORT DELTA HEDGE',
    direction: 'SHORT',
    leverage: 20,
    unrealizedPnL: {
      value: 39.44,
      percentage: 26.29,
    },
    entryPrice: 2510.0,
    currentPrice: 2477.0,
    metrics: {
      investment: 150.0,
      currency: '$',
      investmentEur: 137.25,
      realizedProfit: 14.2,
      profitCycleType: 'Realisiert (Zyklus)',
      dcaRangeMin: 2400,
      dcaRangeMax: 2600,
      dcaSteps: 60,
      dcaOrdersTriggered: 42,
      fundingFees: 1.85,
      liquidationPrice: 2650.0,
      liquidationDistancePct: 6.98,
    },
    runtime: {
      days: 4,
      hours: 9,
      minutes: 33,
      cycles: 28,
      cycleProgressPct: 68,
    },
    totalProfit: 53.64,
    roi: 35.76,
    apr: 1940,
    lastUpdate: '14:37:02',
    statusText: 'Bot aktiv · Verbunden',
    symbol: 'ETH/USD',
    instrumentType: 'KRAKEN FUTURES · SHORT DELTA HEDGE',
    investmentUsd: 150.0,
    investmentEur: 137.25,
    unrealizedPnlUsd: 39.44,
    unrealizedPnlPct: 26.29,
    currentProfitUsd: 14.2,
    totalProfitUsd: 53.64,
    roiPct: 35.76,
    aprPct: 1940,
    dcaOrdersTriggered: 42,
    lastUpdated: '14:37:02',
  },
];

/**
 * Helper: Strict Kraken Exchange Identity Normalizer
 * Completely purges all third-party exchange references (Pionix, Pionex, Bybit, Binance, etc.)
 * and canonicalizes the bot to native Kraken venues (Kraken Futures, Kraken Spot / Margin, Kraken Derivatives).
 */
export function normalizeToKrakenExchangeIdentity(bot: WorkerBotData): WorkerBotData {
  let exchange = (bot.exchange || '').trim();
  const rawPair = bot.pair || bot.symbol || 'BTC/USD';

  // 1. Purge third-party labels and map to canonical Kraken venue
  const hasKraken = exchange.toLowerCase().includes('kraken');
  if (!hasKraken || exchange === '') {
    if (bot.id === 'BOT-7742') {
      exchange = 'Kraken Futures';
    } else if (bot.id === 'BOT-9104') {
      exchange = 'Kraken Futures (PF_XBTUSD)';
    } else if (bot.id === 'BOT-3382') {
      exchange = 'Kraken Futures (PF_ETHUSD)';
    } else if (bot.id === 'BOT-5519') {
      exchange = 'Kraken Futures (PF_SOLUSD)';
    } else if (bot.id === 'BOT-1083') {
      exchange = 'Kraken Spot / Margin';
    } else if (bot.id === 'BOT-6621') {
      exchange = 'Kraken Derivatives / Futures';
    } else if (rawPair.includes('ETH')) {
      exchange = 'Kraken Futures (PF_ETHUSD)';
    } else if (rawPair.includes('SOL')) {
      exchange = 'Kraken Futures (PF_SOLUSD)';
    } else {
      exchange = 'Kraken Futures';
    }
  }

  // 2. Canonicalize trading pair (convert any legacy USDT.P or synthetic suffix to USD)
  let canonicalPair = rawPair;
  if (canonicalPair.includes('USDT.P') || canonicalPair.includes('USDT')) {
    canonicalPair = canonicalPair.replace('USDT.P', 'USD').replace('USDT', 'USD');
  }

  // 3. Canonicalize strategy / instrument type labels
  let strategy = bot.strategy || bot.instrumentType || 'KRAKEN FUTURES · DCA STRATEGY';
  if (/pion[ei]x|bybit|binance|dydx|hyperliquid/i.test(strategy)) {
    strategy = strategy.replace(/pion[ei]x|bybit|binance|dydx|hyperliquid/gi, 'KRAKEN');
  }
  if (!strategy.toUpperCase().includes('KRAKEN')) {
    strategy = `KRAKEN FUTURES · ${strategy}`;
  }

  return {
    ...bot,
    exchange,
    pair: canonicalPair,
    symbol: canonicalPair,
    krakenPair: canonicalPair,
    strategy,
    instrumentType: strategy,
  };
}

/**
 * Revaluates established worker bots against real-time orderbook ticks
 * with strict Kraken exchange identity enforcement and zero-latency price parity.
 */
export function updateWorkerBotsWithMarket(
  bots: WorkerBotData[],
  markets: Record<string, OrderbookData>
): WorkerBotData[] {
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];

  return bots.map((rawBot) => {
    // Enforce strict Kraken venue identity and canonical pair
    const bot = normalizeToKrakenExchangeIdentity(rawBot);
    const pair = bot.pair || 'BTC/USD';

    // Strict Kraken WS Ticker matching: Direct lookup or canonical mapping
    let bookSymbol = 'BTC/USD';
    if (markets[pair]) {
      bookSymbol = pair;
    } else if (pair.includes('ETH')) {
      bookSymbol = 'ETH/USD';
    } else if (pair.includes('SOL')) {
      bookSymbol = 'SOL/USD';
    } else if (pair.includes('BTC') || pair.includes('XBT')) {
      bookSymbol = 'BTC/USD';
    } else if (pair.includes('HYPE')) {
      bookSymbol = 'HYPE/USD';
    } else if (pair.includes('NIO')) {
      bookSymbol = 'NIO/USD';
    }

    const book = markets[bookSymbol];
    if (!book || typeof book.lastPrice !== 'number' || book.lastPrice <= 0) {
      return bot;
    }

    const currentPrice = book.lastPrice;
    const entryPrice = bot.entryPrice > 0 ? bot.entryPrice : currentPrice;
    const priceDiff = currentPrice - entryPrice;
    const directionMultiplier = bot.direction === 'LONG' ? 1 : -1;

    // Position nominal value
    const investment = bot.metrics?.investment ?? bot.investmentUsd ?? 100;
    const leverage = bot.leverage > 0 ? bot.leverage : 1;
    const positionNominal = investment * leverage;
    const pnlRatio = entryPrice > 0 ? (priceDiff / entryPrice) * directionMultiplier : 0;
    const unrealizedValue = Math.round(positionNominal * pnlRatio * 100) / 100;
    const unrealizedPct = Math.round(pnlRatio * leverage * 10000) / 100;

    const realizedProfit = bot.metrics?.realizedProfit ?? bot.currentProfitUsd ?? 0;
    const dcaSteps = bot.metrics?.dcaSteps ?? 100;
    const dcaOrdersTriggered = bot.metrics?.dcaOrdersTriggered ?? bot.dcaOrdersTriggered ?? 0;
    const fundingFees = bot.metrics?.fundingFees ?? 0;

    // Transaction fee calculation (strictly adhering to min 0.04% / 4 bps per trade fill)
    const minFeeRate = 0.0004; // min 0.04%
    const trancheSizeUsd = positionNominal / Math.max(dcaSteps, 1);
    const totalTradedVolumeUsd = positionNominal + (dcaOrdersTriggered * trancheSizeUsd);
    const transactionFees = Math.max(0.01, Math.round(totalTradedVolumeUsd * minFeeRate * 100) / 100);
    const totalFees = Math.round((transactionFees + Math.abs(fundingFees)) * 100) / 100;

    const grossProfit = Math.round((realizedProfit + unrealizedValue) * 100) / 100;
    const netProfit = Math.round((grossProfit - totalFees) * 100) / 100;
    const totalProfit = netProfit;
    const roi = investment > 0 ? Math.round((totalProfit / investment) * 10000) / 100 : 0;

    // Liquidation distance
    const liqPrice = bot.metrics?.liquidationPrice ?? (bot.direction === 'LONG' ? currentPrice * 0.92 : currentPrice * 1.08);
    const liqDist = currentPrice > 0 ? Math.round(((liqPrice - currentPrice) / currentPrice) * 10000) / 100 : 0;

    const updatedMetrics = {
      ...bot.metrics,
      liquidationPrice: liqPrice,
      liquidationDistancePct: liqDist,
      transactionFees,
      feeRatePct: 0.04,
      grossProfit,
      totalFees,
      netProfit,
    };

    const updatedUnrealized = {
      value: unrealizedValue,
      percentage: unrealizedPct,
    };

    return {
      ...bot,
      currentPrice,
      unrealizedPnL: updatedUnrealized,
      metrics: updatedMetrics,
      totalProfit,
      roi,
      lastUpdate: timeStr,
      // Sync convenience aliases
      unrealizedPnlUsd: unrealizedValue,
      unrealizedPnlPct: unrealizedPct,
      totalProfitUsd: totalProfit,
      roiPct: roi,
      lastUpdated: timeStr,
    };
  });
}
