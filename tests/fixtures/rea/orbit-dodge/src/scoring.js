// Scoring: dodging an asteroid inside the combo window grows the multiplier.
// This is the routine a reverse-engineering pass has to recover exactly.
import { CONFIG } from "./config.js";

export function comboMultiplier(combo) {
  const capped = Math.min(combo, CONFIG.maxCombo);
  return 1 + capped * CONFIG.comboStep;
}

export function createScoreState() {
  return { points: 0, combo: 0, lastDodgeMs: 0, multiplier: 1, dodged: 0 };
}

/**
 * Award one dodge.
 * `nowMs` is the game clock; a dodge beyond CONFIG.comboWindowMs resets the
 * combo to 1 before the multiplier is applied.
 */
export function awardDodge(state, nowMs) {
  const elapsed = nowMs - state.lastDodgeMs;
  if (state.dodged === 0 || elapsed > CONFIG.comboWindowMs) {
    state.combo = 1;
  } else {
    state.combo = Math.min(state.combo + 1, CONFIG.maxCombo + 1);
  }
  state.lastDodgeMs = nowMs;
  state.dodged += 1;
  state.multiplier = comboMultiplier(state.combo);
  const gained = Math.round(10 * state.multiplier);
  state.points += gained;
  return gained;
}

export function penalty(state) {
  state.combo = 0;
  state.multiplier = 1;
  state.points = Math.max(0, state.points - 25);
  return state.points;
}

export function finalScore(state) {
  return Math.round(state.points * (1 + state.dodged / 100));
}
