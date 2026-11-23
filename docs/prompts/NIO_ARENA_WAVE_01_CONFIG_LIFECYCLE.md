# Arena Agent — NIO Release Wave A: Configuration and Lifecycle

## Role and objective

You are the coordinating implementation agent for `Finnlayy/NIO`. Work in
**Agent Mode** on repository `Finnlayy/NIO`, starting from branch `main`.

Deliver one integrated, reviewable result branch that makes NIO's configuration
and local lifecycle operational, deterministic and diagnosable. Implement the
equivalent of backlog items NIO-017 through NIO-024:

1. typed runtime configuration,
2. safe `.env.example`,
3. tested configuration precedence and provenance,
4. startup preflight checks,
5. structured startup diagnostics,
6. one supported start command,
7. one supported idempotent stop command,
8. one read-only doctor command.

This is a complete implementation assignment, not a proposal or planning-only
task. Preserve and extend existing working behavior rather than replacing it
with a parallel framework.

## Repository truth and starting context

- `orchestrator/runner.py` remains the sole execution authority.
- `limbs/registry.json` remains the source of Limb availability.
- `core/config.py` already contains `NeuConfig`, path normalization, limits,
  timers and JSON loading. Reuse and extend it instead of introducing a second
  configuration system.
- `orchestrator/cli.py` already contains the NIO CLI and existing status,
  validation, stop/resume and execution-related commands. Extend the existing
  CLI instead of creating a competing executable.
- Release 1 is local-first and single-operator.
- Trading remains paper-only. No live-order behavior belongs in this task.
- The working repository may contain historical or generated artifacts. Treat
  current tracked code and tests as evidence; do not infer behavior from names.

## Internal multi-agent cascade

Coordinate an internal multi-agent cascade, but return one integrated branch:

1. **Repository analyst:** map existing config, CLI, service, registry and test
   behavior; identify compatibility obligations before edits.
2. **Configuration engineer:** implement typed settings, precedence, provenance
   and redacted diagnostics.
3. **Lifecycle engineer:** implement preflight, canonical start/stop and doctor
   behavior without bypassing the existing Orchestrator.
4. **Test engineer:** write failing tests first, then contract, integration and
   failure-path tests using temporary runtime state.
5. **Security reviewer:** inspect secret handling, path containment, process
   cleanup, permission boundaries and command injection risks.
6. **Integrator:** resolve the agents' work, run all required tests, inspect the
   final diff and produce the evidence report.

Internal agents must not edit the same files concurrently. The coordinator must
assign file ownership, serialize overlapping changes and integrate all work
before reporting completion.

## Required behavior

### A. Typed configuration

Extend the existing `NeuConfig` contract so the productive stack has one typed,
validated source for at least:

- repository, runtime, workspace and protocol paths,
- Apollo and Kanban host/port settings,
- local speech endpoint and relevant timeout/size limits,
- feature flags used by the productive local stack,
- Orchestrator deadlines, grace periods and output limits,
- registry path and optional-service settings.

Use safe local defaults. Preserve existing callers. Reject invalid types,
out-of-range ports, unsafe paths and contradictory settings with actionable,
structured errors.

### B. Configuration precedence and provenance

Implement and test this precedence, with later sources winning:

```text
built-in defaults
→ repository configuration file
→ environment variables
→ explicit CLI arguments
```

Diagnostics must show the provenance of non-sensitive settings without exposing
secret values. Secret-like names and values must be redacted. Never print full
environment contents.

### C. Safe example environment

Add or update `.env.example` with variable names and safe, obviously non-secret
placeholders only. Do not add real-looking keys, tokens, passwords, private
keys, cookies or account identifiers. Add a test that rejects secret values and
client-exposed secret prefixes such as `VITE_` or `NEXT_PUBLIC_` for server-side
credentials.

### D. Preflight

Before starting the productive stack, check at least:

- supported Python and Node versions,
- required tracked files and frontend package metadata,
- valid registry structure and resolvable active Limb entrypoints,
- runtime directory creation and write access,
- configured ports and local socket paths,
- required frontend build availability or an actionable build requirement,
- local speech availability as optional/degraded unless explicitly required,
- optional services without making the core depend on them.

Preflight must not start workers or mutate operator databases. It may create and
remove a private temporary probe inside the configured runtime directory when
needed to prove write access.

### E. Structured diagnostics

Provide a stable machine-readable diagnostic structure with component states:

```text
ready | degraded | blocked
```

Each non-ready state needs a stable reason code, human-readable explanation and
an exact remediation hint. Support a human-readable rendering and JSON output.
Do not mislabel absent optional services as fully ready.

### F. Canonical start command

Implement one supported command using the existing CLI namespace, preferably:

```text
neu start
```

or the closest compatible command consistent with current repository naming.
It must:

- run preflight first,
- fail closed on blocked prerequisites,
- launch the documented productive local stack without a second dispatcher,
- report the Apollo URL and component states,
- use explicit process ownership suitable for subsequent stop,
- avoid shells where direct argument-vector execution is possible,
- never expose environment secrets in output or process arguments.

