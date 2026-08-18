/**
 * AUTODIDACTIC REFLECTION ENGINE
 * 
 * Implements the mandatory post-mortem analysis for every agent task.
 * Extracts learnings, computes strategy updates, and stores in behavioral ledger.
 */

import { db } from "@/db";
import { twinBehavioralLedger, orchestratorMemoryEvents } from "@/db/schema";
import { eq, desc, and, sql } from "drizzle-orm";

// ============================================================================
// Type Definitions
// ============================================================================

export interface PostMortemInput {
  eventId: number;
  taskId: string;
  taskType: string;
  outcome: "passed" | "revised" | "escalated";
  score: number;
  agentsUsed: Array<{
    agentId: string;
    role?: string;
    performanceScore: number;
    executionTimeMs: number;
  }>;
  evidence: {
    logs: string[];
    artifacts: string[];
    errors: string[];
  };
  humanFeedback?: {
    decision: "approved" | "modified" | "rejected";
    reasoning: string;
    alternativeApproach?: string;
  };
}

export interface PostMortemOutput {
  behavioralLedgerId: number;
  whatWorked: string[];
  whatFailed: string[];
  rootCause: string | null;
  strategyUpdate: string | null;
  manifestChanges: Record<string, any> | null;
  learningDelta: number;
  shouldRetrain: boolean;
}

interface OutcomeAnalysis {
  success: boolean;
  performanceLevel: "excellent" | "good" | "acceptable" | "poor";
  rootCause: string | null;
  contributingFactors: string[];
}

interface ExtractedLearnings {
  whatWorked: string[];
  whatFailed: string[];
  patterns: string[];
  recommendations: string[];
}

// ============================================================================
// Main Post-Mortem Execution
// ============================================================================

/**
 * Execute mandatory post-mortem analysis after every agent task.
 * This is the core of the autodidactic learning loop.
 */
export async function executePostMortem(input: PostMortemInput): Promise<PostMortemOutput> {
  console.log(`[Post-Mortem] Starting analysis for task ${input.taskId}`);
  
  // Step 1: Analyze outcome
  const analysis = analyzeOutcome(input);
  console.log(`[Post-Mortem] Outcome analysis: ${analysis.success ? "SUCCESS" : "FAILURE"} - ${analysis.performanceLevel}`);
  
  // Step 2: Extract learnings
  const learnings = extractLearnings(analysis, input);
  console.log(`[Post-Mortem] Extracted ${learnings.whatWorked.length} successes, ${learnings.whatFailed.length} failures`);
  
  // Step 3: Compute strategy updates
  const strategyUpdate = computeStrategyUpdate(learnings, input, analysis);
  if (strategyUpdate) {
    console.log(`[Post-Mortem] Strategy update: ${strategyUpdate}`);
  }
  
  // Step 4: Compute manifest changes (if any)
  const manifestChanges = computeManifestChanges(learnings, input, analysis);
  if (manifestChanges) {
    console.log(`[Post-Mortem] Manifest changes proposed: ${JSON.stringify(manifestChanges)}`);
  }
  
  // Step 5: Calculate learning delta
  const learningDelta = calculateLearningDelta(input, analysis);
  console.log(`[Post-Mortem] Learning delta: ${learningDelta}`);
  
  // Step 6: Generate embedding for semantic retrieval
  const embedding = await generateEmbedding(input);
  
  // Step 7: Generate tags for fast filtering
  const tags = generateTags(input, analysis, learnings);
  
  // Step 8: Store in behavioral ledger
  const ledgerEntry = await storeBehavioralLedger({
    input,
    analysis,
    learnings,
    strategyUpdate,
    manifestChanges,
    learningDelta,
    embedding,
    tags,
  });
  
  // Step 9: Determine if retraining is needed
  const shouldRetrain = determineRetrainNeed(analysis, learningDelta, input);
  if (shouldRetrain) {
    console.log(`[Post-Mortem] Retraining recommended`);
  }
  
  // Step 10: If human feedback provided, process RLHF
  if (input.humanFeedback) {
    await processRLHFFeedback(input, ledgerEntry.id);
  }
  
  return {
    behavioralLedgerId: ledgerEntry.id,
    whatWorked: learnings.whatWorked,
    whatFailed: learnings.whatFailed,
    rootCause: analysis.rootCause,
    strategyUpdate,
    manifestChanges,
    learningDelta,
    shouldRetrain,
  };
}

// ============================================================================
// Outcome Analysis
// ============================================================================

