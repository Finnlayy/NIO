
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** CSS property `width` animation and modifications invalidate layout (causes layout thrashing). Flexbox items animated with `scaleX` can improperly shrink before the transform is applied.
**Action:** Replaced `width` with `transform: scaleX(...)` across `CompositeRankings`, `TechnicalGauge`, and `KeyLevelsTable`. Wrapped flexbox items in `PatternScanner` and `NewsSentiment` with `relative` containers and `absolute inset-y-0 left-0` to prevent flex layout shrinking.

## 2026-09-20 - [Graphics / Rendering Insight - Addendum]
**Learning:** `scaleX` on elements with CSS borders applies the scale to the border thickness, rendering them sub-pixel thin. Flex-based stacked bar charts fail visually when inner elements use `scaleX` independently of the flow.
**Action:** Used `clip-path: inset(...)` for `KeyLevelsTable` bars to achieve dynamic hardware-accelerated cropping without border scaling. Replaced flex wrappers with absolute positioning, `translateX(...)`, and `scaleX(...)` in `NewsSentiment` and `PatternScanner` for mathematically accurate GPU-accelerated stacked charts.
