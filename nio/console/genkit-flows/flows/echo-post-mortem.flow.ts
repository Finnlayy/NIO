/**
 * Echo — post-mortem flow.
 *
 * Thin GenKit wrapper around `executePostMortem`. The implementation stays in
 * `src/lib/autodidactic/reflection-engine.ts`; this flow adds schema
 * validation, span tracing, and a canonical input/output contract that the
 * rest of the platform (CLI, evals, console) can rely on.
 */
import { z } from "genkit";
import { ai } from "../index";
import { executePostMortem, type PostMortemInput } from "@/lib/autodidactic/reflection-engine";

const AgentUsage = z.object({
  agentId: z.string().min(1),
  role: z.string().optional(),
  performanceScore: z.number().min(0).max(100),
  executionTimeMs: z.number().int().nonnegative(),
});

const Evidence = z.object({
  logs: z.array(z.string()).default([]),
  artifacts: z.array(z.string()).default([]),
  errors: z.array(z.string()).default([]),
});

const HumanFeedback = z
  .object({
    decision: z.enum(["approved", "modified", "rejected"]),
    reasoning: z.string().min(1),
    alternativeApproach: z.string().optional(),
  })
  .optional();

export const PostMortemInputSchema = z.object({
  eventId: z.number().int().positive(),
  taskId: z.string().min(1),
  taskType: z.string().min(1),
  outcome: z.enum(["passed", "revised", "escalated"]),
  score: z.number().min(0).max(100),
  agentsUsed: z.array(AgentUsage).min(1),
  evidence: Evidence,
  humanFeedback: HumanFeedback,
});

export const PostMortemOutputSchema = z.object({
  behavioralLedgerId: z.number().int().positive(),
  whatWorked: z.array(z.string()),
  whatFailed: z.array(z.string()),
  rootCause: z.string().nullable(),
  strategyUpdate: z.string().nullable(),
  manifestChanges: z.record(z.string(), z.unknown()).nullable(),
  learningDelta: z.number(),
  shouldRetrain: z.boolean(),
});

export type PostMortemFlowOutput = z.infer<typeof PostMortemOutputSchema>;

export const echoPostMortemFlow = ai.defineFlow(
  {
    name: "echoPostMortem",
    inputSchema: PostMortemInputSchema,
    outputSchema: PostMortemOutputSchema,
  },
  async (input) => {
    // The schema is the source of truth; the existing `PostMortemInput`
    // interface is structurally compatible so we pass through without casts.
    const result = await executePostMortem(input);
    return {
      behavioralLedgerId: result.behavioralLedgerId,
      whatWorked: result.whatWorked,
      whatFailed: result.whatFailed,
      rootCause: result.rootCause,
      strategyUpdate: result.strategyUpdate,
      manifestChanges: result.manifestChanges,
      learningDelta: result.learningDelta,
      shouldRetrain: result.shouldRetrain,
    };
  }
);
