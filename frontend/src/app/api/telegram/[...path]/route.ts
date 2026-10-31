import type { NextRequest } from "next/server";
import { proxyTelegram } from "@/telegram/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Never let a proxy buffer the event stream into a stall. */
export const maxDuration = 300;

type Context = { params: Promise<{ path: string[] }> };

async function handle(req: NextRequest, ctx: Context): Promise<Response> {
  const { path } = await ctx.params;
  return proxyTelegram(req, path, process.env, fetch);
}

export const GET = handle;
export const POST = handle;
export const DELETE = handle;
