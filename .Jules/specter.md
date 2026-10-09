
## 2023-10-09 - [UI Aesthetic Insight]
**Learning:** Using `transform: scaleX(...)` on horizontal progress bars causes visual distortion on inner elements (especially with borders). Additionally, using inline hex colors or rgba string interpolation violates the dark-glassmorphism strict Tailwind token system and reduces maintainability.
**Action:** Replace `transform: scaleX(...)` with GPU-accelerated `clip-path: inset(...)` inside a `relative w-full h-full` flex wrapper with absolute positioning for dynamic cropping. Always use semantic Tailwind v4 utility classes (e.g., `bg-emerald-400`, `bg-emerald-400/[0.12]`) instead of hardcoded hex values or inline styles.
