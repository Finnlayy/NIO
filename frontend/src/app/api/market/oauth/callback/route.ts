import { NextResponse, type NextRequest } from "next/server";
import { completeLogin, isLoopbackHost } from "@/server/tradingview/oauth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Redirect-Ziel des TradingView-Logins: tauscht den Code gegen Tokens. */
export async function GET(req: NextRequest) {
  if (!isLoopbackHost(req.nextUrl.hostname)) {
    return NextResponse.json({ ok: false, error: "TradingView-Login nur über localhost" }, { status: 403 });
  }
  const params = req.nextUrl.searchParams;
  const back = new URL("/ops", req.nextUrl.origin);
  const error = params.get("error");
  const code = params.get("code");
  const state = params.get("state");
  if (error || !code || !state) {
    back.searchParams.set("tradingview", `error:${error ?? "missing_code"}`);
    return NextResponse.redirect(back);
  }
  try {
    await completeLogin(code, state);
    back.searchParams.set("tradingview", "connected");
  } catch (err) {
    back.searchParams.set("tradingview", `error:${err instanceof Error ? err.message : "token_exchange"}`);
  }
  return NextResponse.redirect(back);
}
