
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.
## 2026-10-27 - [Graphics / Rendering Insight]
**Learning:** Using `width` for dynamic horizontal progress bars triggers layout reflows and repaints, causing layout thrashing during high-frequency data updates.
**Action:** Enforce 100% GPU-accelerated scaling by wrapping in a `relative overflow-hidden` container and applying `transform: scaleX(...)` with `transformOrigin: left` to `absolute w-full h-full` child elements.