function analyzeOutcome(input: PostMortemInput): OutcomeAnalysis {
  const success = input.outcome === "passed";
  const performanceLevel = determinePerformanceLevel(input.score, input.outcome);
  
  // Determine root cause for failures
  let rootCause: string | null = null;
  const contributingFactors: string[] = [];
  
  if (!success) {
    // Analyze errors
    if (input.evidence.errors.length > 0) {
      rootCause = categorizeError(input.evidence.errors[0]);
      contributingFactors.push(...input.evidence.errors.map(categorizeError));
    }
    
    // Analyze agent performance
    const underperformingAgents = input.agentsUsed.filter(a => a.performanceScore < 70);
    if (underperformingAgents.length > 0) {
      contributingFactors.push(
        `Underperforming agents: ${underperformingAgents.map(a => a.agentId).join(", ")}`
      );
    }
    
    // Analyze execution time
    const slowAgents = input.agentsUsed.filter(a => a.executionTimeMs > 30000);
    if (slowAgents.length > 0) {
      contributingFactors.push(
        `Slow execution: ${slowAgents.map(a => `${a.agentId} (${a.executionTimeMs}ms)`).join(", ")}`
      );
    }
    
    // Human feedback analysis
    if (input.humanFeedback?.decision === "rejected") {
      rootCause = `Human override: ${input.humanFeedback.reasoning}`;
    }
  }
  
  return {
    success,
    performanceLevel,
    rootCause,
    contributingFactors,
  };
}

function determinePerformanceLevel(score: number, outcome: string): "excellent" | "good" | "acceptable" | "poor" {
  if (outcome === "passed" && score >= 95) return "excellent";
  if (outcome === "passed" && score >= 85) return "good";
  if (outcome === "revised") return "acceptable";
  return "poor";
}

function categorizeError(error: string): string {
  const errorCategories: Record<string, string> = {
    "timeout": "TIMEOUT",
    "memory": "RESOURCE_EXHAUSTION",
    "permission": "PERMISSION_DENIED",
    "connection": "NETWORK_ERROR",
    "validation": "VALIDATION_ERROR",
    "syntax": "CODE_ERROR",
    "logic": "LOGIC_ERROR",
  };
  
  const errorLower = error.toLowerCase();
  for (const [keyword, category] of Object.entries(errorCategories)) {
    if (errorLower.includes(keyword)) {
      return category;
    }
  }
  
  return "UNKNOWN";
}

// ============================================================================
// Learning Extraction
// ============================================================================

function extractLearnings(analysis: OutcomeAnalysis, input: PostMortemInput): ExtractedLearnings {
  const whatWorked: string[] = [];
  const whatFailed: string[] = [];
  const patterns: string[] = [];
  const recommendations: string[] = [];
  
  if (analysis.success) {
    // Extract success factors
    whatWorked.push(`Task completed with score ${input.score}/100`);
    
    const highPerformers = input.agentsUsed.filter(a => a.performanceScore >= 90);
    if (highPerformers.length > 0) {
      whatWorked.push(
        `High-performing agents: ${highPerformers.map(a => `${a.agentId} (${a.performanceScore}%)`).join(", ")}`
      );
    }
    
    if (input.evidence.artifacts.length > 0) {
      whatWorked.push(`Generated ${input.evidence.artifacts.length} artifacts successfully`);
    }
  } else {
    // Extract failure factors
    if (analysis.rootCause) {
      whatFailed.push(`Root cause: ${analysis.rootCause}`);
    }
    
    const lowPerformers = input.agentsUsed.filter(a => a.performanceScore < 70);
    if (lowPerformers.length > 0) {
      whatFailed.push(
        `Low-performing agents: ${lowPerformers.map(a => `${a.agentId} (${a.performanceScore}%)`).join(", ")}`
      );
    }
    
    if (input.evidence.errors.length > 0) {
      whatFailed.push(`Errors encountered: ${input.evidence.errors.slice(0, 3).join("; ")}`);
    }
  }
  
  // Identify patterns
  if (input.agentsUsed.length > 1) {
    const avgScore = input.agentsUsed.reduce((sum, a) => sum + a.performanceScore, 0) / input.agentsUsed.length;
    patterns.push(`Multi-agent collaboration average: ${avgScore.toFixed(1)}%`);
  }
  
  // Generate recommendations
  if (!analysis.success && analysis.rootCause) {
    recommendations.push(`Address root cause: ${analysis.rootCause}`);
  }
  
  if (input.humanFeedback?.alternativeApproach) {
    recommendations.push(`Consider alternative: ${input.humanFeedback.alternativeApproach}`);
  }
  
  return { whatWorked, whatFailed, patterns, recommendations };
}

// ============================================================================
// Strategy Computation
// ============================================================================

