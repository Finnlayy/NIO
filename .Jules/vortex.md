
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2025-02-28 - [Graphics / Rendering Insight]
**Learning:** Animating `width` property (or dynamically updating it frequently in loops based on feed/tick updates) causes severe CPU layout thrashing and high Cumulative Layout Shift due to reflow cascades. Elements like `row.score` in `CompositeRankings.tsx` triggered heavy paint hotspots upon receiving telemetry updates.
**Action:** Replaced dynamic `width` styles with pure GPU composite-layer hardware acceleration using `clip-path: inset(0 ${100 - pct}% 0 0)`. Bound the target to a `relative w-full` wrapper and `absolute inset-y-0 left-0 w-full` position, keeping pure render flows decoupled from CPU layout recalculations without mutating generic CSS box properties.
