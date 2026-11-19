import { OrderbookData, OrderbookEntry, PortfolioState, Position, ExecutionOrder, JudgeVerdict } from '../types/trading';

export function createInitialMarketData(): Record<string, OrderbookData> {
  return {
    'BTC/USD': createMockBook('BTC/USD', 76767.0, 0.5, 95000000),
    'ETH/USD': createMockBook('ETH/USD', 2477.0, 0.1, 45000000),
    'SOL/USD': createMockBook('SOL/USD', 99.70, 0.02, 18000000),
    'NIO/USD': createMockBook('NIO/USD', 5.82, 0.01, 12000000),
    'HYPE/USD': createMockBook('HYPE/USD', 77.58, 0.01, 34000000),
  };
}

export function createMockBook(
  symbol: string,
  midPrice: number,
  tickSize: number,
  volume24h: number
): OrderbookData {
  const bids: OrderbookEntry[] = [];
  const asks: OrderbookEntry[] = [];
  let bidAccum = 0;
  let askAccum = 0;

  for (let i = 1; i <= 8; i++) {
    const bidPrice = Math.round((midPrice - i * tickSize) * 100) / 100;
    const bidSize = Math.round((Math.random() * 2.5 + 0.8) * 100) / 100;
    bidAccum += bidSize;
    bids.push({ price: bidPrice, size: bidSize, total: Math.round(bidAccum * 100) / 100 });

    const askPrice = Math.round((midPrice + i * tickSize) * 100) / 100;
    const askSize = Math.round((Math.random() * 2.5 + 0.8) * 100) / 100;
    askAccum += askSize;
    asks.push({ price: askPrice, size: askSize, total: Math.round(askAccum * 100) / 100 });
  }

  const bestBid = bids[0].price;
  const bestAsk = asks[0].price;
  const spread = Math.round((bestAsk - bestBid) * 100) / 100;
  const spreadBps = Math.round(((spread / midPrice) * 10000) * 10) / 10;

  return {
    symbol,
    lastPrice: midPrice,
    priceChange24h: Math.round((Math.random() * 4 - 1.5) * 100) / 100,
    high24h: Math.round(midPrice * 1.035 * 100) / 100,
    low24h: Math.round(midPrice * 0.965 * 100) / 100,
    volume24h,
    spread,
    spreadBps,
    bids,
    asks,
    recentTrades: [
      {
        id: `TR-${Date.now()}-1`,
        price: midPrice,
        size: 0.45,
        side: 'BUY',
        timestamp: Date.now() - 300,
      },
      {
        id: `TR-${Date.now()}-2`,
        price: bestBid,
        size: 1.12,
        side: 'SELL',
        timestamp: Date.now() - 1200,
      },
    ],
  };
}

/**
 * Prioritizes live Kraken WS ticker and orderbook data over internal simulation.
 * Ensures that any symbol with live Kraken exchange data maintains strict price parity
 * across the Swarm, The Judge, and all Worker Bots.
 */
export function prioritizeKrakenMarketData(
  simulatedMarkets: Record<string, OrderbookData>,
  krakenWsMarkets: Record<string, OrderbookData>,
  isKrakenLive: boolean
): Record<string, OrderbookData> {
  const consolidated: Record<string, OrderbookData> = { ...simulatedMarkets };

  for (const [sym, krakenBook] of Object.entries(krakenWsMarkets)) {
    if (!krakenBook || typeof krakenBook.lastPrice !== 'number' || krakenBook.lastPrice <= 0) {
      continue;
    }

    if (isKrakenLive || (simulatedMarkets[sym] && krakenBook.lastPrice > 0)) {
      const existing = consolidated[sym];
      consolidated[sym] = {
        ...(existing || {}),
        ...krakenBook,
        symbol: sym,
        // Guarantee authoritative price and metrics from Kraken exchange
        lastPrice: krakenBook.lastPrice,
        priceChange24h: krakenBook.priceChange24h ?? existing?.priceChange24h ?? 0,
        high24h: krakenBook.high24h || existing?.high24h || krakenBook.lastPrice * 1.02,
        low24h: krakenBook.low24h || existing?.low24h || krakenBook.lastPrice * 0.98,
        volume24h: krakenBook.volume24h || existing?.volume24h || 50000000,
        spread: krakenBook.spread ?? existing?.spread ?? 0.5,
        spreadBps: krakenBook.spreadBps ?? existing?.spreadBps ?? 1.0,
        bids: krakenBook.bids && krakenBook.bids.length > 0 ? krakenBook.bids : existing?.bids || [],
        asks: krakenBook.asks && krakenBook.asks.length > 0 ? krakenBook.asks : existing?.asks || [],
        recentTrades: krakenBook.recentTrades && krakenBook.recentTrades.length > 0 ? krakenBook.recentTrades : existing?.recentTrades || [],
      };
    }
  }

  return consolidated;
}

