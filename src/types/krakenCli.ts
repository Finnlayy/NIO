/**
 * Kraken CLI & Kraken Pro Types
 * Strict typing for all commands, parameters, options, and structured JSON responses
 * from the Kraken CLI (including MCP, Pro, Futures, and Strategy Workspaces).
 */

export type KrakenCliCommand =
  // Market Data & System
  | 'status'
  | 'server-time'
  | 'assets'
  | 'pairs'
  | 'ticker'
  | 'ohlc'
  | 'orderbook'
  | 'orderbook-grouped'
  | 'trades'
  | 'spreads'
  | 'orderbook-l3'
  | 'tape'
  // Account & Portfolio
  | 'balance'
  | 'extended-balance'
  | 'credit-lines'
  | 'trade-balance'
  | 'open-orders'
  | 'closed-orders'
  | 'query-orders'
  | 'trades-history'
  | 'query-trades'
  | 'positions'
  | 'ledgers'
  | 'query-ledgers'
  | 'volume'
  // Reports & Auditing
  | 'export-report'
  | 'export-status'
  | 'export-retrieve'
  | 'export-delete'
  | 'auth'
  // Funding & Transfers
  | 'deposit'
  | 'earn'
  | 'subaccount'
  | 'wallet-transfer'
  | 'withdraw'
  | 'withdrawal'
  // Trading & Execution
  | 'order'
  | 'paper'
  | 'futures'
  | 'workspace'
  // Streaming & Daemons
  | 'ws'
  | 'streamd'
  | 'record'
  | 'replay'
  // AI & Orchestration
  | 'mcp'
  | 'explain'
  | 'feedback'
  | 'lab'
  | 'session'
  | 'playground'
  | 'setup'
  | 'shell'
  | 'help';

export interface KrakenCliGlobalOptions {
  output?: 'json' | 'table';
  verbose?: boolean;
  logFormat?: 'json' | 'pretty' | 'compact';
  workspace?: string;
  apiUrl?: string;
  futuresUrl?: string;
  wsPublicUrl?: string;
  wsAuthUrl?: string;
  wsL3Url?: string;
  wsFuturesUrl?: string;
  apiKey?: string;
  apiSecret?: string;
  otp?: string;
  yes?: boolean;
  dangerAcceptInvalidCerts?: boolean;
  dangerAllowAnyUrlHost?: boolean;
  monitor?: boolean;
  monitorHealthInterval?: number;
  monitorStaleAfter?: number;
  monitorHeartbeatTimeout?: number;
}

export type InternalCommandType =
  | 'STARTUP_ORCHESTRATION_INIT'
  | 'CHECK_SYSTEM_STATUS'
  | 'FETCH_CASH_BALANCES'
  | 'FETCH_EXTENDED_BALANCES'
  | 'FETCH_TRADE_BALANCE'
  | 'FETCH_OPEN_POSITIONS'
  | 'FETCH_OPEN_ORDERS'
  | 'FETCH_ORDERBOOK'
  | 'FETCH_TICKER'
  | 'SET_WORKSPACE'
  | 'INIT_MCP_SERVER'
  | 'EXECUTE_ORDER'
  | 'CANCEL_ORDER'
  | 'RESPAWN_BOT_FROM_HISTORY';

export interface InternalCommandMapping {
  internalType: InternalCommandType;
  cliCommand: KrakenCliCommand;
  defaultArgs: string[];
  defaultOptions: KrakenCliGlobalOptions;
  description: string;
  category: 'STARTUP' | 'ACCOUNT' | 'TRADING' | 'MARKET_DATA' | 'ORCHESTRATOR';
}

export interface KrakenCliExecutionRequest {
  command: KrakenCliCommand;
  args?: string[];
  options?: KrakenCliGlobalOptions;
  internalContext?: {
    initiatedBy: 'ORCHESTRATOR' | 'STARTUP' | 'USER_UI' | 'M8_GATE';
    timestamp: number;
  };
}

export interface KrakenCliExecutionResult<T = any> {
  command: KrakenCliCommand;
  fullCommandLine: string;
  executedAt: string;
  durationMs: number;
  exitCode: number;
  isRealBinary: boolean;
  data: T;
  rawStdout: string;
  rawStderr?: string;
  error?: string;
}

// Structured JSON Schemas (Matching Kraken CLI -o json output)

export interface KrakenSystemStatusResponse {
  status: 'online' | 'maintenance' | 'cancel_only' | 'post_only';
  timestamp: string;
  trading_mode: 'spot' | 'futures' | 'margin' | 'paper';
  api_connectivity: 'connected' | 'degraded' | 'offline';
  server_time: number;
}

export interface KrakenBalanceResponse {
  [asset: string]: {
    balance: number;
    currency: string;
    usd_value?: number;
    available?: number;
  };
}

export interface KrakenTradeBalanceResponse {
  equity: number;
  margin_balance: number;
  free_margin: number;
  initial_margin: number;
  maintenance_margin: number;
  unrealized_profit_loss: number;
  margin_level_pct: number;
  cost_basis: number;
  floating_valuation: number;
  currency: string;
}

export interface KrakenExtendedBalanceResponse {
  [asset: string]: {
    balance: number;
    hold_trade: number;
    hold_withdrawal: number;
    credit: number;
    credit_used: number;
    net_available: number;
  };
}

export interface KrakenPositionItem {
  id: string;
  ordertxid?: string;
  pair: string;
  time: number;
  type: 'buy' | 'sell';
  ordertype: string;
  cost: number;
  fee: number;
  vol: number;
  vol_closed: number;
  margin: number;
  value: number;
  net_pnl: number;
  terms?: string;
  rollovertm?: number;
  leverage: number;
}

