import {
  OrderbookData,
  OrderbookEntry,
  PortfolioState,
  Position,
  ExecutionOrder,
  JudgeVerdict,
} from '../types/trading';

export interface AssetConfig {
  symbol: string;
  name: string;
  basePrice: number;
  tickSize: number;
  volatility: number;
  drift: number;
  typicalSpreadBps: number;
}

export const SUPPORTED_ASSETS: AssetConfig[] = [
  { symbol: 'BTC/USD', name: 'Bitcoin Perpetual', basePrice: 76767.0, tickSize: 0.5, volatility: 0.0012, drift: 0.00001, typicalSpreadBps: 1.5 },
  { symbol: 'ETH/USD', name: 'Ethereum Perpetual', basePrice: 2477.0, tickSize: 0.05, volatility: 0.0018, drift: 0.00001, typicalSpreadBps: 2.1 },
  { symbol: 'SOL/USD', name: 'Solana Perpetual', basePrice: 99.70, tickSize: 0.01, volatility: 0.0026, drift: 0.00002, typicalSpreadBps: 3.4 },
  { symbol: 'HYPE/USD', name: 'Hyperliquid Token', basePrice: 77.58, tickSize: 0.01, volatility: 0.0035, drift: 0.00002, typicalSpreadBps: 1.8 },
  { symbol: 'NVDA', name: 'Nvidia Corp Equities', basePrice: 128.4, tickSize: 0.01, volatility: 0.0015, drift: 0.00001, typicalSpreadBps: 2.0 },
  { symbol: 'SPY', name: 'S&P 500 ETF Trust', basePrice: 554.2, tickSize: 0.01, volatility: 0.0008, drift: 0.000005, typicalSpreadBps: 0.8 },
];

export function initializeMarketData(): Record<string, OrderbookData> {
  const initialData: Record<string, OrderbookData> = {};
  for (const asset of SUPPORTED_ASSETS) {
    initialData[asset.symbol] = generateOrderbook(asset, asset.basePrice);
  }
  return initialData;
}

export function updateMarketPrices(
  currentData: Record<string, OrderbookData>,
  tickCount: number
): Record<string, OrderbookData> {
  const updatedData: Record<string, OrderbookData> = {};

  for (const asset of SUPPORTED_ASSETS) {
    const prevBook = currentData[asset.symbol];
    const prevPrice = prevBook ? prevBook.lastPrice : asset.basePrice;

    // Geometric Brownian motion with jump-diffusion
    const normalShock = (Math.random() - 0.5 + (Math.random() - 0.5)) * 1.5;
    const isJump = Math.random() < 0.04;
    const jumpShock = isJump ? (Math.random() - 0.5) * 4.0 : 0;
    const deltaPct = asset.drift + asset.volatility * normalShock + asset.volatility * jumpShock;

    let newPrice = prevPrice * (1 + deltaPct);
    newPrice = Math.round(newPrice / asset.tickSize) * asset.tickSize;
    if (newPrice <= 0.01) newPrice = prevPrice;

    updatedData[asset.symbol] = generateOrderbook(asset, newPrice, prevBook);
  }

  return updatedData;
}

