## 2026-09-09 - [Graphics / Rendering Insight]
**Learning:** Layout-thrashing pattern triggered by live orderbook re-renders when using `transition-all` on high frequency heatmap cells and animating `height` with Framer Motion.
**Action:** Removed `transition-all` from heatmap cells to rely strictly on composite layer properties. Replaced layout invalidating `height` animation with pure `opacity` transition and enforced `contain: layout paint;` on isolated trading card widgets to avoid repaints.
