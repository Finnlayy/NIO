#!/usr/bin/env node
/*
 * Headless harness for a *shipped* browser-game bundle (no source tree).
 *
 * The bundle expects a browser: a 2D canvas context, DOM nodes,
 * requestAnimationFrame and (here) a Stats stub. The harness provides exactly
 * that surface and a *seeded* Math.random, then drives the game loop for a
 * fixed number of frames with a scripted input pattern.
 *
 * The output is a deterministic behavioural trace -- score, rows, board digest,
 * piece count, game-over state -- which is the ground truth for the
 * reconstruction gate in ``scripts/rea_probe_tetris.py``. Nothing in this file
 * knows about the game's rules; it only presses keys and records what the
 * bundle does.
 *
 *   node tetris_harness.cjs dist/game.min.js --seed 7 --frames 4000
 *
 * Exit 0 = trace written, non-zero = the bundle could not be driven.
 */
"use strict";

const fs = require("fs");
const vm = require("vm");
const crypto = require("crypto");

function parseArgs(argv) {
  const out = { file: argv[0], seed: 7, frames: 4000, maxTrace: 400, "inputs-file": "" };
  for (let i = 1; i < argv.length; i += 2) {
    const key = argv[i].replace(/^--/, "");
    const value = argv[i + 1];
    out[key] = ["seed", "frames", "maxTrace"].includes(key) ? Number(value) : value;
  }
  if (!out.file) {
    console.error("usage: tetris_harness.cjs <bundle.js> [--seed N] [--frames N]");
    process.exit(3);
  }
  return out;
}

const args = parseArgs(process.argv.slice(2));

// --- deterministic PRNG -----------------------------------------------------
function mulberry32(a) {
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// --- a clock we control -----------------------------------------------------
let nowMs = 1_000_000;
class FakeDate extends Date {
  constructor(...a) {
    super(...(a.length ? a : [nowMs]));
  }
  static now() {
    return nowMs;
  }
  getTime() {
    return nowMs;
  }
}

// --- the browser surface the bundle touches ---------------------------------
const context2d = () => ({
  save() {}, restore() {}, translate() {}, clearRect() {}, fillRect() {}, strokeRect() {},
  fillStyle: "", strokeStyle: "", lineWidth: 1, font: "", fillText() {}, drawImage() {},
});

function element(id, width = 200, height = 400) {
  return {
    id,
    style: {},
    innerHTML: "",
    width,
    height,
    clientWidth: width,
    clientHeight: height,
    children: [],
    appendChild(child) { this.children.push(child); return child; },
    addEventListener() {},
    getContext() { return context2d(); },
  };
}

const nodes = new Map();
const document = {
  getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, element(id));
    return nodes.get(id);
  },
  createElement(tag) { return element(tag, 74, 30); },
  addEventListener() {},
};

let rafCallback = null;
const windowObject = {
  addEventListener() {},
  requestAnimationFrame(cb) { rafCallback = cb; return 1; },
};

const sandbox = {
  console,
  document,
  window: windowObject,
  Date: FakeDate,
  Stats: function () { return { domElement: element("stats", 80, 48), update() {} }; },
  requestAnimationFrame(cb) { rafCallback = cb; return 1; },
  setTimeout(fn) { return fn; },
  Math: Object.create(Math),
};
sandbox.Math.random = mulberry32(args.seed);
sandbox.globalThis = sandbox;

let code;
try {
  code = fs.readFileSync(args.file, "utf8");
} catch (error) {
  console.error(`cannot read bundle: ${error.message}`);
  process.exit(2);
}

vm.createContext(sandbox);
try {
  vm.runInContext(code, sandbox, { filename: args.file });
} catch (error) {
  console.error(`bundle threw while loading: ${error.stack}`);
  process.exit(2);
}
if (typeof sandbox.play !== "function") {
  console.error("bundle exposes no play() -- not a game bundle?");
  process.exit(2);
}
sandbox.play();

const KEY = { ESC: 27, SPACE: 32, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40 };
const press = (keyCode) => sandbox.keydown({ keyCode, preventDefault() {} });

// Optional: replay an exact input script [[frame, keyCode], ...]. The script is
// produced by a bot that plans on the reconstruction; the bundle stays the
// authority on what the inputs actually do.
let scripted = null;
if (args["inputs-file"]) {
  scripted = new Map();
  for (const [frame, keyCode] of JSON.parse(fs.readFileSync(args["inputs-file"], "utf8"))) {
    if (!scripted.has(frame)) scripted.set(frame, []);
    scripted.get(frame).push(keyCode);
  }
}

function boardDigest() {
  const blocks = sandbox.blocks || [];
  const flat = [];
  for (let x = 0; x < sandbox.nx; x++) {
    for (let y = 0; y < sandbox.ny; y++) {
      const block = blocks[x] && blocks[x][y];
      flat.push(block ? String(block.color || "?").slice(0, 1) : ".");
    }
  }
  return crypto.createHash("sha256").update(flat.join("")).digest("hex").slice(0, 16);
}

const frameMs = 1000 / 60;
const trace = [];
let lastPiece = sandbox.current;
let pieces = 0;
let lastRows = 0;

for (let frame = 0; frame < args.frames; frame++) {
  nowMs += frameMs;
  if (!rafCallback) break;
  rafCallback();

  if (sandbox.playing) {
    if (scripted) {
      for (const keyCode of scripted.get(frame) || []) press(keyCode);
    } else {
      if (frame % 7 === 0) press(KEY.UP);
      if (frame % 11 === 0) press(KEY.LEFT);
      if (frame % 13 === 0) press(KEY.RIGHT);
      if (frame % 29 === 0) press(KEY.DOWN);
    }
  }

  if (sandbox.current !== lastPiece) {
    lastPiece = sandbox.current;
    pieces += 1;
    if (trace.length < args.maxTrace) {
      trace.push({
        frame,
        score: sandbox.score,
        rows: sandbox.rows,
        piece: String(sandbox.current && sandbox.current.type && sandbox.current.type.color),
        x: sandbox.current && sandbox.current.x,
        y: sandbox.current && sandbox.current.y,
        board: boardDigest(),
      });
    }
  }
  lastRows = sandbox.rows;
  if (!sandbox.playing && frame > 60) break;
}

process.stdout.write(JSON.stringify({
  file: args.file,
  seed: args.seed,
  frames: args.frames,
  score: sandbox.score,
  rows: sandbox.rows,
  playing: sandbox.playing,
  pieces,
  step: sandbox.step,
  board: boardDigest(),
  trace,
}) + "\n");
