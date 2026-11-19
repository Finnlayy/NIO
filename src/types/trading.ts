export type Direction = 'LONG' | 'SHORT' | 'FLAT';

export type GateStatus = 'PASSED' | 'REJECTED' | 'MODIFIED';

export interface StrategyAgent {
  id: string;
  name: string;
  type: 'MOMENTUM' | 'MEAN_REVERSION' | 'MICROSTRUCTURE' | 'VOL_ARB' | 'DEEP_RL';
  weight: number; // 0 to 1
  winRate: number;
  sharpeRatio: number;
  activeSignalsCount: number;
  description: string;
  parameters: Record<string, number | string>;
}

export interface RawSignal {
  id: string;
  timestamp: number;
  strategyId: string;
  strategyName: string;
  symbol: string;
  direction: Direction;
  confidence: number; // 0.0 to 1.0
  expectedAlphaBps: number;
  timeHorizonSec: number;
  suggestedSizeUsd: number;
  rawMetrics: {
    zScore?: number;
    imbalanceRatio?: number;
    volRatio?: number;
    entropy?: number;
    [key: string]: number | undefined;
  };
}

export interface GateResult {
  gateId: 'M1' | 'M2' | 'M3' | 'M4' | 'M5' | 'M6' | 'M7' | 'M8';
  name: string;
  passed: boolean;
  reason?: string;
  metricValue?: number;
  threshold?: number;
}

export interface JudgeVerdict {
  signalId: string;
  timestamp: number;
  status: GateStatus;
  approvedSizeUsd: number;
  originalSizeUsd: number;
  scaleFactor: number; // 0.0 to 1.0
  symbol: string;
  direction: Direction;
  strategyId: string;
  failedGate?: string;
  gateResults: GateResult[];
  executionRoute: 'DIRECT_DMA' | 'TWAP_SLICER' | 'VWAP_ALGO' | 'ICEBERG_PASSIVE';
  executionParams: {
    sliceCount: number;
    urgency: 'HIGH' | 'MEDIUM' | 'LOW';
    limitPrice: number;
    maxSlippageBps: number;
    feeBps?: number; // min 4.0 bps (0.04% min transaction fee)
  };
}

export interface Position {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  allocatedUsd: number;
  openedAt: number;
  strategyId: string;
  stopLossPrice: number;
  takeProfitPrice: number;
}

export interface ExecutionOrder {
  id: string;
  signalId: string;
  timestamp: number;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  filledPrice: number;
  slippageBps: number;
  feeUsd: number;
  status: 'FILLED' | 'CANCELLED';
  executionRoute: string;
}

export interface PortfolioState {
  cashUsd: number;
  navUsd: number;
  grossLeverage: number;
  netLeverage: number;
  realizedPnl: number;
  unrealizedPnl: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  peakNav: number;
  currentDrawdownPct: number;
  maxDrawdownPct: number;
  dailyPnlPct: number;
  sharpeRatio: number;
  var99Usd: number; // 99% 1-day Value at Risk
  cvar99Usd: number; // Conditional VaR / Expected Shortfall
  totalFeesUsd?: number; // Cumulative transaction fees (min 0.04%)
  positions: Position[];
}

export interface OrderbookEntry {
  price: number;
  size: number;
  total: number;
}

export interface OrderbookData {
  symbol: string;
  lastPrice: number;
  priceChange24h: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  spread: number;
  spreadBps: number;
  bids: OrderbookEntry[];
  asks: OrderbookEntry[];
  recentTrades: {
    id: string;
    price: number;
    size: number;
    side: 'BUY' | 'SELL';
    timestamp: number;
  }[];
}

export interface DriveBlueprintItem {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime: string;
  size?: string;
  description?: string;
  webViewLink?: string;
  contentSnippet?: string;
  isBlueprintMatch: boolean;
}

export interface JudgeConfig {
  maxGrossLeverage: number; // e.g. 3.0x
  maxAssetConcentrationPct: number; // e.g. 20%
  kellyFraction: number; // e.g. 0.5 (Half-Kelly)
  maxDailyDrawdownPct: number; // e.g. 2.5%
  maxTotalDrawdownPct: number; // e.g. 6.0%
  maxAdvParticipationPct: number; // e.g. 1.5%
  maxSpreadBpsThreshold: number; // e.g. 8 bps
  volatilityCeilingAtrRatio: number; // e.g. 2.5x
  cvarLimitUsd: number; // e.g. $25,000
  signalMaxLatencyMs: number; // e.g. 500ms
}

export interface WorkerBotMetrics {
  investment: number;
  currency: string;
  investmentEur?: number;
  realizedProfit: number;
  profitCycleType?: string;
  dcaRangeMin: number;
  dcaRangeMax: number;
  dcaSteps: number;
  dcaOrdersTriggered: number;
  fundingFees: number;
  transactionFees?: number; // Cumulative transaction fees (min 0.04% / 4 bps per fill)
  feeRatePct?: number; // Transaction fee rate percentage (e.g. 0.04)
  grossProfit?: number; // Realized + Unrealized profit before fees
  totalFees?: number; // Combined transaction fees + funding fees
  netProfit?: number; // Net profit after subtracting all fees
  liquidationPrice: number;
  liquidationDistancePct: number;
}

