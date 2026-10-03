## 2026-10-03 - [UI Aesthetic Insight]
**Learning:** Hardcoded RGB/RGBA styles and non-tabular raw numerical displays violate MP-17 Dark-Glassmorphism standard and typography boundaries.
**Action:** Replaced inline `rgba(...)` strings with semantic Tailwind tokens (`border-white/[0.08]` and `bg-white/[0.03]`) and applied `font-mono tabular-nums` utility classes to statistical data for pixel-perfect clarity.
