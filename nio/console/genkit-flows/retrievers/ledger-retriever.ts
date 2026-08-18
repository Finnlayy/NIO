/**
 * Ledger retriever — pulls the most relevant past post-mortems for a new task.
 *
 * Phase 1 implementation: Drizzle query on `twin_behavioral_ledger` filtered
 * by task type, ordered by recency. The interface is the GenKit retriever
 * contract so Phase 2 can swap the body for a pgvector cosine search without
 * touching any caller.
 */
import { z, Document } from "genkit";
import { ai } from "../index";
import { db } from "@/db";
import { twinBehavioralLedger, orchestratorMemoryEvents } from "@/db/schema";
import { eq, desc } from "drizzle-orm";

const LedgerQuerySchema = z.object({
  taskType: z.string().min(1),
  limit: z.number().int().min(1).max(20).default(5),
});

type LedgerQuery = z.infer<typeof LedgerQuerySchema>;

export const ledgerRetriever = ai.defineRetriever(
  {
    name: "nexus/ledger",
    configSchema: LedgerQuerySchema,
  },
  async (document: Document, config: LedgerQuery) => {
    const taskType = config.taskType;
    const limit = config.limit;

    // Document text doubles as the query; we extract a token hint if the
    // caller passed a richer description than just the task type.
    const queryText = document.text ?? "";
    const hinted = queryText.split(/\s+/).find((token: string) => token.length > 3);

    const rows = await db
      .select({
        id: twinBehavioralLedger.id,
        taskType: twinBehavioralLedger.taskType,
        whatWorked: twinBehavioralLedger.whatWorked,
        whatFailed: twinBehavioralLedger.whatFailed,
        rootCause: twinBehavioralLedger.rootCause,
        strategyUpdate: twinBehavioralLedger.strategyUpdate,
        outcome: orchestratorMemoryEvents.outcome,
        score: orchestratorMemoryEvents.score,
      })
      .from(twinBehavioralLedger)
      .leftJoin(
        orchestratorMemoryEvents,
        eq(twinBehavioralLedger.eventId, orchestratorMemoryEvents.id)
      )
      .where(eq(twinBehavioralLedger.taskType, hinted ?? taskType))
      .orderBy(desc(twinBehavioralLedger.createdAt))
      .limit(limit);

    const documents = rows.map(
      (row) =>
        new Document({
          content: [
            {
              text: [
                `task_type=${row.taskType}`,
                `outcome=${row.outcome ?? "unknown"}`,
                `score=${row.score ?? 0}`,
                row.whatWorked?.length ? `worked: ${row.whatWorked.join("; ")}` : null,
                row.whatFailed?.length ? `failed: ${row.whatFailed.join("; ")}` : null,
                row.rootCause ? `root_cause: ${row.rootCause}` : null,
                row.strategyUpdate ? `strategy: ${row.strategyUpdate}` : null,
              ]
                .filter(Boolean)
                .join("\n"),
            },
          ],
          metadata: { ledgerId: row.id, taskType: row.taskType },
        })
    );

    return { documents };
  }
);
