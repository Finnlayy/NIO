# NIO Usable Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a locally installable, speech-controllable NIO/Apollo release whose productive path from operator input through Ciel and the Orchestrator to safe Limbs is observable, testable, recoverable and understandable.

**Architecture:** Apollo is the operator interface; the existing NIO Orchestrator remains the execution authority. `apollo/ciel` becomes a policy-aware JIT routing layer through an explicit adapter rather than replacing the Orchestrator. The PDF hierarchy is treated as the canonical target model, while every shipped capability must be supported by current code, tests and runtime evidence.

**Tech Stack:** Python 3.11+, Next.js/TypeScript Apollo frontend, stdlib-first NIO runtime, SQLite, SSE/UDS telemetry, local speaches/faster-whisper, pytest/unittest, Node UI tests, Docker only for explicitly isolated optional workers.

**Spec:** `docs/superpowers/specs/2026-11-10-nio-architecture-map-design.md`

## Global Constraints

- Release 1 is local-first and single-operator; no cloud dependency is required for the core path.
- New trading behavior is paper-only. Live orders are not part of this release.
- Any future live-order mode requires hard limits and an emergency stop outside AI logic.
- No `.env*` except `.env.example`, credentials, keys, tokens, runtime databases, logs, `node_modules`, `.venv`, `target` or `dist` may be committed.
- Apollo speech never auto-submits a transcript; approval and denial remain typed-only.
- Planned PDF components are never labelled implemented without code, tests and runtime evidence.
- `Architect/` remains outside the productive NIO runtime unless a separate reviewed integration explicitly imports a capability.
- Existing dirty-worktree changes must be preserved and unrelated files must not be staged.
- Every implementation task uses a feature branch, targeted staging and a reviewable commit.
- Failures in optional MCP nodes or optional workers fail closed without taking down the core runtime.

## Release Definition

The release is usable when a new operator can install NIO from documented prerequisites, start it with one command, dictate or type an intent in Apollo, review and submit it, observe Ciel routing and policy decisions, execute an allowed active Limb through the real Orchestrator, receive a result in Apollo, inspect the audit trail, stop all work safely, restart without corrupting state, and diagnose common failures from the UI and documentation.

## Review Focus

- Malformed, oversized or adversarial speech/transcript input must remain a draft or produce a structured rejection, never implicit execution.
- Ciel unavailable, slow or internally failing must have an explicit fail-closed/fallback policy covered by integration tests.
- A registry entry marked `planned`, unknown, or changed during a run must never be launched accidentally.
- Process-tree cancellation must stop child processes and containers without leaving hidden workers behind.
- Paper-trading boundaries, approval tickets and the external emergency stop must remain effective even when the model, UI or telemetry layer fails.

---

## Phase 0 - Scope, truth and release governance

- [ ] **NIO-001 (P0): Freeze the Release-1 capability statement.** Add `docs/release/RELEASE_1_SCOPE.md` listing included operator flows, excluded capabilities and the exact meaning of “local-first”; review proves every later P0 item maps to an included flow.
- [ ] **NIO-002 (P0): Define the runtime source of truth.** Document that `orchestrator/runner.py` owns execution and `limbs/registry.json` owns Limb availability; no competing dispatcher may be introduced.
- [ ] **NIO-003 (P0): Create an implementation-status register.** Add `docs/release/IMPLEMENTATION_STATUS.md` with `implemented`, `partial`, `specified`, `planned` and evidence fields for every map component.
- [ ] **NIO-004 (P0): Record PDF-to-code mappings.** Map MANAS, Ciel, Primordials, kernels, RGCCO, Deep-Sea, memory and Apollo NCM to code, planned work or explicit non-goals without claiming semantic equivalence where none exists.
- [ ] **NIO-005 (P0): Define release tiers.** Specify Alpha, Beta and Release Candidate entry/exit gates, including allowed known issues and rollback criteria.
- [ ] **NIO-006 (P0): Establish ownership boundaries.** Name the responsible package and test suite for Apollo, Ciel, Orchestrator, Registry, each Limb, telemetry, installer and release documentation.
- [ ] **NIO-007 (P0): Create an architectural decision log.** Add `docs/adr/` and record the Ciel-adapter decision, local speech decision, paper-only trading decision and no-auto-submit decision.
- [ ] **NIO-008 (P0): Define compatibility floors.** Pin supported Linux distribution assumptions, Python, Node, browser, Docker and speaches versions in one machine-readable compatibility file.

