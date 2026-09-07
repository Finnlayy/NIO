# ⚡ Nexus — Backend & IPC Journal

> Continuous-loop memory for Project Nio. Read at the start of every cycle, update
> at the end. Every entry carries the tool that produced it (benchmark script) and
> the exact before/after delta.

## Repository truth (read once, re-derive each cycle)

- Runtime = Python 3.11 **stdlib-only** (`core/ orchestrator/ limbs/`). No third-party deps.
- Protocol 1.2, file-based transport **by contract** (`orchestrator/transport.py`).
- Event-Bus = `orchestrator/events.py` (`EventBus.emit`, sinks). Serialisiert den
  Datensatz **einmal pro Emit** und teilt die Zeile mit allen Text-Sinks.
- Opt-in Hochfrequenz-Zweige am Bus: `orchestrator/uds.py` (AF_UNIX-Datagramm-
  Broadcast) und `orchestrator/ring.py` (Shared-Memory-Ring). Beide **zusätzlich**,
  nie als Ersatz für Konsole/Sammler/Datei.
- Schema validator = `core/schemacheck.py` (sub-Draft-2020-12, `validate()`),
  kompilierte Muster + `_SUPPORTED_KEYS` (Triad 1). Steht **nicht** auf dem Tick-Pfad.
- Tick-Pfad = `orchestrator/scheduler.py`: vorkompilierte Bedingungen
  (`_CONDITION_CACHE`) + memoisierter Uhr-Anker (`core.protocol.timestamp_epoch_s`).
- Archive/ledger = `runtime/archive/<day>/<intent_id>/` via `FileTransport.archive()`,
  selbstgepflegt: `maybe_compact()` (alle 64 Schreibungen) → `compacted/<day>.jsonl`
  + `.manifest.json` + `.index.json` (Offset-Index) → `lookup_archived()`.
- Gate: `make check` = compile + ruff + mypy + **238 unittest** + e2e. Must stay green.
- Constitution Guard: `neu.config.json`, `core/config.py`, `core/policy.py` sind
  `human_only_globs` → **keine** neuen Konfigurationsknospen dort. Laufzeit-Knobs
  laufen über Umgebungsvariablen (`NEU_ARCHIVE_*`) oder CLI-Flags.
- Active loop focus rotation: A (IPC/Event-Bus) → B (Fast-Path Schema) → C (Ledger).
- Diese Sandbox-Box ist ~1,5× langsamer als die Triad-1-Box (unangetasteter
  `schemacheck.validate`: 95,0 µs hier vs. 60,7 µs dort). **Folgerung für alle
  künftigen Zyklen: Referenzwerte aus älteren Journal-Einträgen sind nicht
  vergleichbar — A/B immer in einem Prozess messen, nicht gegen das Journal.**

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

---

## 🔁 TRIAD Nº2 (2026-09-07)

### Cycle 1 — Focus A: Sub-ms IPC / Event-Bus (single serialization + UDS plane)

**Profile first.** An earlier assumption ("the per-event `flush()` is the cost") was
wrong. Isolated measurement of the default path `EventBus.emit` → `ConsoleSink`:

| component | µs/event |
|---|---|
| `emit` itself (seq, timestamp, record build) | 3.10 |
| `json.dumps(record)` inside **each** sink | 4.44 |
| `stream.write` + `flush` | 1.61 |
| `dict(record)` defensive copy in the sink | 0.03 |

→ **Serialization, not I/O, was the hot cost** — and it was paid *per sink*. With
`json.dumps` on a small dict already costing 1.7 µs of fixed encoder overhead, the
per-sink `dumps` is pure duplicated work whenever more than one consumer listens
(console + collector + dashboard/ring/UDS).

**Change.**
- `EventBus.emit` now renders the canonical JSON line **once** and shares it with
  every sink that declares `wants_prepared_line` via `write_prepared(record, line)`.
  Sinks without it keep the old `write(record)` contract — full fallback preserved.
- Rendering is **lazy**: if no subscribed sink wants text, nothing is serialized at
  all. That is the real production default (`--json`/quiet console + collector), so
  the orchestrator now pays **zero** JSON cost per tick event. A guard test spikes
  `_render_line` to catch a regression into eager rendering.
