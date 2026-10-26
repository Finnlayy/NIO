# REA Subagent Node — Design, Task Breakdown, Runbook

Status: **implemented** · Night shift of 2026-10-25 · Branch `arena/7afcb206-nio`

---

## 0. The request, recited

> "implement another node in the system: its an subagent with its owns sandbox and running
> https://github.com/NabilRFG12/Reverse-Engineer-anything.git.
> first goal is to install everything and make sure it executes well! reiterate until you are
> ready to reverse engineer something like a small game app. recite this prompt, analyse it,
> part it into subtasks and to dos and start now"

Decomposed into what actually has to be true:

| # | Requirement | Decision |
|---|---|---|
| R1 | *Another node in the system* | The node is a **limb** (`limbs/rea_limb.py`) — the only execution seam NEU has — plus a **manager** (`orchestrator/subagent.py`) that owns the node's identity, sandbox and run ledger. No parallel runtime is invented. |
| R2 | *A subagent* | A subagent is an actor with (a) its own sandbox root, (b) its own tool installation, (c) its own state/ledger, (d) its own time budget. `subagent = sandbox + install + ledger + limb`. |
| R3 | *Its own sandbox* | `workspace/subagents/<agent_id>/` — enforced twice, as everywhere else in NEU: `Policy.check()` pre-flight in the orchestrator and `Policy.resolve_path()` at runtime inside the limb. A second subagent is unreadable from the first one. |
| R4 | *Running REA* | REA (`rea-agents` 6.0.0) is installed **inside** the subagent sandbox — from the Git URL (source build) or from npm (prebuilt) — and invoked as an argv-list, never through a shell. |
| R5 | *Install everything, prove it executes* | `rea.install` → `git clone` + `npm ci` + `npm run build` (or `npm i rea-agents`), then `rea --version`, `rea capabilities`, `rea doctor`, and optionally a pwntools venv for the native ELF provider. |
| R6 | *Reiterate until ready for a small game app* | Acceptance is not "command exits 0"; it is: **analyze the bundled game, recover its behaviour, and re-implement it so the numbers match the original**. Fixture: `tests/fixtures/rea/orbit-dodge/`. |

---

## 1. Analysis of the existing system

* `core/` — protocol 1.2 (`neu/intent` → `neu/result`), policy/sandbox, job lifecycle, kernel.
* `orchestrator/` — timer hardening, agent slots, scheduler, archive, event bus, CLI.
* `limbs/` — `base.py` (runtime: one intent in, one result out, own clock watchdog) + `echo` (protocol
  test double) + `bootstrap` (`fs.*`).
* `protocol/operations.json` — normative operation register. An operation only becomes usable when an
  `active` limb implements it.
* `workspace/` — the sandbox, git-ignored (`workspace/*`, `!workspace/.gitkeep`).

Two properties of the existing design drive every decision below:

1. **The limb may not invent its own budget.** `LimbBase` watches `intent.timer` and returns a status
   report on expiry; the orchestrator owns iteration/scale limits. A REA analysis can take minutes, so
   the node must never "just wait" — it must kill its child process group and report.
2. **Sandbox checks happen twice.** Pre-flight (`Policy.check`) and runtime (`Policy.resolve_path`). A
   subagent gets isolation for free *if* every path goes through `ctx.resolve()` — and it must, because
   `rea.analyze` takes a target path straight from the intent.

---

## 2. Architecture

```
                      ┌───────────────────────────────┐
                      │ orchestrator (NEU core)       │
                      │  timer · slots · archive      │
                      └───────────────┬───────────────┘
                                      │ intent (limb=rea)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ SubagentManager  (orchestrator/subagent.py)                             │
│  • identity + ledger   workspace/subagents/<id>/.subagent/state.json    │
│  • create / import target / status / run                                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ Intent(constraints.sandbox_root=workspace/subagents/<id>)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ReaLimb  (limbs/rea_limb.py)                                            │
│  rea.ping · rea.install · rea.doctor · rea.capabilities · rea.analyze   │
│  argv-only subprocess, process-group kill on timer, artifact hashes     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                ▼
       workspace/subagents/<id>/
         rea/        REA installation (git source or npm package) + optional pyenv
         targets/    the artifact under analysis (copied + hashed)
         out/        evidence JSON, reports, summaries
         logs/       raw stdout/stderr of every REA invocation
         tmp/ cache/ home/   HOME/TMPDIR/XDG/npm cache, all inside the sandbox
         .subagent/  state.json — identity, install info, run ledger
```

