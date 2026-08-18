/**
 * PLANNING WITH MEMORY
 * 
 * Implements reflection-driven planning by querying the behavioral ledger
 * before creating execution plans. The Twin learns from past similar tasks.
 */

import { db } from "@/db";
import { twinBehavioralLedger, orchestratorMemoryEvents } from "@/db/schema";
import { desc, and, sql, eq, inArray } from "drizzle-orm";

// ============================================================================
// Type Definitions
// ============================================================================

export interface PlanningContext {
  taskType: string;
  taskDescription: string;
  constraints: string[];
  availableAgents: Agent[];
  priority?: "low" | "medium" | "high" | "critical";
}

export interface Agent {
  agentId: string;
  role: string;
  capabilities: string[];
  currentLoad: number; // 0-100
  reliability: number; // 0-100
}

export interface MemoryInsight {
  eventId: number;
  taskType: string;
  outcome: string;
  score: number;
  whatWorked: string[];
  whatFailed: string[];
  rootCause: string | null;
  strategyUpdate: string | null;
  similarity: number;
}

export interface AgentPerformanceHistory {
  agentId: string;
  tasksCompleted: number;
  successRate: number;
  averageScore: number;
  averageExecutionTimeMs: number;
  commonFailureModes: string[];
  recommendedForTaskTypes: string[];
}

export interface MemoryAugmentedPlan {
  plan: ExecutionPlan;
  memoryInsights: MemoryInsight[];
  strategyChanges: string[];
  confidenceScore: number;
  warnings: string[];
  optimalAgents: string[];
}

export interface ExecutionPlan {
  taskId: string;
  taskType: string;
  phases: PlanPhase[];
  assignedAgents: Array<{
    agentId: string;
    phase: string;
    role: string;
  }>;
  estimatedDurationMs: number;
  riskLevel: "low" | "medium" | "high";
}

export interface PlanPhase {
  phase: string;
  description: string;
  expectedOutcome: string;
  successCriteria: string[];
  fallbackStrategy?: string;
}

// ============================================================================
// Main Planning Function
// ============================================================================

/**
 * Generate execution plan augmented with historical memory.
 * This is the core of reflection-driven planning.
 */
export async function planWithMemory(context: PlanningContext): Promise<MemoryAugmentedPlan> {
  console.log(`[Planning] Starting reflection-driven planning for task type: ${context.taskType}`);
  
  // Step 1: Retrieve similar past tasks from behavioral ledger
  const similarTasks = await retrieveSimilarTasks({
    taskType: context.taskType,
    taskDescription: context.taskDescription,
    limit: 5,
  });
  console.log(`[Planning] Retrieved ${similarTasks.length} similar tasks from memory`);
  
  // Step 2: Analyze patterns from similar tasks
  const patterns = analyzePatterns(similarTasks);
  console.log(`[Planning] Pattern analysis: ${patterns.successRate}% success rate`);
  
  // Step 3: Get agent performance history
  const agentPerformance = await getAgentPerformanceHistory({
    agents: context.availableAgents,
    taskType: context.taskType,
  });
  
  // Step 4: Compute optimal agent selection
  const optimalAgents = computeOptimalAgents({
    availableAgents: context.availableAgents,
    historicalPerformance: agentPerformance,
    taskConstraints: context.constraints,
    patterns: patterns,
  });
  console.log(`[Planning] Optimal agents: ${optimalAgents.join(", ")}`);
  
  // Step 5: Generate plan with learned strategies
  const plan = generatePlan({
    context,
    optimalAgents,
    successfulStrategies: patterns.whatWorked,
    avoidStrategies: patterns.whatFailed,
  });
  
  // Step 6: Calculate confidence score
  const confidenceScore = calculateConfidence({
    similarTasksSuccessRate: patterns.successRate,
    agentReliability: computeAgentReliability(agentPerformance, optimalAgents),
    taskComplexity: context.constraints.length,
    priority: context.priority || "medium",
  });
  console.log(`[Planning] Confidence score: ${confidenceScore}%`);
  
  // Step 7: Generate warnings based on past failures
  const warnings = generateWarnings({
    pastFailures: patterns.whatFailed,
    currentPlan: plan,
    agentPerformance,
  });
  
  // Step 8: Extract strategy changes from memory
  const strategyChanges = extractStrategyChanges(similarTasks);
  
  return {
    plan,
    memoryInsights: similarTasks,
    strategyChanges,
    confidenceScore,
    warnings,
    optimalAgents,
  };
}

// ============================================================================
// Memory Retrieval
// ============================================================================

/**
 * Retrieve similar past tasks from behavioral ledger.
 * Uses both exact matching (task type) and semantic similarity (embeddings).
 */
