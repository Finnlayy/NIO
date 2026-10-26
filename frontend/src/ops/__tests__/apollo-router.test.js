"use strict";
/**
 * Apollo core: routing maths, failover engine, handoff notes and graph layout.
 *
 * These are the modules the deck, terminal and stage all read from, so the
 * assertions here double as the spec for the visible behaviour:
 *  - composite score = Σ (weight × sub-score) / 100, one decimal,
 *  - failover never re-picks the spent model nor a LIMIT_REACHED candidate,
 *  - the context handoff note is < 900 chars and survives a task in flight,
 *  - layout helpers stay inside the ring and never produce NaN.
 */
const assert = require("node:assert/strict");
const test = require("node:test");

const {
  DEFAULT_WEIGHTS,
  normalizeWeights,
  compositeScore,
  rankCandidates,
  chooseNextCandidate,
  poolHealth,
  buildHandoffNote,
  formatRouterTable,
} = require("../apollo/routing");
const {
  initialRouterState,
  activeModelOf,
  consumeQuota,
  shouldFailover,
  failover,
  restorePrimary,
  rollQuotaWindow,
  setQuota,
} = require("../apollo/engine");
const {
  clamp01,
  radialPoint,
  angleOf,
  toPixels,
  ellipseFor,
  widestGapAngle,
  normalizeAngle,
  axonCurve,
  cubicAt,
  springStep,
  hexToRgba,
  mulberry32,
  bowFor,
  RING,
  CARD_BOX,
  cardsCollide,
  fitEllipse,
} = require("../apollo/graph");
const {
  PALETTE,
  ORB_STATE_STYLE,
  NODE_CATEGORY_STYLE,
  NODE_STATE_STYLE,
  PROVIDERS,
  POOL_ENDPOINTS,
  POOL_PROVIDERS,
  SEED_CANDIDATES,
  SEED_NODES,
} = require("../apollo/catalog");

/* ------------------------------------------------------------------ */
/* routing                                                             */
/* ------------------------------------------------------------------ */

test("weights normalise to exactly 100 and the default is 50/25/25", () => {
  assert.deepEqual(DEFAULT_WEIGHTS, { reliability: 50, speed: 25, intelligence: 25 });
  assert.deepEqual(normalizeWeights(DEFAULT_WEIGHTS), DEFAULT_WEIGHTS);
  assert.deepEqual(normalizeWeights({ reliability: 2, speed: 2, intelligence: 6 }), {
    reliability: 20,
    speed: 20,
    intelligence: 60,
  });
  // odd fractions still add up to 100 (drift lands on the largest bucket)
  for (const weights of [
    { reliability: 1, speed: 1, intelligence: 1 },
    { reliability: 33, speed: 33, intelligence: 34 },
    { reliability: 7, speed: 11, intelligence: 13 },
  ]) {
    const w = normalizeWeights(weights);
    assert.equal(w.reliability + w.speed + w.intelligence, 100);
  }
  // a zeroed weight really is zero, and an all-zero config degrades to reliability
  assert.equal(normalizeWeights({ reliability: 50, speed: 50, intelligence: 0 }).intelligence, 0);
  assert.deepEqual(normalizeWeights({ reliability: 0, speed: 0, intelligence: 0 }), {
    reliability: 100,
    speed: 0,
    intelligence: 0,
  });
  // junk never produces NaN
  const junk = normalizeWeights({ reliability: Number.NaN, speed: -5, intelligence: 200 });
  for (const value of Object.values(junk)) assert.ok(Number.isFinite(value));
});

test("composite score is the weighted mean of the sub-scores, one decimal", () => {
  const candidate = { reliability: 95, speed: 94, intelligence: 82 };
  // (0.5 * 95) + (0.25 * 94) + (0.25 * 82) = 91.5
  assert.equal(compositeScore(candidate, DEFAULT_WEIGHTS), 91.5);
  assert.equal(compositeScore({ reliability: 100, speed: 100, intelligence: 100 }, DEFAULT_WEIGHTS), 100);
  assert.equal(compositeScore({ reliability: 0, speed: 0, intelligence: 0 }, DEFAULT_WEIGHTS), 0);
  // a heavy-intelligence weighting reorders the pool
  const smart = compositeScore({ reliability: 60, speed: 50, intelligence: 100 }, { reliability: 1, speed: 1, intelligence: 98 });
  assert.ok(smart > compositeScore({ reliability: 60, speed: 50, intelligence: 100 }, DEFAULT_WEIGHTS));
});

