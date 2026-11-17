
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-11-02 - [Graphics / Rendering Insight]
**Learning:** Animating `width` via CSS transitions (`transition-[width]`) in the Apollo orchestrator UI triggers synchronous layout recalculations and CPU layout thrashing.
**Action:** Replaced `width` animations with `transform: scaleX(...)` and `transformOrigin: left` combined with `transition-transform` to offload animations to the GPU composite layer and maintain 120 FPS frame budgets.

## 2026-11-10 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU layout-thrashing when animating elements like failover ribbons, especially when properties like `max-height` are animated.
**Action:** Replaced `transition-all` with `transition` (or specific properties like `transition-opacity`) and replaced layout-invalidating `max-height` animations with `transform: scaleY()` (`scale-y-0` to `scale-y-100`) and `transform-origin: top` to ensure pure composite-layer animations running on GPU.