Do not silently operate on the currently running machine services during tests.

### G. Canonical stop command

Implement one supported idempotent stop command that:

- stops only processes proven to belong to this NIO launch,
- validates process identity rather than trusting a stale numeric PID,
- performs bounded graceful termination followed by bounded hard termination,
- reports leftovers with structured evidence,
- returns nonzero when owned processes or containers remain,
- succeeds safely when the stack is already stopped,
- never kills unrelated processes.

Do not redesign the independent emergency STOP semantics. Lifecycle shutdown and
execution emergency-stop are separate concepts and must remain distinguishable.

### H. Read-only doctor command

Implement a read-only command, preferably:

```text
neu doctor
```

It must inspect configuration, provenance, versions, registry, paths, ports,
sockets, frontend build compatibility, local speech and known optional services.
It must never start or stop workers, change STOP state, modify operator data,
repair files automatically or contact non-local network destinations. Offer
human and JSON output with exact remediation steps.

## TDD and verification requirements

Write failing tests before implementation. Use temporary directories, temporary
ports and fake processes. Tests must not read the user's real `.env`, touch the
real `runtime/STOP`, use live ports, invoke live trading, contact external
services or mutate operator databases.

Required test coverage includes:

1. configuration precedence for every source,
2. provenance without secret disclosure,
3. invalid ports, unsafe paths and malformed values,
4. safe `.env.example` scanning,
5. preflight ready/degraded/blocked outcomes,
6. occupied port and unwritable runtime failures,
7. missing optional speech versus explicitly required speech,
8. start refusal on blocked preflight,
9. deterministic owned-process startup using fakes,
10. idempotent stop,
11. stale PID and unrelated-process protection,
12. TERM-to-KILL escalation using disposable fake children,
13. doctor read-only behavior,
14. human and JSON diagnostic rendering,
15. backward compatibility for existing config and CLI tests.

Run targeted new tests first, then all existing tests affected by config, CLI,
registry, STOP and process lifecycle. Run the broadest safe repository test
suite available without reaching live services. Report every skipped suite and
the exact reason.

## Allowed paths

You may modify only files needed for this wave, primarily:

```text
core/config.py
orchestrator/cli.py
new focused lifecycle/config modules under core/ or orchestrator/
tests focused on configuration, CLI, preflight, doctor and lifecycle
.env.example
focused documentation for these commands
```

Small compatibility edits elsewhere are allowed only when unavoidable and must
be individually justified in the final report.

## Forbidden overlap and actions

Other workers are currently changing separate areas. Do not modify:

```text
core/protocol.py or new Intent/Result contract modules
core/telemetry.py
tests/test_telemetry.py
orchestrator/runner.py subprocess output/capture implementation
frontend/
limbs/registry.json or its schema
Toolbox capability declarations or handlers
Architect/
graphify-out/
runtime/
```

Also forbidden:

- live trading, order placement or broker credential handling,
- changing paper-only boundaries,
- granting OpenManus exchange tools or keys,
- committing `.env` files other than `.env.example`,
- embedding tokens, credentials or private user data,
- force-push, history rewrite or bypassing hooks,
- broad `git add .`,
- deleting or rewriting unrelated work,
- claiming success from mocks alone,
- adding a second dispatcher or replacing the existing Orchestrator authority,
- accessing deployment, Vercel or production services in this wave.

If a required implementation would violate a forbidden overlap, stop that
specific subtask, document the dependency and continue with independent work.

## Quality and evidence gate

Before completion:

1. inspect `git status`,
2. inspect the complete diff and `git diff --check`,
3. scan touched content for secret-like material,
4. run all required targeted tests,
5. run relevant existing regression tests,
6. prove tests use isolated runtime state,
7. verify no forbidden paths changed,
8. verify no live-order route was introduced,
9. verify start/stop/doctor help output,
10. record unresolved dependencies honestly.

Do not describe an untested path as working. Do not mark a component ready when
only a schema or mock exists.

## Exact final response contract

Return one final report with these sections:

1. **Outcome** — concise implemented result.
2. **Base and result** — base commit, result branch and final commit(s).
3. **Backlog mapping** — NIO-017 through NIO-024, each marked implemented,
   partial, blocked or not applicable with file/test evidence.
4. **Changed files** — every changed file and why.
5. **Configuration contract** — fields, precedence and provenance behavior.
6. **Lifecycle contract** — exact start, stop and doctor behavior.
7. **Tests** — exact commands, pass/fail/skip counts and isolation evidence.
8. **Security review** — secrets, path/process safety and paper-only result.
9. **Known limitations** — no omissions.
10. **Rollback** — safe revert boundaries.
11. **Machine-readable summary** — JSON object containing status, backlog IDs,
    commits, changed files, test commands/results, blocked items and follow-ups.

Completion requires implementation plus passing evidence. A plan, partial code
dump or prose-only answer is not completion.
