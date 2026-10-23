
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2025-05-20 - [Graphics / Rendering Insight]
**Learning:** `flex` wrappers with `scaleX` on inner elements fail visually in high-performance GPU-accelerated stacked bar charts by splitting widths and squishing elements, leading to rendering layout-thrashing problems.
**Action:** Replaced `flex` container logic with `relative` wrappers masking boundaries via `overflow-hidden`. Placed overlapping child bars using `absolute inset-y-0 w-full h-full` and applied `transform: scaleX(...)` with `transformOrigin` to ensure hardware-accelerated 100% GPU scaling without reflows.
