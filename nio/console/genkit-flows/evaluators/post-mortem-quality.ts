/**
 * Post-mortem alignment evaluator.
 *
 * Per-sample evaluator used by `genkit eval:run` against the dataset in
 * `genkit-flows/datasets/post-mortem-samples.json`. Scores 1 when the flow's
 * `learningDelta` sign agrees with the human feedback category, 0 when it
 * contradicts, and falls back to outcome-only alignment (0.5 neutral) when
 * no human signal is present.
 */
import { z } from "genkit";
import { ai } from "../index";

const ReferenceSchema = z.object({
  outcome: z.enum(["passed", "revised", "escalated"]),
  humanFeedbackCategory: z.enum(["approved", "modified", "rejected"]).nullable().optional(),
});

const OutputSchema = z.object({
  learningDelta: z.number(),
});

type Reference = z.infer<typeof ReferenceSchema>;
type Output = z.infer<typeof OutputSchema>;

interface EvalDatapoint {
  testCaseId: string;
  input?: unknown;
  output?: unknown;
  reference?: unknown;
}

export const alignmentEvaluator = ai.defineEvaluator(
  {
    name: "nexus/postMortemAlignment",
    displayName: "Post-mortem alignment",
    definition:
      "1 when learning-delta sign matches human feedback, 0 when it contradicts, 0.5 when no human signal is present. Higher is better.",
  },
  async (datapoint: EvalDatapoint) => {
    // GenKit 1.x evaluators return a full EvalResponse shape; we wrap each
    // sample's score inside `{ testCaseId, evaluation }`.
    const wrap = (score: number, details: Record<string, unknown>) => ({
      testCaseId: datapoint.testCaseId,
      evaluation: { score, details },
    });

    const out = OutputSchema.safeParse(datapoint.output);
    const ref = ReferenceSchema.safeParse(datapoint.reference);
    if (!out.success || !ref.success) {
      return wrap(0, { error: "schema-mismatch" });
    }

    const { learningDelta } = out.data;
    const { outcome, humanFeedbackCategory } = ref.data;

    if (!humanFeedbackCategory) {
      const aligned =
        (outcome === "passed" && learningDelta >= 0) ||
        (outcome !== "passed" && learningDelta <= 0);
      return wrap(aligned ? 1 : 0.25, { reason: "outcome-only" });
    }

    const humanPositive = humanFeedbackCategory === "approved";
    const humanNegative = humanFeedbackCategory === "rejected";
    const deltaPositive = learningDelta > 0;
    const deltaNegative = learningDelta < 0;

    if (humanPositive && deltaPositive) return wrap(1, { reason: "approved-positive" });
    if (humanNegative && deltaNegative) return wrap(1, { reason: "rejected-negative" });
    if (humanPositive && deltaNegative) return wrap(0, { reason: "approved-negative" });
    if (humanNegative && deltaPositive) return wrap(0, { reason: "rejected-positive" });
    return wrap(0.5, { reason: "neutral-delta" });
  }
);