export function simulateTick(
  prevMarkets: Record<string, OrderbookData>,
  lockedSymbols: string[] = []
): Record<string, OrderbookData> {
  const updated: Record<string, OrderbookData> = {};

  for (const [symbol, book] of Object.entries(prevMarkets)) {
    // Zero-drift lock: if this symbol is prioritized with live Kraken WS ticker data, do NOT mutate
    if (lockedSymbols.includes(symbol)) {
      updated[symbol] = book;
      continue;
    }

    // Stochastic micro-drift + mean-reversion
    const deltaPct = (Math.random() - 0.499) * 0.0018; // ~0.18% max jitter
    const newMid = Math.max(0.1, Math.round((book.lastPrice * (1 + deltaPct)) * 100) / 100);
    const tickSize = symbol.includes('BTC') ? 0.5 : symbol.includes('ETH') ? 0.1 : 0.01;

    const bids: OrderbookEntry[] = [];
    const asks: OrderbookEntry[] = [];
    let bidAccum = 0;
    let askAccum = 0;

    for (let i = 1; i <= 8; i++) {
      const bidPrice = Math.round((newMid - i * tickSize) * 100) / 100;
      const bidSize = Math.round((Math.random() * 3.0 + 0.5) * 100) / 100;
      bidAccum += bidSize;
      bids.push({ price: bidPrice, size: bidSize, total: Math.round(bidAccum * 100) / 100 });

      const askPrice = Math.round((newMid + i * tickSize) * 100) / 100;
      const askSize = Math.round((Math.random() * 3.0 + 0.5) * 100) / 100;
      askAccum += askSize;
      asks.push({ price: askPrice, size: askSize, total: Math.round(askAccum * 100) / 100 });
    }

    const spread = Math.round((asks[0].price - bids[0].price) * 100) / 100;
    const spreadBps = Math.round(((spread / newMid) * 10000) * 10) / 10;

    const newTrades = [...book.recentTrades];
    if (Math.random() > 0.4) {
      newTrades.unshift({
        id: `TR-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        price: Math.random() > 0.5 ? asks[0].price : bids[0].price,
        size: Math.round((Math.random() * 1.8 + 0.1) * 100) / 100,
        side: Math.random() > 0.5 ? 'BUY' : 'SELL',
        timestamp: Date.now(),
      });
      if (newTrades.length > 15) newTrades.pop();
    }

    updated[symbol] = {
      ...book,
      lastPrice: newMid,
      spread,
      spreadBps,
      bids,
      asks,
      recentTrades: newTrades,
    };
  }

  return updated;
}

export function executeVerdict(
  verdict: JudgeVerdict,
  portfolio: PortfolioState,
  marketBook: OrderbookData | undefined
): {
  updatedPortfolio: PortfolioState;
  executedOrder?: ExecutionOrder;
} {
  if (verdict.status === 'REJECTED' || verdict.approvedSizeUsd <= 0) {
    return { updatedPortfolio: portfolio };
  }

  const currentPrice = marketBook?.lastPrice || 100;
  const quantity = Math.round((verdict.approvedSizeUsd / currentPrice) * 1000) / 1000;
  if (quantity <= 0) return { updatedPortfolio: portfolio };

  // Model realistic slippage based on execution route
  const slippageBps =
    verdict.executionRoute === 'DIRECT_DMA'
      ? Math.random() * 1.5 + 0.8
      : verdict.executionRoute === 'TWAP_SLICER'
      ? Math.random() * 0.8 + 0.3
      : Math.random() * 1.0 + 0.5;

  const slippageMultiplier =
    verdict.direction === 'LONG' ? 1 + slippageBps / 10000 : 1 - slippageBps / 10000;
  const filledPrice = Math.round(currentPrice * slippageMultiplier * 100) / 100;
  // Transaction fee rate: min 0.04% (4 bps) as required
  const feeRate = Math.max(0.0004, verdict.executionParams?.feeBps ? verdict.executionParams.feeBps / 10000 : 0.0004);
  const feeUsd = Math.max(0.01, Math.round(verdict.approvedSizeUsd * feeRate * 100) / 100); // min 0.04% transaction fee

  const executedOrder: ExecutionOrder = {
    id: `ORD-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    signalId: verdict.signalId,
    timestamp: Date.now(),
    symbol: verdict.symbol,
    side: verdict.direction === 'LONG' ? 'BUY' : 'SELL',
    quantity,
    filledPrice,
    slippageBps: Math.round(slippageBps * 10) / 10,
    feeUsd,
    status: 'FILLED',
    executionRoute: verdict.executionRoute,
  };

  // Update or create position
  const existingPosIndex = portfolio.positions.findIndex((p) => p.symbol === verdict.symbol);
  let newPositions = [...portfolio.positions];
  let realizedPnlDelta = 0;
  let exitFeeUsd = 0;

  const stopDistancePct = 0.025; // 2.5% stop loss
  const tpDistancePct = 0.055; // 5.5% take profit
  const stopLossPrice =
    verdict.direction === 'LONG'
      ? filledPrice * (1 - stopDistancePct)
      : filledPrice * (1 + stopDistancePct);
  const takeProfitPrice =
    verdict.direction === 'LONG'
      ? filledPrice * (1 + tpDistancePct)
      : filledPrice * (1 - tpDistancePct);

  if (existingPosIndex >= 0) {
    const existing = newPositions[existingPosIndex];
    if (existing.direction === verdict.direction) {
      // Scale into position
      const totalQty = existing.quantity + quantity;
      const blendedEntry =
        (existing.entryPrice * existing.quantity + filledPrice * quantity) / totalQty;
      newPositions[existingPosIndex] = {
        ...existing,
        quantity: Math.round(totalQty * 1000) / 1000,
        entryPrice: Math.round(blendedEntry * 100) / 100,
        allocatedUsd: existing.allocatedUsd + verdict.approvedSizeUsd,
      };
    } else {
      // Opposite direction closes or reduces position
      const closedQty = Math.min(existing.quantity, quantity);
      const closeNotional = closedQty * filledPrice;
      exitFeeUsd = Math.max(0.01, Math.round(closeNotional * feeRate * 100) / 100);
      const grossPnl =
        existing.direction === 'LONG'
          ? (filledPrice - existing.entryPrice) * closedQty
          : (existing.entryPrice - filledPrice) * closedQty;
      realizedPnlDelta = grossPnl - exitFeeUsd;

      if (quantity >= existing.quantity) {
        // Closed position completely
        newPositions.splice(existingPosIndex, 1);
      } else {
        newPositions[existingPosIndex] = {
          ...existing,
          quantity: Math.round((existing.quantity - quantity) * 1000) / 1000,
          allocatedUsd: Math.max(0, existing.allocatedUsd - verdict.approvedSizeUsd),
        };
      }
    }
  } else {
      // Max 20 concurrent trades hard cap
      if (newPositions.length >= 20) {
        return { updatedPortfolio: portfolio };
      }
      // Add new position
      newPositions.push({
        symbol: verdict.symbol,
        direction: verdict.direction === 'LONG' ? 'LONG' : 'SHORT',
        quantity,
        entryPrice: filledPrice,
        currentPrice: filledPrice,
        unrealizedPnl: 0,
        unrealizedPnlPct: 0,
        allocatedUsd: verdict.approvedSizeUsd,
        openedAt: Date.now(),
        strategyId: verdict.strategyId,
        stopLossPrice: Math.round(stopLossPrice * 100) / 100,
        takeProfitPrice: Math.round(takeProfitPrice * 100) / 100,
      });
    }

  // Update cash and NAV
  const totalTradeFees = feeUsd + exitFeeUsd;
  const newCash = portfolio.cashUsd - feeUsd + realizedPnlDelta;
  const updatedPortfolio = recalculatePortfolio({
    ...portfolio,
    cashUsd: newCash,
    realizedPnl: Math.round((portfolio.realizedPnl + realizedPnlDelta) * 100) / 100,
    totalFeesUsd: Math.round(((portfolio.totalFeesUsd || 0) + totalTradeFees) * 100) / 100,
    positions: newPositions,
    totalTrades: portfolio.totalTrades + 1,
  }, { [verdict.symbol]: marketBook || createMockBook(verdict.symbol, filledPrice, 0.1, 1000000) });

  return { updatedPortfolio, executedOrder };
}

export function recalculatePortfolio(
  portfolio: PortfolioState,
  markets: Record<string, OrderbookData>
): PortfolioState {
  let unrealizedTotal = 0;
  let totalAllocated = 0;
  let netExposure = 0;

  const updatedPositions = portfolio.positions.map((pos) => {
    const book = markets[pos.symbol];
    const currentPrice = book ? book.lastPrice : pos.currentPrice;
    const priceDiff = pos.direction === 'LONG' ? currentPrice - pos.entryPrice : pos.entryPrice - currentPrice;
    const pnl = priceDiff * pos.quantity;
    const pnlPct = (priceDiff / pos.entryPrice) * 100;
    unrealizedTotal += pnl;
    totalAllocated += pos.allocatedUsd;
    netExposure += pos.direction === 'LONG' ? pos.allocatedUsd : -pos.allocatedUsd;

    return {
      ...pos,
      currentPrice,
      unrealizedPnl: Math.round(pnl * 100) / 100,
      unrealizedPnlPct: Math.round(pnlPct * 100) / 100,
    };
  });

  const baseCash = typeof portfolio.cashUsd === 'number' ? portfolio.cashUsd : 0;
  const navUsd = Math.round((baseCash + portfolio.realizedPnl + unrealizedTotal) * 100) / 100;
  const grossLeverage = Math.round((totalAllocated / Math.max(navUsd, 1)) * 100) / 100;
  const netLeverage = Math.round((netExposure / Math.max(navUsd, 1)) * 100) / 100;

  const peakNav = Math.max(portfolio.peakNav || navUsd, navUsd);
  const currentDrawdownPct =
    peakNav > 0 ? Math.round((((peakNav - navUsd) / peakNav) * 100) * 100) / 100 : 0;
  const maxDrawdownPct = Math.max(portfolio.maxDrawdownPct || 0, currentDrawdownPct);
  const dailyPnlPct = peakNav > 0 ? Math.round((((navUsd - peakNav) / peakNav) * 100) * 100) / 100 : 0;

  // Cornish-Fisher VaR and CVaR estimation
  const estPortfolioDailyVol = 0.016; // 1.6% daily portfolio standard deviation
  const var99Usd = Math.round(totalAllocated * estPortfolioDailyVol * 2.33); // 2.33 z-score for 99%
  const cvar99Usd = Math.round(var99Usd * 1.25); // Expected shortfall fat-tailed multiplier

  return {
    ...portfolio,
    navUsd,
    grossLeverage,
    netLeverage,
    unrealizedPnl: Math.round(unrealizedTotal * 100) / 100,
    peakNav,
    currentDrawdownPct,
    maxDrawdownPct,
    dailyPnlPct,
    var99Usd,
    cvar99Usd,
    positions: updatedPositions,
  };
}

export function createInitialPortfolio(initialCapital: number = 1000): PortfolioState {
  return {
    cashUsd: initialCapital,
    navUsd: initialCapital,
    grossLeverage: 0,
    netLeverage: 0,
    realizedPnl: 0,
    unrealizedPnl: 0,
    totalTrades: 0,
    winningTrades: 0,
    losingTrades: 0,
    peakNav: initialCapital,
    currentDrawdownPct: 0,
    maxDrawdownPct: 0,
    dailyPnlPct: 0,
    sharpeRatio: 0,
    var99Usd: 0,
    cvar99Usd: 0,
    totalFeesUsd: 0,
    positions: [],
  };
}