## Phase 1 - Repository hygiene and reproducible baseline

- [ ] **NIO-009 (P0): Audit the current dirty worktree.** Classify every modified/untracked path by owner and purpose before staging anything; preserve unrelated user work.
- [ ] **NIO-010 (P0): Verify `.gitignore` coverage.** Add missing exclusions for local speech caches, runtime sockets, SQLite files, generated graphs, frontend builds and worker sandboxes while preserving intentionally tracked examples.
- [ ] **NIO-011 (P0): Scan tracked content for secrets.** Run a documented secret scanner against history and the working tree; release gate requires zero unresolved high-confidence findings.
- [ ] **NIO-012 (P0): Pin Python dependencies.** Produce a reproducible lock or constraints file for core, Ciel and test extras with hashes or an equivalent integrity mechanism.
- [ ] **NIO-013 (P0): Pin frontend dependencies.** Ensure the lockfile is current, deterministic and validated with a clean install in CI.
- [ ] **NIO-014 (P0): Capture the baseline test inventory.** Record every Python, Node and end-to-end suite, current pass/fail totals and environmental skips before implementation.
- [ ] **NIO-015 (P0): Remove generated artifacts from architecture inputs.** Ensure Graphify and release scripts exclude `.next`, caches, worktrees, runtime state and generated output from semantic claims.
- [ ] **NIO-016 (P0): Add a one-command baseline verifier.** Create `scripts/verify_baseline.sh` that performs formatting, static checks and existing core tests without mutating runtime state.

## Phase 2 - Canonical configuration and startup contract

- [ ] **NIO-017 (P0): Define a typed runtime configuration schema.** Consolidate ports, paths, speech endpoint, feature flags, timeouts and limits under `core/config.py` with validation and safe defaults.
- [ ] **NIO-018 (P0): Publish a safe `.env.example`.** Include variable names and non-secret placeholders only; tests reject real-looking keys and client-exposed secret prefixes.
- [ ] **NIO-019 (P0): Define configuration precedence.** Document and test defaults → config file → environment → explicit CLI arguments, including provenance shown in diagnostics without values for secrets.
- [ ] **NIO-020 (P0): Add startup preflight checks.** Verify writable runtime directories, available ports, Python/Node versions, registry validity and optional service reachability before starting workers.
- [ ] **NIO-021 (P0): Add structured startup diagnostics.** Produce machine-readable component status with `ready`, `degraded`, `blocked` and reason codes.
- [ ] **NIO-022 (P0): Implement one supported start command.** Add `neu start` or an equivalent canonical command that launches the productive stack and reports the Apollo URL.
- [ ] **NIO-023 (P0): Implement one supported stop command.** Stop the complete process tree idempotently, return nonzero on leftovers and provide their PIDs/containers without exposing secrets.
- [ ] **NIO-024 (P0): Implement a read-only doctor command.** `neu doctor` checks configuration, services, sockets, registry, storage and frontend build and suggests exact remediations.

## Phase 3 - Apollo operator experience

- [ ] **NIO-025 (P0): Add a real backend connection indicator.** Apollo must distinguish connected, reconnecting, offline and demo/mock data; the UI may never silently present mock state as live runtime state.
- [ ] **NIO-026 (P0): Add a runtime component panel.** Show health for speech, Ciel, Orchestrator, Registry, event stream and each optional worker with reason codes.
- [ ] **NIO-027 (P0): Add an intent review step.** Typed and dictated input must show target, operation, parameters, risk class and required approval before dispatch.
- [ ] **NIO-028 (P0): Preserve draft input across recoverable UI errors.** Reconnects and failed submissions must not silently discard the operator’s reviewed text.
- [ ] **NIO-029 (P0): Add explicit execution states.** Display queued, policy-checking, routing, awaiting approval, running, cancelling, succeeded, partial and failed.
- [ ] **NIO-030 (P0): Add result provenance.** Every result displays run ID, selected Limb, operation, start/end time, status and a link to its audit record.
- [ ] **NIO-031 (P0): Add accessible keyboard operation.** All core actions, confirmation dialogs and status panels must work without a mouse and expose correct ARIA labels.
- [ ] **NIO-032 (P1): Integrate the architecture map into Apollo.** Add a read-only `/architecture` route backed by the deterministic model, linked from navigation, with no separate manual HTTP server required.

