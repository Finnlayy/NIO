## 2026-10-20 - [UI Aesthetic Insight]
**Learning:** Raw numerical data rendering without monospace/tabular-nums fonts breaks visual rhythm, and dynamic inline styling causes Tailwind tokens to be missed during compilation.
**Action:** Enforce `font-mono tabular-nums` on all numerical UI fields. Remove dynamic arbitrary inline styles and map them statically to explicit Tailwind semantic utility classes.
