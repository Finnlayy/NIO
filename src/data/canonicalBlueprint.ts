import { JudgeConfig, StrategyAgent } from '../types/trading';

export interface BlueprintDocumentation {
  title: string;
  version: string;
  codename: string;
  philosophy: string;
  zeroDummyDirective: string;
  systemArchitecture: string;
  mathFormulas: {
    name: string;
    formula: string;
    description: string;
  }[];
  gateSpecifications: {
    gateId: string;
    name: string;
    strictness: string;
    description: string;
    failAction: string;
  }[];
}

export const CANONICAL_BLUEPRINT_DOCS: BlueprintDocumentation = {
  title: 'OMEGA NIO: The Judge & The Swarm',
  version: '4.2.0-PROD',
  codename: 'SIGMA ALPHA DYNAMICS',
  philosophy:
    'Rigorously separates speculative Signal Generation (The Swarm) from deterministic Risk & Capital Allocation (The Judge / M8-Gate). Signals possess zero execution privileges; all risk budgets are strictly adjudicated through mathematical invariants.',
  zeroDummyDirective:
    'ZERO-DUMMY GUARANTEE: In accordance with high-frequency quantitative systems mandates, all calculation paths are fully implemented, non-stumped, mathematically closed, and strictly verified.',
  systemArchitecture:
    'Three-tier asynchronous architecture: 1) Swarm Agent cluster emitting typed RawSignal payloads with microsecond timestamps; 2) The Judge M8-Gate evaluating multi-dimensional risk barriers; 3) Execution Slicer executing TWAP/VWAP/DMA routed orders into simulated liquidity pools.',
  mathFormulas: [
    {
      name: 'Fractional Kelly Criterion (Half-Kelly)',
      formula: 'f^* = c · [(p · (b + 1) - 1) / b]',
      description:
        'Calculates mathematically optimal capital leverage f* based on empirical win probability p and payoff ratio b, scaled by safety damping parameter c = 0.50.',
    },
    {
      name: 'Ornstein-Uhlenbeck Mean-Reversion Drift',
      formula: 'dX_t = θ(μ - X_t)dt + σ dW_t',
      description:
        'Estimates mean-reversion speed θ and equilibrium level μ to trade statistical deviations on the Sigma-Alpha pair matrices.',
    },
    {
      name: 'Volume Synchronized Probability of Toxicity (VPIN)',
      formula: 'VPIN = Σ |V_τ^B - V_τ^S| / (N · V)',
      description:
        'Measures order flow toxicity across constant volume bars to detect adverse selection before entering book queues.',
    },
    {
      name: 'Cornish-Fisher Value-at-Risk (99% CVaR)',
      formula: 'VaR_α = μ - σ · [z_α + (z_α^2 - 1)S/6 + (z_α^3 - 3z_α)K/24]',
      description:
        'Higher-moment VaR adjustment incorporating empirical return skewness S and excess kurtosis K for fat-tailed market distributions.',
    },
  ],
  gateSpecifications: [
    {
      gateId: 'M1',
      name: 'Sanity & Latency Monotonicity',
      strictness: 'HARD_REJECT',
      description: 'Checks signal freshness (max latency threshold ≤ 500ms) and strictly monotonic tick nonces.',
      failAction: 'Instant discard of stale signal.',
    },
    {
      gateId: 'M2',
      name: 'Portfolio Gross & Net Exposure Barrier',
      strictness: 'HARD_REJECT',
      description: 'Validates portfolio aggregate gross leverage ≤ 3.0x and single asset concentration ≤ 20% NAV.',
      failAction: 'Rejection if leverage ceiling exceeded.',
    },
    {
      gateId: 'M3',
      name: 'Volatility Regime Filter (Parkinson / GARCH)',
      strictness: 'PROPORTIONAL_SCALE',
      description: 'Calculates realized high-frequency volatility ratio. Scales down position if regime is turbulent.',
      failAction: 'Scale size down by 25% to 75%.',
    },
    {
      gateId: 'M4',
      name: 'Kelly Capital Allocation Sizer',
      strictness: 'MODIFIER',
      description: 'Determines mathematically optimal position sizing via Half-Kelly formula and confidence scaling.',
      failAction: 'Replaces raw requested size with safe Kelly allocation.',
    },
    {
      gateId: 'M5',
      name: 'Drawdown Circuit Breaker & High-Water Mark',
      strictness: 'HARD_REJECT',
      description: 'Enforces maximum daily loss limit (-2.5%) and peak-to-trough trailing stop (-6.0%).',
      failAction: 'Disables new risk intake, allows only risk-reducing exits.',
    },
    {
      gateId: 'M6',
      name: 'ADV Liquidity & Spread Barrier',
      strictness: 'PROPORTIONAL_SCALE',
      description: 'Limits order slice to ≤ 1.5% of rolling 5-minute volume bucket and checks bid-ask spread ≤ 8 bps.',
      failAction: 'Rejects wide-spread illiquid ticks or caps slice size.',
    },
    {
      gateId: 'M7',
      name: 'Conditional VaR (CVaR) Stress Barrier',
      strictness: 'HARD_REJECT',
      description: 'Simulates 99% Expected Shortfall under 3-sigma stress shock. Maximum CVaR threshold $25,000.',
      failAction: 'Blocks allocations that violate portfolio tail risk budget.',
    },
    {
      gateId: 'M8',
      name: 'Execution Routing & TWAP/VWAP Slicing',
      strictness: 'ROUTING_DIRECTIVE',
      description: 'Determines optimal order routing: Direct DMA for high alpha, TWAP/VWAP for larger blocks, Iceberg for thick book.',
      failAction: 'Assigns optimal execution protocol and execution parameters.',
    },
  ],
};

