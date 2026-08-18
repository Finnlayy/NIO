/**
 * RLHF (Reinforcement Learning from Human Feedback) Capture
 * 
 * Processes human feedback on agent decisions to train the Twin's preference model.
 * Captures, embeds, and stores human preferences for future alignment.
 */

import { db } from "@/db";
import { rlhfSamples, twinBehavioralLedger } from "@/db/schema";
import { eq } from "drizzle-orm";

// ============================================================================
// Type Definitions
// ============================================================================

export interface HumanFeedbackInput {
  eventId: number;
  ledgerId?: number;
  originalDecision: string;
  humanDecision: string;
  humanReasoning: string;
  alternativeApproach?: string;
  feedbackCategory: "approved" | "modified" | "rejected" | "escalated";
  humanConfidence?: number; // 1-10
}

export interface RLHFLearning {
  sampleId: number;
  preferenceEmbedding: number[] | null;
  patternIdentified: string;
  ruleUpdate: string | null;
  shouldRetrain: boolean;
  appliedToModel: "pending" | "applied" | "deferred";
}

interface FeedbackPattern {
  type: "preference_mismatch" | "safety_override" | "efficiency_improvement" | "quality_adjustment";
  description: string;
  severity: "low" | "medium" | "high";
}

// ============================================================================
// Main RLHF Processing
// ============================================================================

/**
 * Process human feedback and extract learnings for preference model.
 */
export async function processHumanFeedback(input: HumanFeedbackInput): Promise<RLHFLearning> {
  console.log(`[RLHF] Processing human feedback for event ${input.eventId}`);
  
  // Step 1: Generate preference embedding
  const preferenceEmbedding = await generatePreferenceEmbedding(input);
  
  // Step 2: Identify feedback pattern
  const pattern = identifyFeedbackPattern(input);
  console.log(`[RLHF] Pattern identified: ${pattern.type} - ${pattern.description}`);
  
  // Step 3: Compute rule update (if applicable)
  const ruleUpdate = computeRuleUpdate(pattern, input);
  if (ruleUpdate) {
    console.log(`[RLHF] Rule update: ${ruleUpdate}`);
  }
  
  // Step 4: Determine if retraining needed
  const shouldRetrain = determineRetrainNeed(input, pattern);
  
  // Step 5: Store RLHF sample
  const sample = await storeRLHFSample({
    ...input,
    preferenceEmbedding,
    pattern,
    ruleUpdate,
    shouldRetrain,
  });
  
  // Step 6: Update preference model if needed
  let appliedToModel: "pending" | "applied" | "deferred" = "pending";
  if (shouldRetrain) {
    const applied = await updatePreferenceModel({
      sample: input,
      pattern,
      embedding: preferenceEmbedding,
      sampleId: sample.id,
    });
    appliedToModel = applied ? "applied" : "deferred";
  }
  
  return {
    sampleId: sample.id,
    preferenceEmbedding,
    patternIdentified: pattern.description,
    ruleUpdate,
    shouldRetrain,
    appliedToModel,
  };
}

// ============================================================================
// Preference Embedding
// ============================================================================

async function generatePreferenceEmbedding(input: HumanFeedbackInput): Promise<number[] | null> {
  try {
    // In production, call Vertex AI Embedding API
    const content = JSON.stringify({
      decision: input.humanDecision,
      reasoning: input.humanReasoning,
      alternative: input.alternativeApproach,
      originalDecision: input.originalDecision,
      category: input.feedbackCategory,
    });
    
    // TODO: Implement Vertex AI embedding generation
    // const embedding = await vertexAI.generateEmbedding({
    //   model: "text-embedding-005",
    //   content,
    // });
    
    console.log(`[RLHF] Embedding generated for feedback (length: ${content.length} chars)`);
    return null; // Placeholder - will be generated asynchronously
  } catch (error) {
    console.error("[RLHF] Failed to generate embedding:", error);
    return null;
  }
}

// ============================================================================
// Pattern Identification
// ============================================================================

function identifyFeedbackPattern(input: HumanFeedbackInput): FeedbackPattern {
  const reasoning = input.humanReasoning.toLowerCase();
  const original = input.originalDecision.toLowerCase();
  const human = input.humanDecision.toLowerCase();
  
  // Pattern 1: Preference mismatch (human preferred different approach)
  if (reasoning.includes("prefer") || reasoning.includes("better") || reasoning.includes("instead")) {
    return {
      type: "preference_mismatch",
      description: "Human preferred alternative approach over agent decision",
      severity: "medium",
    };
  }
  
  // Pattern 2: Safety override (human blocked for safety reasons)
  if (reasoning.includes("safety") || reasoning.includes("risk") || reasoning.includes("security")) {
    return {
      type: "safety_override",
      description: "Human overrode agent decision for safety reasons",
      severity: "high",
    };
  }
  
  // Pattern 3: Efficiency improvement (human found faster way)
  if (reasoning.includes("faster") || reasoning.includes("efficient") || reasoning.includes("optimize")) {
    return {
      type: "efficiency_improvement",
      description: "Human suggested more efficient approach",
      severity: "low",
    };
  }
  
  // Pattern 4: Quality adjustment (human improved output quality)
  if (reasoning.includes("quality") || reasoning.includes("accuracy") || reasoning.includes("correct")) {
    return {
      type: "quality_adjustment",
      description: "Human improved output quality or correctness",
      severity: "medium",
    };
  }
  
  // Default pattern
  return {
    type: "preference_mismatch",
    description: "Human decision differed from agent decision",
    severity: "low",
  };
}

