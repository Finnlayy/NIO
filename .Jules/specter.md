## 2024-05-18 - [UI Aesthetic Insight]
**Learning:** Found raw inline styles for colors and dark background with missing font-mono in numerical data inside TradePlan.tsx. This breaks the Dark-Glassmorphism standard.
**Action:** Replaced inline styles with semantic Tailwind tokens (bg-[#0a0a0c]/80 backdrop-blur-md) and enforced font-mono tabular-nums on Stat component.
