import { NextResponse, type NextRequest } from "next/server";
import { OAuthError, buildAuthorizeUrl, isLoopbackHost } from "@/server/tradingview/oauth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Startet den TradingView-Login: leitet auf die Autorisierungsseite weiter. */
export async function GET(req: NextRequest) {
  if (!isLoopbackHost(req.nextUrl.hostname)) {
    return NextResponse.json({ ok: false, error: "TradingView-Login nur über localhost" }, { status: 403 });
  }
  const redirectUri = `${req.nextUrl.origin}/api/market/oauth/callback`;
  try {
    return NextResponse.redirect(await buildAuthorizeUrl(redirectUri));
  } catch (err) {
    const status = err instanceof OAuthError ? err.status : 502;
    const message = err instanceof Error ? err.message : "OAuth start failed";
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}
