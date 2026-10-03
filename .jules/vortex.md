# Vortex — Graphics / Rendering Journal

## 2026-09-08 - Heatmap `transition-all` thrashes paint on live ticks
**Learning:** `transition-all` on high-frequency CVD heatmap bins animated layout properties together with background color, so each engine tick triggered extra CPU reflow/repaint on the 12-bin grid.
**Action:** Constrain the cell class in `frontend/src/ops/widgets/CvdHeatmap.tsx` to `transition-colors` (color, background-color, border-color, fill, stroke). Keep that assertion in `telemetry.test.js`.

## 2026-09-12 - [Animation / Rendering Optimization]
**Learning:** High-frequency live orderbook (CVD heatmap) updates were causing a layout-thrashing bottleneck due to animating the non-composite `width` property on progress bars and utilizing `transition-all` on dynamically repainted elements.
**Action:** Removed `transition-all` from the CVD heatmap grid cells to prevent unnecessary layout recalculations. Refactored the `buyPct` and `sellPct` progress bars to use the hardware-accelerated composite property `transform: scaleX(...)` with `transformOrigin` instead of animating layout-invalidating `width`. Enforced `contain: layout paint;` on the isolated `.ops-widget` trading cards in `globals.css` to limit reflow scopes.
## 2024-05-24 - [Graphics / Rendering Insight]
**Learning:** Animating `width` directly causes synchronous CPU layout thrashing. Replacing it with `transform: scaleX(...)` provides GPU acceleration but fails visually on elements with border radii, squishing the rounded corners. Flexbox containers wrapping elements with `transform: scaleX` also distort widths irregularly.
**Action:** Transitioned from `width`/`scaleX` on flex children to GPU-accelerated `clip-path: inset(...)` for dynamic cropping. For stacked bars, replaced `flex` containers with `relative` containers using `absolute` children and combined `translateX`/`scaleX` properties to preserve layout without visual squishing or thrashing.
