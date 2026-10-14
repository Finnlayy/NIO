
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2024-05-24 - [Graphics / Rendering Insight]
**Learning:** For horizontal progress bars, using `transform: scaleX(...)` inside flex wrappers causes visual distortion (squishing) on elements with `border-radius`, and trying to animate layout properties (`width`) causes layout thrashing.
**Action:** Replaced the flex wrappers with a `relative w-full` container, absolute positioning, and used GPU-accelerated `clip-path: inset(...)` to achieve dynamic hardware-accelerated cropping without border scaling or layout invalidation.