export interface KrakenPositionsResponse {
  count: number;
  positions: KrakenPositionItem[];
}

export interface KrakenOpenOrdersResponse {
  count: number;
  open: Array<{
    txid: string;
    refid?: string;
    userref?: number;
    status: 'open' | 'pending';
    opentm: number;
    descr: {
      pair: string;
      type: 'buy' | 'sell';
      ordertype: 'limit' | 'market' | 'stop-loss' | 'take-profit';
      price: number;
      leverage: string;
      order: string;
    };
    vol: number;
    vol_exec: number;
    cost: number;
    fee: number;
  }>;
}

export interface KrakenWorkspaceResponse {
  active_workspace: string;
  available_workspaces: string[];
  storage_path: string;
  is_paper_trading: boolean;
}

export interface KrakenPaperPosition {
  pair: string;
  type: 'buy' | 'sell';
  side?: 'LONG' | 'SHORT';
  vol: number;
  volume?: number;
  cost: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  opened_at?: number;
  opened_at_formatted?: string;
  txid?: string;
}

export interface KrakenPaperStatusResponse {
  mode: 'paper';
  current_value: number;
  initial_balance: number;
  cash: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  trades_count: number;
  positions: KrakenPaperPosition[];
  timestamp: string;
}

export interface KrakenPaperTrade {
  txid: string;
  time: number;
  pair: string;
  type: 'buy' | 'sell';
  price: number;
  vol: number;
  cost: number;
  fee: number;
  pnl?: number;
  status: 'filled';
}

export interface KrakenPairInfo {
  altname: string;
  wsname: string;
  base: string;
  quote: string;
  ordermin: number;
  costmin: number;
  pair_decimals: number;
  lot_decimals: number;
  status: string;
}

export interface KrakenCliCommandMeta {
  id: string;
  name: string;
  command: KrakenCliCommand;
  subcommand?: string;
  argsSpec: string;
  readsBook: 'LIVE' | 'PAPER' | 'PUBLIC' | 'NONE';
  writesBook: 'LIVE' | 'PAPER' | 'NONE';
  mode: 'LIVE' | 'PAPER' | 'PUBLIC';
  dangerous: boolean;
  category: 'Market Data' | 'Account' | 'Trading' | 'Paper' | 'Streaming' | 'Orchestration' | 'Reports' | 'Funding';
  description: string;
}

export interface SituationCycleResult {
  cycleId: string;
  timestamp: string;
  activeMode: 'LIVE' | 'PAPER';
  bookObserved: {
    current_value: number;
    available_capital: number;
    source: string;
  };
  universe: Array<{
    symbol: string;
    price: number;
    ordermin: number;
    costmin: number;
    liveEligible: boolean;
  }>;
  selection: {
    symbol: string;
    moduleId: string;
    action: 'BUY' | 'SELL' | 'HOLD';
    reason: string;
  };
  actResult: {
    executedVia: string;
    cliCommand: string;
    cliOutput: any;
    txid?: string;
    bookChanged: boolean;
    newCurrentValue: number;
  };
  journalEntry: {
    id: string;
    timestamp: number;
    text: string;
  };
}

export interface KrakenAccountSummary {
  system_status: KrakenSystemStatusResponse;
  workspace: KrakenWorkspaceResponse;
  active_book: 'LIVE' | 'PAPER';
  paper_status: KrakenPaperStatusResponse;
  balances: KrakenBalanceResponse;
  trade_balance: KrakenTradeBalanceResponse;
  extended_balance: KrakenExtendedBalanceResponse;
  positions: KrakenPositionsResponse;
  open_orders: KrakenOpenOrdersResponse;
  command_map?: KrakenCliCommandMeta[];
  last_sync_timestamp: string;
  mode: 'REAL_CLI' | 'HIGH_FIDELITY_FALLBACK';
}

export interface RespawnBotPayload {
  historicalBotId: string;
  modifier?: {
    leverage?: number;
    pair?: string;
    strategy?: string;
    investment?: number;
    dcaSteps?: number;
    dcaRangeMin?: number;
    dcaRangeMax?: number;
  };
}

export interface KrakenBotOrderRequest {
  botId: string;
  botName: string;
  pair: string;
  side: 'buy' | 'sell';
  orderType: 'limit' | 'market';
  price?: number;
  volume: number;
  leverage?: number;
  reason?: string;
}

export interface KrakenBotOrderResponse {
  success: boolean;
  txid: string;
  executedVia: string;
  cliCommand: string;
  botId: string;
  botName: string;
  pair: string;
  side: 'buy' | 'sell';
  orderType: 'limit' | 'market';
  volume: number;
  price: number;
  cost: number;
  fee: number;
  timestamp: number;
  status: 'filled' | 'open';
  bookMode: 'PAPER' | 'LIVE';
  newCurrentValue?: number;
  newCash?: number;
  dcaOrdersTriggered?: number;
  journalText?: string;
  error?: string;
}

export interface KrakenToolDefinition {
  id: string;
  name: string;
  category:
    | 'DCA & Algorithmic Bots'
    | 'Order Execution & Management'
    | 'Paper Trading & Simulation'
    | 'Balances, Margin & Risk'
    | 'Market Data & Orderbook'
    | 'MCP & Workspaces'
    | 'Situation-Cycle & Meta Orchestration';
  description: string;
  cliCommandTemplate: string;
  readsBook: 'PAPER' | 'LIVE' | 'BOTH' | 'NONE';
  writesBook: 'PAPER' | 'LIVE' | 'BOTH' | 'NONE';
  dangerous: boolean;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    defaultValue?: any;
  }>;
}