Import direction stays `orchestrator → core`, `limbs → core`. The new module is a thin client of
`Orchestrator.run_job`, so every subagent run inherits: policy pre-flight, agent slot, timer,
result validation, archive, events. Nothing is bypassed.

---

## 3. Task breakdown

Legend: **done** = implemented and covered in this branch · *(blocked)* = needs a component this
sandbox does not have (Ghidra/Hopper/JDK).

### T0 — Reconnaissance (done)
- [x] Clone REA, read `README.md`, `docs/cli.md`, `package.json`, `install.sh`.
- [x] Node engine check: REA needs Node 22.19+/24.11+/26+. Host: Node 22.22.3 ✔.
- [x] `npm ci` (374 packages, 8 s) and `npm run build` (16 s) verified in a scratch clone.
- [x] `rea --version`, `rea capabilities --json`, `rea doctor --json` verified.
- [x] Shape of the analysis output recorded (`normalized_result.graph` / `.semantic_graph` /
      `.statistics` / `.limitations`) → drives the summary contract.

### T1 — Limb (done)
- [x] `limbs/rea_limb.py`: five operations, argv allowlist, structured options only.
- [x] Process runner: own process group, hard kill on timer, bounded capture, full log artifact.
- [x] Sandbox-only paths via `ctx.resolve()`; `HOME`/`TMPDIR`/`XDG`/npm cache redirected into the sandbox.
- [x] `rea.install`: git (clone → `npm ci` → `npm run build`) and npm (prebuilt) sources, idempotent
      marker `.rea-install.json`, optional pwntools venv for the ELF provider, network gate.
- [x] `rea.ping` / `rea.doctor` / `rea.capabilities` / `rea.analyze` with bounded summaries.
- [x] Artifact records with sha256 for every file the node writes.

### T2 — Registry & policy (done)
- [x] `limbs/registry.json`: `rea` (phase 3, active, writes files).
- [x] `protocol/operations.json`: `rea.*` with risk/elevation/path params (`target`, `paths`, `out`).

### T3 — Subagent manager (done)
- [x] `orchestrator/subagent.py`: `SubagentManager`, `SubagentRecord`, `SubagentStore`,
      `import_target` (hashed copy into `targets/`), `status`, `run`, `install`.
- [x] Id validation (`^[a-z0-9][a-z0-9._-]{1,47}$`) — no path separators, no traversal.
- [x] Runs go through `Orchestrator.run_job` with `parent_job_id` for lineage.

### T4 — CLI (done)
- [x] `python3 -m orchestrator subagent create|list|status|import|install|run`.

### T5 — Tests (done)
- [x] `tests/test_rea_limb.py` — install gate, command allowlist, sandbox escape, artifact capture,
      timer kill, summary shape. Uses a stub `rea` entry point, so it runs offline.
- [x] `tests/test_subagent.py` — isolation between two subagents, ledger, import manifest, run lineage.
- [x] Full suite (`python3 -m unittest discover -s tests -t .`) green.

### T6 — Proof on a small game app (done, measured)
- [x] Fixture `tests/fixtures/rea/orbit-dodge/` — a real canvas game (5 ES modules) + `app/`
      with an esbuild-minified bundle and a deterministic Node replay entry (`app/cli.cjs`).
- [x] Native twin `tests/fixtures/rea/orbit-dodge/native/orbit.c` → stripped ELF, same scoring rules.
- [x] `rea.install` inside `workspace/subagents/rea-lab` (real network install).
- [x] `rea.analyze analyze-javascript-application targets/orbit-dodge` → evidence + summary.
- [x] Recovered scoring rules re-implemented and checked against the original replay output.
- [x] `inspect-binary-layout` on the ELF (pwntools venv) → sections/symbols/mitigations.

### T7 — Docs (done)
- [x] this file, `prompts/limbs/rea_limb.md`, link from `docs/NEU.md`, root `README.md`.
- [x] `scripts/rea_demo.py` — one-command reproduction of the whole chain.

---

## 4. Operation contract