- Envelope is assembled by concatenation with a bounded literal cache
  (`_json_str`, 4096 entries) instead of encoding the fixed keys; only `payload`
  goes through `json.dumps`. Output is **byte-identical** to `json.dumps(record)`
  (verified over 144 payload/clock/escape combinations, incl. NaN/Inf/umlauts).
- New `orchestrator/uds.py`: `UDSBroadcastSink` (AF_UNIX `SOCK_DGRAM`, **non-blocking
  send**, drop counter, never raises) + `UDSBroadcastServer` (binds, chmod 0600,
  removes stale inodes, drains all queued datagrams per call). Sink marginal cost:
  `encode` 0.10 + `send` 0.74 µs. Opt-in via `watch --uds PATH [--uds-batch BYTES]`,
  consumed by `orchestrator bus tail --socket PATH`.
- `SharedMemoryRingSink.write_prepared` consumes the shared line: the ring stopped
  being the slow path (see Graveyard — triad 1 entry corrected below).
- `Event` gained `slots=True`. Latency neutral (3.06 → 3.08 µs measured, i.e. within
  noise) — the win is the **−18.8 %** footprint of a run that keeps its events.
- Ring hot-path overflow now **counts a drop** instead of raising `RingFull` per
  event (a slow reader must not push the bus into its per-event stderr error path);
  the direct `write()` API still raises for callers that want backpressure.

**Result (after)** — `scripts/nexus_bench.py`, same process, same host:

Measured in one process on one host; the "before" column is the triad-1 code path
replicated or reached through the compatibility `write()` route — not a journal value.

| metric | before | after | Δ |
|---|---|---|---|
| one event → 3 text consumers | **23.20 µs** | **11.59 µs** | **−11.61 µs (2.00×)** |
| marginal cost per extra text consumer | **6.62 µs** | **0.79 µs** | **8.4×** |
| shared-memory ring write (sink only) | **7.20 µs** | **2.43 µs** | **2.96×** |
| UDS delivery, burst (send + consumer drain) | 6.62 µs (serializing sink) | **2.35 µs** | 2.8× |
| UDS single-event round trip (send + recv) | — | 4.95 µs | — |
| one text sink (file + flush) | 9.95 µs | 10.01 µs | **wash** (by construction) |
| `emit` floor, no text sink | **2.95 µs** (triad-1 replica) | **2.98 µs** | **+0.03 µs (0.9 %)** |
| saturated UDS (no consumer) | would block forever | 9.44 µs, counted | never stalls the run |
| `Event` retained memory | 48.9 MB / 200k | **39.7 MB / 200k** | **−18.8 %** (`slots=True`) |

The single-sink case is a **wash by construction** (the bytes still have to be
encoded exactly once) — the win is structural: delivery cost no longer scales with
the number of consumers.

### Cycle 2 — Focus B: Fast-Path per-tick validation (compiled conditions + clock anchor)

**Profile.** `validate()` in `core/schemacheck.py` is **not** on the tick path (only
`orchestrator validate --schema`). What runs every tick, per trigger, is the raw
condition string, and what runs every tick *and every event* is the clock anchor:

| per-tick work (before) | µs/call | note |
|---|---|---|
| `evaluate_condition("elapsed >= 6", t)` | 0.841 | 90 % of it is `parse_condition` |
| `parse_condition` (`strip` + `re.fullmatch` + `float` + `op in tuple`) | 0.759 | result fixed at job creation |
| `ScheduleState.elapsed_s()` | 1.523 | re-parses immutable `t0` |
| `Timer.elapsed()` (per **event**, from `runner._emit`) | ~1.0 | same re-parse |

**Change.**
- `orchestrator/scheduler.py`: `parse_condition` = **cached compiled validator**.
  `_compile_condition()` holds the grammar, `_CONDITION_CACHE` (bounded, 512) maps
  the raw `when` text → `(op, value)`. Failures are deliberately **not** cached so
  the error keeps naming the offending text and a corrupt state still complains
  every tick. `_COMPARISONS` became a frozenset (it was a linear tuple scan).