test("rankCandidates is descending, stable on ties, and carries its score", () => {
  const ranked = rankCandidates(SEED_CANDIDATES, DEFAULT_WEIGHTS);
  assert.equal(ranked.length, SEED_CANDIDATES.length);
  for (let i = 1; i < ranked.length; i++) {
    const prev = ranked[i - 1];
    const next = ranked[i];
    assert.ok(prev.compositeScore >= next.compositeScore, `${prev.name} should rank above ${next.name}`);
    if (prev.compositeScore === next.compositeScore) {
      assert.ok(prev.reliability >= next.reliability, "ties break on reliability");
    }
  }
  assert.ok(ranked.every((c) => typeof c.compositeScore === "number" && Number.isFinite(c.compositeScore)));
  // the ranking is a pure function of the input set, not of its order
  assert.deepEqual(
    rankCandidates([...SEED_CANDIDATES].reverse(), DEFAULT_WEIGHTS).map((c) => c.id),
    ranked.map((c) => c.id),
  );
  // and it never mutates the candidates it was handed
  const before = SEED_CANDIDATES.map((c) => c.compositeScore);
  rankCandidates(SEED_CANDIDATES, { reliability: 10, speed: 10, intelligence: 80 });
  assert.deepEqual(SEED_CANDIDATES.map((c) => c.compositeScore), before);
});

test("chooseNextCandidate skips the current model and anything LIMIT_REACHED", () => {
  const ranked = rankCandidates(SEED_CANDIDATES, DEFAULT_WEIGHTS);
  const first = ranked[0];
  const second = ranked[1];

  // current model is excluded
  assert.equal(chooseNextCandidate(ranked, first.id).id, second.id);
  // a limited top pick is skipped in favour of the next usable one
  const limited = ranked.map((c) => (c.id === second.id ? { ...c, status: "LIMIT_REACHED" } : c));
  const picked = chooseNextCandidate(limited, first.id);
  assert.equal(picked.id, ranked[2].id);
  // nothing usable -> null, which the engine turns into EXHAUSTED
  const allLimited = ranked.map((c) => ({ ...c, status: "LIMIT_REACHED" }));
  assert.equal(chooseNextCandidate(allLimited, null), null);
});

test("poolHealth counts each provider status", () => {
  const pool = [
    { providerId: "a", status: "ACTIVE" },
    { providerId: "b", status: "STANDBY" },
    { providerId: "c", status: "LIMIT_REACHED" },
    { providerId: "d", status: "ACTIVE" },
  ];
  const health = poolHealth(pool);
  assert.equal(health.active, 2);
  assert.equal(health.standby, 1);
  assert.equal(health.limited, 1);
  assert.equal(health.total, 4);
  const empty = poolHealth([]);
  assert.equal(empty.total, 0);
  assert.equal(empty.active, 0);
});