## Phase 4 - Speech input suitable for daily use

- [ ] **NIO-033 (P0): Validate microphone capability before recording.** Explain insecure-origin, denied-permission and unsupported-browser failures without losing the current draft.
- [ ] **NIO-034 (P0): Make the local-vs-browser speech choice persistent and explicit.** Never fall back from local recognition to vendor recognition without operator selection.
- [ ] **NIO-035 (P0): Enforce the 60-second recording limit in UI and server paths.** Tests cover timeout, cancellation and late response disposal.
- [ ] **NIO-036 (P0): Enforce audio size and MIME allowlists.** Reject unsupported, empty and oversized uploads before forwarding to speaches.
- [ ] **NIO-037 (P0): Add transcription cancellation.** Closing the terminal, replacing a recording or pressing Cancel must abort the active request and ignore late results.
- [ ] **NIO-038 (P0): Harden slash-command normalization.** Only known explicitly spoken slash prefixes become commands; approvals and denials remain typed-only in German and English.
- [ ] **NIO-039 (P0): Add vocabulary diagnostics.** Show which vocabulary file is loaded, its timestamp and parse errors without exposing unrelated filesystem paths.
- [ ] **NIO-040 (P1): Add a local speech quality harness.** Store opt-in test fixtures without personal recordings and measure word error, latency, silence behavior and proper-name regression.

## Phase 5 - Ciel-to-Orchestrator productive wiring

- [ ] **NIO-041 (P0): Define the Ciel runtime adapter interface.** Create an adapter with typed `route(intent, state)`, `dispatch(decision)` and `close()` contracts; it may call the Orchestrator but not duplicate its execution rules.
- [ ] **NIO-042 (P0): Write a failing end-to-end adapter test.** Prove Apollo intent → Ciel decision → existing Orchestrator → Echo Limb → structured result using real registries and isolated temporary runtime state.
- [ ] **NIO-043 (P0): Mirror active registry operations into Ciel at startup.** Planned/deprecated Limbs remain visible for diagnostics but cannot receive executable handlers.
- [ ] **NIO-044 (P0): Synchronize registry reloads safely.** Version registry snapshots and prevent a decision produced against one version from silently executing against an incompatible version.
- [ ] **NIO-045 (P0): Define Ciel failure semantics.** Choose and test fail-closed behavior for risky operations and a narrowly scoped direct-Orchestrator fallback for explicitly safe local operations.
- [ ] **NIO-046 (P0): Propagate correlation IDs end to end.** Apollo request, Ciel events, policy decisions, Orchestrator attempt, Limb result and audit entry share one immutable run ID.
- [ ] **NIO-047 (P0): Connect Ciel telemetry to the productive event stream.** Verify cold-state, routing, JIT reload and macro events reach Apollo without blocking execution.
- [ ] **NIO-048 (P0): Remove contradictory runtime claims.** Update `docs/CIEL.md`, `docs/hermes/RUNTIME_PLAN.md` and status documents only after the productive path test passes.

## Phase 6 - Intent, routing and output contracts

- [ ] **NIO-049 (P0): Version the Intent schema.** Define required identifiers, target Limb, operation, parameters, risk metadata, deadlines and compatibility behavior for unknown versions.
- [ ] **NIO-050 (P0): Version the Result schema.** Require status, output, structured errors, partial artifacts, timings, evidence and schema version for every Limb.
- [ ] **NIO-051 (P0): Add strict boundary validation.** Reject unknown top-level fields where security-relevant, invalid Unicode/control characters, impossible deadlines and non-finite numeric values.
- [ ] **NIO-052 (P0): Add deterministic target resolution.** Ciel suggestions never override an explicit valid target without showing and recording the change for operator confirmation.
- [ ] **NIO-053 (P0): Add routing confidence rules.** Configure and test bypass/JIT thresholds, ties, no-match behavior and low-confidence escalation.
- [ ] **NIO-054 (P0): Add execution budgets.** Carry wall-clock, subprocess, output-size and retry budgets from intent through every adapter and Limb context.
- [ ] **NIO-055 (P0): Normalize structured errors.** Define stable codes for validation, policy, approval, registry, spawn, timeout, cancellation, dependency and internal failures.
- [ ] **NIO-056 (P1): Add deterministic response rendering.** Apollo renders known result types without asking an LLM to interpret security-sensitive status or approval data.

