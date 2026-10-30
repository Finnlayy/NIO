
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-10-30 - [Graphics / Rendering Insight]
**Learning:** `transition-all` and `max-h` animations cause CPU layout thrashing. Direct width animations (`transition-[width]`) also invalidates layout recalculations.
**Action:** Replaced `transition-all` and `max-h` in Apollo UI (like the failover ribbon) with a zero-height `relative` container housing an absolute item animated via `transition-transform: translateY()`. Replaced horizontal width progress bar animations in `ApolloOrb.tsx`, `NeuralGraph.tsx`, and `ui.tsx` with pure `transform: scaleX(...)` leveraging `transformOrigin: left` for hardware-accelerated GPU execution.
