
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-21 - [Graphics / Rendering Insight]
**Learning:** Using `transform: scaleX(...)` on flex wrapper inner elements for stacked bar charts causes visual distortion (squishing) on elements with `border-radius`.
**Action:** Replaced `scaleX` in stacked progress bars with a `relative w-full h-full` container, absolute positioning, and GPU-accelerated `clip-path: inset(...)` for dynamic cropping without border distortion or layout invalidation in `NewsSentiment`, `PatternScanner`, and `CvdHeatmap`.
