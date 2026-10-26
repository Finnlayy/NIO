## 2024-05-18 - [UI Aesthetic Insight]
**Learning:** Found arbitrary rgba inline values for opacity and borders instead of Tailwind alpha modifiers, and numerical metrics missing the monospace typography requirement, which breaks the Dark-Glassmorphism standard and visual consistency.
**Action:** Replaced inline 'rgba' styles with Tailwind alpha modifiers (e.g. bg-white/[0.03]) and enforced 'font-mono' on all data-driven numerical fields (e.g. alongside 'tabular-nums') in grid modules.
