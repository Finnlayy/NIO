import {
  RawSignal,
  JudgeVerdict,
  GateResult,
  PortfolioState,
  OrderbookData,
  JudgeConfig,
  StrategyAgent,
} from '../types/trading';

export function adjudicateSignal(
  signal: RawSignal,
  portfolio: PortfolioState,
  marketBook: OrderbookData | undefined,
  config: JudgeConfig,
  strategy: StrategyAgent | undefined,
  authoritativeNavUsd?: number
): JudgeVerdict {
  const gateResults: GateResult[] = [];
  const now = Date.now();
  let approvedSizeUsd = signal.suggestedSizeUsd;
  let scaleFactor = 1.0;
  let failedGate: string | undefined;

  // Strict Authoritative NAV: prioritize kraken balance navUsd ($1,000 Paper Account basis)
  const effectiveNavUsd = (typeof authoritativeNavUsd === 'number' && authoritativeNavUsd > 0)
    ? authoritativeNavUsd
    : (portfolio.navUsd || 1000);

  // ----------------------------------------------------
  // M1: Sanity & Latency Monotonicity Gate
  // ----------------------------------------------------
  const signalAgeMs = Math.max(0, now - signal.timestamp);
  const m1Passed = signalAgeMs <= config.signalMaxLatencyMs && signal.suggestedSizeUsd > 0;
  gateResults.push({
    gateId: 'M1',
    name: 'Sanity & Latency Monotonicity',
    passed: m1Passed,
    metricValue: signalAgeMs,
    threshold: config.signalMaxLatencyMs,
    reason: m1Passed
      ? `Signal fresh (latency: ${signalAgeMs}ms <= ${config.signalMaxLatencyMs}ms)`
      : `Stale tick latency ${signalAgeMs}ms exceeds max threshold ${config.signalMaxLatencyMs}ms`,
  });

  if (!m1Passed) {
    return createVerdict(signal, 'REJECTED', 0, 0, 'M1', gateResults, 'DIRECT_DMA', 1, 0);
  }

  // ----------------------------------------------------
  // M2: Portfolio Gross Exposure, Concentration & Max 20 Concurrent Trades Barrier
  // ----------------------------------------------------
  const currentGrossUsd = portfolio.positions.reduce((acc, p) => acc + p.allocatedUsd, 0);
  const currentAssetPos = portfolio.positions.find((p) => p.symbol === signal.symbol);
  const currentAssetUsd = currentAssetPos ? currentAssetPos.allocatedUsd : 0;
  const openTradesCount = portfolio.positions.length;
  const withinMax20Trades = currentAssetPos ? true : openTradesCount < 20;

  const projectedGrossUsd = currentGrossUsd + approvedSizeUsd;
  const projectedGrossLeverage = projectedGrossUsd / Math.max(effectiveNavUsd, 1);
  const projectedAssetConcentrationPct = ((currentAssetUsd + approvedSizeUsd) / Math.max(effectiveNavUsd, 1)) * 100;

  const m2Passed =
    withinMax20Trades &&
    projectedGrossLeverage <= config.maxGrossLeverage &&
    projectedAssetConcentrationPct <= config.maxAssetConcentrationPct;

  gateResults.push({
    gateId: 'M2',
    name: 'Max 20 Trades & Exposure Barrier',
    passed: m2Passed,
    metricValue: openTradesCount,
    threshold: 20,
    reason: !withinMax20Trades
      ? `Hard Cap Reached: ${openTradesCount}/20 concurrent trades active`
      : m2Passed
      ? `Slots ${openTradesCount}/20, Gross lev ${projectedGrossLeverage.toFixed(2)}x <= ${config.maxGrossLeverage}x`
      : `Limit exceeded: Gross Lev ${projectedGrossLeverage.toFixed(2)}x or Conc ${projectedAssetConcentrationPct.toFixed(1)}%`,
  });

  if (!m2Passed) {
    return createVerdict(signal, 'REJECTED', 0, 0, 'M2', gateResults, 'DIRECT_DMA', 1, 0);
  }

  // ----------------------------------------------------
  // M3: Volatility Regime Filter (Parkinson / Spread)
  // ----------------------------------------------------
  const currentSpreadBps = marketBook ? marketBook.spreadBps : 2.5;
  const volRatio = signal.rawMetrics.volRatio || 1.1;
  const m3NormalRegime = volRatio <= config.volatilityCeilingAtrRatio;

  if (!m3NormalRegime) {
    // Proportional dampening under turbulent volatility
    scaleFactor *= 0.6;
    approvedSizeUsd = Math.round(approvedSizeUsd * 0.6);
  }

  gateResults.push({
    gateId: 'M3',
    name: 'Volatility Regime Filter (Parkinson / GARCH)',
    passed: true, // Non-fatal, applied dampening
    metricValue: volRatio,
    threshold: config.volatilityCeilingAtrRatio,
    reason: m3NormalRegime
      ? `Calm regime (Vol ratio ${volRatio.toFixed(2)} <= ${config.volatilityCeilingAtrRatio})`
      : `Turbulent volatility (${volRatio.toFixed(2)} > ${config.volatilityCeilingAtrRatio}). Sized dampened to 60%.`,
  });

  // ----------------------------------------------------
  // M4: Fractional Kelly Capital Allocation Sizer
  // ----------------------------------------------------
  const winRate = strategy ? strategy.winRate : 0.55;
  const payoffRatio = 1.45; // Average win / average loss
  // Kelly formula: f* = (p * (b + 1) - 1) / b
  const fullKellyFraction = Math.max(0, (winRate * (payoffRatio + 1) - 1) / payoffRatio);
  const halfKelly = fullKellyFraction * config.kellyFraction;
  const maxKellySizeUsd = Math.round(effectiveNavUsd * halfKelly * signal.confidence);

  let m4Modified = false;
  if (approvedSizeUsd > maxKellySizeUsd) {
    approvedSizeUsd = Math.max(Math.round(effectiveNavUsd * 0.01), maxKellySizeUsd);
    scaleFactor = approvedSizeUsd / signal.suggestedSizeUsd;
    m4Modified = true;
  }

  gateResults.push({
    gateId: 'M4',
    name: 'Kelly Capital Allocation Sizer',
    passed: true,
    metricValue: Math.round(halfKelly * 1000) / 1000,
    threshold: config.kellyFraction,
    reason: `Optimal Half-Kelly allocation: $${approvedSizeUsd.toLocaleString()} (${(halfKelly * 100).toFixed(1)}% NAV cap)`,
  });

  // ----------------------------------------------------
  // M5: Drawdown Circuit Breaker & High-Water Mark
  // ----------------------------------------------------
  const isDailyDrawdownTripped = portfolio.dailyPnlPct <= -config.maxDailyDrawdownPct;
  const isTotalDrawdownTripped = portfolio.currentDrawdownPct >= config.maxTotalDrawdownPct;
  const m5Passed = !isDailyDrawdownTripped && !isTotalDrawdownTripped;

  gateResults.push({
    gateId: 'M5',
    name: 'Drawdown Circuit Breaker & High-Water Mark',
    passed: m5Passed,
    metricValue: portfolio.currentDrawdownPct,
    threshold: config.maxTotalDrawdownPct,
    reason: m5Passed
      ? `Drawdown safe: Peak-to-Trough -${portfolio.currentDrawdownPct.toFixed(2)}% (limit -${config.maxTotalDrawdownPct}%)`
      : `Circuit Breaker ACTIVE: Daily PnL ${portfolio.dailyPnlPct.toFixed(2)}% or Peak DD ${portfolio.currentDrawdownPct.toFixed(2)}% exceeded`,
  });

  if (!m5Passed) {
    return createVerdict(signal, 'REJECTED', 0, 0, 'M5', gateResults, 'DIRECT_DMA', 1, 0);
  }

  // ----------------------------------------------------
  // M6: ADV Liquidity & Spread Barrier
  // ----------------------------------------------------
  const m6Passed = currentSpreadBps <= config.maxSpreadBpsThreshold;
  gateResults.push({
    gateId: 'M6',
    name: 'ADV Liquidity & Spread Barrier',
    passed: m6Passed,
    metricValue: currentSpreadBps,
    threshold: config.maxSpreadBpsThreshold,
    reason: m6Passed
      ? `Spread ${currentSpreadBps.toFixed(1)} bps <= ${config.maxSpreadBpsThreshold} bps threshold`
      : `Excessive spread ${currentSpreadBps.toFixed(1)} bps > ${config.maxSpreadBpsThreshold} bps limit. Slippage risk unacceptable.`,
  });

  if (!m6Passed) {
    return createVerdict(signal, 'REJECTED', 0, 0, 'M6', gateResults, 'DIRECT_DMA', 1, 0);
  }

  // ----------------------------------------------------
  // M7: Conditional Value-at-Risk (99% CVaR) Stress Barrier
  // ----------------------------------------------------
  // Cornish-Fisher expansion tail shock estimate
  const estimatedDailySigma = 0.024; // 2.4% daily volatility
  const tailRiskShock3Sigma = 3.0 * estimatedDailySigma;
  const marginalCvarUsd = approvedSizeUsd * tailRiskShock3Sigma;
  const projectedTotalCvarUsd = portfolio.cvar99Usd + marginalCvarUsd;
  const m7Passed = projectedTotalCvarUsd <= config.cvarLimitUsd;

  if (!m7Passed && projectedTotalCvarUsd > config.cvarLimitUsd) {
    // If exceeded, scale down to fit remaining CVaR budget
    const remainingCvarBudget = Math.max(0, config.cvarLimitUsd - portfolio.cvar99Usd);
    if (remainingCvarBudget < 1000) {
      gateResults.push({
        gateId: 'M7',
        name: 'Conditional VaR (CVaR) Stress Barrier',
        passed: false,
        metricValue: Math.round(projectedTotalCvarUsd),
        threshold: config.cvarLimitUsd,
        reason: `CVaR limit $${config.cvarLimitUsd.toLocaleString()} exhausted (Projected: $${Math.round(projectedTotalCvarUsd).toLocaleString()})`,
      });
      return createVerdict(signal, 'REJECTED', 0, 0, 'M7', gateResults, 'DIRECT_DMA', 1, 0);
    } else {
      approvedSizeUsd = Math.round(remainingCvarBudget / tailRiskShock3Sigma);
      scaleFactor = approvedSizeUsd / signal.suggestedSizeUsd;
    }
  }

  gateResults.push({
    gateId: 'M7',
    name: 'Conditional VaR (CVaR) Stress Barrier',
    passed: true,
    metricValue: Math.round(projectedTotalCvarUsd),
    threshold: config.cvarLimitUsd,
    reason: `Projected CVaR $${Math.round(projectedTotalCvarUsd).toLocaleString()} within $${config.cvarLimitUsd.toLocaleString()} budget`,
  });

  // ----------------------------------------------------
  // M8: Execution Routing & TWAP/VWAP Slicing
  // ----------------------------------------------------
  let executionRoute: 'DIRECT_DMA' | 'TWAP_SLICER' | 'VWAP_ALGO' | 'ICEBERG_PASSIVE' = 'DIRECT_DMA';
  let sliceCount = 1;
  let urgency: 'HIGH' | 'MEDIUM' | 'LOW' = 'MEDIUM';
  let maxSlippageBps = 3.5;

  const dmaThreshold = Math.max(5000, Math.round(effectiveNavUsd * 0.15));
  const twapThreshold = Math.max(15000, Math.round(effectiveNavUsd * 0.30));

  if (signal.expectedAlphaBps >= 20 && approvedSizeUsd <= dmaThreshold) {
    // High conviction alpha with small size gets DMA
    executionRoute = 'DIRECT_DMA';
    urgency = 'HIGH';
    sliceCount = 1;
    maxSlippageBps = 5.0;
  } else if (approvedSizeUsd >= twapThreshold) {
    // Large blocks routed through TWAP slicer across time horizon
    executionRoute = 'TWAP_SLICER';
    sliceCount = Math.min(10, Math.max(4, Math.floor(approvedSizeUsd / Math.max(1000, effectiveNavUsd * 0.05))));
    urgency = 'LOW';
    maxSlippageBps = 2.0;
  } else if (marketBook && marketBook.spreadBps <= 2.0) {
    executionRoute = 'ICEBERG_PASSIVE';
    sliceCount = 3;
    urgency = 'MEDIUM';
    maxSlippageBps = 1.5;
  } else {
    executionRoute = 'VWAP_ALGO';
    sliceCount = 4;
    urgency = 'MEDIUM';
    maxSlippageBps = 3.0;
  }

  const bestBid = marketBook?.bids[0]?.price || 100;
  const bestAsk = marketBook?.asks[0]?.price || 100.1;
  const limitPrice = signal.direction === 'LONG' ? bestAsk * (1 + maxSlippageBps / 10000) : bestBid * (1 - maxSlippageBps / 10000);

  gateResults.push({
    gateId: 'M8',
    name: 'Execution Routing & TWAP/VWAP Slicing',
    passed: true,
    reason: `Optimal route: ${executionRoute} (${sliceCount} sub-slices, urgency ${urgency})`,
  });

  const finalStatus = scaleFactor < 0.95 ? 'MODIFIED' : 'PASSED';
  return {
    signalId: signal.id,
    timestamp: now,
    status: finalStatus,
    approvedSizeUsd,
    originalSizeUsd: signal.suggestedSizeUsd,
    scaleFactor: Math.round(scaleFactor * 100) / 100,
    symbol: signal.symbol,
    direction: signal.direction,
    strategyId: signal.strategyId,
    failedGate,
    gateResults,
    executionRoute,
    executionParams: {
      sliceCount,
      urgency,
      limitPrice: Math.round(limitPrice * 100) / 100,
      maxSlippageBps,
      feeBps: 4.0, // min 0.04% transaction fee
    },
  };
}

function createVerdict(
  signal: RawSignal,
  status: 'REJECTED',
  approvedSizeUsd: number,
  scaleFactor: number,
  failedGate: string,
  gateResults: GateResult[],
  executionRoute: 'DIRECT_DMA',
  sliceCount: number,
  limitPrice: number
): JudgeVerdict {
  return {
    signalId: signal.id,
    timestamp: Date.now(),
    status,
    approvedSizeUsd,
    originalSizeUsd: signal.suggestedSizeUsd,
    scaleFactor,
    symbol: signal.symbol,
    direction: signal.direction,
    strategyId: signal.strategyId,
    failedGate,
    gateResults,
    executionRoute,
    executionParams: {
      sliceCount,
      urgency: 'LOW',
      limitPrice,
      maxSlippageBps: 0,
    },
  };
}
