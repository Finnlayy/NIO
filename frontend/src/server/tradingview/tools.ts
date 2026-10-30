/* ------------------------------------------------------------------ */
/* Tool-Zuordnung fuer den offiziellen TradingView-MCP.                */
/* Pure Funktionen ohne I/O, damit der UI-Test-Harness sie pruefen kann.*/
/* ------------------------------------------------------------------ */

/** Widget-Datensatz -> Tool-Name auf mcp.tradingview.com. */
export const TOOLS = {
  quote: "mcp-tv-get-symbol-data",
  quotes: "mcp-tv-get-symbol-data-batch",
  ohlcv: "mcp-tv-get-ohlcv",
  technicals: "mcp-tv-get-technicals-rating",
  news: "mcp-tv-get-news",
  screener: "mcp-tv-run-screener",
} as const;

/** Bar-Intervalle des MCP: 1m 5m 15m 30m 1h 2h 4h 1D 1W 1M. */
const MINUTE_INTERVALS: Record<string, string> = {
  "1": "1m",
  "5": "5m",
  "15": "15m",
  "30": "30m",
  "60": "1h",
  "120": "2h",
  "240": "4h",
};

/**
 * Normalize an interval to the MCP's vocabulary. Accepts the legacy
 * TradingView-chart form ("60", "240", "D", "W") the widgets still send.
 */
export function toMcpInterval(interval: string | null | undefined): string {
  const raw = (interval ?? "").trim();
  if (!raw) return "1h";
  if (raw in MINUTE_INTERVALS) return MINUTE_INTERVALS[raw];
  const upper = raw.toUpperCase();
  if (upper === "D" || upper === "1D") return "1D";
  if (upper === "W" || upper === "1W") return "1W";
  // "1m" is one minute, "1M"/"M" one month.
  if (raw === "M" || raw === "1M") return "1M";
  return raw;
}

/**
 * The generic passthrough may only reach read-only tools. Write tools
 * (create/update/delete alerts, watchlist edits) act on the user's
 * TradingView account and must never be callable via GET.
 */
export function isReadOnlyTool(name: string): boolean {
  return /^mcp-(tv|watchlist)-(get|list|search)-[a-z0-9-]+$/.test(name);
}
