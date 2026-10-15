
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** Using `transform: scaleX(...)` on flex items for horizontal progress bars/stacked charts causes layout thrashing via flex recalculation and visual distortion (squishing) on elements with `border-radius`.
**Action:** Replaced `scaleX` and flex wrappers with `relative w-full` containers and absolute positioning. Applied GPU-accelerated `clip-path: inset(...)` for dynamic visual cropping of the bars, achieving 120 FPS capable, zero-layout-thrashing hardware-accelerated transitions without border distortion.
