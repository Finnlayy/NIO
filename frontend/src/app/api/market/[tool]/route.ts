import { NextResponse, type NextRequest } from "next/server";
import { McpError, callTool } from "@/server/tvremix/client";
import { smartCall } from "@/server/tvremix/args";
import {
  adaptNews,
  adaptOhlcv,
  adaptQuote,
  adaptScreener,
  adaptTechnicals,
} from "@/server/tvremix/adapters";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TTL = {
  quote: 90_000,
  ohlcv: 120_000,
  technicals: 180_000,
  news: 300_000,
  screener: 300_000,
} as const;

async function handle(tool: string, req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const symbol = params.get("symbol") ?? "BINANCE:BTCUSDT";
  const interval = params.get("interval") ?? "60";
  const limit = Number(params.get("limit") ?? 100);

  switch (tool) {
    case "tools": {
      const { listTools } = await import("@/server/tvremix/client");
      return NextResponse.json({ ok: true, tools: await listTools() });
    }

    case "quote": {
      const raw = await smartCall(
        "get_quote_snapshot",
        { symbol, market: "crypto" },
        TTL.quote,
      );
      const quote = adaptQuote(raw, symbol);
      if (!quote) throw new McpError(502, "Quote shape not recognized");
      return NextResponse.json({ ok: true, source: "tvremix", data: quote });
    }

    case "quotes": {
      // Batch breadth quotes: fan out with per-symbol caching so the
      // 20/min limit is respected (cached ticks don't hit the MCP).
      const symbolsParam = params.get("symbols");
      const { tickers: watchlist } = await import("@/ops/marketData");
      const symbols = symbolsParam
        ? symbolsParam.split(",").map((s) => s.trim()).filter(Boolean)
        : watchlist.slice(0, 12).map((t) => `BINANCE:${t.symbol.replace(".P", "")}`);

      const results = await Promise.all(
        symbols.map(async (sym) => {
          try {
            const raw = await smartCall(
              "get_quote_snapshot",
              { symbol: sym, market: "crypto" },
              TTL.quote,
            );
            const q = adaptQuote(raw, sym);
            return q ?? { symbol: sym, live: false };
          } catch {
            return { symbol: sym, live: false };
          }
        }),
      );

      const live = results.filter((r) => "price" in r);
      if (!live.length) throw new McpError(502, "No live quotes returned");
      const byBase: Record<string, { price: number; changePct: number }> = {};
      for (const q of live) {
        const base = q.symbol.split(":").pop()!.replace(/USDT$/, "").replace(/\.P$/, "");
        byBase[base] = { price: q.price, changePct: q.changePct };
      }
      return NextResponse.json({ ok: true, source: "tvremix", data: { byBase } });
    }

    case "ohlcv": {
      const raw = await smartCall(
        "get_ohlcv",
        { symbol, interval, limit, market: "crypto" },
        TTL.ohlcv,
      );
      const data = adaptOhlcv(raw);
      if (!data) throw new McpError(502, "OHLCV shape not recognized");
      return NextResponse.json({ ok: true, source: "tvremix", data });
    }

    case "technicals": {
      const raw = await smartCall(
        "get_technicals",
        { symbol, interval, market: "crypto" },
        TTL.technicals,
      );
      const data = adaptTechnicals(raw);
      if (!data) throw new McpError(502, "Technicals shape not recognized");
      return NextResponse.json({ ok: true, source: "tvremix", data });
    }

    case "news": {
      const raw = await smartCall(
        "get_news",
        { symbol, limit: 8 },
        TTL.news,
      );
      const data = adaptNews(raw);
      if (!data) throw new McpError(502, "News shape not recognized");
      return NextResponse.json({ ok: true, source: "tvremix", data });
    }

    case "screener": {
      const raw = await smartCall(
        "screen_stocks",
        { market: "crypto", limit: 10 },
        TTL.screener,
      );
      const data = adaptScreener(raw);
      if (!data) throw new McpError(502, "Screener shape not recognized");
      return NextResponse.json({ ok: true, source: "tvremix", data });
    }

    default:
      // Generic passthrough — call any tool by name with symbol/interval/limit.
      const raw = await callTool(
        tool,
        { symbol, interval, limit, market: "crypto" },
        120_000,
      );
      return NextResponse.json({ ok: true, source: "tvremix", data: raw });
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