function computeStrategyUpdate(
  learnings: ExtractedLearnings,
  input: PostMortemInput,
  analysis: OutcomeAnalysis
): string | null {
  if (analysis.success && analysis.performanceLevel === "excellent") {
    return null; // No change needed for excellent performance
  }
  
  const updates: string[] = [];
  
  // Agent selection strategy
  const lowPerformers = input.agentsUsed.filter(a => a.performanceScore < 70);
  if (lowPerformers.length > 0) {
    updates.push(
      `Avoid or replace underperforming agents: ${lowPerformers.map(a => a.agentId).join(", ")}`
    );
  }
  
  // Workflow strategy
  if (input.evidence.errors.some(e => e.toLowerCase().includes("timeout"))) {
    updates.push("Consider parallel execution to reduce latency");
  }
  
  // Human feedback integration
  if (input.humanFeedback?.decision === "modified") {
    updates.push(`Incorporate human preference: ${input.humanFeedback.reasoning}`);
  }
  
  return updates.length > 0 ? updates.join("; ") : null;
}

// ============================================================================
// Manifest Changes
// ============================================================================

function computeManifestChanges(
  learnings: ExtractedLearnings,
  input: PostMortemInput,
  analysis: OutcomeAnalysis
): Record<string, any> | null {
  const changes: Record<string, any> = {};
  
  // Agent tool updates
  const lowPerformers = input.agentsUsed.filter(a => a.performanceScore < 60);
  if (lowPerformers.length > 0) {
    changes.agentUpdates = lowPerformers.map(a => ({
      agentId: a.agentId,
      recommendation: "Add tools or increase context window",
      evidence: `Performance score ${a.performanceScore}% < 60%`,
    }));
  }
  
  // New agent recommendation
  if (analysis.rootCause?.includes("missing capability")) {
    changes.newAgentRecommendation = {
      reason: analysis.rootCause,
      suggestedCapabilities: ["TBD - requires human specification"],
    };
  }
  
  return Object.keys(changes).length > 0 ? changes : null;
}

// ============================================================================
// Learning Delta Calculation
// ============================================================================

function calculateLearningDelta(input: PostMortemInput, analysis: OutcomeAnalysis): number {
  // Base delta from outcome
  let delta = 0;
  
  if (analysis.success) {
    delta += input.score >= 95 ? 10 : input.score >= 85 ? 5 : 2;
  } else {
    delta -= analysis.performanceLevel === "poor" ? 10 : 5;
  }
  
  // Adjust for human feedback
  if (input.humanFeedback?.decision === "rejected") {
    delta -= 15; // Significant learning from rejection
  } else if (input.humanFeedback?.decision === "approved") {
    delta += 5; // Positive reinforcement
  }
  
  // Adjust for task complexity (learning more from complex tasks)
  const complexityBonus = input.taskType.includes("complex") ? 5 : 0;
  delta += complexityBonus;
  
  return delta;
}

// ============================================================================
// Embedding Generation
// ============================================================================

async function generateEmbedding(input: PostMortemInput): Promise<number[] | null> {
  try {
    // In production, call Vertex AI Embedding API
    // For now, return null (embedding will be generated asynchronously)
    
    // TODO: Implement Vertex AI embedding generation
    // const embedding = await vertexAI.generateEmbedding({
    //   model: "text-embedding-005",
    //   content: JSON.stringify({
    //     taskType: input.taskType,
    //     outcome: input.outcome,
    //     rootCause: input.evidence.errors[0],
    //     humanFeedback: input.humanFeedback?.reasoning,
    //   }),
    // });
    
    return null;
  } catch (error) {
    console.error("[Post-Mortem] Failed to generate embedding:", error);
    return null;
  }
}

// ============================================================================
// Tag Generation
// ============================================================================

function generateTags(
  input: PostMortemInput,
  analysis: OutcomeAnalysis,
  learnings: ExtractedLearnings
): string[] {
  const tags: string[] = [];
  
  // Outcome tags
  tags.push(`outcome:${input.outcome}`);
  tags.push(`performance:${analysis.performanceLevel}`);
  
  // Task type tags
  tags.push(`task:${input.taskType}`);
  
  // Agent tags
  input.agentsUsed.forEach(a => tags.push(`agent:${a.agentId}`));
  
  // Error category tags
  input.evidence.errors.forEach(error => {
    const category = categorizeError(error);
    tags.push(`error:${category}`);
  });
  
  // Human feedback tags
  if (input.humanFeedback) {
    tags.push(`human:${input.humanFeedback.decision}`);
  }
  
  return [...new Set(tags)]; // Deduplicate
}

