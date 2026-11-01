
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.
## 2026-11-01 - [Graphics / Rendering Insight]
**Learning:** Animating flex stacked bars using inline `width` scaling or wrappers that trigger inner `scaleX` without container boundary clipping causes full layout recalculation and continuous repaints. Furthermore, direct `scaleX` on border-radius children squishes their borders.
**Action:** Always wrap high-frequency horizontal stacked/progress bars in a `relative overflow-hidden` container. Apply `border-radius` to this parent, and use overlapping `absolute inset-0` child elements styled entirely with `transform: scaleX(...)` and `transformOrigin`. This offloads all scaling to the GPU composite layer and bypasses the CPU layout engine completely while preserving correct corner radii.
