import { NextResponse, type NextRequest } from "next/server";
import { McpError, callTool, listTools } from "@/server/tradingview/client";
import { TOOLS, isReadOnlyTool, toMcpInterval } from "@/server/tradingview/tools";
import {
  adaptNews,
  adaptOhlcv,
  adaptQuote,
  adaptScreener,
  adaptTechnicals,
} from "@/server/tradingview/adapters";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TTL = {
  quote: 90_000,
  ohlcv: 120_000,
  technicals: 180_000,
  news: 300_000,
  screener: 300_000,
} as const;

const SOURCE = "tradingview";

async function handle(tool: string, req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const symbol = params.get("symbol") ?? "BINANCE:BTCUSDT";
  const interval = toMcpInterval(params.get("interval"));
  const limit = Math.min(500, Math.max(1, Number(params.get("limit") ?? 100) || 100));
  // Set by a widget's refresh button: bypass the TTL cache once.
  const fresh = params.get("fresh") === "1";

  switch (tool) {
    case "tools":
      return NextResponse.json({ ok: true, tools: await listTools() });

    case "quote": {
      const raw = await callTool(TOOLS.quote, { symbol }, TTL.quote, fresh);
      const quote = adaptQuote(raw, symbol);
      if (!quote) throw new McpError(502, "Quote shape not recognized");
      return NextResponse.json({ ok: true, source: SOURCE, data: quote });
    }

    case "quotes": {
      // Breadth quotes in one batch call (the MCP takes up to 50 symbols).
      const symbolsParam = params.get("symbols");
      const { tickers: watchlist } = await import("@/ops/marketData");
      const symbols = (
        symbolsParam
          ? symbolsParam.split(",").map((s) => s.trim()).filter(Boolean)
          : watchlist.slice(0, 12).map((t) => `BINANCE:${t.symbol.replace(".P", "")}`)
      ).slice(0, 50);

      const raw = (await callTool(TOOLS.quotes, { symbols }, TTL.quote, fresh)) as Record<string, unknown> | null;
      const byBase: Record<string, { price: number; changePct: number }> = {};
      for (const sym of symbols) {
        const q = adaptQuote(raw?.[sym], sym);
        if (!q) continue;
        const base = sym.split(":").pop()!.replace(/USDT$/, "").replace(/\.P$/, "");
        byBase[base] = { price: q.price, changePct: q.changePct };
      }
      if (!Object.keys(byBase).length) throw new McpError(502, "No live quotes returned");
      return NextResponse.json({ ok: true, source: SOURCE, data: { byBase } });
    }

    case "ohlcv": {
      const raw = await callTool(TOOLS.ohlcv, { symbol, interval, count: limit }, TTL.ohlcv, fresh);
      const data = adaptOhlcv(raw);
      if (!data) throw new McpError(502, "OHLCV shape not recognized");
      return NextResponse.json({ ok: true, source: SOURCE, data });
    }

    case "technicals": {
      const raw = await callTool(TOOLS.technicals, { symbol, interval }, TTL.technicals, fresh);
      const data = adaptTechnicals(raw);
      if (!data) throw new McpError(502, "Technicals shape not recognized");
      return NextResponse.json({ ok: true, source: SOURCE, data });
    }

    case "news": {
      const raw = await callTool(TOOLS.news, { symbol, limit: 8 }, TTL.news, fresh);
      const data = adaptNews(raw);
      if (!data) throw new McpError(502, "News shape not recognized");
      return NextResponse.json({ ok: true, source: SOURCE, data });
    }

    case "screener": {
      // The MCP rejects unfiltered scans; a preset keeps the call cheap.
      const raw = await callTool(
        TOOLS.screener,
        { market: "crypto", filter_preset: "relative_strength", limit: 10 },
        TTL.screener,
        fresh,
      );
      const data = adaptScreener(raw);
      if (!data) throw new McpError(502, "Screener shape not recognized");
      return NextResponse.json({ ok: true, source: SOURCE, data });
    }

    default: {
      // Generic passthrough for read-only tools; arguments come verbatim from
      // the query string (numbers parsed), so each tool gets only what it declares.
      if (!isReadOnlyTool(tool)) {
        throw new McpError(403, `Tool ${tool} is not a read-only TradingView tool`);
      }
      const args: Record<string, unknown> = {};
      for (const [key, value] of params) {
        if (key === "fresh") continue;
        args[key] = /^-?\d+(\.\d+)?$/.test(value) ? Number(value) : value;
      }
      const raw = await callTool(tool, args, 120_000, fresh);
      return NextResponse.json({ ok: true, source: SOURCE, data: raw });
    }
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ tool: string }> }) {
  const { tool } = await ctx.params;
  try {
    return await handle(tool, req);
  } catch (err) {
    const status = err instanceof McpError ? err.status : 502;
    const message = err instanceof Error ? err.message : "Unknown data error";
    return NextResponse.json(
      { ok: false, source: "error", error: message },
      { status: status >= 400 && status < 600 ? status : 502 },
    );
  }
}
