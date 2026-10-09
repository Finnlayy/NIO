
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** Animating or dynamically assigning `width` and `transform: scaleX(...)` on horizontal progress bars triggers layout-thrashing on every frame and visual distortion (squishing) on elements with `border-radius`.
**Action:** Replaced `width` and `transform: scaleX(...)` dynamic assignments with GPU-accelerated `clip-path: inset(...)` for hardware-accelerated cropping without layout invalidation or border distortion. Wrapped flexbox items in `relative w-full` containers and used `absolute` positioning to prevent flex-layout from improperly shrinking them.
