
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-11-02 - [Graphics / Rendering Insight]
**Learning:** Animating `width` via CSS transitions (`transition-[width]`) in the Apollo orchestrator UI triggers synchronous layout recalculations and CPU layout thrashing.
**Action:** Replaced `width` animations with `transform: scaleX(...)` and `transformOrigin: left` combined with `transition-transform` to offload animations to the GPU composite layer and maintain 120 FPS frame budgets.
## 2026-11-09 - [Graphics / Rendering Insight]
**Learning:** Animating  or using `transition-[max-height,...]` triggers synchronous layout recalculations and CPU layout thrashing, even when restricted to specific properties.
**Action:** Replaced `max-height` animations with `transform: scaleY()` combined with `origin-top` and `transition-[transform,opacity,...]` to fully offload animations to the GPU composite layer and maintain 120 FPS frame budgets.

## 2024-05-24 - [Graphics / Rendering Insight]
**Learning:** Animating `max-height` or using `transition-[max-height,...]` triggers synchronous layout recalculations and CPU layout thrashing, even when restricted to specific properties.
**Action:** Replaced `max-height` animations with `transform: scaleY()` combined with `origin-top` and `transition-[transform,opacity,...]` to fully offload animations to the GPU composite layer and maintain 120 FPS frame budgets.
