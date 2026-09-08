# OMEGA Architect — Divergence Log

Documented, intentional divergences between the Omega Blueprint
(`docs/ARCHITECTURE.md`, `docs/NEU.md`, `protocol/PROTOCOL.md`) and Jules's
`Architect/` implementation. Updated per phase (Phase 3 → 5).

| # | Area | Blueprint | Architect | Rationale |
|---|------|-----------|-----------|-----------|
| 1 | Dependency model | Python 3.11+, stdlib-only | PyQt6, torch/onnx, qdrant-client, google-genai, ccxt.pro | Jules's stack is a desktop trading terminal; external services are the product. The **learning core** (Phases 4–5) is stdlib-only by design. |
| 2 | Transport | File-based, deterministic, auditable | External APIs + Qdrant cloud + WebSocket feeds | Domain requirement; the event bus still writes a file sink (`runtime/system.log`) as the auditable backbone. |
| 3 | Protocol | Protocol 1.2 (492-line normative spec) | Lightweight JSON schemas (`schemas/*.schema.json`) + mini validator (`core/schema_utils.py`) | No `jsonschema` dependency; validator mirrors the schema subset actually used (`type`, `required`, `enum`, `minimum/maximum`, `oneOf`). |
| 4 | Event bus transport | stderr + shared-memory ring + UDS | stderr NDJSON + file sink (`runtime/system.log`) | Shared-memory ring deferred; file sink is the Phase 5 trajectory source. |
| 5 | Archive | NDJSON ledger, cross-day verification | Per-job JSON + `.history.jsonl` + SHA-256 digest | Human-inspectable artifacts; digests provide the audit property. |
| 6 | UI stack | React/Next.js web frontend | PyQt6 desktop terminal | Product decision (Phase 1). |
| 7 | **GUI imports (P4/P5)** | n/a | Phase 4/5 GUI modules use *guarded* imports (`try: from PyQt6...`) with headless logic classes (`FeedbackSubmission`, `TrajectoryModel`, `AlignmentDashboardModel`) | Lets the full 214-test suite run without a desktop stack; widgets raise a clear `RuntimeError` when PyQt6 is missing. Phase 1 GUI files keep hard imports. |
| 8 | **Preference model (P4)** | TODO sketch: ONNX weights (`runtime/models/updated_<ts>.onnx`) | Stdlib logistic regressor over hashed bag-of-words features, stored as JSON + SHA-256 (`updated_<timestamp>.json`) | torch/onnx are unavailable to the learning core path; deterministic, seed-fixed SGD keeps training auditable and portable. The ONNX regime model (`models/weights/omega_regime_16d.onnx`) is untouched. |
| 9 | **Trajectory visualization (P5)** | TODO sketch: matplotlib/pyqtgraph (optional) | Plain `QPainter` timeline | Zero additional dependencies; `TrajectoryModel` keeps all data prep headless and testable. |
| 10 | **Skill profiling (P4)** | `src/learning/algorithm.ts` (TS) | Direct Python port of `wilsonLowerBound` + SM-2 variant | Formula parity verified by reference-value tests (e.g. Wilson(1,1)=0.2065, (5,5)=0.5655, (50,50)=0.9287). |
| 11 | **Error pattern fingerprint (P4)** | Token-based task signature | Fingerprint = error *type* (`E_SAFETY_NET`, ...), samples retained per pattern | TODO Phase 4 specifies grouping "by type"; token-level fingerprints made same-type occurrences fragment. |
| 12 | **Alignment formula (P5)** | n/a (beyond blueprint) | `0.5*preference + 0.3*guard_pass_rate + 0.2*learning_efficiency`, documented in PHASES.md |TODO Phase 5 example formula, adopted verbatim with component fallbacks. |
| 13 | Default paths | `runtime/` under repo/process root | Defaults assume repo-root CWD (`Architect/runtime/...`); schema paths resolve from module location | Matches Phase 1–3 convention; every constructor accepts overrides so tests inject tempdirs. |

## Non-divergences (kept aligned)

- Event whitelist (`VALID_EVENT_KINDS`) extended with `risk_guard_failed` /
  `risk_guard_warning` in Phase 4; all other Phase 4/5 kinds were pre-whitelisted.
- Manifest validation (`validate_manifest_update`) remains the single gate for
  self-modification, including plans produced by the learning loop (Phase 5 test
  asserts a denied path is still rejected).
- Wilson / SM-2 semantics mirror the blueprint algorithm files.
