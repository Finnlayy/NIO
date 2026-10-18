
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2025-02-27 - [Graphics / Rendering Insight]
**Learning:** Using `transform: scaleX(...)` on progress bar elements inside Flexbox wrappers causes visual distortion (border-radius squishing) and layout thrashing, degrading framerate rendering budgets.
**Action:** Replaced `scaleX` with `clip-path: inset(...)` along with `relative w-full h-full` absolute positioning in `NewsSentiment`, `PatternScanner`, and `CvdHeatmap` stacked progress bars. This achieves smooth GPU-accelerated cropping without layout invalidation or border distortion.
