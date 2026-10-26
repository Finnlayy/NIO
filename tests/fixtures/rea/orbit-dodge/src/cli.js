// Node entry: deterministic headless replay, used as the ground-truth oracle.
import { runSimulation } from "./engine.js";

const argv = typeof process !== "undefined" ? process.argv.slice(2) : [];
const seed = Number(argv[0] || 1337);
const frames = Number(argv[1] || 1200);
process.stdout.write(`${JSON.stringify(runSimulation(seed, frames))}\n`);
