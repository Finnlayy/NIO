1.  **Refactor `NewsSentiment.tsx` to use `transform: scaleX`:**
    *   Currently, the progress bar uses `width` inline styles: `<div style={{ width: \`${negative}%\`, background: "#f87171" }} />`
    *   Change this to use a 100% width parent with three absolutely positioned children, layered or flexed properly, or change the children to have `width: "100%"` and `transform: scaleX(...)`. Wait, since they are stacked sequentially, it's easier to keep them as flex children and change `flexBasis`? No, flexBasis still triggers layout.
    *   To properly use `transform: scaleX` for a segmented bar, we can stack them using absolute positioning and change `transformOrigin: "left"`.
    *   Negative (red) starts at 0, spans `negative`% -> `transform: scaleX(negative / 100)`.
    *   Neutral (gray) starts at `negative`%, spans `neutral`% -> we could position it with `left: negative%` (which triggers layout... wait) or use a single bar structure where we just stack them.
    *   Alternatively, just use `transform: scaleX(...)` on flex items, but `scaleX` scales from the center by default. If we set `transformOrigin: left`, they will scale but they will overlap unless their container width is fixed.
    *   Wait, the standard way to do this without layout shifts is to have three `absolute` divs inside a `relative` container, all width 100%.
        *   Red: `transform: scaleX(negative / 100)`, `transformOrigin: "left"`.
        *   Gray: `transform: scaleX(neutral / 100)`, `transformOrigin: "left"`, but we need it to start after Red. If we translate it, `translateX` also uses %. `translateX(negative * 100%)`? No, `translateX` on a 100% width element is relative to the element's width.
        *   Let's check how `CvdHeatmap.tsx` did it. It has a left and right bar:
            ```tsx
            <div className="flex-1 h-1.5 rounded-full overflow-hidden flex relative">
              <div className="absolute inset-y-0 left-0 h-full" style={{ width: "100%", background: "#34d399", transform: `scaleX(${buyPct / 100})`, transformOrigin: "left" }} />
              <div className="absolute inset-y-0 right-0 h-full" style={{ width: "100%", background: "#f87171", transform: `scaleX(${sellPct / 100})`, transformOrigin: "right" }} />
            </div>
            ```
        *   For 3 segments (negative, neutral, positive):
            *   We can have the container background be neutral (gray).
            *   Then left bar is negative (red) scaling from left.
            *   Right bar is positive (green) scaling from right.
            *   Since total is 100%, negative + positive <= 100%, and the gap in the middle will just show the gray container background! This is a perfect 0-layout-thrashing trick.

2.  **Refactor `PatternScanner.tsx` to use `transform: scaleX`:**
    *   Currently uses:
        ```tsx
        <div style={{ width: `${(bullish / total) * 100}%`, background: upBar }} />
        <div style={{ width: `${(bearish / total) * 100}%`, background: downBar }} />
        ```
    *   Since it's just two segments, we can use the same left/right absolute positioning trick.
    *   Left bar (bullish) scales from left: `transform: scaleX(bullish / total)`, `transformOrigin: "left"`.
    *   Right bar (bearish) scales from right: `transform: scaleX(bearish / total)`, `transformOrigin: "right"`.

3. **Check `LimbMesh.tsx` for layout thrashing:**
    *   It uses `style={{ left: \`${pos.x}%\`, top: \`${pos.y}%\` }}`.
    *   Since `pos` comes from a static `positions` map and doesn't animate, it doesn't cause layout thrashing on every frame. But to be safe, could it be changed to `transform: translate(..., ...)`? It's not animated so it's probably fine as is, per rule: "Animate properties that invalidate layout (width, height, margin, top, left)". Since it's not animated, it's not violating the rule.

4.  **Log to `.Jules/vortex.md`:**
    *   Add an entry about fixing layout thrashing in `NewsSentiment` and `PatternScanner` progress bars by replacing `width` animations with `transform: scaleX` and leveraging the background for the neutral segment.

5.  **Run Tests & Pre-commit:**
    *   Run frontend `pnpm run typecheck` and `make ui-test`
    *   Use Playwright script to verify UI visually if needed.
    *   Run `pre_commit_instructions`.

6.  **Submit PR:**
    *   Title: `🚀 Vortex: [Animation / Rendering Optimization]`