## Phase 7 - Policy, approvals and operator control

- [ ] **NIO-057 (P0): Inventory every operation by risk class.** Classify read-only, local-write, process, network, credential-adjacent, trading-paper and forbidden/live operations.
- [ ] **NIO-058 (P0): Make the policy matrix machine-readable.** Store default allow/deny/approval requirements by operation and profile with schema validation.
- [ ] **NIO-059 (P0): Integrate one-time approval tickets.** Bind tickets to run ID, operation, canonical argument hash, operator, expiry and one-time consumption.
- [ ] **NIO-060 (P0): Add typed-only approval enforcement.** Speech-derived events cannot resolve approval tickets even if their text resembles `/approve` or `/deny`.
- [ ] **NIO-061 (P0): Add policy decision explanations.** Apollo shows the matched rule, risk tier, required action and immutable decision ID.
- [ ] **NIO-062 (P0): Add a global execution pause.** The operator can prevent new dispatches while allowing inspection and controlled cancellation of existing runs.
- [ ] **NIO-063 (P0): Add an external emergency-stop mechanism.** Implement a local mechanism outside model logic that blocks new process/trading actions and is checked by the Orchestrator immediately before execution.
- [ ] **NIO-064 (P0): Test degraded-control behavior.** If Apollo, Ciel or telemetry dies, the emergency stop and policy enforcement must still prevent disallowed execution.

## Phase 8 - Limb lifecycle and isolation

- [ ] **NIO-065 (P0): Validate the registry against a JSON Schema.** Reject duplicate operations, missing entrypoints, invalid statuses, unknown runtimes and unsafe environment allowlists.
- [ ] **NIO-066 (P0): Verify entrypoint integrity at startup.** Resolve paths beneath the repository root and reject symlinks or traversal that escape allowed roots.
- [ ] **NIO-067 (P0): Enforce active-only dispatch twice.** Check status during routing and immediately before spawn to close reload races.
- [ ] **NIO-068 (P0): Start every Limb in a new process group.** Cancellation and timeout must terminate descendants with a bounded TERM-to-KILL sequence.
- [ ] **NIO-069 (P0): Sanitize Limb environments.** Begin from a minimal environment and inject only explicitly allowed variables and runtime necessities.
- [ ] **NIO-070 (P0): Bound stdout and stderr capture.** Prevent memory exhaustion, preserve a truncated diagnostic tail and record truncation in the result.
- [ ] **NIO-071 (P0): Clean temporary intent/result files.** Use private permissions, atomic writes and lifecycle cleanup while retaining explicitly configured audit artifacts.
- [ ] **NIO-072 (P0): Add a lifecycle conformance suite.** Run ping, valid operation, invalid operation, timeout, cancellation, malformed output and crash tests against every active Limb.

## Phase 9 - Limb-specific release readiness

- [ ] **NIO-073 (P0): Certify Echo as the release canary.** Use Echo for startup, routing, cancellation and schema smoke tests with no side effects.
- [ ] **NIO-074 (P0): Certify Speech Limb locality.** Reject non-loopback endpoints by default, test engine outage and prove audio bytes are not logged.
- [ ] **NIO-075 (P0): Harden Bootstrap path controls.** Test traversal, symlink escape, stale expected hashes, atomic patches, write elevation and sandbox boundaries.
- [ ] **NIO-076 (P0): Harden Vault trust boundaries.** Mark retrieved notes as untrusted content, limit writes to approved directories and test FTS corruption/rebuild behavior.
- [ ] **NIO-077 (P1): Certify REA sandbox cleanup.** Verify installation, analysis, timeout, disk budget, cancellation and evidence retention without touching unrelated files.
- [ ] **NIO-078 (P0): Keep OpenManus blocked.** Add a test proving its `planned` status cannot be overridden by a Ciel route, UI request or stale handler.
- [ ] **NIO-079 (P0): Certify Trading in paper-only mode.** Verify every start/backtest/lake path has no exchange order route, uses a separate sandbox and exposes paper status in Apollo.
- [ ] **NIO-080 (P1): Certify Toolbox catalog consistency.** Ensure search/describe returns only current registry operations, status and safe descriptions with no secret environment values.