| Operation | Risk | Network | Purpose |
|---|---|---|---|
| `rea.ping` | none | no | Is REA installed here? version, entry point, layout, node version. |
| `rea.install` | write | **yes** (`--allow-network`) | Install/refresh REA in this sandbox. |
| `rea.doctor` | read | no | `rea doctor` in JSON, condensed to checks/capabilities. |
| `rea.capabilities` | none | no | Available operations + side effects from the provider matrix. |
| `rea.analyze` | read | per command | Run one allowlisted REA verb against a path inside the sandbox. |

`rea.analyze` parameters:

```json
{
  "command": "analyze-javascript-application",
  "target": "targets/orbit-dodge",
  "args": [],
  "options": {"artifact_format": "directory"},
  "out": "out/orbit-dodge-evidence.json",
  "timeout_s": 300,
  "summary_mode": "full"
}
```

`target` / `paths[]` are policy-checked path parameters (`path_params` in the operation register).
`command` is not free text: it must be one of the verbs in `ReaLimb.COMMANDS`, each with a fixed
positional shape and an explicit flag allowlist. The node never interpolates a shell string.

REA verbs currently admitted: `analyze-javascript-application`, `analyze`, `inspect`,
`inspect-binary-layout`, `inspect-artifact`, `inspect-managed-members`, `inspect-evm-interface`,
`inspect-web-network-capture`, `strings`, `instructions`, `function`, `decompile`, `xrefs`, `search`,
`providers`, `capabilities`, `doctor`, `evidence-import`, `evidence-export`, `compare`,
`import-reference-source`, `compare-source-to-bundle`.

---

## 5. Security boundaries

* **Path**: every path parameter resolves through `Policy.resolve_path`; absolute paths and `..` are
  rejected before a process starts. `rea.analyze` additionally requires the target to exist.
* **Process**: `argv` lists only, `start_new_session=True`, kill the whole group at the timer.
* **Environment**: `HOME`, `TMPDIR`, `XDG_CACHE_HOME`, `npm_config_cache` point into the sandbox, so a
  REA run cannot scribble into the host home directory. `GIT_TERMINAL_PROMPT=0` prevents a hanging
  credential prompt during install.
* **Network**: only `rea.install` needs it, and it refuses to run unless
  `constraints.allow_network=true` (CLI: `--allow-network`). Static analysis never opens a socket.
* **Ownership**: `rea.install --force` only replaces a directory that carries this node's install
  marker. A foreign non-empty directory is a policy error, not a `rm -rf`.
* **Budget**: the limb never invents a deadline; it honours `intent.timer` and reports
  `status="timeout"` with a status report instead of hanging.

---

## 6. Runbook

```bash
# 1) create the node (own sandbox under workspace/subagents/rea-lab/)
python3 -m orchestrator subagent create rea-lab

# 2) install REA inside that sandbox (needs network; ~20 s from the Git URL)
python3 -m orchestrator subagent install rea-lab --with-pwntools

# 3) bring a target in (hashed copy into targets/<name>/)
python3 -m orchestrator subagent import rea-lab tests/fixtures/rea/orbit-dodge/app --name orbit-dodge

# 4) ask the node to reverse engineer it
python3 -m orchestrator subagent run rea-lab --goal "Recover Orbit Dodge scoring" \
  --op rea.analyze \
  --params '{"command":"analyze-javascript-application","target":"targets/orbit-dodge"}'

# 5) inspect
python3 -m orchestrator --json subagent status rea-lab
python3 -m orchestrator job show <job_id>
```

Full chain incl. native layout and the behavioural check:

```bash
python3 scripts/rea_demo.py --install
```

### Install sources

| Source | Command inside the node | When |
|---|---|---|
| `git` (default) | `git clone --depth 1 <repo>` → `npm ci` → `npm run build` | the repository named in the request |
| `npm` | `npm install --prefix rea rea-agents@<version>` | prebuilt, no toolchain, faster |
| pwntools venv (optional) | `python3 -m venv rea/pyenv` + `pip install pwntools==4.15.0 pyelftools==0.33 unicorn==2.1.2` | unlocks `inspect-binary-layout` on Linux |

REA never installs Python itself; the venv is caller-supplied, which is exactly what
`REA_PWNTOOLS_PYTHON` expects.

---

## 7. Verification — measured, not asserted

