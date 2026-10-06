
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2025-02-21 - GPU Acceleration for Progress and Stacked Bars
**Learning:** Animating or dynamically updating the `width` property on progress bars causes layout thrashing, and using `transform: scaleX(...)` on flex-box items in stacked bar charts creates visual distortion (squishing).
**Action:** Replaced `width` updates with hardware-accelerated `clip-path: inset(...)` for single progress bars. For stacked bar charts, used `absolute` positioning within a relative container, applying `translateX(...)` and `scaleX(...)` on elements without borders to prevent flex distortion and layout invalidation.
