import { NextResponse } from "next/server";
import { echoPostMortemFlow, PostMortemInputSchema } from "../../../../../genkit-flows/flows/echo-post-mortem.flow";

/**
 * POST /api/genkit/post-mortem
 *
 * Invokes the `echoPostMortem` flow with a schema-validated body. The flow
 * body delegates to `executePostMortem`, which writes a row to
 * `twin_behavioral_ledger`. If the table is not yet migrated in this
 * environment, we fall back to a schema-only preview so the console demo
 * keeps working; the response carries `degraded: true` in that case.
 */
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid-json" }, { status: 400 });
  }

  const parsed = PostMortemInputSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "schema-validation-failed", issues: parsed.error.issues },
      { status: 422 }
    );
  }

  const startedAt = Date.now();
  try {
    const output = await echoPostMortemFlow(parsed.data);
    return NextResponse.json({
      degraded: false,
      latencyMs: Date.now() - startedAt,
      output,
    });
  } catch (error) {
    // Fallback: compute a deterministic preview so the console remains live
    // even when the underlying ledger table is not yet migrated.
    const input = parsed.data;
    const passed = input.outcome === "passed";
    const learningDelta = passed
      ? Math.max(2, Math.round((input.score - 70) / 4))
      : input.humanFeedback?.decision === "rejected"
      ? -15
      : -Math.max(5, Math.round((100 - input.score) / 6));

    return NextResponse.json({
      degraded: true,
      reason: error instanceof Error ? error.message : "flow-error",
      latencyMs: Date.now() - startedAt,
      output: {
        behavioralLedgerId: 0,
        whatWorked: passed ? [`score ${input.score} on ${input.taskType}`] : [],
        whatFailed: passed ? [] : [`outcome=${input.outcome}`, ...input.evidence.errors.slice(0, 2)],
        rootCause: input.evidence.errors[0] ?? null,
        strategyUpdate: passed ? null : `Re-run ${input.taskType} with tighter timeout`,
        manifestChanges: null,
        learningDelta,
        shouldRetrain: !passed && input.score < 70,
      },
    });
  }
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