## Phase 10 - State, memory and recovery

- [ ] **NIO-081 (P0): Define persistent versus ephemeral state.** Document ownership, schema, retention and deletion rules for audit, Ciel cache, registry snapshot, Kanban, Vault and worker state.
- [ ] **NIO-082 (P0): Add schema migrations.** Every persistent SQLite store has a version table, forward migration, backup step and tested failure rollback.
- [ ] **NIO-083 (P0): Add atomic run-state transitions.** A crash cannot leave one run simultaneously shown as queued and completed or consume approval twice.
- [ ] **NIO-084 (P0): Reconcile interrupted runs on startup.** Mark orphaned runs interrupted, check for surviving processes and require explicit operator action before retry.
- [ ] **NIO-085 (P0): Add bounded retention.** Configure maximum age and size for logs, telemetry, temporary artifacts and caches with a dry-run cleanup report.
- [ ] **NIO-086 (P0): Add backup and restore commands.** Back up configuration metadata, persistent stores and audit indexes without secrets; verify restore into a clean temporary installation.
- [ ] **NIO-087 (P1): Implement memory provenance.** Any recalled Vault/Ciel memory shows source, timestamp, trust classification and the run that consumed it.
- [ ] **NIO-088 (P1): Add corruption recovery drills.** Test unreadable SQLite, partial JSON, missing directories and disk-full behavior with actionable operator messages.

## Phase 11 - Telemetry, audit and diagnostics

- [ ] **NIO-089 (P0): Define a versioned event envelope.** Include event ID, run ID, timestamp, producer, type, schema version and redaction classification.
- [ ] **NIO-090 (P0): Redact secrets at emission.** Apply centrally tested key/value and pattern redaction before events reach logs, UDS, SSE or Apollo.
- [ ] **NIO-091 (P0): Make telemetry loss visible.** Count dropped queue events, reconnect gaps and subscriber errors without blocking the execution path.
- [ ] **NIO-092 (P0): Add an Apollo run timeline.** Render intent, policy, approval, Ciel route, dispatch, Limb lifecycle and result in timestamp order.
- [ ] **NIO-093 (P0): Add audit-chain integrity.** Hash-link immutable security-relevant records or provide an equivalent tamper-evident mechanism with a verifier command.
- [ ] **NIO-094 (P0): Separate operator and debug detail.** Default UI messages remain understandable while expandable diagnostics retain structured codes and evidence.
- [ ] **NIO-095 (P1): Add performance metrics.** Measure speech latency, routing latency, queue time, Limb duration, result size and UI delivery without recording transcript content by default.
- [ ] **NIO-096 (P0): Add a support bundle generator.** Export redacted configuration metadata, versions, health, recent error codes and test summaries; never include secrets or raw personal audio.

## Phase 12 - Security and adversarial validation

- [ ] **NIO-097 (P0): Threat-model the complete operator path.** Cover speech injection, prompt injection, malicious Vault notes, registry tampering, MCP compromise, subprocess escape, SSRF and frontend trust confusion.
- [ ] **NIO-098 (P0): Add prompt-injection boundaries.** Treat PDF, webpages, Vault notes, tool output and MCP descriptions as untrusted data that cannot grant permissions or alter policy.
- [ ] **NIO-099 (P0): Restrict outbound network destinations.** Define per-component allowlists and default-deny behavior for Limbs that do not require network access.
- [ ] **NIO-100 (P0): Harden MCP configuration.** Permit environment references but reject embedded credentials, unsafe commands, unbounded timeouts and unexpected transports.
- [ ] **NIO-101 (P0): Add dependency vulnerability gates.** Scan Python, Node and container dependencies; document triage and block release on unresolved exploitable critical findings.
- [ ] **NIO-102 (P0): Add static security checks.** Detect shell injection, unsafe subprocess usage, path traversal, weak temporary files and client-exposed secrets in touched code.
- [ ] **NIO-103 (P0): Run abuse-case integration tests.** Include malicious filenames, huge outputs, malformed JSON, forged approval IDs, stale tickets, hostile note content and registry swaps.
- [ ] **NIO-104 (P0): Commission an independent security review.** Resolve or explicitly accept every finding with owner, severity, rationale and expiry before Release Candidate.

