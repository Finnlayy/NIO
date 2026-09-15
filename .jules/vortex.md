# Vortex — Graphics / Rendering Journal

## 2026-09-08 - Heatmap `transition-all` thrashes paint on live ticks
**Learning:** `transition-all` on high-frequency CVD heatmap bins animated layout properties together with background color, so each engine tick triggered extra CPU reflow/repaint on the 12-bin grid.
**Action:** Constrain the cell class in `frontend/src/ops/widgets/CvdHeatmap.tsx` to `transition-colors` (color, background-color, border-color, fill, stroke). Keep that assertion in `telemetry.test.js`.

## 2025-02-27 - [Graphics / Rendering Insight]
**Learning:** Usage of `transition-all` on buttons and grid cells causes a layout-thrashing pattern during rendering and triggers heavy CPU reflow on high-frequency UI updates because it attempts to transition properties like layout width, height, and margins, rather than utilizing the GPU composite layer.
**Action:** Replaced `transition-all` with hardware-accelerated composite property transitions like `transition-colors` across components, restricting animations strictly to transform, opacity, and color properties, resulting in zero jank frame execution without CPU-heavy layout recalculations.