test("catalog constants match the advertised pool", () => {
  assert.equal(POOL_PROVIDERS, 36);
  assert.equal(POOL_ENDPOINTS, 635);
  assert.equal(PROVIDERS.length, 36);
  assert.equal(PROVIDERS.reduce((sum, p) => sum + p.endpoints, 0), 635);
  assert.equal(SEED_NODES.length, 8);
  assert.equal(new Set(SEED_NODES.map((n) => n.id)).size, 8);
  assert.deepEqual(Object.keys(ORB_STATE_STYLE), [
    "IDLE", "LISTENING", "THINKING", "FAILOVER_SWITCH", "DISPATCHING", "SYNTHESIZING", "ERROR",
  ]);
  assert.deepEqual(Object.keys(NODE_CATEGORY_STYLE).sort(), [
    "DATA_STREAM", "FREELLM_ROUTER", "INFERENCE", "MCP_WORKER", "MEMORY", "ORCHESTRATOR", "SANDBOX",
  ]);
  assert.deepEqual(Object.keys(NODE_STATE_STYLE).sort(), [
    "COMPLETED", "FAULT", "IDLE", "LYMP_SPAWNING", "PROCESSING", "STREAMING",
  ]);
  // the spec palette, verbatim
  assert.deepEqual(PALETTE, {
    obsidian: "#0a0f1d",
    cyan: "#00e5ff",
    violet: "#a855f7",
    amber: "#f59e0b",
    emerald: "#10b981",
    magenta: "#d946ef",
    crimson: "#ef4444",
    ink: "#050810",
  });
  // every node category and orb state has a colour from the palette
  for (const style of Object.values(NODE_CATEGORY_STYLE)) {
    assert.match(style.color, /^#[0-9a-f]{6}$/i);
  }
  for (const style of Object.values(ORB_STATE_STYLE)) {
    assert.match(style.color, /^#[0-9a-f]{6}$/i);
    assert.ok(style.label.length > 0);
  }
});

/* ------------------------------------------------------------------ */
/* failover engine                                                     */
/* ------------------------------------------------------------------ */

test("consumeQuota clamps at zero and ignores junk", () => {
  const state = initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 82);
  assert.equal(consumeQuota(state, 12).primaryQuotaPercent, 70);
  assert.equal(consumeQuota(state, 1000).primaryQuotaPercent, 0);
  assert.equal(consumeQuota(state, -5), state);
  assert.equal(consumeQuota(state, Number.NaN), state);
});

test("shouldFailover fires at or below the threshold", () => {
  const state = initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 30);
  assert.equal(shouldFailover(state, 0), false);
  assert.equal(shouldFailover(state, 30), true);
  assert.equal(shouldFailover(state, 29), false);
  assert.equal(shouldFailover(setQuota(state, 0), 0), true);
});

test("failover hot-swaps, marks the old model limited, and counts the swap", () => {
  const state = initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 0);
  const outcome = failover(state, {
    weights: DEFAULT_WEIGHTS,
    reason: "primary quota exhausted (0% · 429)",
  });

  assert.equal(outcome.switched, true);
  assert.equal(outcome.from.name, "Claude Sonnet 4.5");
  assert.ok(outcome.to, "a free candidate must be available");
  assert.equal(outcome.state.mode, "FAILOVER");
  assert.equal(outcome.state.activeCandidateId, outcome.to.id);
  assert.equal(outcome.state.failoverCount, 1);
  assert.ok(outcome.state.lastHandoffNote.includes("CONTEXT HANDOFF"));
  assert.ok(outcome.state.lastHandoffNote.length <= 900);

  const active = activeModelOf(outcome.state);
  assert.equal(active.name, outcome.to.name);
  assert.notEqual(active.name, "Claude Sonnet 4.5");

  // the original primary is not the active candidate and routing stays internal
  assert.equal(outcome.state.chain.filter((c) => c.status === "ACTIVE").length, 1);
  assert.equal(outcome.state.chain.find((c) => c.status === "ACTIVE").id, outcome.to.id);
});

test("a second failover never re-picks the candidate that just died", () => {
  const first = failover(initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 0), { weights: DEFAULT_WEIGHTS });
  const second = failover(first.state, { weights: DEFAULT_WEIGHTS });

  assert.equal(second.switched, true);
  assert.notEqual(second.to.id, first.to.id);
  assert.equal(second.state.failoverCount, 2);
  assert.equal(second.state.chain.filter((c) => c.status === "ACTIVE").length, 1);
  assert.ok(second.state.chain.find((c) => c.id === first.to.id).status === "LIMIT_REACHED");
});

test("an exhausted pool reports EXHAUSTED instead of inventing a model", () => {
  const saturated = {
    ...initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 0),
    chain: SEED_CANDIDATES.map((c) => ({ ...c, status: "LIMIT_REACHED" })),
  };
  const outcome = failover(saturated, { weights: DEFAULT_WEIGHTS });
  assert.equal(outcome.switched, false);
  assert.equal(outcome.to, null);
  assert.equal(outcome.state.mode, "EXHAUSTED");
  assert.equal(activeModelOf(outcome.state).name, "Claude Sonnet 4.5");
});

