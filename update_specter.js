const fs = require('fs');
const file = '.jules/specter.md';
let content = fs.readFileSync(file, 'utf8');

const newEntry = `
## 2026-09-08 - TradePlan visual inconsistencies and missing monospace typography
**Learning:** \`TradePlan.tsx\` used raw hex colors in inline styles (\`#34d399\`, \`#60a5fa\`, \`#f87171\`) for the ladder component and lacked explicit dark-glassmorphism tokens (\`bg-[#0a0a0c]/80 backdrop-blur-sm\`). The Stat and Row percentages and numerical values also lacked monospace tabular figures (\`font-mono tabular-nums\`), which violates the MP-17 Dark-Glassmorphism standard.
**Action:** Replaced inline hex colors with a \`theme\` prop using Tailwind semantic color tokens (\`emerald\`, \`blue\`, \`rose\`). Applied \`bg-[#0a0a0c]/80 backdrop-blur-sm\` to the ladder badges. Enforced \`font-mono tabular-nums\` on all numerical values in Stat and Row components.
`;

fs.writeFileSync(file, content + newEntry);
console.log('specter.md updated successfully');
