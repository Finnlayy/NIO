# J10: Real data on /ops (NIO)

Branch: `jules/j10-ops-echtdaten`

Files: `frontend/src/app/ops/page.tsx`, a new read-only route under `frontend/src/app/api/ops/`, frontend tests.

## Gap

`/ops` shows simulated data. `frontend/src/app/ops/page.tsx` fills widgets with `Math.random()` in a timer.

## Required result

- Widgets with a real source read it through the new read-only route: Kanban tasks and workers, limb registry, recent runs under `runtime/agents/`.
- Widgets without a real source are clearly labelled as simulated on screen, or are removed. No random value may look like a real measurement.
- A failing source shows "keine Daten", not an old or invented value.
- The route accepts no paths or URLs from the request and returns no secrets or environment values.
- Tests cover the data mapping, a failing source and the simulated label.

Package J9 changes `frontend/src/apollo/`. Stay out of that folder.