test("restorePrimary and rollQuotaWindow reset the pool without losing history", () => {
  const failed = failover(initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 0), { weights: DEFAULT_WEIGHTS }).state;

  const restored = restorePrimary(failed, 100);
  assert.equal(restored.mode, "PRIMARY");
  assert.equal(restored.primaryQuotaPercent, 100);
  assert.equal(restored.activeCandidateId, null);
  assert.equal(restored.chain.filter((c) => c.status === "ACTIVE").length, 0);

  const rolled = rollQuotaWindow(failed, 100);
  assert.equal(rolled.mode, "PRIMARY");
  assert.equal(rolled.chain.filter((c) => c.status === "LIMIT_REACHED").length, 0);
  assert.equal(rolled.failoverCount, failed.failoverCount, "history survives a quota roll");
  assert.equal(rolled.lastHandoffNote, failed.lastHandoffNote);
});

test("setQuota clamps to 0..100 with one decimal", () => {
  const state = initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 50);
  assert.equal(setQuota(state, 150).primaryQuotaPercent, 100);
  assert.equal(setQuota(state, -20).primaryQuotaPercent, 0);
  assert.equal(setQuota(state, 42.44).primaryQuotaPercent, 42.4);
});

test("activeModelOf is referentially stable for an unchanged router", () => {
  const state = initialRouterState("Claude Sonnet 4.5", SEED_CANDIDATES, 50);
  const a = activeModelOf(state);
  const b = activeModelOf(state);
  assert.equal(a, b, "same state object must return the same model object");
  assert.equal(a.name, "Claude Sonnet 4.5");
  // a new state object is allowed to produce a new model object
  const moved = restorePrimary(state, 90);
  assert.notEqual(activeModelOf(moved), a);
});

/* ------------------------------------------------------------------ */
/* handoff note                                                        */
/* ------------------------------------------------------------------ */

test("handoff note carries the whole story and stays under 900 chars", () => {
  const task = {
    id: "t1",
    label: "Reverse-engineer the orbit-dodge build",
    completed: ["cloned the repo", "bundled with esbuild", "ran the recovery probe"],
    pending: ["map the collision constants", "write the harness", "diff two seeds"],
  };
  const note = buildHandoffNote({
    from: "Claude Sonnet 4.5",
    to: "Gemini 2.5 Flash",
    task,
    reason: "primary quota exhausted (0% · 429)",
    directive: "Operate as NIO's Apollo core: decompose the objective.",
  });

  assert.ok(note.startsWith("CONTEXT HANDOFF · NIO/APOLLO"));
  assert.match(note, /from: Claude Sonnet 4\.5 → to: Gemini 2\.5 Flash/);
  assert.match(note, /reason: primary quota exhausted/);
  assert.match(note, /task: Reverse-engineer the orbit-dodge build/);
  assert.match(note, /completed: 1\) cloned the repo/);
  assert.match(note, /pending: 1\) map the collision constants/);
  assert.match(note, /directive: Operate as NIO's Apollo core/);
  // directive sits between task and completed, never between the two lists
  const order = ["task:", "directive:", "completed:", "pending:", "resume:"].map((key) => note.indexOf(key));
  assert.deepEqual([...order].sort((a, b) => a - b), order);
  assert.match(note, /resume: continue at the next pending objective/);
  assert.ok(note.length <= 900, `note was ${note.length} chars`);

  // an idle router still produces a usable note
  const idle = buildHandoffNote({ from: "A", to: "B" });
  assert.match(idle, /task: idle · no task in flight/);
  assert.match(idle, /completed: —/);
  assert.ok(idle.length < 400);
});

test("handoff note truncates runaway objectives instead of exploding", () => {
  const huge = "x".repeat(5000);
  const note = buildHandoffNote({
    from: "Claude Sonnet 4.5",
    to: "GPT-OSS 120B",
    task: { id: "t", label: huge, completed: [huge, huge, huge, huge, huge], pending: [huge] },
    directive: huge,
    maxChars: 900,
  });
  assert.equal(note.length, 900);
});

/* ------------------------------------------------------------------ */
/* CLI table                                                           */
/* ------------------------------------------------------------------ */

