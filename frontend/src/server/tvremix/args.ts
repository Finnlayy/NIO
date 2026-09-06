/* ------------------------------------------------------------------ */
/* Smart argument builder — maps our canonical params onto whatever    */
/* property names the live MCP tool schema actually declares.          */
/* ------------------------------------------------------------------ */

import { callTool, listTools } from "./client";

type Provided = Record<string, string | number | undefined>;

const MATCHERS: Record<string, RegExp> = {
  symbol: /^(symbol|ticker|instrument|pair|security|s)$/i,
  interval: /^(interval|timeframe|resolution|period|tf|barsize)$/i,
  limit: /^(limit|bars|count|n|maxbars|rows|quantity)$/i,
  market: /^(market|assetclass|asset_class|type|exchange|universe)$/i,
  query: /^(query|q|search|screener|filter)$/i,
};

async function findTool(name: string): Promise<any | null> {
  try {
    const list = await listTools();
    const tools = list?.tools ?? [];
    const exact = tools.find((t: any) => t.name === name);
    if (exact) return exact;
    // fuzzy: e.g. "get_quote_snapshot" vs "quote_snapshot"
    const tail = name.replace(/^get_|^fetch_/, "");
    return (
      tools.find((t: any) => t.name?.includes(tail)) ??
      tools.find((t: any) => tail.includes(t.name?.replace(/^get_|^fetch_/, ""))) ??
      null
    );
  } catch {
    return null;
  }
}

export async function smartCall(
  canonicalName: string,
  provided: Provided,
  ttlMs: number,
): Promise<unknown> {
  const tool = await findTool(canonicalName);
  const args: Record<string, unknown> = {};

  if (tool?.inputSchema?.properties) {
    const props = tool.inputSchema.properties as Record<string, any>;
    for (const [key, value] of Object.entries(provided)) {
      if (value === undefined) continue;
      const matcher = MATCHERS[key];
      const propName =
        Object.keys(props).find((p) => matcher?.test(p)) ??
        (key in props ? key : undefined);
      if (propName) args[propName] = value;
    }
    // Fill uncovered required params with a typed default so strict servers
    // don't reject the call; symbol-less tools usually have sane defaults.
    const required: string[] = tool.inputSchema.required ?? [];
    for (const req of required) {
      if (req in args) continue;
      const type = props[req]?.type;
      if (type === "string") args[req] = provided.symbol ?? "";
      else if (type === "number" || type === "integer") args[req] = Number(provided.limit ?? 100);
      else if (type === "boolean") args[req] = false;
    }
    const toolName = tool.name as string;
    return callTool(toolName, args, ttlMs);
  }

  // No schema available (tools/list failed) — call with the canonical name.
  const clean = Object.fromEntries(Object.entries(provided).filter(([, v]) => v !== undefined));
  return callTool(canonicalName, clean as Record<string, unknown>, ttlMs);
}
