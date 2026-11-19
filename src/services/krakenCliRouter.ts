/**
 * Kraken CLI Command Router & Parser
 *
 * Provides bidirectional translation between internal engine/orchestrator operations
 * and the Kraken CLI commands specified in the official command hierarchy.
 * Handles argument generation, strict JSON parsing, startup mode verification,
 * and high-fidelity failover.
 */

import {
  KrakenCliCommand,
  KrakenCliGlobalOptions,
  InternalCommandType,
  InternalCommandMapping,
  KrakenCliExecutionRequest,
  KrakenCliExecutionResult,
  KrakenAccountSummary,
  KrakenCliCommandMeta,
  KrakenPaperStatusResponse,
  KrakenPaperTrade,
  KrakenPairInfo,
  SituationCycleResult,
  KrakenBotOrderRequest,
  KrakenBotOrderResponse,
  KrakenToolDefinition,
} from '../types/krakenCli';

/**
 * The Master Command Map (Kommando-Karte) for Kraken CLI 0.3.2
 * Maps command name, arguments, readsBook, writesBook, mode, danger classification.
 * The orchestrator chooses strictly from this map!
 */
export const KRAKEN_COMMAND_MAP: KrakenCliCommandMeta[] = [
  // 1. PUBLIC & MARKET DATA (Public, reads NONE, writes NONE, safe)
  {
    id: 'status',
    name: 'status',
    command: 'status',
    argsSpec: '',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get system status, server connectivity, and trading mode',
  },
  {
    id: 'server-time',
    name: 'server-time',
    command: 'server-time',
    argsSpec: '',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get authoritative Kraken server time (epoch and UTC ISO)',
  },
  {
    id: 'assets',
    name: 'assets',
    command: 'assets',
    argsSpec: '[--asset <asset>]',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get asset info, decimals, and collateral status',
  },
  {
    id: 'pairs',
    name: 'pairs',
    command: 'pairs',
    argsSpec: '[--pair <pair>]',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get all tradable asset pairs, min order size (ordermin), costmin, lot decimals',
  },
  {
    id: 'ticker',
    name: 'ticker',
    command: 'ticker',
    argsSpec: '<pairs...>',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get real-time ticker data, spread, bid/ask, volume, and 24h VWAP',
  },
  {
    id: 'ohlc',
    name: 'ohlc',
    command: 'ohlc',
    argsSpec: '<pair> [--interval <min>]',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get historical OHLC candle data',
  },
  {
    id: 'orderbook',
    name: 'orderbook',
    command: 'orderbook',
    argsSpec: '<pair> [--depth <count>]',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Get consolidated L2 order book depth',
  },
  {
    id: 'tape',
    name: 'tape',
    command: 'tape',
    argsSpec: '<pair>',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Market Data',
    description: 'Consolidated real-time market trade tape',
  },

  // 2. LIVE ACCOUNT & PORTFOLIO (Live, reads LIVE, writes NONE, safe)
  {
    id: 'balance',
    name: 'balance',
    command: 'balance',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Account',
    description: 'Get live spot cash balances directly from Kraken (Source of Truth)',
  },
  {
    id: 'extended-balance',
    name: 'extended-balance',
    command: 'extended-balance',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Account',
    description: 'Get live extended balances (hold for trade, credit lines, net available)',
  },
  {
    id: 'trade-balance',
    name: 'trade-balance',
    command: 'trade-balance',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Account',
    description: 'Get margin equity, free margin, margin level, and floating unrealized PnL',
  },
  {
    id: 'positions',
    name: 'positions',
    command: 'positions',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Trading',
    description: 'Get open leveraged margin positions from Kraken',
  },
  {
    id: 'open-orders',
    name: 'open-orders',
    command: 'open-orders',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Trading',
    description: 'Get live active open limit and stop orders',
  },
  {
    id: 'closed-orders',
    name: 'closed-orders',
    command: 'closed-orders',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Trading',
    description: 'Get executed closed orders history',
  },
  {
    id: 'trades-history',
    name: 'trades-history',
    command: 'trades-history',
    argsSpec: '',
    readsBook: 'LIVE',
    writesBook: 'NONE',
    mode: 'LIVE',
    dangerous: false,
    category: 'Trading',
    description: 'Get live trades history with fees, cost, and fill timestamps',
  },

  // 3. LIVE TRADING EXECUTION (Live, reads LIVE, writes LIVE, dangerous)
  {
    id: 'order',
    name: 'order',
    command: 'order',
    argsSpec: 'add|cancel|edit <pair> <type> <vol> [--price <p>] [--leverage <lev>]',
    readsBook: 'LIVE',
    writesBook: 'LIVE',
    mode: 'LIVE',
    dangerous: true,
    category: 'Trading',
    description: 'Place live orders on Kraken exchange. Requires liveEligible + M8 Gate confirmation!',
  },

  // 4. PAPER TRADING LEDGER (Paper, reads PAPER, writes PAPER, safe simulation)
  {
    id: 'paper-status',
    name: 'paper status',
    command: 'paper',
    subcommand: 'status',
    argsSpec: 'status',
    readsBook: 'PAPER',
    writesBook: 'NONE',
    mode: 'PAPER',
    dangerous: false,
    category: 'Paper',
    description: 'Get CLI Paper Ledger status (current_value, cash, unrealized_pnl, realized_pnl, trades count)',
  },
  {
    id: 'paper-buy',
    name: 'paper buy',
    command: 'paper',
    subcommand: 'buy',
    argsSpec: 'buy <pair> <volume> [--price <limit>]',
    readsBook: 'PAPER',
    writesBook: 'PAPER',
    mode: 'PAPER',
    dangerous: false,
    category: 'Paper',
    description: 'Execute a paper buy order; updates paper ledger cash, position, and records PAPER-* txid',
  },
  {
    id: 'paper-sell',
    name: 'paper sell',
    command: 'paper',
    subcommand: 'sell',
    argsSpec: 'sell <pair> <volume> [--price <limit>]',
    readsBook: 'PAPER',
    writesBook: 'PAPER',
    mode: 'PAPER',
    dangerous: false,
    category: 'Paper',
    description: 'Execute a paper sell order; closes position, realizes PnL, updates paper ledger',
  },
  {
    id: 'paper-history',
    name: 'paper history',
    command: 'paper',
    subcommand: 'history',
    argsSpec: 'history',
    readsBook: 'PAPER',
    writesBook: 'NONE',
    mode: 'PAPER',
    dangerous: false,
    category: 'Paper',
    description: 'Get executed paper trades history (PAPER-* transactions)',
  },
  {
    id: 'paper-positions',
    name: 'paper positions',
    command: 'paper',
    subcommand: 'positions',
    argsSpec: 'positions',
    readsBook: 'PAPER',
    writesBook: 'NONE',
    mode: 'PAPER',
    dangerous: false,
    category: 'Paper',
    description: 'Get open positions currently held in the CLI Paper Ledger',
  },
  {
    id: 'paper-reset',
    name: 'paper reset',
    command: 'paper',
    subcommand: 'reset',
    argsSpec: 'reset [--balance <amount>]',
    readsBook: 'PAPER',
    writesBook: 'PAPER',
    mode: 'PAPER',
    dangerous: true,
    category: 'Paper',
    description: 'Reset paper ledger positions, cash, and trade history',
  },

  // 5. ORCHESTRATION & STREAMING
  {
    id: 'workspace',
    name: 'workspace',
    command: 'workspace',
    argsSpec: '[<name>|list]',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Orchestration',
    description: 'Switch or query active strategy execution workspace',
  },
  {
    id: 'streamd',
    name: 'streamd',
    command: 'streamd',
    argsSpec: 'start|status|stop',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Streaming',
    description: 'Manage high-performance WebSocket streaming daemon for real-time tickers and depth',
  },
  {
    id: 'mcp',
    name: 'mcp',
    command: 'mcp',
    argsSpec: '[--transport stdio]',
    readsBook: 'NONE',
    writesBook: 'NONE',
    mode: 'PUBLIC',
    dangerous: false,
    category: 'Orchestration',
    description: 'Run Model Context Protocol (MCP) server for autonomous multi-agent systems',
  },
];