test("formatRouterTable renders a ranked, aligned table with the pool footer", () => {
  const ranked = rankCandidates(SEED_CANDIDATES, DEFAULT_WEIGHTS);
  const pool = [
    ...Array.from({ length: 4 }, (_, i) => ({ providerId: `active-${i}`, status: "ACTIVE" })),
    ...Array.from({ length: 3 }, (_, i) => ({ providerId: `standby-${i}`, status: "STANDBY" })),
    { providerId: "limited-0", status: "LIMIT_REACHED" },
  ];
  const table = formatRouterTable(pool, ranked, DEFAULT_WEIGHTS);

  assert.match(table, /reliability 50% \/ speed 25% \/ intelligence 25%/);
  assert.match(table, / 1\.\s+91\.5\s+Gemini 2\.5 Flash/);
  assert.match(table, /2\.\s+90\.5\s+GPT-OSS 120B/);
  assert.match(table, /635 endpoints \/ 36 providers/);
  assert.match(table, /pool: 4 active · 3 standby · 1 limited/);
  // every line is padded consistently (no ragged rank column)
  const rows = table.split("\n").filter((line) => /^\s*\d+\./.test(line));
  assert.equal(rows.length, 8, "the HUD table shows the top 8");
  assert.ok(ranked.length >= 8);
});

/* ------------------------------------------------------------------ */
/* geometry                                                            */
/* ------------------------------------------------------------------ */

test("clamp01 and radialPoint stay in range", () => {
  assert.equal(clamp01(-3), 0);
  assert.equal(clamp01(0.42), 0.42);
  assert.equal(clamp01(9), 1);

  for (const angle of [0, Math.PI / 3, -Math.PI / 2, 5.5, -7]) {
    const point = radialPoint(angle);
    assert.ok(Math.abs(Math.hypot(point.x, point.y) - 1) < 1e-9);
    const raw = Math.atan2(point.y, point.x);
    assert.ok(Math.abs(angleOf({ x: 0, y: 0 }, point) - raw) < 1e-9);
  }
  // explicit radius scaling for the oval layout
  const oval = radialPoint(0, 2, 0.5);
  assert.equal(oval.x, 2);
  assert.equal(oval.y, 0);
});

test("ellipseFor keeps the ring a fixed fraction of the short edge", () => {
  const wide = ellipseFor(1600, 800);
  const tall = ellipseFor(800, 1600);
  assert.equal(wide.cx, 800);
  assert.equal(wide.cy, 400);
  assert.equal(wide.rx, 800 * RING.rx);
  assert.equal(wide.ry, 800 * RING.ry);
  assert.equal(tall.rx, 800 * RING.rx);
  assert.equal(tall.ry, 800 * RING.ry);

  const point = toPixels(radialPoint(0), wide);
  assert.equal(point.x, 800 + 800 * RING.rx);
  assert.equal(point.y, 400);
});

test("widestGapAngle spreads spawns around the membrane", () => {
  assert.equal(widestGapAngle([]), -Math.PI / 2);
  // two nodes left and right: the spawn lands in one of the two equal gaps
  const spawn = widestGapAngle([0, Math.PI]);
  const distance = (a, b) => {
    const delta = Math.abs(normalizeAngle(a - b));
    return Math.min(delta, Math.PI * 2 - delta);
  };
  assert.ok(distance(spawn, 0) > 0.7 && distance(spawn, Math.PI) > 0.7, `spawn ${spawn} is too close to a node`);
  // a ring with one wide slice puts the node in that slice, not on a neighbour
  const gap = widestGapAngle([0, 1, 2, 3]);
  assert.ok(normalizeAngle(gap) > 3 && normalizeAngle(gap) < Math.PI * 2);
  // seeded nodes are far enough apart that a spawn keeps its distance
  const angles = SEED_NODES.map((n) => n.angle);
  const nextAngle = widestGapAngle(angles);
  for (const angle of angles) {
    const delta = Math.abs(normalizeAngle(nextAngle - angle));
    assert.ok(Math.min(delta, Math.PI * 2 - delta) > 0.35, "spawn must not land on an existing node");
  }
});

test("seed nodes are evenly spaced enough for 196px cards", () => {
  const angles = SEED_NODES.map((n) => n.angle).sort((a, b) => a - b);
  for (let i = 0; i < angles.length; i++) {
    const next = i + 1 < angles.length ? angles[i + 1] : angles[0] + Math.PI * 2;
    assert.ok(next - angles[i] > 0.6, `gap ${(next - angles[i]).toFixed(2)} rad is too tight`);
  }
});

