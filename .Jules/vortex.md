
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-10-28 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame. Animating properties like `width` on horizontal progress bars causes full layout invalidation and drops below the 120 FPS frame budget.
**Action:** Replaced `transition-[width]` with GPU-accelerated `transform: scaleX(...)` and `transformOrigin: left` on progress bars in `ApolloOrb.tsx`, `NeuralGraph.tsx`, and `ui.tsx`. Refactored `transition-all` to composite-safe properties like `transition-colors` and `transition-opacity` in `ApolloOrb.tsx`, `NeuralGraph.tsx`, and `page.tsx`.