export async function retrieveSimilarTasks(params: {
  taskType: string;
  taskDescription: string;
  limit: number;
}): Promise<MemoryInsight[]> {
  // Step 1: Get events with exact task type match
  const exactMatches = await db.select({
    eventId: twinBehavioralLedger.eventId,
    taskType: twinBehavioralLedger.taskType,
    outcome: orchestratorMemoryEvents.outcome,
    score: orchestratorMemoryEvents.score,
    whatWorked: twinBehavioralLedger.whatWorked,
    whatFailed: twinBehavioralLedger.whatFailed,
    rootCause: twinBehavioralLedger.rootCause,
    strategyUpdate: twinBehavioralLedger.strategyUpdate,
    createdAt: twinBehavioralLedger.createdAt,
  })
  .from(twinBehavioralLedger)
  .leftJoin(orchestratorMemoryEvents, eq(twinBehavioralLedger.eventId, orchestratorMemoryEvents.id))
  .where(eq(twinBehavioralLedger.taskType, params.taskType))
  .orderBy(desc(twinBehavioralLedger.createdAt))
  .limit(params.limit);
  
  // Step 2: If not enough exact matches, get related task types
  let allMatches = exactMatches;
  if (exactMatches.length < params.limit) {
    const relatedMatches = await db.select({
      eventId: twinBehavioralLedger.eventId,
      taskType: twinBehavioralLedger.taskType,
      outcome: orchestratorMemoryEvents.outcome,
      score: orchestratorMemoryEvents.score,
      whatWorked: twinBehavioralLedger.whatWorked,
      whatFailed: twinBehavioralLedger.whatFailed,
      rootCause: twinBehavioralLedger.rootCause,
      strategyUpdate: twinBehavioralLedger.strategyUpdate,
      createdAt: twinBehavioralLedger.createdAt,
    })
    .from(twinBehavioralLedger)
    .leftJoin(orchestratorMemoryEvents, eq(twinBehavioralLedger.eventId, orchestratorMemoryEvents.id))
    .where(sql`1=1`) // Placeholder - in production, use embedding similarity here
    .orderBy(desc(twinBehavioralLedger.createdAt))
    .limit(params.limit - exactMatches.length);
    
    allMatches = [...exactMatches, ...relatedMatches];
  }
  
  // Step 3: Transform to MemoryInsight format
  return allMatches.map(match => ({
    eventId: match.eventId ?? 0,
    taskType: match.taskType,
    outcome: match.outcome ?? "unknown",
    score: match.score ?? 0,
    whatWorked: match.whatWorked ?? [],
    whatFailed: match.whatFailed ?? [],
    rootCause: match.rootCause ?? null,
    strategyUpdate: match.strategyUpdate ?? null,
    similarity: match.taskType === params.taskType ? 1.0 : 0.5, // Placeholder - use embedding similarity in production
  }));
}

// ============================================================================
// Pattern Analysis
// ============================================================================

interface PatternAnalysis {
  successRate: number;
  averageScore: number;
  whatWorked: string[];
  whatFailed: string[];
  commonRootCauses: string[];
  strategyChanges: string[];
}

function analyzePatterns(similarTasks: MemoryInsight[]): PatternAnalysis {
  if (similarTasks.length === 0) {
    return {
      successRate: 0,
      averageScore: 0,
      whatWorked: [],
      whatFailed: [],
      commonRootCauses: [],
      strategyChanges: [],
    };
  }
  
  // Calculate success rate
  const successCount = similarTasks.filter(t => t.outcome === "passed").length;
  const successRate = Math.round((successCount / similarTasks.length) * 100);
  
  // Calculate average score
  const averageScore = Math.round(
    similarTasks.reduce((sum, t) => sum + t.score, 0) / similarTasks.length
  );
  
  // Extract common successful strategies
  const whatWorkedFlat = similarTasks.flatMap(t => t.whatWorked);
  const whatWorked = getMostCommon(whatWorkedFlat, 5);
  
  // Extract common failure modes
  const whatFailedFlat = similarTasks.flatMap(t => t.whatFailed);
  const whatFailed = getMostCommon(whatFailedFlat, 5);
  
  // Extract common root causes
  const rootCauses = similarTasks
    .map(t => t.rootCause)
    .filter((cause): cause is string => cause !== null);
  const commonRootCauses = getMostCommon(rootCauses, 3);
  
  // Extract strategy changes
  const strategyChanges = similarTasks
    .map(t => t.strategyUpdate)
    .filter((update): update is string => update !== null);
  
  return {
    successRate,
    averageScore,
    whatWorked,
    whatFailed,
    commonRootCauses,
    strategyChanges,
  };
}

function getMostCommon(items: string[], limit: number): string[] {
  const frequency: Record<string, number> = {};
  items.forEach(item => {
    frequency[item] = (frequency[item] || 0) + 1;
  });
  
  return Object.entries(frequency)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([item]) => item);
}

