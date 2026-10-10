
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2023-10-24 - [Graphics / Rendering Insight]
**Learning:** `transform: scaleX(...)` on inner elements of flex wrappers for GPU-accelerated stacked bar charts fails visually and causes layout thrashing. It also causes visual distortion (squishing) on elements with `border-radius`.
**Action:** Replaced flex wrappers with `relative w-full` containers, used absolute positioning (`absolute inset-y-0 left-0 w-full h-full`), and applied `clip-path: inset(...)` for dynamic hardware-accelerated cropping without border scaling or layout invalidation in `NewsSentiment.tsx`, `PatternScanner.tsx`, and `CvdHeatmap.tsx`.