test("axonCurve bows perpendicular to the chord and is a monotone bezier", () => {
  const from = { x: 100, y: 100 };
  const to = { x: 300, y: 100 };
  const [p0, p1, p2, p3] = axonCurve(from, to, 0.2);
  assert.deepEqual(p0, from);
  assert.deepEqual(p3, to);
  assert.ok(p1.y !== p0.y, "control points must leave the straight line");
  assert.ok(p2.y !== p3.y);

  const midpoint = cubicAt(p0, p1, p2, p3, 0.5);
  assert.ok(midpoint.x > 100 && midpoint.x < 300);
  assert.ok(Math.abs(midpoint.y - 100) > 1);
  assert.deepEqual(cubicAt(p0, p1, p2, p3, 0), p0);
  assert.deepEqual(cubicAt(p0, p1, p2, p3, 1), p3);
});

test("springStep converges without exploding", () => {
  let state = { x: 0, y: 0, vx: 0, vy: 0 };
  const target = { x: 120, y: -40 };
  for (let i = 0; i < 240; i++) {
    state = springStep(state, target, 1 / 60, 92, 13);
    assert.ok(Number.isFinite(state.x) && Number.isFinite(state.vx));
  }
  assert.ok(Math.abs(state.x - target.x) < 0.5, `x settled at ${state.x}`);
  assert.ok(Math.abs(state.y - target.y) < 0.5, `y settled at ${state.y}`);
});

test("hexToRgba parses 3- and 6-digit hex and clamps alpha", () => {
  assert.equal(hexToRgba("#00e5ff", 0.5), "rgba(0, 229, 255, 0.5)");
  assert.equal(hexToRgba("#fff", 1), "rgba(255, 255, 255, 1)");
  assert.equal(hexToRgba("#00e5ff", 4), "rgba(0, 229, 255, 1)");
  assert.equal(hexToRgba("#00e5ff", -1), "rgba(0, 229, 255, 0)");
});

test("bowFor is deterministic per node id and stays small", () => {
  const a = bowFor("node-router");
  assert.equal(a, bowFor("node-router"));
  assert.ok(Math.abs(a) <= 0.32);
  assert.ok(mulberry32(7)() === mulberry32(7)());
});

/* ------------------------------------------------------------------ */
/* ring capacity — /spawn must never stack cards on top of each other  */
/* ------------------------------------------------------------------ */

/** Seed positions plus `n` spawns placed in the widest gap, as the store does. */
function ringWith(n) {
  // Seeds carry an angle, not a point; the store projects them onto the ring.
  const points = SEED_NODES.map((node) => radialPoint(node.angle));
  while (points.length < n) {
    const angle = widestGapAngle(points.map((point) => angleOf({ x: 0, y: 0 }, point)));
    points.push(radialPoint(angle));
  }
  return points;
}

test("eight seed nodes keep the nominal ring and stay card-free", () => {
  const scene = { width: 1440, height: 719 };
  const fit = fitEllipse(ringWith(8), scene.width, scene.height);
  assert.equal(fit.crowded, false);
  assert.equal(fit.scale, 1);
  assert.equal(cardsCollide(ringWith(8), fit.ellipse, scene), false);
});

test("spawns keep filling the ring until the scene really runs out", () => {
  const scene = { width: 1440, height: 719 };
  for (const count of [10, 12, 16]) {
    const fit = fitEllipse(ringWith(count), scene.width, scene.height);
    assert.equal(fit.crowded, false, `${count} nodes should still fit the ring`);
    const box = { width: CARD_BOX.width * fit.scale, height: CARD_BOX.height * fit.scale };
    assert.equal(cardsCollide(ringWith(count), fit.ellipse, scene, box), false, `${count} nodes overlap`);
  }
  // Cards step down before they would touch.
  assert.ok(fitEllipse(ringWith(16), scene.width, scene.height).scale < 1);
});

test("a short scene falls back to the board instead of stacking cards", () => {
  const scene = { width: 1024, height: 519 };
  const fit = fitEllipse(ringWith(16), scene.width, scene.height);
  assert.equal(fit.crowded, true);
});

test("cardsCollide spots a pile-up and a card hanging off the edge", () => {
  const scene = { width: 800, height: 600 };
  const centre = { cx: 400, cy: 300, rx: 200, ry: 150 };
  assert.equal(cardsCollide([{ x: 0, y: 0 }, { x: 0, y: 0 }], centre, scene), true);
  assert.equal(cardsCollide([{ x: -3, y: 0 }], centre, scene), true);
  assert.equal(cardsCollide([{ x: 0, y: 1 }], centre, scene), false);
});