Everything below was executed in this checkout. Numbers are from the actual runs.

### 7.1 Installation (inside `workspace/subagents/rea-lab/`)

| Step | Result |
|---|---|
| `git clone --depth 1` the repository from the request | 1.06 s |
| `npm ci` | 374 packages, 8.19 s |
| `npm run build` (`tsc` + catalogue generators) | 16.51 s |
| `rea --version` | `6.0.0` |
| pwntools venv (`pwntools==4.15.0`, `pyelftools==0.33`, `unicorn==2.1.2`) | 11.83 s, `REA_PWNTOOLS_PYTHON` wired automatically |
| marker `.rea-install.json` | sha256 `b07cc481…`, every step + duration recorded |

`rea doctor` inside the sandbox: `node` healthy, `host` `unsupported_host`
(Debian 12), `hopper`/`ghidra`/`ida` `missing_analysis_engine`. That is the
honest answer of this machine — the static paths do not need them.

### 7.2 JavaScript analysis (the game)

```
evidence_id   ev_1ceecfb8b0d7ba511ebaa5619b3f82948c3c24a0b4f1984a601f46b1cf9f3101
subject       orbit-dodge (directory), sha256 d7db204a7e66b8392e2f5c894644ed29c1cbd50b8fc0fc3d868f26ccac69b373
raw bundle    8 168 248 bytes  ->  out/orbit-dodge-evidence.json
summary       2 686 bytes (0.03 % of the raw bundle)
graph         8 application nodes / 9 edges
semantics     1 816 nodes, 1 815 relations, 48 functions, 42 literals
unknowns      156  (dynamic-call 78, ambiguous-target 76, dynamic-property 2)
duration      3.17 s (direct) / 3.7 s through the orchestrator, job `resolved`
```

The **subject digest equals the digest of the pristine fixture tree** — the
import copies bytes and keeps its manifest outside the tree, so REA analyses
what was imported and nothing else.

### 7.3 Native analysis (same subagent, ELF provider)

```
evidence_id   ev_d43569bbf32691f829e3ff8d7dbc5d1b6eae106078e5045f491ee6c5250dbb7d
provider      pwntools-elf (pwntools@4.15.0;pyelftools@0.33;unicorn@2.1.2)
subject       orbit-game, format elf, sha256 1bcbf6e51275597c1b38d641989ab2c77e1df648f537ab8275a0035662696deb
raw bundle    87 844 bytes  ->  out/…-inspect-binary-layout.json
summary       2 686 bytes: 29 sections, 13 segments, 9 symbols (printf, strtol, …),
              11 relocations, PIE + NX, Partial RELRO, no canary, libc only
duration      1.91 s
```

### 7.4 Reconstruction (the actual acceptance)

`scripts/rea_recover_orbit.py` takes the evidence as its **only** source of
numbers, recovers 13 named constants from literal role keys
(`…:property:comboWindowMs:1400`), ports the game, and compares against the
original executable:

```
seeds   1, 2, 3, 7, 42, 1337, 20260101   ×   frames 300, 900, 1200
cases   21                              deviations 0
native  orbit-game seed=42: final=327   recomputed 327
result  reconstruction reproduces the original
```

Three constants are not named in the bundle (dodge payout 10, penalty 25,
final-score correction `1 + dodged/100`); they are confirmed by the
differential test, not assumed. That distinction is documented in the script's
report so a reader can tell evidence from inference.

### 7.5 Gates

```
python3 -m unittest discover -s tests -t .   -> 337 tests, OK (24.97 s)
ruff check (touched files)                   ->  All checks passed
mypy (core/, orchestrator/, limbs/)          ->  clean for the new modules
scripts/rea_demo.py                          ->  all steps passed (6.8 s warm)
scripts/rea_probe_tetris.py                  ->  6/6 cases, foreign bundle (6.4 s warm)
```

The `scripts/rea_demo.py` run is the one-command reproduction: create →
install → import → analyse JS → analyse ELF → reconstruct.

---

## 8. A foreign game, no sources — the generalisation test

The Orbit Dodge fixture is this repository's own code, so the *structure* of the
port could be read from its `src/`. `scripts/rea_probe_tetris.py` closes that
gap with a real third-party target that the subagent has never seen:

