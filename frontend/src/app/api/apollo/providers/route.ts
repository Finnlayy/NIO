import { NextResponse } from "next/server";
import { probeProviders, providerStatuses } from "@/server/providers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function GET() {
  try { return NextResponse.json({ ok: true, providers: await providerStatuses() }, { headers: { "Cache-Control": "no-store" } }); }
  catch { return NextResponse.json({ ok: false, error: "secret_store_unavailable_or_invalid", providers: [] }, { status: 503 }); }
}
export async function POST() {
  try {
    const providers = await probeProviders();
    return NextResponse.json({ ok: providers.some((p) => p.status === "ready"), providers,
      note: "One real completion per configured provider with a model, max 16 output tokens. No simulation." },
    { status: providers.some((p) => p.status === "ready") ? 200 : 503 });
  } catch { return NextResponse.json({ ok: false, error: "secret_store_unavailable_or_invalid", providers: [] }, { status: 503 }); }
}