// ============================================================================
// Agent Performance History
// ============================================================================

async function getAgentPerformanceHistory(params: {
  agents: Agent[];
  taskType: string;
}): Promise<AgentPerformanceHistory[]> {
  const agentIds = params.agents.map(a => a.agentId);
  
  // Query behavioral ledger for each agent's performance
  const performanceData = await db.select({
    agentsUsed: twinBehavioralLedger.agentsUsed,
    outcome: orchestratorMemoryEvents.outcome,
    score: orchestratorMemoryEvents.score,
  })
  .from(twinBehavioralLedger)
  .leftJoin(orchestratorMemoryEvents, eq(twinBehavioralLedger.eventId, orchestratorMemoryEvents.id))
  .where(sql`1=1`); // In production, filter by task type and use JSON containment for agentsUsed
  
  // Compute performance metrics for each agent
  return params.agents.map(agent => {
    const agentTasks = performanceData.filter(data => {
      const agentsUsed = data.agentsUsed as Array<{ agentId: string }> || [];
      return agentsUsed.some(a => a.agentId === agent.agentId);
    });
    
    const tasksCompleted = agentTasks.length;
    const successCount = agentTasks.filter(t => t.outcome === "passed").length;
    const successRate = tasksCompleted > 0 ? Math.round((successCount / tasksCompleted) * 100) : 0;
    const averageScore = tasksCompleted > 0
      ? Math.round(agentTasks.reduce((sum, t) => sum + (t.score || 0), 0) / tasksCompleted)
      : 0;
    
    // Extract common failure modes
    const failureModes: string[] = [];
    
    return {
      agentId: agent.agentId,
      tasksCompleted,
      successRate,
      averageScore,
      averageExecutionTimeMs: 0, // Would need additional data
      commonFailureModes: failureModes,
      recommendedForTaskTypes: successRate >= 80 ? [params.taskType] : [],
    };
  });
}

// ============================================================================
// Optimal Agent Selection
// ============================================================================

function computeOptimalAgents(params: {
  availableAgents: Agent[];
  historicalPerformance: AgentPerformanceHistory[];
  taskConstraints: string[];
  patterns: PatternAnalysis;
}): string[] {
  // Score each agent based on multiple factors
  const agentScores = params.availableAgents.map(agent => {
    const performance = params.historicalPerformance.find(
      p => p.agentId === agent.agentId
    );
    
    let score = 0;
    
    // Factor 1: Historical success rate (40% weight)
    score += (performance?.successRate || 50) * 0.4;
    
    // Factor 2: Current load (20% weight - lower is better)
    score += (100 - agent.currentLoad) * 0.2;
    
    // Factor 3: Base reliability (20% weight)
    score += agent.reliability * 0.2;
    
    // Factor 4: Task type recommendation (20% weight)
    if (performance?.recommendedForTaskTypes.includes(params.patterns.whatWorked[0] || "")) {
      score += 20;
    }
    
    return {
      agentId: agent.agentId,
      score: Math.round(score),
    };
  });
  
  // Sort by score and select top agents
  const sorted = agentScores.sort((a, b) => b.score - a.score);
  
  // Select top 3 agents (or fewer if not available)
  const selected = sorted.slice(0, Math.min(3, sorted.length));
  
  return selected.map(a => a.agentId);
}

function computeAgentReliability(
  performance: AgentPerformanceHistory[],
  selectedAgents: string[]
): number {
  const selectedPerformance = performance.filter(p =>
    selectedAgents.includes(p.agentId)
  );
  
  if (selectedPerformance.length === 0) {
    return 50;
  }
  
  const avgReliability = selectedPerformance.reduce(
    (sum, p) => sum + p.successRate,
    0
  ) / selectedPerformance.length;
  
  return Math.round(avgReliability);
}

// ============================================================================
// Plan Generation
// ============================================================================

