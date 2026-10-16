
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-10-16 - GPU-Accelerated Dynamic Progress Bars
**Learning:** Animating `width` on horizontal progress bars triggers heavy CPU reflow and layout-thrashing on every frame. Using `transform: scaleX(...)` provides GPU acceleration but squishes elements with CSS borders.
**Action:** Replaced `width` and `scaleX` dynamic progress bar animations with absolute positioning and GPU-accelerated `clip-path: inset(...)` inside `relative w-full` wrappers to avoid layout invalidation and border distortion.