export const KRAKEN_COMMAND_REGISTRY: Record<InternalCommandType, InternalCommandMapping> = {
  STARTUP_ORCHESTRATION_INIT: {
    internalType: 'STARTUP_ORCHESTRATION_INIT',
    cliCommand: 'status',
    defaultArgs: [],
    defaultOptions: { output: 'json', logFormat: 'json', workspace: 'default' },
    description: 'Verifies system connectivity, active mode (spot/futures/paper) and sets the active workspace on boot',
    category: 'STARTUP',
  },
  CHECK_SYSTEM_STATUS: {
    internalType: 'CHECK_SYSTEM_STATUS',
    cliCommand: 'status',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Queries Kraken system status and operational trading mode',
    category: 'STARTUP',
  },
  FETCH_CASH_BALANCES: {
    internalType: 'FETCH_CASH_BALANCES',
    cliCommand: 'balance',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Retrieves all spot cash balances (USD, EUR, USDT, BTC, ETH)',
    category: 'ACCOUNT',
  },
  FETCH_EXTENDED_BALANCES: {
    internalType: 'FETCH_EXTENDED_BALANCES',
    cliCommand: 'extended-balance',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Retrieves extended balances including margin credits, hold for trade, and hold for withdrawal',
    category: 'ACCOUNT',
  },
  FETCH_TRADE_BALANCE: {
    internalType: 'FETCH_TRADE_BALANCE',
    cliCommand: 'trade-balance',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Queries margin equity, free margin, margin level, and floating unrealized PnL',
    category: 'ACCOUNT',
  },
  FETCH_OPEN_POSITIONS: {
    internalType: 'FETCH_OPEN_POSITIONS',
    cliCommand: 'positions',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Fetches open leveraged margin and perpetual positions',
    category: 'TRADING',
  },
  FETCH_OPEN_ORDERS: {
    internalType: 'FETCH_OPEN_ORDERS',
    cliCommand: 'open-orders',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Retrieves currently active open limit and stop orders',
    category: 'TRADING',
  },
  FETCH_ORDERBOOK: {
    internalType: 'FETCH_ORDERBOOK',
    cliCommand: 'orderbook',
    defaultArgs: ['BTC/USD', '--depth', '10'],
    defaultOptions: { output: 'json' },
    description: 'Fetches Level 2 consolidated depth order book for market analysis',
    category: 'MARKET_DATA',
  },
  FETCH_TICKER: {
    internalType: 'FETCH_TICKER',
    cliCommand: 'ticker',
    defaultArgs: ['BTC/USD', 'ETH/USD', 'SOL/USD'],
    defaultOptions: { output: 'json' },
    description: 'Queries latest ticker snapshots, 24h volume, and high/low ranges',
    category: 'MARKET_DATA',
  },
  SET_WORKSPACE: {
    internalType: 'SET_WORKSPACE',
    cliCommand: 'workspace',
    defaultArgs: ['default'],
    defaultOptions: { output: 'json' },
    description: 'Sets or scopes strategy execution to an isolated workspace tree',
    category: 'ORCHESTRATOR',
  },
  INIT_MCP_SERVER: {
    internalType: 'INIT_MCP_SERVER',
    cliCommand: 'mcp',
    defaultArgs: [],
    defaultOptions: {},
    description: 'Starts the built-in MCP (Model Context Protocol) server over stdio for autonomous AI agents',
    category: 'ORCHESTRATOR',
  },
  EXECUTE_ORDER: {
    internalType: 'EXECUTE_ORDER',
    cliCommand: 'order',
    defaultArgs: [],
    defaultOptions: { output: 'json', yes: true },
    description: 'Places a spot/margin order validated by The Judge M8 gate',
    category: 'TRADING',
  },
  CANCEL_ORDER: {
    internalType: 'CANCEL_ORDER',
    cliCommand: 'order',
    defaultArgs: ['cancel'],
    defaultOptions: { output: 'json', yes: true },
    description: 'Cancels specific or all open orders',
    category: 'TRADING',
  },
  RESPAWN_BOT_FROM_HISTORY: {
    internalType: 'RESPAWN_BOT_FROM_HISTORY',
    cliCommand: 'paper',
    defaultArgs: [],
    defaultOptions: { output: 'json' },
    description: 'Clones an archived bot session with AI modifiers and boots it into the live engine',
    category: 'ORCHESTRATOR',
  },
};