function generatePlan(params: {
  context: PlanningContext;
  optimalAgents: string[];
  successfulStrategies: string[];
  avoidStrategies: string[];
}): ExecutionPlan {
  const taskId = `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  
  // Generate phases based on task type
  const phases: PlanPhase[] = generatePhasesForTaskType(
    params.context.taskType,
    params.successfulStrategies,
    params.avoidStrategies
  );
  
  // Assign agents to phases
  const assignedAgents = phases.map((phase, index) => ({
    agentId: params.optimalAgents[index % params.optimalAgents.length],
    phase: phase.phase,
    role: "executor",
  }));
  
  // Estimate duration
  const estimatedDurationMs = phases.length * 30000; // 30s per phase baseline
  
  // Calculate risk level
  const riskLevel = calculateRiskLevel(params.context, phases);
  
  return {
    taskId,
    taskType: params.context.taskType,
    phases,
    assignedAgents,
    estimatedDurationMs,
    riskLevel,
  };
}

function generatePhasesForTaskType(
  taskType: string,
  successfulStrategies: string[],
  avoidStrategies: string[]
): PlanPhase[] {
  // Default phases for most tasks
  const phases: PlanPhase[] = [
    {
      phase: "planning",
      description: "Analyze task requirements and create execution plan",
      expectedOutcome: "Detailed execution plan with agent assignments",
      successCriteria: ["Plan reviewed and validated", "All constraints addressed"],
    },
    {
      phase: "execution",
      description: "Execute planned tasks with assigned agents",
      expectedOutcome: "Task artifacts and evidence",
      successCriteria: ["All steps completed", "Evidence collected"],
      fallbackStrategy: "Retry with alternative agent if failure",
    },
    {
      phase: "review",
      description: "Review execution results and validate quality",
      expectedOutcome: "Quality assessment and approval",
      successCriteria: ["Quality score >= 85", "No critical issues"],
    },
    {
      phase: "completion",
      description: "Finalize and archive task results",
      expectedOutcome: "Task marked complete with full evidence",
      successCriteria: ["All artifacts archived", "Memory ledger updated"],
    },
  ];
  
  // Adjust phases based on successful strategies
  if (successfulStrategies.some(s => s.includes("parallel"))) {
    phases[1].description += " (parallel execution where possible)";
  }
  
  // Add warnings for strategies to avoid
  if (avoidStrategies.some(s => s.includes("timeout"))) {
    phases[1].fallbackStrategy = "Monitor execution time closely; abort if approaching timeout";
  }
  
  return phases;
}

function calculateRiskLevel(
  context: PlanningContext,
  phases: PlanPhase[]
): "low" | "medium" | "high" {
  let riskScore = 0;
  
  // Factor 1: Number of constraints
  riskScore += context.constraints.length * 10;
  
  // Factor 2: Task priority
  const priorityWeights = { low: 0, medium: 10, high: 20, critical: 30 };
  riskScore += priorityWeights[context.priority || "medium"];
  
  // Factor 3: Number of phases
  riskScore += phases.length * 5;
  
  // Determine risk level
  if (riskScore >= 50) return "high";
  if (riskScore >= 25) return "medium";
  return "low";
}

// ============================================================================
// Confidence Calculation
// ============================================================================

function calculateConfidence(params: {
  similarTasksSuccessRate: number;
  agentReliability: number;
  taskComplexity: number;
  priority: string;
}): number {
  let confidence = 0;
  
  // Factor 1: Historical success rate (50% weight)
  confidence += params.similarTasksSuccessRate * 0.5;
  
  // Factor 2: Agent reliability (30% weight)
  confidence += params.agentReliability * 0.3;
  
  // Factor 3: Task complexity (inverse, 20% weight)
  const complexityFactor = Math.max(0, 100 - params.taskComplexity * 10);
  confidence += complexityFactor * 0.2;
  
  // Adjust for priority (higher priority = more scrutiny = lower confidence)
  const priorityAdjustments: Record<string, number> = {
    low: 5,
    medium: 0,
    high: -5,
    critical: -10,
  };
  confidence += priorityAdjustments[params.priority] || 0;
  
  return Math.round(Math.max(0, Math.min(100, confidence)));
}

// ============================================================================
// Warning Generation
// ============================================================================

function generateWarnings(params: {
  pastFailures: string[];
  currentPlan: ExecutionPlan;
  agentPerformance: AgentPerformanceHistory[];
}): string[] {
  const warnings: string[] = [];
  
  // Warning 1: Recurring failure modes
  params.pastFailures.slice(0, 3).forEach(failure => {
    warnings.push(`Past failure mode: ${failure}`);
  });
  
  // Warning 2: Low-performing agents in plan
  params.currentPlan.assignedAgents.forEach(assignment => {
    const performance = params.agentPerformance.find(
      p => p.agentId === assignment.agentId
    );
    if (performance && performance.successRate < 70) {
      warnings.push(
        `Agent ${assignment.agentId} has ${performance.successRate}% success rate for this task type`
      );
    }
  });
  
  // Warning 3: High risk level
  if (params.currentPlan.riskLevel === "high") {
    warnings.push("High risk task - consider human review before execution");
  }
  
  return warnings;
}

// ============================================================================
// Strategy Extraction
// ============================================================================

function extractStrategyChanges(similarTasks: MemoryInsight[]): string[] {
  const changes = similarTasks
    .map(t => t.strategyUpdate)
    .filter((update): update is string => update !== null);
  
  return [...new Set(changes)]; // Deduplicate
}
