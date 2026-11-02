## 2026-10-31 - Layout Thrashing in High-Frequency Canvas UI
**Learning:** Animating `width` and `max-height` in components that update frequently (like progress bars or live failover ribbons) triggers full CPU reflows and repaints, severely degrading framerate (jank) in heavy environments like the NeuralGraph canvas.
**Action:** Exclusively use composite layer properties: `transform: scaleX(...)` on absolute layers for horizontal bars, and `transform: translateY(...)` for slide-in ribbons. Wrap them in `relative overflow-hidden` containers.