```
upstream   github.com/jakesgordon/javascript-tetris @ e5c0c42f (MIT)
delivery   inline <script> extracted -> esbuild 0.25.10 --minify -> dist/
           the subagent only ever sees dist/ (6 258 B bundle + vendor file + page)
analysis   rea.analyze analyze-javascript-application  ->  60 functions, 2 359 nodes
```

### What came out of the evidence

| Recovered | Value | Source |
|---|---|---|
| board | 10 × 20 | role keys `binding:nx:binding:10`, `binding:ny:binding:20` |
| preview | 5 × 5 | `binding:nu:binding:5` |
| gravity | `step = max(0.1, 0.6 - 0.005·rows)` | `speed:property:start:0.6`, `…decrement:0.005`, `…min:0.1` |
| pieces | 7 × 4 rotations, sizes 2–4, 7 colours | table pattern in the artifact; sizes/colours cross-checked against role keys (14/14 match) |
| scoring | +10 per piece, `100·2^(n−1)` per clear | literals + differential test |
| functions | 60 named functions in the semantic graph | `rea.analyze` |

### The gate

The bundle is executed in `scripts/tetris_harness.cjs` (canvas/DOM stub, seeded
`Math.random`, one key per frame). A rebuild of the rules in Python must match
the bundle bit for bit — score, rows, piece count, **board SHA-256** and the
game-over frame:

```
[ok] pattern seed=7     frames=4000  score=180   rows=0  pieces=18  board=74a4535c672292c5
[ok] pattern seed=42    frames=4000  score=130   rows=0  pieces=13  board=b191cdb7f40334ea
[ok] pattern seed=1337  frames=4000  score=170   rows=0  pieces=17  board=09878289a23ea706
[ok] bot     seed=7     frames=6000  score=1500  rows=6  pieces=50  board=06c5eb3a8e239fbc
[ok] bot     seed=42    frames=6000  score=1360  rows=9  pieces=46  board=93c74c367be78f9b
[ok] bot     seed=1337  frames=6000  score=770   rows=4  pieces=37  board=d3d2edc50f41c61e
```

The `bot` rows matter: a greedy planner plays the *reconstruction*, its key
sequence is replayed into the **original bundle**, and both agree — including
the line-clear scoring and the board shift. Without it the gate would only ever
exercise piece placement.

### Three things only a real target teaches

1. **Row 0 is never checked.** The original's clear loop is `for(y=ny; y>0; --y)`,
   so a full row at index 0 survives. A "clean" reimplementation would clear it
   and diverge at the first flush; the port reproduces the quirk.
2. **`DOWN` is not a step, it is a drop.** The key handler calls `drop()`, which
   locks the piece as soon as it cannot move — that is why the first trace
   diverged at frame 959 by exactly one placement.
3. **The build environment is part of the artifact.** Compiled from inside this
   repository, esbuild picks up `tsconfig.json` (`strict: true`), prepends
   `"use strict"`, and the game dies on its implicit global `now`. The probe
   passes `--tsconfig-raw={}` so the bundle behaves like the shipped page. Same
   source, different semantics — a reminder that "the bytes" are not the whole
   contract.

Run it with `make rea-probe` (or `python3 scripts/rea_probe_tetris.py`);
`--reuse` skips fetching/building and only replays the gate (≈2 s).

---

## 9. Known limits

* `rea doctor` reports `unsupported_host` for Debian 12 and `missing_analysis_engine` for Hopper/Ghidra.
  That is honest: deep native decompilation needs one of those engines. Everything static
  (JavaScript, artifacts, .NET via the static provider, ELF layout via pwntools) works.
* The Orbit Dodge fixture is authored for this repository; the Tetris probe (§8) is the control
  for "no sources". It still needs one *pattern* to be recognised in the bundle (the piece table
  and the bag), and it validates that pattern behaviourally rather than trusting it.
* Deep native decompilation is still blocked here: no Hopper/Ghidra/IDA on this host. The ELF
  provider gives layout, symbols, relocations and mitigations — not pseudocode.
* The source install needs network once per sandbox. `workspace/` is git-ignored, so a fresh checkout
  must run `subagent install` again — the marker makes that explicit rather than silent.
* `node_modules/` and the REA clone are intentionally **not** committed (they are tool state, not
  source). Reproducibility comes from pinned versions in the install marker, not from vendoring.
