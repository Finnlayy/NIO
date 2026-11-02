import { NextResponse, type NextRequest } from "next/server";
import { handleGenericProxy } from "../../../../apollo/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let body: { path: string; method: string; payload?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON" }, { status: 400 });
  }

  const result = await handleGenericProxy(body.path, body.method, body.payload, process.env);

  if (result.body) {
    return NextResponse.json(result.body, { status: result.status });
  }

  return new NextResponse(result.rawText, {
    status: result.status,
    headers: result.headers
  });
}
