/**
 * Predictive Delta Compression (PDC) — brain-inspired chat compression types.
 * Maps Jancke lab primary visual cortex principles to conversation state.
 */

export type ChatRole = 'user' | 'assistant';

export interface ChatTurn {
  role: ChatRole;
  content: string;
  timestamp?: string;
}

/** Predictive state maintained across the session (long-interval baseline). */
export interface SessionBaseline {
  topics: string[];
  decisions: string[];
  openTasks: string[];
  entities: string[];
  summaryVersion: number;
  narrativeSummary?: string;
  updatedAt?: string;
}

/** Structured delta vs baseline for a cold/warm turn (error signal, not full state). */
export interface TurnDelta {
  turnIndex: number;
  role: ChatRole;
  newFacts: string[];
  changedFacts: string[];
  resolvedTasks: string[];
  strippedRedundant: string[];
  timestamp?: string;
}

/** Full compressed conversation bundle passed through PromptContext. */
export interface ConversationCompression {
  baseline: SessionBaseline;
  hotWindow: ChatTurn[];
  deltas: TurnDelta[];
  tokenBudget: number;
  /** Number of recent turns kept at full fidelity (default 3). */
  hotWindowTurns?: number;
}

export interface RehydratedConversation {
  /** Text block injected into the user prompt or first user message. */
  conversationBlock: string;
  /** Hot-window turns as structured messages for multi-turn LLM calls. */
  hotMessages: ChatTurn[];
  estimatedTokens: number;
}

export interface CompressionConfig {
  tokenBudget: number;
  hotWindowTurns: number;
  maxDeltas: number;
}

export const DEFAULT_COMPRESSION_CONFIG: CompressionConfig = {
  tokenBudget: 2000,
  hotWindowTurns: 3,
  maxDeltas: 12,
};
