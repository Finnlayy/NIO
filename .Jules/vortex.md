
## 2026-09-20 - [Graphics / Rendering Insight]
**Learning:** `transition-all` triggers heavy CPU reflow and layout-thrashing on every frame, and animating properties like `width` causes layout invalidation.
**Action:** Replaced `transition-all` with `transition-colors` in FilterBar and page ops. Replaced `width` animations in `NewsSentiment` and `PatternScanner` horizontal progress bars with `transform: scaleX(...)` and `transformOrigin: left` to ensure pure composite-layer animation running on GPU.

## 2026-10-29 - Apollo components `transition-all` thrashes layout
**Learning:** `transition-all` on elements in `ApolloOrb`, `NeuralGraph`, and `page` was causing unnecessary layout recalculations and CPU reflow on every frame when toggling visibility or styles.
**Action:** Replaced `transition-all` with specific transitions (`transition-colors`, `transition-opacity`, and standard `transition`) to restrict animations to composite properties and avoid layout thrashing.
