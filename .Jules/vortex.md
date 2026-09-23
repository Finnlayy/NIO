
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.
## 2026-09-23 - [Graphics / Rendering Insight]
**Learning:** Using `width` or `margin` to animate horizontal progress bars causes heavy CPU reflow and layout-thrashing on every frame, which severely impacts framerate in high-frequency orderbook or market data feeds.
**Action:** Refactored horizontal progress bars in `CompositeRankings`, `TechnicalGauge`, and `KeyLevelsTable` to use GPU-accelerated `transform: scaleX(...)` and `transform: translateX(...)` with `transformOrigin` and `absolute` positioning to prevent flex-layout shrinkage.
