
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-11-02 - [Graphics / Rendering Insight]
**Learning:** Animating `width` via CSS transitions (`transition-[width]`) in the Apollo orchestrator UI triggers synchronous layout recalculations and CPU layout thrashing.
**Action:** Replaced `width` animations with `transform: scaleX(...)` and `transformOrigin: left` combined with `transition-transform` to offload animations to the GPU composite layer and maintain 120 FPS frame budgets.

## 2026-11-04 - [Graphics / Rendering Insight]
**Learning:** `transition-all` on components with layout changes triggers CPU reflow-thrashing. Animating `max-h` dynamically in combination with layout also results in full layout invalidation.
**Action:** Replaced `transition-all` with hardware-accelerated equivalents (`transition-[transform,border-color,background-color]`, `transition-opacity`, `transition`). Replaced `max-h` animations on the failover ribbon with `transform: scaleY()` and `origin-top` in combination with `absolute` positioning to offload animations to the GPU composite layer and maintain 120 FPS frame budgets.
