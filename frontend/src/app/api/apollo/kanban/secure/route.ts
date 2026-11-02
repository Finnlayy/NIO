import { NextResponse, type NextRequest } from "next/server";
import { handleSecureProxy } from "../../../../../apollo/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let body: { path: string; method: string; pin: string; payload?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON" }, { status: 400 });
  }

  const result = await handleSecureProxy(body.path, body.method, body.pin, body.payload, process.env);

  if (result.body) {
    return NextResponse.json(result.body, { status: result.status });
  }

  return new NextResponse(result.rawText, {
    status: result.status,
    headers: result.headers
  });
}