/**
 * Builds the exact CLI argument vector for executing `kraken [OPTIONS] [COMMAND] [ARGS]`
 */
export function buildKrakenCliArgs(
  command: KrakenCliCommand,
  args: string[] = [],
  options: KrakenCliGlobalOptions = {}
): string[] {
  const cliArgs: string[] = [];

  // Global options before command
  if (options.output) {
    cliArgs.push('-o', options.output);
  }
  if (options.logFormat) {
    cliArgs.push('--log-format', options.logFormat);
  }
  if (options.workspace) {
    cliArgs.push('--workspace', options.workspace);
  }
  if (options.apiUrl) {
    cliArgs.push('--api-url', options.apiUrl);
  }
  if (options.futuresUrl) {
    cliArgs.push('--futures-url', options.futuresUrl);
  }
  if (options.yes) {
    cliArgs.push('--yes');
  }
  if (options.verbose) {
    cliArgs.push('-v');
  }

  // The command itself
  cliArgs.push(command);

  // Command-specific arguments
  if (args.length > 0) {
    cliArgs.push(...args);
  }

  return cliArgs;
}

/**
 * Formats command into a displayable shell string: e.g. `kraken -o json balance`
 */
export function formatKrakenCommandLine(
  command: KrakenCliCommand,
  args: string[] = [],
  options: KrakenCliGlobalOptions = {}
): string {
  const parts = ['kraken'];
  if (options.output) parts.push(`-o ${options.output}`);
  if (options.workspace) parts.push(`--workspace ${options.workspace}`);
  if (options.logFormat) parts.push(`--log-format ${options.logFormat}`);
  if (options.yes) parts.push('--yes');
  parts.push(command);
  if (args.length > 0) parts.push(...args);
  return parts.join(' ');
}

