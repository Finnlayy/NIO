## 2024-05-15 - [UI Aesthetic Insight]
**Learning:** Hardcoded hex colors with dynamic opacity and arbitrary rgba backgrounds violate the MP-17 Dark-Glassmorphism standard.
**Action:** Enforce the use of static semantic Tailwind v4 tokens (e.g. `border-emerald-400/40`) and the base `#0a0a0c` background instead of string concatenation and inline styles.
