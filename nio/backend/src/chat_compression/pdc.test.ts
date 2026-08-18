import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { emptyBaseline, mergeDeltaIntoBaseline } from './baseline_store';
import { encodeDelta, stripFiller, suppressRedundant } from './delta_encoder';
import { compressSession, shouldCompress } from './compression_trigger';
import { estimateTokens, rehydrateConversation } from './rehydrator';
import type { ChatTurn } from './types';

describe('PDC delta encoder', () => {
  it('strips conversational filler', () => {
    const cleaned = stripFiller('Um, please fix the bug okay thanks');
    assert.ok(!cleaned.toLowerCase().includes('um'));
    assert.ok(cleaned.includes('fix'));
  });

  it('encodes new facts vs baseline', () => {
    const baseline = emptyBaseline();
    const turn: ChatTurn = { role: 'user', content: 'We decided to use Redis for caching.' };
    const delta = encodeDelta(turn, baseline, 0);
    assert.ok(delta.newFacts.length > 0);
    assert.equal(delta.role, 'user');
  });

  it('suppresses redundant sentences already in baseline', () => {
    const baseline = {
      ...emptyBaseline(),
      topics: ['Use Redis for caching'],
    };
    const kept = suppressRedundant('Use Redis for caching. Also add rate limiting.', baseline);
    assert.ok(kept.some((s) => /rate limiting/i.test(s)));
  });
});

describe('PDC baseline store', () => {
  it('merges delta into baseline and bumps version', () => {
    const baseline = emptyBaseline();
    const delta = {
      turnIndex: 0,
      role: 'user' as const,
      newFacts: ['Need to implement PDC module'],
      changedFacts: [],
      resolvedTasks: [],
      strippedRedundant: [],
    };
    const updated = mergeDeltaIntoBaseline(baseline, delta);
    assert.ok(updated.openTasks.length > 0 || updated.topics.length > 0);
    assert.equal(updated.summaryVersion, baseline.summaryVersion + 1);
  });
});

describe('PDC compression trigger', () => {
  const longMessages: ChatTurn[] = Array.from({ length: 12 }, (_, i) => ({
    role: i % 2 === 0 ? 'user' : 'assistant',
    content: `Turn ${i}: ${'word '.repeat(80)}`,
  }));

  it('triggers compression when over token budget', () => {
    assert.ok(shouldCompress(longMessages, { tokenBudget: 500, hotWindowTurns: 3, maxDeltas: 12 }));
  });

  it('compresses cold turns while preserving hot window', () => {
    const result = compressSession(longMessages, undefined, undefined, {
      tokenBudget: 800,
      hotWindowTurns: 2,
      maxDeltas: 12,
    });
    assert.ok(result.hotWindow.length <= 4);
    assert.ok(result.deltas.length > 0);
    assert.ok(result.baseline.summaryVersion >= 0);
  });
});

describe('PDC rehydrator', () => {
  it('rehydrates within token budget', () => {
    const messages: ChatTurn[] = [
      { role: 'user', content: 'Build chat compression for NIO.' },
      { role: 'assistant', content: 'I will implement PDC with baseline and deltas.' },
      { role: 'user', content: 'Add unit tests too.' },
    ];
    const compressed = compressSession(messages, undefined, undefined, {
      tokenBudget: 1500,
      hotWindowTurns: 2,
      maxDeltas: 12,
    });
    const rehydrated = rehydrateConversation(compressed);
    assert.ok(rehydrated.conversationBlock.includes('Session baseline'));
    assert.ok(rehydrated.estimatedTokens <= estimateTokens(rehydrated.conversationBlock) + 1);
  });

  it('achieves smaller payload than full history for long sessions', () => {
    const messages: ChatTurn[] = Array.from({ length: 40 }, (_, i) => ({
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `Message ${i}: discussing architecture and implementation details repeatedly.`,
    }));
    const rawTokens = estimateTokens(messages.map((m) => m.content).join('\n'));
    const compressed = compressSession(messages, undefined, undefined, {
      tokenBudget: 600,
      hotWindowTurns: 3,
      maxDeltas: 6,
    });
    const rehydrated = rehydrateConversation(compressed);
    assert.ok(
      rehydrated.estimatedTokens < rawTokens,
      `expected ${rehydrated.estimatedTokens} < ${rawTokens}`,
    );
    assert.ok(rehydrated.estimatedTokens <= 600 + 50);
  });
});