## Phase 13 - Test pyramid and continuous integration

- [ ] **NIO-105 (P0): Establish unit-test gates by package.** Core, Ciel, Orchestrator, Limbs and Apollo utility tests must pass independently with deterministic seeds and temporary state.
- [ ] **NIO-106 (P0): Add contract tests across boundaries.** Pin Intent, Result, event, policy, approval, registry and SSE schemas for Python and TypeScript consumers.
- [ ] **NIO-107 (P0): Add a real-stack local E2E suite.** Start temporary services, submit an Echo intent from Apollo, observe Ciel/Orchestrator events and verify the rendered result and audit trail.
- [ ] **NIO-108 (P0): Add failure-path E2E tests.** Cover speech down, Ciel down, unknown Limb, planned Limb, policy denial, approval expiry, timeout, cancellation and malformed result.
- [ ] **NIO-109 (P0): Add browser coverage.** Test the supported Chrome/Edge versions and a no-Web-Speech browser path, including keyboard and responsive layouts.
- [ ] **NIO-110 (P0): Add clean-install CI.** Build and test from an empty cache using only tracked files and documented system prerequisites.
- [ ] **NIO-111 (P0): Add an artifact reproducibility check.** Two builds from the same commit must produce equivalent packages excluding declared timestamps/signatures.
- [ ] **NIO-112 (P0): Publish a release-gate summary.** CI emits pass/fail evidence for every P0 gate and refuses to label a candidate when any mandatory gate is missing.

## Phase 14 - Installation, packaging and upgrades

- [ ] **NIO-113 (P0): Choose one supported installation path.** Document package/container/system-service boundaries and remove competing “maybe” startup instructions from the primary guide.
- [ ] **NIO-114 (P0): Create an idempotent installer.** Re-running it preserves configuration, verifies dependencies and never overwrites operator data silently.
- [ ] **NIO-115 (P0): Package the frontend and backend compatibly.** Embed or version-match Apollo assets with the runtime API and reject incompatible combinations clearly.
- [ ] **NIO-116 (P0): Add a service definition.** Provide a user-level service with restricted permissions, controlled restart behavior and no automatic privilege escalation.
- [ ] **NIO-117 (P0): Add an upgrade preflight.** Back up state, verify disk space and compatibility, show migrations and allow abort before mutation.
- [ ] **NIO-118 (P0): Add a rollback procedure.** Restore the previous package and compatible state snapshot, then verify Apollo, Orchestrator and audit access.
- [ ] **NIO-119 (P1): Add offline installation support.** Document and test how pinned packages, containers and speech model artifacts are staged without internet access.
- [ ] **NIO-120 (P0): Add uninstall behavior.** Remove executables/services while preserving operator data by default and requiring explicit confirmation for data deletion.

## Phase 15 - Documentation and operator onboarding

- [ ] **NIO-121 (P0): Write a 15-minute quick start.** A new operator reaches Apollo, types an Echo intent and sees a verified result without reading architecture internals.
- [ ] **NIO-122 (P0): Write the speech setup guide.** Include local Whisper installation, browser alternative disclosure, permissions, vocabulary, latency expectations and troubleshooting.
- [ ] **NIO-123 (P0): Write the safety model.** Explain risk classes, approvals, typed-only decisions, pause, emergency stop, paper trading and prohibited live behavior.
- [ ] **NIO-124 (P0): Publish the architecture truth map.** Integrate the generated map, status definitions and evidence links and make clear what comes only from the canonical PDF.
- [ ] **NIO-125 (P0): Write operation runbooks.** Cover start, stop, doctor, backup, restore, upgrade, rollback, speech failure, stuck run and surviving child process.
- [ ] **NIO-126 (P0): Write a Limb authoring guide.** Specify registry entry, schemas, environment allowlist, process/output contracts, risk review and conformance tests.
- [ ] **NIO-127 (P1): Add an in-product guided tour.** Point to connection state, voice controls, review, approvals, run timeline, architecture and emergency stop without blocking expert use.
- [ ] **NIO-128 (P0): Remove stale contradictions.** Search all README/blueprint/plan files for obsolete claims and label historical documents so they cannot be mistaken for current runtime truth.

