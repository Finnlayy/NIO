# NIO Architecture Map - Design

## Intent

The current `graphify-out/graph.html` is a repository-community graph. It is
useful as an evidence index, but it is not a readable explanation of how NIO
works. The primary visualization shall instead communicate both the canonical
MANAS/CIEL target from the supplied v8.1 PDF and the runtime path proven by the
repository: human speech through Apollo and the Orchestrator to registered
Limbs and their downstream systems.

The intended reader is a human operator who wants to understand and navigate
NIO without first knowing its file layout.

## Goals

- Make the main control flow legible from the first screen.
- Put Apollo at the visible center of the operator experience while showing
  MANAS: CIEL as the specified Ring-0 governance layer above it.
- Show Core/Kernel and the Orchestrator as the technical control center below
  Apollo rather than hiding them in statistical clusters.
- Fan out from the Orchestrator through the Limb Registry to individual Limbs.
- Show each Limb's downstream systems, data and feedback paths.
- Distinguish implemented, partial, specified-only and planned relationships.
- Preserve links back to source files and the full Graphify evidence graph.
- Reuse the existing extraction; do not perform another semantic extraction.

## Non-goals

- This is not a replacement for `graphify-out/graph.json` or its complete
  symbol-level evidence.
- This is not a generic force-directed repository browser.
- This is not an attempt to display every test, function, document or research
  note on the first screen.
- This does not change NIO runtime behavior or wire currently disconnected
  components together.
- `Architect/` is not part of the NIO main map. It may receive a separate map
  later.

## Anti-goals

The result fails if it again looks like hundreds of equal circles, if repeated
directory names such as `frontend - src (17)` dominate the view, or if planned
connections look indistinguishable from working runtime paths.

## Chosen approach

### Considered approaches

1. **Hand-authored static architecture diagram.** Clearest, but cannot expose
   evidence or stay synchronized with the registry.
2. **Filtered Graphify community graph.** Cheap to produce, but still allows
   clustering to determine the story and can fragment one subsystem into many
   technical communities.
3. **Hybrid architecture map.** A curated architectural backbone with details
   and evidence derived from the repository and existing Graphify output.

The hybrid architecture map was chosen because it preserves clarity while
keeping the result inspectable and evidence-backed.

## Primary topology

The default view is a directed, layered radial map:

```text
Human / microphone
        |
Speech input (local Whisper or disclosed browser speech)
        |
Apollo UI and terminal
        |
Core / Kernel / Intent
        |
Orchestrator / Policy / Timer / Event Bus / Ledger
        |
Limb Registry
   /    |     |      |       |        \
Trading Toolbox  REA   Speech   Vault   Bootstrap ...
   |      |     |       |       |        |
Sigma   MCPs   REA   speaches Obsidian Workspace/files
```

Apollo is the visual center. Core and Orchestrator form the inner technical
ring. Limbs form the next ring. External systems, storage and providers form
the outer ring. Feedback such as results, telemetry, audit events and approval
status travels back inward to Apollo.

Spatial distance is architectural, not statistical. Nodes do not drift into a
force-directed layout.

## Speech paths

The map must represent two distinct speech paths:

1. **Human dictation path:** microphone -> `MediaRecorder` or browser speech ->
   `/api/apollo/transcribe` -> local `speaches`/Whisper where selected -> draft
   text in Apollo -> explicit user Send.
2. **Agent/Kanban speech tool:** Orchestrator -> Speech Limb -> local
   `speaches`/Whisper -> Result.

Both may share the engine, but they must not be shown as the same control path.
Spoken text is not automatically executed, and approval/denial remains typed.

## Runtime truth and edge styles

Every edge has one of three visible states:

- **Implemented:** solid line. Directly supported by current code or registry.
- **Indirect:** dashed line. Coupled through HTTP, files, subprocesses, queues or
  another explicit adapter.
- **Planned:** dotted line. Documented target architecture but not productively
  wired in current code.

Hovering or selecting an edge shows its status, relation, evidence source and
source location. Inferred Graphify edges may appear only in a detail panel and
must be labelled `INFERRED`; they cannot silently become backbone edges.

## Main components

### Entry and control

- Human/operator
- Local speech engine and optional browser speech
- Apollo Orb, Terminal and Control Deck
- Apollo API/proxy routes
- Core Protocol, Kernel, Policy and Intent
- Orchestrator Runner, Scheduler, Event Bus, Audit/Ledger and Kanban control
  plane
- Limb Registry and shared `LimbBase`/`LimbContext`

### Limbs

The Limb ring is generated from `limbs/registry.json` so registered Limbs stay
visible without manually editing the diagram. Each Limb card includes its
operations, implementation file, status and downstream systems. The initial
map includes all Limbs currently registered in the checked-out repository, not
only the five present in the older Graphify snapshot.

### Excluded from the main map

- `Architect/`
- `.claude/worktrees/`
- tests and fixtures
- research notes and reports
- historical implementation plans and journals
- build outputs, runtime state, `node_modules`, `.next` and temporary data

These may be reached through an evidence/detail link but do not become primary
architecture nodes.

## Interaction

- Initial screen shows only the directed architectural backbone.
- Selecting a component opens a side panel with purpose, operations, source
  files, downstream dependencies and evidence.
- Selecting a Limb expands only that Limb's branch.
- A toggle shows or hides feedback paths such as telemetry, events, audit and
  results.
- A toggle shows planned connections; planned edges are hidden by default.
- A link opens the complete Graphify graph for symbol-level exploration.
- Search focuses architectural components and registered Limbs, not arbitrary
  low-level symbols by default.

## Data sources

- Curated component and layer definitions for the stable architectural
  backbone.
- `limbs/registry.json` for current Limb inventory and operations.
- Existing `graphify-out/graph.json` for evidence, source locations and optional
  details.
- Current source files and normative documentation for truth classification.

No LLM call or semantic re-extraction is required to generate the map.

## Outputs

- `graphify-out/nio-architecture.html`: primary interactive architecture map.
- A small deterministic generator script in `scripts/` so the map can be
  regenerated after registry or graph changes.
- The existing `graphify-out/graph.html` remains the complete repository graph.
- A validation summary listing backbone edges whose evidence cannot be resolved.

## Constraints

- Standard local browser delivery; no external service required.
- No secrets or runtime data embedded in the HTML.
- Deterministic output from repository state and existing graph data.
- Must remain useful if the full Graphify graph is temporarily absent: the
  curated backbone and registry-derived Limb ring still render, while evidence
  links degrade gracefully.
- The generator must not modify NIO runtime code.

## Builder decisions

The builder may choose the lightweight browser visualization library or plain
SVG/Canvas implementation already compatible with the repository. The choice
must support fixed layered positioning, keyboard navigation, tooltips and a
detail panel without requiring a hosted backend.

## Acceptance criteria

- A new viewer can describe the path from microphone to a Limb after looking at
  the initial screen without opening documentation.
- Apollo is visually central; Core/Orchestrator and Limb Registry are clearly
  distinct layers.
- Every registered Limb appears exactly once in the Limb ring.
- `Architect/` and low-level test clusters are absent from the main view.
- Implemented, indirect and planned edges are visually and textually distinct.
- Clicking Speech explains the two separate speech paths.
- Clicking a Limb shows evidence and source links when available.
- Generation performs no semantic extraction and consumes no LLM/API tokens.
- The existing complete graph remains unchanged.