- `core/protocol.py`: `timestamp_epoch_s()` — memoized epoch for immutable stamps,
  used by `Timer.elapsed()` and `ScheduleState.elapsed_s()` on their no-`now`
  fast path; the `now=` path is untouched (tests/`tick(now=…)` rely on it).

**Result (after):**

| metric | before | after | Δ |
|---|---|---|---|
| condition evaluation per call | **1.042 µs** | **0.181 µs** | **5.76×** |
| one tick, 8 triggers | **8.34 µs** | **1.45 µs** | **−6.89 µs/tick** |
| `elapsed_s()` per tick | **1.422 µs** | **0.598 µs** | **2.38×** |
| combined tick saving | — | **−7.71 µs/tick** | at `tick_s=0.05`: 154 µs/s/job |
| `schemacheck.validate` (untouched code path) | 60.7 µs (triad-1 host) | 95.0 µs (this host) | no change — host delta |

At the fastest supported tick (0.05 s) that is **~7.7 µs of CPU per tick per job**
returned, with zero semantic change (verified against the old parser over a table of
operators/thresholds in `tests/test_nexus_triad2.py`).

### Cycle 3 — Focus C: Ledger compaction, offset index, self-maintenance

**Profile** (400 entries → one 891 KB day snapshot):

| operation (before) | µs |
|---|---|
| find one `intent_id` in a snapshot (`read_jsonl` full scan) | **7 552** |
| `archive_stats()` (counts by parsing every record) | **8 356** |
| `verify_archive()` (re-parse + re-hash every field) | **21 357** |
| compaction of 400 entries | 183 ms |
| …and compaction was **manual only** (CLI) — the ledger had no bound in practice |

**Change.**
- `write_jsonl_indexed()`: the snapshot writer now derives the
  `intent_id → byte offset` table **while** it writes (line lengths are already
  known), and persists it as a sidecar `compacted/<day>.index.json`. Cost: 15.3 KB
  per 891 KB snapshot (**1.72 %**), and it is a *derived* artifact — never the
  source of truth.
- `FileTransport.snapshot_index()` memoizes per (mtime, size); a missing or
  mismatching sidecar is rebuilt by one scan and written back.
- `FileTransport.lookup_archived(intent_id)`: **one door for both ledger states** —
  compacted record via `seek` + `readline` + `json.loads`, expanded record via the
  day directory. Includes a parity check (the parsed line must carry the requested
  `intent_id`), so a stale/corrupt index can never return someone else's record;
  a mismatch falls back to a rebuild scan.
- `archive_stats()` reads `count` from the manifest instead of parsing the
  snapshot; falls back to a scan when no manifest exists (older snapshots).
- `verify_archive()` gained a **day-digest fast path**: `sha256_snapshot` in the
  manifest answers "unchanged?" in one hash pass; on mismatch it falls through to
  the deep per-record rehash and reports the exact field. `force=True` (or the old
  digest-less manifests) keeps the previous full behaviour.
- **Verify-before-prune**: `compact_archive()` now deep-verifies the snapshot it
  just wrote and **refuses to prune** if verification fails (day reported as
  `aborted`). Data integrity is ranked above storage savings.
- **Bounded without a human**: `archive()` runs the `maybe_compact()` gate every 64
  writes. Thresholds are module constants, overridable by `NEU_ARCHIVE_AUTOCOMPACT`,
  `NEU_ARCHIVE_COMPACT_DAYS`, `NEU_ARCHIVE_KEEP_RECENT`, `NEU_ARCHIVE_MIN_STALE`
  (env, not `neu.config.json` — that file is under the Constitution Guard).
  Defaults: only entries > 7 days old, newest 8 per day stay expanded, nothing
  happens below 64 stale entries → fresh/test runtimes are never touched.
- CLI: `archive lookup <intent_id>`, `archive verify [--deep]`, richer
  `archive stats` (stale counts, index state, digest prefix), `archive compact`
  now reports index size.

**Result (after):**

