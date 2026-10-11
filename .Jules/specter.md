## 2025-03-09 - Remove raw hex values and inline styles
**Learning:** The `Ladder` component in `TradePlan.tsx` uses raw hex values and string concatenation for inline styles, as well as a hardcoded background color, which violates the dark-glassmorphism design system constraints.
**Action:** Replaced the raw hex values with semantic `tone` props mapping to Tailwind utility classes, and updated the hardcoded background color to the designated `bg-[#0a0a0c]/90` token.
