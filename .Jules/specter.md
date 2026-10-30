## 2024-10-27 - [UI Aesthetic Insight]
**Learning:** Found inconsistent color token patterns (using raw `rgba()` in inline `style={{}}` attributes instead of Tailwind classes) in `DomainsGrid.tsx` and `FilterBar.tsx`. Also found missing `font-mono` classes on numerical tabular data in `KpiStrip.tsx`, `DomainsGrid.tsx`, `CoreTile.tsx`, and `InspectorTile.tsx`.
**Action:** Enforce the use of Tailwind v4 semantic token classes (e.g. `border-white/[0.08] bg-white/[0.03]`) and remove raw inline colors. Ensure all numerical data strictly uses `font-mono tabular-nums`.