| metric | before | after | Δ |
|---|---|---|---|
| single-entry lookup (400-record snapshot) | **7 552 µs** | **80.9 µs** | **93.3×** |
| …cold (no sidecar; rebuild by scan, one time) | — | 387 µs | self-healing |
| `archive_stats()` | **8 356 µs** | **899 µs** | **9.3×** |
| `verify_archive()` | **21 357 µs** | **1 546 µs** | **13.8×** |
| tamper detection (both paths) | yes | **yes** | integrity intact |
| data loss on compaction | 0 | **0** (392 pruned, all 400 still resolvable) | — |
| storage: 400 dirs → 1 snapshot | 1.31 MB freed | snapshot 891 KB + index 15 KB | −32 % (wie Triad 1) |
| auto-compaction gate cost | — (didn't exist) | 63.5 µs per check, 1 per 64 archives | amortized ~1 µs/archive |

---

## The Graveyard (architectural dead ends)

- **UDS socket *transport* for intent delivery** — still NO. The cross-process
  contract between Orchestrator and Limbs is file-based *by design* (crash-replay +
  language neutrality, `orchestrator/transport.py`); converting intent delivery to
  UDS would break every Limb-subprocess test and give up replayability.
  **Triad 2 refinement:** the *observability plane* (event stream) has no such
  contract — it is fire-and-forget — so it moved to UDS as an **additional sink**
  (`orchestrator/uds.py`), with console/collector/file untouched as fallback.
- ~~**Shared-memory ring is not strictly faster than a buffered file write**~~ —
  **corrected in Triad 2.** It was slower only because it re-`json.dumps`'d each
  event itself (4.7–6.8 µs). With the shared line from the bus the ring write is
  **2.00 µs/event** (3.4×), i.e. now the *fastest* consumer. Kept opt-in, and it
  gained non-raising drop accounting so a stuck reader can't spam the bus.
- **`ensure_ascii=True` for the envelope** — measured 4.44 → 3.68 µs/event
  (0.77 µs) but escapes every umlaut (`\u00e4`) in a codebase whose event payloads
  carry German text. Rejected: unreadable logs are not a µs win.
- **Skipping the `record` dict when only line-sinks are attached** — worth ~0.6 µs
  but would make `write_prepared(record, line)` lie about its first argument and
  split the bus into two record shapes. Rejected; the collector needs it anyway.
- **Bigger `SO_RCVBUF` as UDS backpressure** — setting 4 MB raised the reported
  buffer but not the queue: AF_UNIX `SOCK_DGRAM` accepts ~278 datagrams regardless
  of size (per-datagram skb accounting + `net.unix.max_dgram_qlen`). Buffering is
  not a strategy here; the drop counter is.
- **`settimeout()` per datagram in `recv_batch`** — first draft paid a
  `setsockopt` for every datagram in a burst (~3 µs/event). Hoisted to twice per
  call (once "wait", once "don't block"): burst delivery is now 2.34 µs/event.
- **UDS batching as the default** — through the bus it is only a small win
  (8.58 vs 9.46 µs/event, and 2.35 µs/event at sink level in burst mode) because
  the per-event cost is dominated by `emit` + render, not by the syscall. It
  delays what a live `tail` sees, so it ships as an opt-in flag
  (`--uds-batch BYTES`) with that trade-off in the help text, never as the default.
- **Compiling `schemacheck.validate()` into a closure tree** — still tempting
  (95 µs per intent validation), but its only callers are `orchestrator validate
  --schema` and the parity tests: **not per tick**. Parked until a schema actually
  lands on the fast path. Focus B must not optimize cold code twice.

## System Quirks

- `FileTransport.write_json_atomic` does `os.fsync()` per write → ~ms cost per
  file. That is *correct* (crash-safety contract) and must NOT be removed for the
  standard path; do not "optimize" it away.
- The limb subprocess reads its intent via a file path; converting to UDS/stdin
  sockets would break `tests/` (real subprocess + real timers). Keep file transport.
- **AF_UNIX `SOCK_DGRAM` queue capacity is a *datagram count* (~278 on this box),
  not bytes.** A producer that outpaces its consumer hits `EAGAIN` after ~278
  events, so the sink must be non-blocking and count drops (it is).
- A UDS client `connect()` to a missing path raises `FileNotFoundError`
  immediately — cheap probe. But it must be `setblocking(False)` **after** the
  connect, or a full peer queue blocks the producer inside `send`.
- `sun_path` is limited to 108 bytes; `uds.py` falls back to the Linux abstract
  namespace (`\0neu-<path>`). No inode, no cleanup needed — but also no file
  permissions, so 0600 only applies to the filesystem variant.
- Socket files ignore `fchmod`-at-create; `chmod(path, 0o600)` **after** `bind()` is
  what works. Asserted by `test_socket_rechte_0600`.
- `bus tail` measures *idle*, not per-datagram latency: `--idle` must exceed the
  producer's startup (~1–2 s: interpreter + config + limb spawn) or the tailer quits
  before the first event arrives. That cost me one debugging cycle; default is 5 s.
- `int_YYYYMMDDT…` embeds the **creation** day, but archiving can happen one second
  later, i.e. on the next day. `lookup_archived` therefore tries the hinted day
  first, then all other days (days are few; O(1) in the common case).
- Compaction order is a data-integrity decision: snapshot (fsync, atomic) → index →
  deep verify → only then prune. A lost index is recoverable, lost data is not.
- The compacted snapshot hashes **canonical JSON** (compact separators), *not* raw
  file bytes — so `verify_archive()` is independent of `indent`/line-ending. The
  *day digest* (`sha256_snapshot`) hashes raw file bytes and is therefore
  formatting-sensitive by design: it detects any edit, the per-record digests
  localize it.
- `archive()` now triggers `maybe_compact()` every 64 writes. Benchmarks/tests that
  create many **aged** entries must set `NEU_ARCHIVE_AUTOCOMPACT=0` (the bench does).
- `_CONDITION_CACHE`, `_EPOCH_CACHE`, `_LITERAL_CACHE` are all **bounded** (clear at
  max). Never turn one into an unbounded dict: the tick path would grow the process
  forever, which is the same mistake as an unbounded ledger.
- `repr(float)` matches `json.dumps` for finite floats, but writes `nan`/`inf` where
  the encoder writes `NaN`/`Infinity` → `_json_number` delegates non-finite values.
  Found by the byte-parity test, not by the benchmark.

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

### Files changed (Triad 1)
- `orchestrator/events.py` — fast timestamp + single-record emit; ring sink hook.
- `orchestrator/ring.py` — NEW `SharedMemoryRingSink` / `SharedMemoryRingReader`.
- `core/schemacheck.py` — `_PATTERN_CACHE`, `_SUPPORTED_KEYS`, single-type fast path.
- `orchestrator/transport.py` — `archive_stats()`, `compact_archive()`, `verify_archive()`,
  `read_jsonl`/`write_jsonl_atomic`.
- `orchestrator/cli.py` — `orchestrator archive stats|compact` subcommands.
- `scripts/nexus_bench.py` — reproducible triad benchmark.
- `tests/test_nexus_triad.py` — NEW guards (3 tests).

---

## 📊 TRIAD Nº2 SUMMARY (benchmark deltas)

All numbers from `scripts/nexus_bench.py` (rewritten for this triad), measured
**in-process, both paths, same host, median of 3 runs**. Cross-host comparison
against triad-1 numbers is explicitly avoided (this box is ~1.5× slower).
Gate: compile + ruff + mypy + **241 tests** + e2e all green.

| Focus | Headline metric | Before | After | Δ |
|---|---|---|---|---|
| A | event → 3 text consumers | **23.20 µs** | **11.59 µs** | **2.00×, −11.61 µs** |
| A | marginal cost per extra consumer | **6.62 µs** | **0.79 µs** | **8.4×** |
| A | shared-memory ring write | 7.20 µs | **2.43 µs** | **2.96×** (graveyard fixed) |
| A | UDS burst delivery, producer+consumer | 6.62 µs | **2.35 µs** | **2.8×**, zero disk/pipe |
| A | retained-event memory | 48.9 MB/200k | **39.7 MB/200k** | **−18.8 %** |
| B | per-tick trigger eval (8 triggers) | 8.34 µs | **1.45 µs** | **5.76×, −6.89 µs/tick** |
| B | `elapsed_s()` per tick + per event | 1.42 µs | **0.60 µs** | **2.38×** |
| C | archived-ledger single-record lookup | **7 552 µs** | **80.9 µs** | **93.3×** |
| C | `archive_stats()` | 8 356 µs | **899 µs** | **9.3×** |
| C | `verify_archive()` | 21 357 µs | **1 546 µs** | **13.8×** |
| C | ledger growth | unbounded, manual | **self-compacting**, 0 records lost | bounded by policy |

**Not a regression, stated plainly:** the one-text-sink case is a wash
(9.95 → 10.01 µs) and the `emit` floor moved +0.03 µs (0.9 %) for the
per-sink capability probe — encoding has to happen exactly once either way. The
optimization is structural (cost no longer scales with consumer count), plus the
new plane removes the disk from the hot path when a live consumer exists.

### Files changed (Triad 2)
- `orchestrator/events.py` — shared-line fanout (`write_prepared`), lazy rendering,
  `_render_line` + bounded `_LITERAL_CACHE`, `render_record()`.
- `orchestrator/uds.py` — **NEW** `UDSBroadcastSink` + `UDSBroadcastServer`
  (non-blocking datagram broadcast, drop counting, stale-inode recovery,
  abstract-namespace fallback, 0600).
- `orchestrator/ring.py` — `write_prepared` fast path, non-raising drop accounting
  on the hot path (`dropped`), strict `write()` kept.
- `orchestrator/scheduler.py` — `_CONDITION_CACHE` + `_compile_condition`,
  frozenset `_COMPARISONS`, memoized `elapsed_s()`.
- `core/protocol.py` — `timestamp_epoch_s()` (+ `_EPOCH_CACHE`), fast `Timer.elapsed()`.
- `orchestrator/transport.py` — `write_jsonl_indexed`, `snapshot_index`,
  `lookup_archived`, `stale_entry_count`, `maybe_compact`, digest fast path in
  `verify_archive(force=…)`, verify-before-prune, manifest-based `archive_stats`,
  self-maintenance gate in `archive()`.
- `orchestrator/cli.py` — `watch --uds/--uds-batch`, `bus tail`,
  `archive lookup|verify`, richer `archive stats`.
- `scripts/nexus_bench.py` — rewritten: in-process A/B for all three focuses.
- `tests/test_nexus_triad2.py` — **NEW** 28 guards (line parity, lazy render,
  ring fanout/drop, UDS delivery/perms/no-consumer, condition parity + bounded
  caches, clock anchor, index rebuild, tamper both paths, no-data-loss, auto-compact,
  stale-socket takeover vs. live-listener refusal).
- `README.md` — the new opt-in ops surface.

### Next cycle (queue, do not re-litigate)
1. **Focus B:** compile `schemacheck` schemas once (`validate()` closure tree) —
   only once a schema lands on the tick path; today it's cold (95 µs, CLI-only).
2. **Focus A:** the remaining `emit` floor is 1.4 µs of `Event(...)` construction
   per call — an object *every* in-repo caller discards. `slots=True` was taken this
   cycle (memory, not speed). A read-only shared record view is still open, but
   `MappingProxyType` costs 0.4 µs, so measure before adopting.
3. **Focus C:** day digest is per-file; a **cross-day** digest manifest
   (`compacted/index.json` with per-day digests + counts) would let
   `archive verify` skip unchanged days *without* opening them at all.
4. Per-tick cost now dominated by `save()`'s `json.dumps` of the whole
   `ScheduleState` on every state change — delta-persistence is the next candidate.

### PR
**#10** — `⚡ Nexus: IPC & Core Performance Triad [2026-09-07T02:05:00Z]`
→ https://github.com/Finnlayy/NIO/pull/10 (`main` <- `arena/01a07962-nio`,
12 files, +2545/-189, `MERGEABLE`). commit `bb47077`.
Der fertige PR-Text liegt als `.nio/pr_triad2_body.md` im Branch.
