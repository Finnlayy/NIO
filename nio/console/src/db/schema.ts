import { integer, jsonb, pgTable, serial, text, timestamp, varchar } from "drizzle-orm/pg-core";

/**
 * Immutable evidence emitted by the Autonomous Orchestrator evaluation loop.
 * The table is intentionally small and portable: a future vector-store adapter can
 * embed the `notes` payload while this table remains the system-of-record ledger.
 */
export const orchestratorMemoryEvents = pgTable("orchestrator_memory_events", {
  id: serial("id").primaryKey(),
  agentId: varchar("agent_id", { length: 80 }).notNull(),
  workflowState: varchar("workflow_state", { length: 40 }).notNull(),
  outcome: varchar("outcome", { length: 24 }).notNull(),
  score: integer("score").notNull(),
  notes: text("notes").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

/**
 * AUTODIDACTIC EXTENSION: Behavioral Ledger for the Virtual Human Twin.
 * Stores post-mortem analysis, learnings, strategy updates, and human feedback.
 * Enables the Twin to learn from every task and optimize future performance.
 */
export const twinBehavioralLedger = pgTable("twin_behavioral_ledger", {
  id: serial("id").primaryKey(),
  
  // Correlation id to the originating memory event. Not a hard FK: ledger
  // rows can be written by flows that run before, after, or without a parent
  // memory event, so referential integrity is enforced at the application
  // layer rather than by the database.
  eventId: integer("event_id"),
  
  // Task metadata
  taskType: varchar("task_type", { length: 120 }).notNull(),
  taskComplexity: integer("task_complexity").notNull(), // 1-10 scale
  agentsUsed: jsonb("agents_used").notNull(), // [{agent_id, role, performance_score}]
  
  // Reflection analysis
  whatWorked: text("what_worked").array(),
  whatFailed: text("what_failed").array(),
  rootCause: text("root_cause"),
  
  // Learning outcomes
  strategyUpdate: text("strategy_update"),
  manifestChanges: jsonb("manifest_changes"),
  humanFeedback: text("human_feedback"),
  humanFeedbackCategory: varchar("human_feedback_category", { length: 40 }),
  
  // Meta-learning metrics
  confidenceBefore: integer("confidence_before"), // 0-100
  confidenceAfter: integer("confidence_after"), // 0-100
  learningDelta: integer("learning_delta"), // confidence_after - confidence_before
  
  // Phase 1 stores the embedding as JSON-serialized floats so the schema
  // can be pushed without the pgvector extension. Phase 2 swaps this for a
  // real `vector(768)` column once `CREATE EXTENSION vector` is enabled on
  // Cloud SQL and the local dev Postgres image ships pgvector.
  embedding: text("embedding"),
  
  // Tags for fast filtering
  tags: text("tags").array(),
  
  // Timestamps
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

/**
 * MANIFEST VERSIONING: Track all changes to the agent registry.
 * Enables rollback and audit of self-modifications.
 */
export const agentManifestVersions = pgTable("agent_manifest_versions", {
  id: serial("id").primaryKey(),
  version: varchar("version", { length: 40 }).notNull().unique(),
  previousVersion: varchar("previous_version", { length: 40 }),
  
  // The manifest content
  manifest: jsonb("manifest").notNull(),
  
  // Change metadata
  changeReason: text("change_reason").notNull(),
  evidenceEventIds: integer("evidence_event_ids").array(), // References to behavioral ledger
  
  // Approval workflow
  requiresHumanApproval: varchar("requires_human_approval", { length: 20 }).notNull(), // 'pending', 'approved', 'rejected', 'not_required'
  approvedBy: varchar("approved_by", { length: 80 }),
  approvedAt: timestamp("approved_at", { withTimezone: true }),
  rejectionReason: text("rejection_reason"),
  
  // Safety validation
  safetyValidationPassed: varchar("safety_validation_passed", { length: 20 }).notNull(), // 'passed', 'failed', 'pending'
  safetyViolations: text("safety_violations").array(),
  
  // Metadata
  createdBy: varchar("created_by", { length: 80 }).notNull(), // 'twin' or 'human'
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

/**
 * RLHF SAMPLES: Store human feedback for preference learning.
 * Used to train the Twin's preference model.
 */
export const rlhfSamples = pgTable("rlhf_samples", {
  id: serial("id").primaryKey(),
  
  // See twinBehavioralLedger.eventId for why this is a correlation id and not
  // a hard foreign key.
  eventId: integer("event_id"),
  
  // Feedback content
  originalDecision: text("original_decision").notNull(),
  humanDecision: text("human_decision").notNull(),
  humanReasoning: text("human_reasoning").notNull(),
  alternativeApproach: text("alternative_approach"),
  feedbackCategory: varchar("feedback_category", { length: 40 }).notNull(),
  humanConfidence: integer("human_confidence"), // 1-10
  
  // Learning artifacts
  // See comment on twinBehavioralLedger.embedding for the Phase 2 pgvector swap.
  preferenceEmbedding: text("preference_embedding"),
  patternIdentified: text("pattern_identified"),
  ruleUpdate: text("rule_update"),
  shouldRetrain: varchar("should_retrain", { length: 20 }).notNull(), // 'true', 'false'
  
  // Model update tracking
  appliedToModel: varchar("applied_to_model", { length: 20 }).notNull(), // 'pending', 'applied', 'deferred'
  appliedAt: timestamp("applied_at", { withTimezone: true }),
  
  // Metadata
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

/**
 * SELF-MODEL SNAPSHOTS: Periodic snapshots of the Twin's self-assessment.
 * Used for tracking learning trajectory and generating insights.
 */
export const selfModelSnapshots = pgTable("self_model_snapshots", {
  id: serial("id").primaryKey(),
  
  // Snapshot metadata
  snapshotDate: timestamp("snapshot_date", { withTimezone: true }).notNull(),
  
  // Performance metrics
  overallSuccessRate: varchar("overall_success_rate", { length: 10 }).notNull(), // Stored as string for precision
  totalTasksCompleted: integer("total_tasks_completed").notNull(),
  totalLearningEvents: integer("total_learning_events").notNull(),
  
  // Agent performance
  agentPerformance: jsonb("agent_performance").notNull(), // [{agent_id, success_rate, avg_score, tasks_completed}]
  
  // Task type performance
  taskTypePerformance: jsonb("task_type_performance").notNull(), // [{task_type, success_rate, avg_score}]
  
  // Human alignment
  humanAlignmentScore: varchar("human_alignment_score", { length: 10 }).notNull(),
  
  // Top learnings
  topLearnings: jsonb("top_learnings").notNull(), // [{insight, impact, applied_at}]
  
  // Learning trajectory
  learningTrajectory: jsonb("learning_trajectory").notNull(), // [{date, success_rate, avg_confidence}]
  
  // Metadata
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});
