# Vortex — Graphics / Rendering Journal

## 2026-09-08 - Heatmap `transition-all` thrashes paint on live ticks
**Learning:** `transition-all` on high-frequency CVD heatmap bins animated layout properties together with background color, so each engine tick triggered extra CPU reflow/repaint on the 12-bin grid.
**Action:** Constrain the cell class in `frontend/src/ops/widgets/CvdHeatmap.tsx` to `transition-colors` (color, background-color, border-color, fill, stroke). Keep that assertion in `telemetry.test.js`.

## 2026-09-12 - [Animation / Rendering Optimization]
**Learning:** High-frequency live orderbook (CVD heatmap) updates were causing a layout-thrashing bottleneck due to animating the non-composite `width` property on progress bars and utilizing `transition-all` on dynamically repainted elements.
**Action:** Removed `transition-all` from the CVD heatmap grid cells to prevent unnecessary layout recalculations. Refactored the `buyPct` and `sellPct` progress bars to use the hardware-accelerated composite property `transform: scaleX(...)` with `transformOrigin` instead of animating layout-invalidating `width`. Enforced `contain: layout paint;` on the isolated `.ops-widget` trading cards in `globals.css` to limit reflow scopes.