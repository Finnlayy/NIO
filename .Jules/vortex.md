
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** Animating or dynamically setting layout invalidating properties like `width` and `marginLeft` causes CPU layout thrashing for high-frequency updates.
**Action:** Replaced `width` and `marginLeft` with hardware-accelerated `transform: scaleX(...)` and `clip-path: inset(...)` in `CompositeRankings`, `TechnicalGauge`, and `KeyLevelsTable` components to eliminate layout recalculations and move them to the GPU composite layer.
