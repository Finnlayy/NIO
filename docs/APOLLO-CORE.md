# Apollo Core UI — orb, neural graph, FreeLLMAPI router

The frontend in `frontend/` is a Next 16 app. `/` and `/apollo` render the
**Apollo stage**: a radial neural-node graph around a shader orb, a control
deck, and a hybrid chat/log/CLI terminal. `/ops` keeps the widget grid.

```
frontend/src/apollo/
  types.ts       contract from the spec (§4) + additive UI types
  catalog.ts     palette, orb states, node categories/states, 36 providers,
                 635 endpoints, 16 seed candidates, 8 seed nodes, MCP servers
  routing.ts     weights -> composite score -> ranked chain, handoff note
  engine.ts      RouterState reducer: quota, failover, restore, roll-window
  commands.ts    CLI parser (8 commands), config coercion, Levenshtein hints
  graph.ts       ellipse layout, bezier axons, springs, easings, colour utils
  store.ts       zustand store: config, router, nodes, vesicles, impulses,
                 orb state, task rail, terminal entries, deck/terminal flags
  orbShader.ts   GLSL: SDF sphere, domain-warped fbm plasma, rim, halo,
                 amber shockwave, crimson error ring, dispatch flare
  ApolloOrb.tsx  WebGL renderer + Canvas2D fallback, quota tick ring, HUD
  NeuralGraph.tsx  canvas axons/vesicles/impulses + HTML node cards
  ApolloDeck.tsx 3-tab modal (runtime / router / bridge), draft + apply
  Terminal.tsx   unified chat+telemetry stream and raw log, CLI with
                 autocomplete, history, Tab completion
  ui.tsx         Badge, Toggle, Slider, Segmented, Field, MiniBar, ...

frontend/src/app/apollo/page.tsx   the stage shell (hotkeys, task rail)
frontend/src/app/api/apollo/route.ts   server-side OpenAI-compatible proxy
frontend/src/app/api/sandbox/route.ts  read-only command jail
```

## Orb states

`IDLE → LISTENING → THINKING → DISPATCHING → SYNTHESIZING`, plus
`FAILOVER_SWITCH` (amber shockwave) and `ERROR` (crimson pulse). Each state maps
to an energy/colour target in `ApolloOrb.tsx`; the shader interpolates, so a
state change is a colour drift rather than a cut. `prefers-reduced-motion`
freezes the plasma to a still frame and shortens the CSS animations.

The renderer reports itself in `[data-testid=apollo-orb]`'s `data-renderer`
attribute (`webgl` / `canvas2d` / `none`). WebGL is attempted first; the 2D
fallback draws the same glow, body, tick ring and shock/flare overlays.

## FreeLLMAPI failover

`routing.ts` is pure:

```
compositeScore(candidate, weights) =
  (reliability · w.rel + speed · w.spd + intelligence · w.int) / 100
```

`normalizeWeights` clamps to 0..100 and renormalises so the three buckets always
sum to exactly 100 (rounding drift lands on the largest bucket). `rankCandidates`
sorts desc, ties broken by reliability then id, so the leaderboard never
reshuffles between renders.

`engine.ts` holds the failover rules:

- `failover()` never re-picks the current candidate and never picks a
  `LIMIT_REACHED` one; it marks the previous model `LIMIT_REACHED`, sets
  `mode: "FAILOVER"`, increments `failoverCount` and attaches the handoff note.
- No usable candidate ⇒ `mode: "EXHAUSTED"`, `switched: false`. The UI says so;
  it never invents a model.
- `restorePrimary()` / `rollQuotaWindow()` reset the pool. A roll keeps the
  swap history and the last handoff note.

The **context handoff note** (`buildHandoffNote`) is plain text, ≤900 chars,
headed `CONTEXT HANDOFF · NIO/APOLLO`, ordered
`from → reason → task → directive → completed → pending → resume` so the next
model reads state, not a transcript.

`activeModelOf` is memoised on the identity of `RouterState`. It is used directly
as a zustand selector, and returning a fresh object each call trips React's
"getServerSnapshot should be cached" guard, which silently blocks hydration.

## Endpoints

`POST /api/apollo` — `{endpointUrl, model, messages, temperature?, maxTokens?}`.
Keys come from the server environment only (`FREELLMAPI_KEY`,
`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`,
`CEREBRAS_API_KEY`); the browser never sees one. Fail-closed:

| case | status | body |
| --- | --- | --- |
| no/blank endpoint | 400 | `{error:"no_endpoint"}` — client falls back to labelled simulation |
| non-http(s) | 400 | `{error:"endpoint must be http(s)"}` |
| upstream non-2xx | 502 | `{error:"upstream HTTP 500", detail}` |
| upstream 200 but not JSON / no `choices` | 502 | `upstream_not_json` / `upstream_not_openai_compatible` |
| empty completion | 502 | `empty_upstream_response` |
| > 20 s | 504 | `upstream timeout` |

`POST /api/sandbox` — `{command}` in `pwd ls cat echo date whoami head wc uname`.
No shell: the command is tokenised in-process and run with `execFile`, so
`; | && $( ) > <` are inert text. Paths must be relative and stay inside
`<tmp>/nio-sandbox`, 5 s timeout, output capped. `GET` reports the allowlist.

## Testing

`package.json` and `tsconfig.json` are frozen, so there is no test framework.
`scripts/ui-test.mjs` compiles the import closure with the project's own `tsc`
into `.test-build/` and runs the plain-JS tests under `node --test`:

```bash
cd frontend
node scripts/ui-test.mjs     # 65 tests (Apollo + existing ops suite)
npx tsc --noEmit
npm run build
```

`src/ops/__tests__/apollo-router.test.js` covers the routing maths, the failover
engine (including the exhausted pool), handoff-note ordering and truncation, the
CLI table, and the geometry helpers (ring fit, widest-gap spawn, card collision
and the board fallback, spring
convergence). It is the spec for the visible behaviour.

## Dev server

```bash
cd frontend
npx next dev -H 0.0.0.0 -p 4001   # 0.0.0.0 so the preview proxy can reach it
```

`next.config.ts` allows `localhost`, `127.0.0.1` and `*.e2b.app` as dev origins;
without that Next refuses the client chunks when the page is served through a
proxy host and the stage never hydrates. `devIndicators: false` keeps the dev
badge out of the task rail.

## Layout behaviour

At ≥720 px the eight cards sit on the ellipse; the ellipse is clamped so a
196 × 96 card always fits on screen. Below 720 px the graph folds into a column
(orb, then a scrollable card grid) and the axons are skipped — eight cards
cannot share a ring at that width without overlapping.

`/spawn` can push past eight nodes, so the ring adapts instead of piling cards
up: `fitEllipse()` walks the radius out to the scene bounds and, when the height
will not allow it, steps the cards down (196 → 180 → 165 → 149 px). Only if even
the smallest step collides does the stage switch to `data-layout="board"` — an
opaque, scrollable two-column node board with the corner HUD and the axon legend
hidden (they belong to the radial scene). Before the `ResizeObserver` reports a
size the graph assumes a nominal 1440 × 720 scene, so the server and the first
client render agree and hydration stays clean.