## Phase 16 - Release candidate, field trial and release

- [ ] **NIO-129 (P0): Cut an internal Alpha from a clean branch.** Build from a tagged commit with generated SBOM, checksums, test summary and known-issues file.
- [ ] **NIO-130 (P0): Run a seven-day local dogfood trial.** Record starts, speech attempts, routed intents, failures, cancellations and recovery events without collecting personal content by default.
- [ ] **NIO-131 (P0): Triage every Alpha failure.** Assign severity, owner, reproduction, workaround and release decision; no unexplained execution or approval anomaly may remain.
- [ ] **NIO-132 (P0): Cut Beta after P0 functional gates pass.** Install it on a clean machine/profile and upgrade an Alpha installation with preserved state.
- [ ] **NIO-133 (P0): Conduct operator acceptance scenarios.** A non-developer completes install, voice draft, typed intent, approval, Echo/Speech/Vault action, cancellation, doctor and restart from documentation.
- [ ] **NIO-134 (P0): Run disaster-recovery acceptance.** Simulate process crash, disk-full warning, corrupted cache, speech outage and interrupted upgrade and recover without unsafe execution.
- [ ] **NIO-135 (P0): Freeze the Release Candidate.** Permit only reviewed release-blocker fixes; rerun clean install, upgrade, security, E2E, backup/restore and rollback gates after every fix.
- [ ] **NIO-136 (P0): Publish Release 1.0.** Tag the verified commit, publish checksums/SBOM/release notes, archive evidence, document rollback and open a post-release monitoring window.

## Release gates summary

Release 1.0 is blocked unless all of the following are true:

- [ ] All 112 P0 items above are complete or an exact recount in this document shows the corrected total after priority changes.
- [ ] The productive Apollo → Ciel → Orchestrator → active Limb test passes from a clean installation.
- [ ] Speech never auto-submits and cannot resolve approvals.
- [ ] Planned Limbs cannot execute.
- [ ] Paper-only trading is proven; no live-order route is reachable.
- [ ] The external emergency stop works with Apollo, Ciel and telemetry unavailable.
- [ ] Stop/cancel leaves no child processes or containers.
- [ ] Backup, restore, upgrade and rollback pass on release artifacts.
- [ ] Secret, dependency and independent security reviews have no unresolved release-blocking findings.
- [ ] Architecture/status documentation matches the released commit and labels PDF-only components as specified rather than implemented.

## Recommended execution order

1. Complete Phases 0-2 to freeze truth, configuration and lifecycle contracts.
2. Complete Phases 5-8 to establish the real safe execution spine.
3. Complete Phases 3-4 to make that spine usable from Apollo and speech.
4. Complete Phases 9-12 to certify capabilities, recovery, observability and security.
5. Complete Phases 13-15 to make installation and operation reproducible.
6. Execute Phase 16 only from clean release branches with all P0 gates visible in CI.

## Self-review result

- Spec coverage: operator flow, PDF/runtime distinction, Ciel bridge, registry fan-out, speech split, evidence links and planned/implemented status are mapped to tasks.
- Type consistency: the plan introduces one Ciel adapter, one versioned Intent, one versioned Result and one event envelope; later phases consume those boundaries rather than inventing alternatives.
- Failure coverage: malformed input, Ciel failure, registry races, process-tree cancellation and external emergency-stop behavior are explicit P0 tests.
- Scope control: full semantic MANAS/Primordial personalities, cloud deployment, multi-user authorization and live trading remain outside Release 1 unless separately specified and reviewed.
