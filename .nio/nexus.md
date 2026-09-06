# ⚡ Nexus — Backend & IPC Journal

> Continuous-loop memory for Project Nio. Read at the start of every cycle, update
> at the end. Every entry carries the tool that produced it (benchmark script) and
> the exact before/after delta.

## Repository truth (read once, re-derive each cycle)

- Runtime = Python 3.11 **stdlib-only** (`core/ orchestrator/ limbs/`). No third-party deps.
- Protocol 1.2, file-based transport **by contract** (`orchestrator/transport.py`).
- Event-Bus = `orchestrator/events.py` (`EventBus.emit`, sinks).
- Schema validator = `core/schemacheck.py` (sub-Draft-2020-12, `validate()`).
- Archive/ledger = `runtime/archive/<day>/<intent_id>/` via `FileTransport.archive()`.
- Gate: `make check` = compile + ruff + mypy + 210 unittest. Must stay green.
- Active loop focus rotation: A (IPC/Event-Bus) → B (Fast-Path Schema) → C (Ledger).

---

## 🔁 TRIAD Nº1

### Cycle 1 — Focus A: Sub-ms IPC / Event-Bus hot path

**Benchmark (baseline, `scripts/nexus_bench.py`):**
- `EventBus.emit` (null sink): **2.81 µs/emit**
- `EventBus.emit` (CollectingSink): **3.57 µs/emit**
- Timestamp component (`datetime.now(UTC).isoformat(ms).replace('+00:00','Z')`): **1.05 µs/call**
- `Event()` dataclass + `to_dict()` double-copy: **1.21 µs/call**

**Findings:** emit is dominated by (1) building the ISO-millisecond timestamp via
`datetime` + `.replace`, and (2) a redundant double copy of `payload` (once into the
`Event` dataclass, once in `to_dict()`). Both are pure CPU, no disk I/O.

**Change:**
- Replaced timestamp generation with a fast `time.time()`-based ISO-ms formatter
  (`_iso_ms_z_fast`, no `datetime` object, no `.replace`). Timestamp cost:
  **1.05 µs → 0.36 µs/call**.
- Build the delivery record once; stop re-copying `payload` for the record path
  (the `Event.to_dict()` double-copy in the delivery loop is gone).
- Added an opt-in `SharedMemoryRingSink` (`orchestrator/ring.py`): a bounded,
  `multiprocessing.shared_memory` ring buffer for high-frequency event streaming
  (no syscall per event, no disk). Console/Collector sinks (and the file-based
  `FileTransport`) remain the default/fallback — nothing was removed.

**Result (after):** see bottom-of-file summary for the measured delta.

### Cycle 2 — Focus B: Fast-Path Schema Validation

**Findings:** `core/schemacheck.py` re-runs `re.search(pattern, value)` per
string node. Even though CPython caches compiled regex internally, every call still
goes through the `re._compile` cache-lookup layer, and the set of *supported*
keywords is recomputed per `validate()` call. Raw JSON schema is re-walked on every
tick in the CLI/tests (this is the "compile-on-every-tick" anti-pattern).

**Change:**
- Cache compiled `re.Pattern` objects in a module-level registry (`_PATTERN_CACHE`
  + `_compiled()`); use `pattern.search(value)` directly on the hot paths.
- Hoist the supported-keyword allowance into a `_SUPPORTED_KEYS` frozenset so
  `validate()` no longer rebuilds a ~30-element set on each call.
- Micro-optimize `_matches_type` / single-type dispatch: the common
  `type:"<string>"` branch no longer builds an `any()` genexpr per node.

**Result (after):** measured delta in the summary below.

### Cycle 3 — Focus C: Ledger Compaction & Archive

**Findings:** `runtime/archive/<day>/<intent_id>/{intent,result,verdict}.json` grows
without bound. `QueueState.archived` only counts entries; nothing ever compacts or
prunes. Infinite growth would eventually degrade any index/summary built over it.

**Change:**
- Added `FileTransport.archive_stats()` (count + bytes per day, + `compacted/`).
- Added `FileTransport.compact_archive()`: merges stale per-intent directories into a
  single per-day `compacted/<day>.jsonl` snapshot + a per-day `.manifest.json` with
  canonical SHA-256 digests, then prunes the individual directories. Recent entries
  stay expanded so the active `attempt.archive_dir` contract is untouched.
  Snapshotting is atomic + fully verifiable via `verify_archive()`.
