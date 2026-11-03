import { NextResponse } from "next/server";
import { connectionStatus } from "@/server/tradingview/oauth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Verbindungsstatus ohne Token-Inhalte. */
export async function GET() {
  return NextResponse.json({ ok: true, ...connectionStatus() });
}
