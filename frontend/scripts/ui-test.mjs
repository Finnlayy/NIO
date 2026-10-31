#!/usr/bin/env node
/**
 * Zero-dependency UI test runner for the frontend.
 *
 * The project has no test framework (and package.json/tsconfig.json are
 * frozen), so this harness:
 *   1. copies the modules under test into `.test-build/`,
 *   2. rewrites `@/` alias imports to relative paths (tsc CLI has no `paths`),
 *   3. compiles them with the project's own TypeScript compiler (CommonJS),
 *   4. runs the plain-JS tests from `src/ops/__tests__/` under Node's
 *      built-in test runner (`node --test`).
 *
 * Tests SSR-render with `react-dom/server` (no DOM required) and
 * unit-test the pure modules directly.
 *
 * Usage: node scripts/ui-test.mjs
 */
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const buildDir = path.join(frontendRoot, ".test-build");
const srcDir = path.join(frontendRoot, "src");
const tscBin = path.join(frontendRoot, "node_modules", "typescript", "bin", "tsc");

/* Entry points whose import closure gets compiled. Files that do not
   exist yet (new modules introduced by a cycle) are skipped. */
const entries = [
  "ops/GridCanvas.tsx",
  "ops/McpConsole.tsx",
  "ops/store.ts",
  "ops/widgets/bits.tsx",
  "ops/widgets/CvdHeatmap.tsx",
  "ops/widgets/NewsSentiment.tsx",
  "ops/hotkeys.ts",
  "ops/hooks/useMarketData.ts",
  "data/network.ts",
  /* Apollo core: pure router/layout/command modules + the zustand store. */
  "apollo/catalog.ts",
  "apollo/engine.ts",
  "apollo/routing.ts",
  "apollo/graph.ts",
  "apollo/commands.ts",
  "apollo/store.ts",
  "kanban/types.ts",
  "kanban/seed.ts",
  "kanban/board-logic.ts",
  "kanban/validate.ts",
  "kanban/repository.ts",
  "kanban/store.ts",
  "kanban/hotkeys.ts",
  "kanban/useKanbanStore.ts",
  "kanban/dragState.ts",
  "kanban/MoveMenu.tsx",
  "kanban/TaskCard.tsx",
  "kanban/KanbanColumn.tsx",
  "kanban/BoardToolbar.tsx",
  "kanban/KanbanBoard.tsx",
  "telegram/state.ts",
  "telegram/proxy.ts",
  "telegram/Panels.tsx",
].filter((rel) => existsSync(path.join(srcDir, rel)));

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name)) out.push(full);
  }
  return out;
}

function toPosix(p) {
  return p.split(path.sep).join("/");
}

/* 1+2. Copy the import closure and rewrite `@/` imports to relative paths. */
rmSync(buildDir, { recursive: true, force: true });
const closure = new Set(entries.map((rel) => toPosix(path.join(srcDir, rel))));
const queue = [...closure];

function resolveImport(baseDir, spec) {
  const base = spec.startsWith("@/")
    ? path.join(srcDir, spec.slice(2))
    : spec.startsWith(".")
      ? path.resolve(baseDir, spec)
      : null;
  if (!base) return null;
  const candidates = [base, `${base}.ts`, `${base}.tsx`, path.join(base, "index.ts"), path.join(base, "index.tsx")];
  return candidates.find((c) => existsSync(c) && statSync(c).isFile()) ?? null;
}

while (queue.length) {
  const file = queue.pop();
  const code = readFileSync(file, "utf8");
  const importRe = /from\s+["']([^"']+)["']/g;
  let m;
  while ((m = importRe.exec(code))) {
    const resolved = resolveImport(path.dirname(file), m[1]);
    if (resolved) queue.push(toPosix(resolved));
  }
  let rewritten = code;
  rewritten = rewritten.replace(importRe, (full, spec) => {
    if (!spec.startsWith("@/")) return full;
    const to = path.join(srcDir, spec.slice(2)); // no extension in the spec
    const rel = toPosix(path.relative(path.dirname(file), to));
    return `from "${rel.startsWith(".") ? rel : "./" + rel}"`;
  });
  const dest = path.join(buildDir, toPosix(path.relative(srcDir, file)));
  mkdirSync(path.dirname(dest), { recursive: true });
  writeFileSync(dest, rewritten);
}

/* 3. Compile with the project's tsc (CommonJS, noEmit off). */
execFileSync(
  process.execPath,
  [
    tscBin,
    ...entries.map((rel) => path.join(buildDir, rel)),
    "--outDir", buildDir,
    "--module", "commonjs",
    "--moduleResolution", "node",
    "--target", "es2017",
    "--jsx", "react-jsx",
    "--esModuleInterop",
    "--skipLibCheck",
    "--strict",
    "--noEmitOnError",
    "--types", "node,react,react-dom",
  ],
  { cwd: frontendRoot, stdio: "inherit" },
);

/* 4. Copy the plain-JS tests and run them. Test files are passed
   explicitly: `node --test <dir>` chokes when the dir holds non-test .js
   files (dev utilities like churn-report.js). */
const testDest = path.join(buildDir, "__tests__");
mkdirSync(testDest, { recursive: true });
const testFiles = [];

/* All test dirs share one flat .test-build/__tests__/ (relative requires
   like "../kanban/store" depend on it), so file names must be unique. */
const copied = new Map();
for (const dirName of ["ops", "kanban", "telegram"]) {
  const testSrc = path.join(srcDir, dirName, "__tests__");
  if (!existsSync(testSrc)) continue;
  for (const f of readdirSync(testSrc).sort()) {
    if (!f.endsWith(".js")) continue;
    if (copied.has(f)) throw new Error(`test file name clash: ${dirName}/__tests__/${f} vs ${copied.get(f)}/__tests__/${f}`);
    copied.set(f, dirName);
    cpSync(path.join(testSrc, f), path.join(testDest, f));
    if (f.endsWith(".test.js")) testFiles.push(path.join(testDest, f));
  }
}

if (testFiles.length === 0) throw new Error("no *.test.js files found in src/ops/__tests__/, src/kanban/__tests__/ or src/telegram/__tests__/");
execFileSync(process.execPath, ["--test", "--test-reporter=spec", ...testFiles], {
  cwd: frontendRoot,
  stdio: "inherit",
});