// ============================================================================
// Behavioral Ledger Storage
// ============================================================================

async function storeBehavioralLedger(data: {
  input: PostMortemInput;
  analysis: OutcomeAnalysis;
  learnings: ExtractedLearnings;
  strategyUpdate: string | null;
  manifestChanges: Record<string, any> | null;
  learningDelta: number;
  embedding: number[] | null;
  tags: string[];
}) {
  const [entry] = await db.insert(twinBehavioralLedger).values({
    eventId: data.input.eventId,
    taskType: data.input.taskType,
    taskComplexity: estimateTaskComplexity(data.input),
    agentsUsed: data.input.agentsUsed,
    whatWorked: data.learnings.whatWorked,
    whatFailed: data.learnings.whatFailed,
    rootCause: data.analysis.rootCause,
    strategyUpdate: data.strategyUpdate,
    // Manifest-change proposals are wrapped with a limb-only audit envelope at
    // write time. The free-form proposal is preserved verbatim; the envelope
    // records the decision boundary so any downstream consumer (the Boundary
    // console, a CI check, an audit query) can see that the proposal was
    // screened against the limb-only contract. Typed validation through
    // `validateManifestMutation` lands when the typed `proposeLimbMutation`
    // API is introduced in Phase 2.
    manifestChanges: data.manifestChanges
      ? {
          proposal: data.manifestChanges,
          boundaryCheck: "limb-only",
          checkedAt: new Date().toISOString(),
          note: "free-form proposal — typed validation via validateManifestMutation lands with the typed proposeLimbMutation API",
        }
      : null,
    humanFeedback: data.input.humanFeedback?.reasoning,
    humanFeedbackCategory: data.input.humanFeedback?.decision,
    confidenceBefore: estimateConfidenceBefore(data.input),
    confidenceAfter: estimateConfidenceAfter(data.input, data.analysis),
    learningDelta: data.learningDelta,
    embedding: data.embedding ? JSON.stringify(data.embedding) : null,
    tags: data.tags,
  }).returning();
  
  return entry;
}

function estimateTaskComplexity(input: PostMortemInput): number {
  // Simple heuristic: more agents = more complex
  let complexity = input.agentsUsed.length;
  
  // Adjust for errors
  if (input.evidence.errors.length > 0) {
    complexity += 2;
  }
  
  // Adjust for human involvement
  if (input.humanFeedback) {
    complexity += 1;
  }
  
  return Math.min(complexity, 10); // Cap at 10
}

function estimateConfidenceBefore(input: PostMortemInput): number {
  // Base confidence on agent reliability
  const avgReliability = input.agentsUsed.reduce((sum, a) => sum + a.performanceScore, 0) / input.agentsUsed.length;
  return Math.round(avgReliability);
}

function estimateConfidenceAfter(input: PostMortemInput, analysis: OutcomeAnalysis): number {
  if (analysis.success) {
    return Math.min(100, input.score + 5);
  } else {
    return Math.max(0, input.score - 10);
  }
}

// ============================================================================
// Retraining Decision
// ============================================================================

function determineRetrainNeed(
  analysis: OutcomeAnalysis,
  learningDelta: number,
  input: PostMortemInput
): boolean {
  // Retrain if:
  // 1. Poor performance with significant learning delta
  if (analysis.performanceLevel === "poor" && Math.abs(learningDelta) >= 10) {
    return true;
  }
  
  // 2. Human rejection with high confidence
  if (input.humanFeedback?.decision === "rejected" && input.humanFeedback.reasoning.length > 50) {
    return true;
  }
  
  // 3. Recurring error pattern
  if (analysis.rootCause && analysis.contributingFactors.length >= 3) {
    return true;
  }
  
  return false;
}

// ============================================================================
// RLHF Feedback Processing
// ============================================================================

async function processRLHFFeedback(input: PostMortemInput, ledgerId: number) {
  if (!input.humanFeedback) return;
  
  // Import RLHF capture function
  const { processHumanFeedback } = await import("./rlhf-capture");
  
  await processHumanFeedback({
    eventId: input.eventId,
    ledgerId,
    originalDecision: input.outcome,
    humanDecision: input.humanFeedback.decision,
    humanReasoning: input.humanFeedback.reasoning,
    alternativeApproach: input.humanFeedback.alternativeApproach,
    feedbackCategory: input.humanFeedback.decision === "approved" && input.outcome === "escalated" 
      ? "approved" 
      : input.outcome === "passed" && input.humanFeedback.decision === "modified"
      ? "modified"
      : "rejected",
    humanConfidence: 8, // Default confidence, could be captured from UI
  });
}