- Wiring: new CLI subcommands `orchestrator archive stats` and
  `orchestrator archive compact [--older-than-days N] [--keep-recent N]`.

**Result (after):** measured reduction in file count + size in the summary below.

---

## The Graveyard (architectural dead ends)

- **UDS socket transport** — deliberately NOT attempted. The cross-process contract
  between Orchestrator and Limbs is file-based *by design* (crash-replay + language
  neutrality, see `orchestrator/transport.py`). Converting intent delivery to
  UDS/stdin would break every Limb-subprocess test (real subprocesses + real timers)
  and would give up replayability. The latency win was taken **in-process** on the
  Event-Bus hot path (which is the real per-tick cost) + an opt-in shared-memory sink.
- **Shared-memory ring is NOT strictly faster than a buffered file write** in a bare
  micro-benchmark (~4.7 µs vs ~1.0 µs/event), because it still `json.dumps` each event
  and the OS buffers file writes. Its value is *bounded + zero-syscall + readable by a
  neighbour process without a file handle* — it ships as opt-in, not as the default.

## System Quirks

- `FileTransport.write_json_atomic` does `os.fsync()` per write → ~ms cost per
  file. That is *correct* (crash-safety contract) and must NOT be removed for the
  standard path; do not "optimize" it away.
- The limb subprocess reads its intent via a file path; converting to UDS/stdin
  sockets would break `tests/` (real subprocess + real timers). Keep file transport.
- Shared-memory objects are process-local in a test harness; the ring sink is opt-in.
- The compacted snapshot hashes **canonical JSON** (compact separators), *not* raw
  file bytes — so `verify_archive()` is independent of `indent`/line-ending.
- This repo has **no vector database / no `twin_behavioral_ledger` index**. The
  unbounded structure that maps to "ledger" is `runtime/archive/<day>/<intent_id>/`
  (the Job archive) — that is exactly what Focus C now compacts.

---

## 📊 TRIAD Nº1 SUMMARY (benchmark deltas)

All numbers from `scripts/nexus_bench.py`. Baseline = Commit `2639525` (parent of
this branch). Gate: compile + ruff + mypy + **213 tests** all green.

### Focus A — Event-Bus (sub-ms IPC)
| Metric | Before | After | Δ |
|---|---|---|---|
| `EventBus.emit` (null sink) | **2.81 µs** | **1.99 µs** | **−0.82 µs (1.4×)** |
| `EventBus.emit` (CollectingSink) | **3.57 µs** | **3.20 µs** | −0.37 µs |
| ISO-ms timestamp | **1.05 µs** | **0.36 µs** | **−0.69 µs (2.9×)** |
| Shared-memory ring write (opt-in) | file flush ~1.0 µs | **4.7 µs/event** | bounded, zero-syscall, readable cross-process |

> The ring is slower per-event than a buffered file write in isolation, but it is
> the *bounded no-syscall* path and ships as opt-in; the default file/console sinks
> are unchanged (fallback preserved).

### Focus B — Fast-Path Schema Validation
| Metric | Before | After | Δ |
|---|---|---|---|
| `schemacheck.validate` (intent.schema) | **77.20 µs** | **60.7 µs** | **−16.5 µs (1.27×)** |

### Focus C — Ledger Compaction & Archive (120 entries)
| Metric | Before | After | Δ |
|---|---|---|---|
| Expanded entries | **120** | **0** | compacted into 1/day snapshots |
| Expanded bytes | **400,720 B** | **0 B** (snapshot **272,550 B**) | **−32 % storage**, 400,720 B freed |
| Pruned dirs | — | 120 | — |
| `verify_archive` violations | — | **0** | integrity preserved |

### Files changed
- `orchestrator/events.py` — fast timestamp + single-record emit; ring sink hook.
- `orchestrator/ring.py` — NEW `SharedMemoryRingSink` / `SharedMemoryRingReader`.
- `core/schemacheck.py` — `_PATTERN_CACHE`, `_SUPPORTED_KEYS`, single-type fast path.
- `orchestrator/transport.py` — `archive_stats()`, `compact_archive()`, `verify_archive()`,
  `read_jsonl`/`write_jsonl_atomic`.
- `orchestrator/cli.py` — `orchestrator archive stats|compact` subcommands.
- `scripts/nexus_bench.py` — reproducible triad benchmark.
- `tests/test_nexus_triad.py` — NEW guards (3 tests).

### PR
`⚡ Nexus: IPC & Core Performance Triad [2026-09-06T23:45:00Z]`