function generateOrderbook(
  asset: AssetConfig,
  midPrice: number,
  prevBook?: OrderbookData
): OrderbookData {
  const spread = Math.max(asset.tickSize, midPrice * (asset.typicalSpreadBps / 10000));
  const halfSpread = spread / 2;
  const spreadBps = Math.round((spread / midPrice) * 10000 * 10) / 10;

  const bids: OrderbookEntry[] = [];
  const asks: OrderbookEntry[] = [];

  let bidAcc = 0;
  let askAcc = 0;
  const levels = 8;

  for (let i = 0; i < levels; i++) {
    const bidPrice = Math.round((midPrice - halfSpread - i * asset.tickSize * (1 + i * 0.2)) / asset.tickSize) * asset.tickSize;
    const askPrice = Math.round((midPrice + halfSpread + i * asset.tickSize * (1 + i * 0.2)) / asset.tickSize) * asset.tickSize;

    // Depth scales with square root of distance from mid
    const baseSize = asset.basePrice > 1000 ? 0.4 + Math.random() * 0.8 : 25 + Math.random() * 60;
    const bidSize = Math.round(baseSize * (1 + i * 0.4) * 100) / 100;
    const askSize = Math.round(baseSize * (1 + i * 0.4) * 100) / 100;

    bidAcc += bidSize;
    askAcc += askSize;

    bids.push({ price: bidPrice, size: bidSize, total: Math.round(bidAcc * 100) / 100 });
    asks.push({ price: askPrice, size: askSize, total: Math.round(askAcc * 100) / 100 });
  }

  // Recent trades tape
  const recentTrades = prevBook ? [...prevBook.recentTrades] : [];
  if (Math.random() < 0.75) {
    const side: 'BUY' | 'SELL' = Math.random() > 0.5 ? 'BUY' : 'SELL';
    const fillPrice = side === 'BUY' ? asks[0].price : bids[0].price;
    const fillSize = Math.round((bids[0].size * (0.2 + Math.random() * 0.6)) * 100) / 100;
    recentTrades.unshift({
      id: `TRD-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      price: fillPrice,
      size: fillSize,
      side,
      timestamp: Date.now(),
    });
    if (recentTrades.length > 20) recentTrades.pop();
  }

  const high24h = prevBook ? Math.max(prevBook.high24h, midPrice) : midPrice * 1.025;
  const low24h = prevBook ? Math.min(prevBook.low24h, midPrice) : midPrice * 0.975;
  const volume24h = prevBook ? prevBook.volume24h + Math.floor(Math.random() * 12) : 184500;
  const priceChange24h = Math.round(((midPrice - asset.basePrice) / asset.basePrice) * 10000) / 100;

  return {
    symbol: asset.symbol,
    lastPrice: midPrice,
    priceChange24h,
    high24h: Math.round(high24h * 100) / 100,
    low24h: Math.round(low24h * 100) / 100,
    volume24h,
    spread: Math.round(spread * 100) / 100,
    spreadBps,
    bids,
    asks,
    recentTrades,
  };
}

export function executeVerdict(
  verdict: JudgeVerdict,
  portfolio: PortfolioState,
  book: OrderbookData | undefined
): { updatedPortfolio: PortfolioState; executionOrder?: ExecutionOrder } {
  if (verdict.status === 'REJECTED' || verdict.approvedSizeUsd <= 0 || !book) {
    return { updatedPortfolio: portfolio };
  }

  const midPrice = book.lastPrice;
  const isBuy = verdict.direction === 'LONG';
  // Slippage simulation via square-root law
  const baseSlippageBps = (book.spreadBps / 2) + (verdict.approvedSizeUsd / 200000) * 1.5;
  const effectiveSlippageBps = Math.min(verdict.executionParams.maxSlippageBps, baseSlippageBps);
  const slippageMultiplier = isBuy ? 1 + effectiveSlippageBps / 10000 : 1 - effectiveSlippageBps / 10000;
  const filledPrice = Math.round(midPrice * slippageMultiplier * 100) / 100;

  const quantity = Math.round((verdict.approvedSizeUsd / filledPrice) * 10000) / 10000;
  // Transaction fee rate: min 0.04% (4 bps)
  const feeRate = Math.max(0.0004, verdict.executionParams?.feeBps ? verdict.executionParams.feeBps / 10000 : 0.0004);
  const feeUsd = Math.max(0.01, Math.round(verdict.approvedSizeUsd * feeRate * 100) / 100); // min 0.04% fee

  const executionOrder: ExecutionOrder = {
    id: `ORD-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    signalId: verdict.signalId,
    timestamp: Date.now(),
    symbol: verdict.symbol,
    side: isBuy ? 'BUY' : 'SELL',
    quantity,
    filledPrice,
    slippageBps: Math.round(effectiveSlippageBps * 10) / 10,
    feeUsd,
    status: 'FILLED',
    executionRoute: verdict.executionRoute,
  };

  // Update existing position or open new
  const existingPosIndex = portfolio.positions.findIndex((p) => p.symbol === verdict.symbol);
  let updatedPositions = [...portfolio.positions];
  let realizedPnlDelta = 0;
  let exitFeeUsd = 0;
  let winningDelta = 0;
  let losingDelta = 0;

  if (existingPosIndex >= 0) {
    const currentPos = updatedPositions[existingPosIndex];
    // If same direction, average in
    if (currentPos.direction === verdict.direction) {
      const totalQty = currentPos.quantity + quantity;
      const avgEntry = (currentPos.entryPrice * currentPos.quantity + filledPrice * quantity) / totalQty;
      const totalAllocated = currentPos.allocatedUsd + verdict.approvedSizeUsd;
      updatedPositions[existingPosIndex] = {
        ...currentPos,
        quantity: Math.round(totalQty * 10000) / 10000,
        entryPrice: Math.round(avgEntry * 100) / 100,
        allocatedUsd: totalAllocated,
      };
    } else {
      // Opposite direction: close or flip
      const closedQty = Math.min(currentPos.quantity, quantity);
      exitFeeUsd = Math.max(0.01, Math.round(closedQty * filledPrice * feeRate * 100) / 100);
      const pnl = currentPos.direction === 'LONG'
        ? (filledPrice - currentPos.entryPrice) * closedQty
        : (currentPos.entryPrice - filledPrice) * closedQty;

      realizedPnlDelta = pnl - feeUsd - exitFeeUsd;
      if (realizedPnlDelta > 0) winningDelta = 1;
      else losingDelta = 1;

      if (quantity >= currentPos.quantity) {
        // Closed position completely
        updatedPositions.splice(existingPosIndex, 1);
      } else {
        // Partially reduced
        const remainingQty = currentPos.quantity - quantity;
        updatedPositions[existingPosIndex] = {
          ...currentPos,
          quantity: Math.round(remainingQty * 10000) / 10000,
          allocatedUsd: Math.round(remainingQty * currentPos.entryPrice),
        };
      }
    }
  } else {
    // Open brand new position
    const stopDistance = filledPrice * 0.015; // 1.5% stop
    const takeDistance = filledPrice * 0.035; // 3.5% target
    const newPosition: Position = {
      symbol: verdict.symbol,
      direction: verdict.direction as 'LONG' | 'SHORT',
      quantity,
      entryPrice: filledPrice,
      currentPrice: filledPrice,
      unrealizedPnl: 0,
      unrealizedPnlPct: 0,
      allocatedUsd: verdict.approvedSizeUsd,
      openedAt: Date.now(),
      strategyId: verdict.strategyId,
      stopLossPrice: isBuy ? filledPrice - stopDistance : filledPrice + stopDistance,
      takeProfitPrice: isBuy ? filledPrice + takeDistance : filledPrice - takeDistance,
    };
    updatedPositions.push(newPosition);
  }

  // Calculate updated portfolio metrics
  let totalUnrealizedPnl = 0;
  let totalPositionValue = 0;
  for (const pos of updatedPositions) {
    const currentPrice = pos.symbol === verdict.symbol ? filledPrice : pos.currentPrice;
    const diff = pos.direction === 'LONG' ? currentPrice - pos.entryPrice : pos.entryPrice - currentPrice;
    pos.unrealizedPnl = Math.round(diff * pos.quantity * 100) / 100;
    pos.unrealizedPnlPct = Math.round((pos.unrealizedPnl / pos.allocatedUsd) * 10000) / 100;
    pos.currentPrice = currentPrice;
    totalUnrealizedPnl += pos.unrealizedPnl;
    totalPositionValue += pos.allocatedUsd;
  }

  const updatedCash = portfolio.cashUsd - (verdict.approvedSizeUsd * 0.1) - feeUsd + realizedPnlDelta;
  const updatedNav = portfolio.cashUsd + totalUnrealizedPnl + portfolio.realizedPnl + realizedPnlDelta;
  const peakNav = Math.max(portfolio.peakNav, updatedNav);
  const currentDrawdownPct = Math.max(0, ((peakNav - updatedNav) / peakNav) * 100);
  const maxDrawdownPct = Math.max(portfolio.maxDrawdownPct, currentDrawdownPct);
  const grossLeverage = Math.round((totalPositionValue / Math.max(updatedNav, 1)) * 100) / 100;

  // 99% CVaR approximation
  const cvar99Usd = Math.round(totalPositionValue * 0.072);
  const var99Usd = Math.round(totalPositionValue * 0.048);

  const updatedPortfolio: PortfolioState = {
    ...portfolio,
    cashUsd: Math.round(updatedCash * 100) / 100,
    navUsd: Math.round(updatedNav * 100) / 100,
    realizedPnl: Math.round((portfolio.realizedPnl + realizedPnlDelta) * 100) / 100,
    unrealizedPnl: Math.round(totalUnrealizedPnl * 100) / 100,
    grossLeverage,
    netLeverage: Math.round((grossLeverage * 0.4) * 100) / 100,
    totalTrades: portfolio.totalTrades + 1,
    winningTrades: portfolio.winningTrades + winningDelta,
    losingTrades: portfolio.losingTrades + losingDelta,
    peakNav: Math.round(peakNav * 100) / 100,
    currentDrawdownPct: Math.round(currentDrawdownPct * 100) / 100,
    maxDrawdownPct: Math.round(maxDrawdownPct * 100) / 100,
    dailyPnlPct: portfolio.peakNav > 0 ? Math.round(((updatedNav - portfolio.peakNav) / portfolio.peakNav) * 10000) / 100 : 0,
    cvar99Usd,
    var99Usd,
    totalFeesUsd: Math.round(((portfolio.totalFeesUsd || 0) + feeUsd + exitFeeUsd) * 100) / 100,
    positions: updatedPositions,
  };

  return { updatedPortfolio, executionOrder };
}
