
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.
## 2026-10-13 - [Graphics / Rendering Insight]
**Learning:** Modifying inline `width` properties or using `transform: scaleX` with `width: 100%` in flex containers for dynamic progress bars causes expensive layout recalculations (thrashing) and visual flexbox distortion during high-frequency render cycles.
**Action:** Replaced dynamic `width` and `scaleX` flexbox techniques with absolutely positioned, full-width/height elements using mathematically precise `clip-path: inset(...)` calculations. This safely hardware-accelerates the bounds cropping in the GPU composite layer, eliminating all layout reflows and flex gap rendering errors.