/**
 * Executes a Kraken CLI command via the backend proxy
 */
export async function executeKrakenCliCommand<T = any>(
  request: KrakenCliExecutionRequest
): Promise<KrakenCliExecutionResult<T>> {
  const response = await fetch('/api/kraken/cli/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Kraken CLI Execution Failed [${response.status}]: ${errText}`);
  }

  return response.json();
}

/**
 * Fetches the aggregated account summary directly parsed from the CLI
 */
export async function fetchKrakenAccountSummary(): Promise<KrakenAccountSummary> {
  const response = await fetch('/api/kraken/cli/summary');
  if (!response.ok) {
    throw new Error(`Failed to fetch Kraken account summary: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Spawns an archived bot as a new live session with AI modifiers
 */
export async function fetchKrakenPaperStatus(): Promise<KrakenPaperStatusResponse> {
  const response = await fetch('/api/kraken/cli/paper/status');
  if (!response.ok) {
    throw new Error(`Failed to fetch Paper status: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchKrakenPaperHistory(): Promise<KrakenPaperTrade[]> {
  const response = await fetch('/api/kraken/cli/paper/history');
  if (!response.ok) {
    throw new Error(`Failed to fetch Paper history: ${response.statusText}`);
  }
  return response.json();
}

export async function executeKrakenPaperBuy(pair: string, volume: number, price?: number): Promise<any> {
  const args = ['buy', pair, String(volume)];
  if (price !== undefined) {
    args.push('--price', String(price));
  }
  return executeKrakenCliCommand({
    command: 'paper',
    args,
    options: { output: 'json' },
    internalContext: { initiatedBy: 'ORCHESTRATOR', timestamp: Date.now() },
  });
}

export async function executeKrakenPaperSell(pair: string, volume: number, price?: number): Promise<any> {
  const args = ['sell', pair, String(volume)];
  if (price !== undefined) {
    args.push('--price', String(price));
  }
  return executeKrakenCliCommand({
    command: 'paper',
    args,
    options: { output: 'json' },
    internalContext: { initiatedBy: 'ORCHESTRATOR', timestamp: Date.now() },
  });
}

export async function executeKrakenPaperReset(balance: number = 1000): Promise<any> {
  return executeKrakenCliCommand({
    command: 'paper',
    args: ['reset', '--balance', String(balance)],
    options: { output: 'json' },
    internalContext: { initiatedBy: 'USER_UI', timestamp: Date.now() },
  });
}

export async function executeSituationCycle(): Promise<SituationCycleResult> {
  const response = await fetch('/api/kraken/cli/situation-cycle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || 'Situation cycle failed');
  }
  return response.json();
}

export async function fetchKrakenPairs(): Promise<KrakenPairInfo[]> {
  const response = await fetch('/api/kraken/cli/market/pairs');
  if (!response.ok) {
    throw new Error(`Failed to fetch pairs: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchKrakenTicker(pairs: string[] = ['BTC/USD', 'ETH/USD', 'SOL/USD']): Promise<Record<string, any>> {
  const response = await fetch(`/api/kraken/cli/market/ticker?pairs=${encodeURIComponent(pairs.join(','))}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch ticker: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Spawns an archived bot as a new live session with AI modifiers
 */
export async function spawnBotFromHistory(
  historicalBotId: string,
  modifier?: Record<string, any>
): Promise<{ success: boolean; newBotId: string; bot: any }> {
  const response = await fetch('/api/v1/swarm/spawn-from-history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ historicalBotId, modifier }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || 'Failed to respawn bot from history');
  }

  return response.json();
}

/**
 * Dispatches an automated or user-triggered bot order directly to the Kraken CLI Engine.
 * Guarantees real execution (`kraken paper buy/sell` or `kraken order add`) with TXID & Book mutability.
 */
export async function executeKrakenBotOrder(
  request: KrakenBotOrderRequest
): Promise<KrakenBotOrderResponse> {
  const response = await fetch('/api/kraken/cli/bot-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || 'Kraken CLI bot order execution failed');
  }

  return response.json();
}

/**
 * Fetches the entire 150+ Kraken CLI tools and Cursor skills catalog.
 */
export async function fetchKrakenTools(): Promise<{
  totalTools: number;
  categories: string[];
  tools: KrakenToolDefinition[];
}> {
  const response = await fetch('/api/kraken/cli/tools');
  if (!response.ok) {
    throw new Error(`Failed to fetch Kraken tools: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Executes any tool or Cursor skill through the Kraken CLI interface.
 */
export async function executeKrakenTool(
  toolId: string,
  parameters: Record<string, any> = {}
): Promise<any> {
  const response = await fetch('/api/kraken/cli/tools/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ toolId, parameters }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error || `Execution of tool ${toolId} failed`);
  }

  return response.json();
}

/**
 * Fetches recent audit entries from the Kraken CLI journal.
 */
export async function fetchKrakenJournal(): Promise<
  Array<{ id: string; timestamp: number; text: string; botId?: string; txid?: string; command?: string }>
> {
  const response = await fetch('/api/kraken/cli/journal');
  if (!response.ok) {
    throw new Error(`Failed to fetch Kraken journal: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetches the authoritative 3-Layer Kraken CLI 0.4.1 Inventory:
 * 1. 53 Top-Level Commands
 * 2. 181 Leaf Commands
 * 3. 151 Catalog Tools & 27 MCP Loaded ("Peter-Schnitt")
 * Plus the Version Drift Matrix (Sigma vs CLI 0.4.1)
 */
export async function fetchKrakenInventory(): Promise<{
  cli_version: string;
  binary_path: string;
  is_real_binary: boolean;
  three_layers: {
    layer_1_top_level: {
      total: number;
      commands: any[];
    };
    layer_2_leaf_commands: {
      total: number;
      commands: any[];
    };
    layer_3_catalog_and_mcp: {
      total_catalog_tools: number;
      loaded_mcp_count: number;
      loaded_mcp_tools: string[];
    };
  };
  version_drift_matrix: any[];
}> {
  const response = await fetch('/api/kraken/cli/inventory');
  if (!response.ok) {
    throw new Error(`Failed to fetch Kraken inventory: ${response.statusText}`);
  }
  return response.json();
}

export interface KrakenRecalibrationResult {
  success: boolean;
  action: string;
  message: string;
  calibratedSymbols: string[];
  errors?: string[];
  markets: Record<string, any>;
  paperLedger?: {
    current_value: number;
    cash: number;
    unrealized_pnl: number;
    positions_count: number;
  };
  timestamp: number;
}

/**
 * Executes a Force Price Recalibration:
 * Triggers a hard flush of the local market state and fetches the absolute current ticker data
 * from the Kraken Public REST API to eliminate lingering simulation drifts.
 */
export async function executeKrakenPriceRecalibration(): Promise<KrakenRecalibrationResult> {
  const response = await fetch('/api/kraken/recalibrate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to force price recalibration: ${response.statusText}`);
  }
  return response.json();
}

