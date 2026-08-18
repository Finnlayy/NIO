import { db } from "@/db";
import { orchestratorMemoryEvents } from "@/db/schema";
import { desc } from "drizzle-orm";

export const dynamic = "force-dynamic";

const validStates = new Set([
  "PLANNING",
  "EXECUTING",
  "REVIEWING",
  "EVALUATING",
  "REVISING",
  "DEPLOYING",
  "ESCALATED",
]);

const validOutcomes = new Set(["passed", "revised", "escalated", "blocked"]);

function asMemoryEvent(value: unknown) {
  if (!value || typeof value !== "object") return null;
  const payload = value as Record<string, unknown>;
  const agentId = typeof payload.agentId === "string" ? payload.agentId.trim() : "";
  const workflowState = typeof payload.workflowState === "string" ? payload.workflowState : "";
  const outcome = typeof payload.outcome === "string" ? payload.outcome : "";
  const notes = typeof payload.notes === "string" ? payload.notes.trim() : "";
  const score = typeof payload.score === "number" ? payload.score : Number.NaN;

  if (
    !agentId ||
    agentId.length > 80 ||
    !validStates.has(workflowState) ||
    !validOutcomes.has(outcome) ||
    !Number.isInteger(score) ||
    score < 0 ||
    score > 100 ||
    !notes ||
    notes.length > 1200
  ) {
    return null;
  }

  return { agentId, workflowState, outcome, score, notes };
}

export async function GET() {
  try {
    const events = await db
      .select()
      .from(orchestratorMemoryEvents)
      .orderBy(desc(orchestratorMemoryEvents.createdAt), desc(orchestratorMemoryEvents.id))
      .limit(12);

    return Response.json({ events });
  } catch {
    return Response.json(
      {
        events: [],
        message: "Memory store is currently unavailable. The visual simulator remains local.",
      },
      { status: 503 },
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const event = asMemoryEvent(body);

    if (!event) {
      return Response.json({ message: "Invalid evaluation payload." }, { status: 400 });
    }

    const [created] = await db.insert(orchestratorMemoryEvents).values(event).returning();
    return Response.json({ event: created }, { status: 201 });
  } catch {
    return Response.json({ message: "Unable to store evaluation evidence." }, { status: 500 });
  }
}
