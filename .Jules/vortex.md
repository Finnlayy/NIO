
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-21 - [Graphics / Rendering Insight]
**Learning:** For GPU-accelerated stacked bar charts, flex wrappers with `scaleX` inner elements fail visually and cause layout thrashing/distortion on elements with `border-radius`.
**Action:** Wrapped stacked bar elements in a `relative w-full h-full` container, used absolute positioning (`absolute inset-y-0 left-0 w-full h-full`), and applied `clip-path: inset(...)` to define the visible segment for each element. This achieves dynamic hardware-accelerated cropping without border scaling or layout invalidation.
