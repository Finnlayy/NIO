## 2025-02-12 - [Graphics / Rendering Insight]
**Learning:** The `transition-all` class on high-frequency live market data grids triggers unnecessary CPU layout/paint operations when properties like background color change rapidly, causing frame drops.
**Action:** Constrained the CSS transition in `frontend/src/ops/widgets/CvdHeatmap.tsx` to `transition-colors` (which applies `transition: color, background-color, border-color, text-decoration-color, fill, stroke`) to ensure changes don't recompute layout or use `all`, restricting to composite/paint safe properties.