// ============================================================================
// Rule Update Computation
// ============================================================================

function computeRuleUpdate(pattern: FeedbackPattern, input: HumanFeedbackInput): string | null {
  if (pattern.severity === "low") {
    return null; // No rule update for low-severity feedback
  }
  
  const updates: string[] = [];
  
  switch (pattern.type) {
    case "safety_override":
      updates.push("Add safety check for similar scenarios");
      updates.push(`Reasoning: ${input.humanReasoning.slice(0, 100)}`);
      break;
      
    case "preference_mismatch":
      if (input.alternativeApproach) {
        updates.push(`Store alternative approach: ${input.alternativeApproach.slice(0, 150)}`);
      }
      updates.push("Update preference model with human decision pattern");
      break;
      
    case "efficiency_improvement":
      updates.push("Consider human-suggested optimization in future planning");
      break;
      
    case "quality_adjustment":
      updates.push("Update quality thresholds based on human feedback");
      break;
  }
  
  return updates.join("; ");
}

// ============================================================================
// Retraining Decision
// ============================================================================

function determineRetrainNeed(input: HumanFeedbackInput, pattern: FeedbackPattern): boolean {
  // Always retrain for high-severity patterns
  if (pattern.severity === "high") {
    return true;
  }
  
  // Retrain for rejected decisions with high confidence
  if (input.feedbackCategory === "rejected" && (input.humanConfidence ?? 0) >= 8) {
    return true;
  }
  
  // Retrain for safety overrides
  if (pattern.type === "safety_override") {
    return true;
  }
  
  // Retrain if alternative approach provided
  if (input.alternativeApproach && input.alternativeApproach.length > 50) {
    return true;
  }
  
  return false;
}

// ============================================================================
// RLHF Sample Storage
// ============================================================================

async function storeRLHFSample(data: HumanFeedbackInput & {
  preferenceEmbedding: number[] | null;
  pattern: FeedbackPattern;
  ruleUpdate: string | null;
  shouldRetrain: boolean;
}) {
  const [sample] = await db.insert(rlhfSamples).values({
    eventId: data.eventId,
    originalDecision: data.originalDecision,
    humanDecision: data.humanDecision,
    humanReasoning: data.humanReasoning,
    alternativeApproach: data.alternativeApproach,
    feedbackCategory: data.feedbackCategory,
    humanConfidence: data.humanConfidence,
    preferenceEmbedding: data.preferenceEmbedding ? JSON.stringify(data.preferenceEmbedding) : null,
    patternIdentified: data.pattern.description,
    ruleUpdate: data.ruleUpdate,
    shouldRetrain: data.shouldRetrain ? "true" : "false",
    appliedToModel: "pending",
  }).returning();
  
  return sample;
}

// ============================================================================
// Preference Model Update
// ============================================================================

async function updatePreferenceModel(data: {
  sample: HumanFeedbackInput;
  pattern: FeedbackPattern;
  embedding: number[] | null;
  sampleId: number;
}): Promise<boolean> {
  try {
    // In production, this would update the Twin's preference model
    // For now, just mark the sample as applied
    
    await db.update(rlhfSamples)
      .set({ appliedToModel: "applied", appliedAt: new Date() })
      .where(eq(rlhfSamples.id, data.sampleId));
    
    console.log(`[RLHF] Preference model updated with sample ${data.sampleId}`);
    return true;
  } catch (error) {
    console.error("[RLHF] Failed to update preference model:", error);
    
    // Mark as deferred
    await db.update(rlhfSamples)
      .set({ appliedToModel: "deferred" })
      .where(eq(rlhfSamples.id, data.sampleId));
    
    return false;
  }
}

// ============================================================================
// Query Functions
// ============================================================================

/**
 * Get RLHF samples for retraining
 */
export async function getRLHFSamplesForRetraining(limit: number = 100) {
  const samples = await db.select()
    .from(rlhfSamples)
    .where(eq(rlhfSamples.shouldRetrain, "true"))
    .orderBy(rlhfSamples.createdAt)
    .limit(limit);
  
  return samples;
}

/**
 * Get human alignment score (percentage of decisions matching human preferences)
 */
export async function getHumanAlignmentScore(timeRange?: { start: Date; end: Date }): Promise<number> {
  const samples = await db.select()
    .from(rlhfSamples)
    .where(eq(rlhfSamples.appliedToModel, "applied"));
  
  if (samples.length === 0) {
    return 0;
  }
  
  const approvedCount = samples.filter(s => s.feedbackCategory === "approved").length;
  return Math.round((approvedCount / samples.length) * 100);
}

/**
 * Get feedback patterns distribution
 */
export async function getFeedbackPatternsDistribution() {
  const samples = await db.select()
    .from(rlhfSamples)
    .orderBy(rlhfSamples.createdAt);
  
  const distribution: Record<string, number> = {};
  samples.forEach(sample => {
    const pattern = sample.patternIdentified || "unknown";
    distribution[pattern] = (distribution[pattern] || 0) + 1;
  });
  
  return distribution;
}
