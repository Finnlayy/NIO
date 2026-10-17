
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** To animate horizontal progress bars dynamically without layout thrashing, animating `width` or using `transform: scaleX(...)` causes visual distortion or layout invalidation.
**Action:** Replaced `width` and `scaleX` on progress bars across widgets with GPU-accelerated `clip-path: inset(...)` inside `absolute w-full h-full` wrappers for pure composite-layer animation.
