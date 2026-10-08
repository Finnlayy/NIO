
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.
## 2025-02-21 - [Graphics / Rendering Insight]
**Learning:** Animating `width` property or using flex layouts with inner elements using `scaleX` for progress bars and stacked charts causes severe CPU layout thrashing and visual distortion on elements with `border-radius`. Border scaling gets distorted on elements with `transform: scaleX(...)` as well.
**Action:** Replaced flex wrappers with absolute positioning (`relative w-full h-full`), and substituted layout-invalidating `width` or `margin` changes with `clip-path: inset(...)` or explicit `transform: translateX(...) scaleX(...)` on `absolute` components for GPU hardware acceleration and zero layout jank.
