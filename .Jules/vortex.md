
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-10-19 - [Graphics / Rendering Insight]
**Learning:** Using `scaleX(...)` on horizontal flex progress bars causes visual distortion (squishing) on elements with border radius and fails visually.
**Action:** Replaced `scaleX(...)` with GPU-accelerated `clip-path: inset(...)` inside `relative w-full h-full` and `absolute inset-y-0 left-0` containers for dynamic cropping without distortion on `PatternScanner.tsx`, `NewsSentiment.tsx` and `CvdHeatmap.tsx`.
