import { NextResponse } from "next/server";
import { GENKIT_RUNTIME } from "../../../../../genkit-flows";

/**
 * GET /api/genkit/status
 *
 * Returns the runtime configuration of the GenKit singleton and the static
 * list of registered actions. The CLI (`npx genkit start`) discovers actions
 * by loading `genkit.config.ts`; the Next.js runtime enumerates them here so
 * the console can show a live "what's wired up" panel.
 */
export async function GET() {
  return NextResponse.json({
    runtime: GENKIT_RUNTIME,
    flows: [
      {
        name: "echoPostMortem",
        description: "Post-mortem analysis wrapping src/lib/autodidactic/reflection-engine.ts",
        input: "PostMortemInputSchema",
        output: "PostMortemOutputSchema",
      },
    ],
    retrievers: [
      {
        name: "nexus/ledger",
        description: "Drizzle-backed retriever over twin_behavioral_ledger (pgvector swap planned)",
      },
    ],
    evaluators: [
      {
        name: "nexus/postMortemAlignment",
        description: "Per-sample alignment metric between learning-delta sign and human feedback",
        dataset: "genkit-flows/datasets/post-mortem-samples.json",
      },
    ],
  });
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
