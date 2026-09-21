
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.
## 2026-09-21 - [Graphics / Rendering Insight]
**Learning:** Found layout-thrashing caused by dynamic width updates on high-frequency progress bars (like those in CompositeRankings and TechnicalGauge), causing synchronous layout recalculation.
**Action:** Replaced width assignments with composite layer GPU-accelerated transforms (`transform: scaleX(...)` with `transformOrigin: "left"` and `absolute inset-y-0 left-0`) to prevent layout thrashing and maintain 120 FPS.
