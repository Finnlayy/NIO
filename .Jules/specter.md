## 2026-11-08 - [UI Aesthetic Insight]
**Learning:** Found raw hardcoded hex colors and inline styling violating the Dark-Glassmorphism token standards in KeyLevelsTable. Raw hex values like #f87171, #34d399, and inline color interpolations bypass Tailwind's utility class advantages.
**Action:** Enforce strict usage of semantic Tailwind tokens (e.g. text-rose-400, bg-emerald-400/20) and restrict inline styles purely to dynamic layout transformations (e.g., width computation).