export const INITIAL_JUDGE_CONFIG: JudgeConfig = {
  maxGrossLeverage: 3.0,
  maxAssetConcentrationPct: 20.0,
  kellyFraction: 0.5,
  maxDailyDrawdownPct: 2.5,
  maxTotalDrawdownPct: 6.0,
  maxAdvParticipationPct: 1.5,
  maxSpreadBpsThreshold: 8.0,
  volatilityCeilingAtrRatio: 2.5,
  cvarLimitUsd: 25000,
  signalMaxLatencyMs: 500,
};

export const INITIAL_SWARM_STRATEGIES: StrategyAgent[] = [
  {
    id: 'strat_alpha_momentum',
    name: 'Alpha-Momentum (Trend Breakout)',
    type: 'MOMENTUM',
    weight: 0.28,
    winRate: 0.56,
    sharpeRatio: 2.41,
    activeSignalsCount: 0,
    description: 'High-frequency breakout detector utilizing exponential moving average ribbons and volume expansion filters.',
    parameters: { lookbackBars: 20, breakoutZScore: 2.1, holdingPeriodBars: 15 },
  },
  {
    id: 'strat_sigma_mean_reversion',
    name: 'Sigma-MeanReversion (Ornstein-Uhlenbeck)',
    type: 'MEAN_REVERSION',
    weight: 0.25,
    winRate: 0.63,
    sharpeRatio: 2.85,
    activeSignalsCount: 0,
    description: 'Ornstein-Uhlenbeck continuous mean reversion on microstructural price divergences with dynamic Bollinger envelopes.',
    parameters: { meanReversionSpeedTheta: 0.85, zScoreThreshold: 1.85, maxHalfLifeSec: 180 },
  },
  {
    id: 'strat_orderbook_microstructure',
    name: 'Microstructure (L2 Imbalance & VPIN)',
    type: 'MICROSTRUCTURE',
    weight: 0.22,
    winRate: 0.59,
    sharpeRatio: 3.12,
    activeSignalsCount: 0,
    description: 'Analyzes top-of-book bid/ask queue replenishment, cancels, and volume-synchronized probability of toxicity.',
    parameters: { depthLevels: 10, vpinToxicityCutoff: 0.45, imbalanceRatioMin: 1.6 },
  },
  {
    id: 'strat_vol_arb',
    name: 'Vol-Arbitrage (Dispersion & Surface)',
    type: 'VOL_ARB',
    weight: 0.13,
    winRate: 0.54,
    sharpeRatio: 1.95,
    activeSignalsCount: 0,
    description: 'Captures discrepancies between intraday Parkinson high-low volatility and implied surface pricing.',
    parameters: { parkinsonWindow: 60, impliedVolRatioMin: 1.25 },
  },
  {
    id: 'strat_deep_rl',
    name: 'Deep-RL Multi-Horizon (Actor-Critic)',
    type: 'DEEP_RL',
    weight: 0.12,
    winRate: 0.58,
    sharpeRatio: 2.28,
    activeSignalsCount: 0,
    description: 'Continuous actor-critic neural network trained on multi-horizon markov decision process with reward penalizing drawdown.',
    parameters: { gammaDiscount: 0.99, entropyWeight: 0.02, hiddenLayers: '256x256' },
  },
];