export interface WorkerBotRuntime {
  days: number;
  hours: number;
  minutes: number;
  cycles: number;
  cycleProgressPct?: number;
}

export interface WorkerBotUnrealizedPnL {
  value: number;
  percentage: number;
}

export type BotStatus =
  | 'active'
  | 'paused'
  | 'completed'
  | 'liquidated'
  | 'stopped'
  | 'ACTIVE'
  | 'PAUSED'
  | 'IDLE';

export interface WorkerBotData {
  id: string; // e.g. 'BOT-7742'
  name: string; // e.g. 'DCA Bot Alpha'
  exchange: string; // e.g. 'Kraken Futures', 'Kraken Spot'
  status: BotStatus;
  pair: string; // e.g. 'BTC/USD', 'ETH/USD'
  strategy: string; // e.g. 'KRAKEN FUTURES · DCA STRATEGY'
  direction: 'LONG' | 'SHORT';
  leverage: number; // e.g. 75

  // Live P&L
  unrealizedPnL: WorkerBotUnrealizedPnL;
  entryPrice: number;
  currentPrice: number;

  // 2x3 Metrik-Raster
  metrics: WorkerBotMetrics;

  // Footer & Performance
  runtime: WorkerBotRuntime;
  totalProfit: number;
  roi: number;
  apr: number;
  lastUpdate: Date | string;
  statusText?: string;
  linkedStrategyId?: string;

  // History & Lifecycle fields
  finishReason?: 'TAKE_PROFIT' | 'MANUAL_STOP' | 'LIQUIDATED' | 'STOP_LOSS' | string;
  finishedAt?: string;
  durationFormatted?: string;

  // Optional flattened convenience accessors
  symbol?: string;
  instrumentType?: string;
  investmentUsd?: number;
  investmentEur?: number;
  unrealizedPnlUsd?: number;
  unrealizedPnlPct?: number;
  currentProfitUsd?: number;
  totalProfitUsd?: number;
  roiPct?: number;
  aprPct?: number;
  dcaOrdersTriggered?: number;
  lastUpdated?: string;

  // Kraken CLI Routing & Real-Time Order Execution
  krakenPair?: string;
  lastCliExecution?: {
    command: string;
    txid: string;
    status: string;
    timestamp: number;
    price?: number;
    volume?: number;
    cost?: number;
    side?: 'buy' | 'sell';
  };
  cliExecutionHistory?: Array<{
    command: string;
    txid: string;
    status: string;
    timestamp: number;
    price?: number;
    volume?: number;
    cost?: number;
    side?: 'buy' | 'sell';
  }>;
}

export type WorkerBot = WorkerBotData;

export interface WorkerBotTickPayload {
  id: string;
  currentPrice?: number;
  unrealizedPnL?: {
    value: number;
    percentage: number;
  };
  metrics?: Partial<WorkerBotMetrics>;
  runtime?: Partial<WorkerBotRuntime>;
  totalProfit?: number;
  roi?: number;
  apr?: number;
  status?: 'active' | 'paused' | 'ACTIVE' | 'PAUSED' | 'IDLE';
  statusText?: string;
  lastUpdate?: string | Date;
}

export interface WorkerBotWsMessage {
  type:
    | 'TICK_UPDATE'
    | 'BOT_STATUS_CHANGED'
    | 'SYNC_ALL_BOTS'
    | 'COMMAND_ACK'
    | 'BOT_FINISHED'
    | 'BOT_ORDER_EXECUTED';
  payload: any;
  timestamp?: number;
}

export interface WorkerBotCommand {
  type: 'TOGGLE_STATUS' | 'SET_LEVERAGE' | 'UPDATE_DCA_RANGE' | 'REBALANCE';
  botId: string;
  params?: Record<string, any>;
  timestamp: number;
}

export type ConnectionEventType =
  | 'CONNECTED'
  | 'DISCONNECTED'
  | 'RECONNECT_SCHEDULED'
  | 'HANDSHAKE_INIT'
  | 'FALLBACK_SSE'
  | 'MANUAL_RECONNECT'
  | 'ERROR';

export type ConnectionSeverity = 'SUCCESS' | 'WARNING' | 'ERROR' | 'INFO';

export interface ConnectionEvent {
  id: string;
  timestamp: number;
  type: ConnectionEventType;
  severity: ConnectionSeverity;
  port: number;
  endpoint: string;
  attempt: number;
  code?: number;
  reason: string;
  details?: string;
  backoffDelayMs?: number | null;
  latencyMs?: number;
}

