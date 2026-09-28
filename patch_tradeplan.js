const fs = require('fs');
const file = 'frontend/src/ops/widgets/TradePlan.tsx';
let content = fs.readFileSync(file, 'utf8');

content = content.replace(
  '<Ladder y="8%" label="T2" price={plan.t2} plan={plan} color="#34d399" dashed />\n        <Ladder y="38%" label="T1" price={plan.t1} plan={plan} color="#34d399" dashed />\n        <Ladder y="58%" label="Entry" price={plan.entry} plan={plan} color="#60a5fa" solid dot />\n        <Ladder y="92%" label="Stop" price={plan.stop} plan={plan} color="#f87171" dashed />',
  '<Ladder y="8%" label="T2" price={plan.t2} plan={plan} theme="emerald" dashed />\n        <Ladder y="38%" label="T1" price={plan.t1} plan={plan} theme="emerald" dashed />\n        <Ladder y="58%" label="Entry" price={plan.entry} plan={plan} theme="blue" solid dot />\n        <Ladder y="92%" label="Stop" price={plan.stop} plan={plan} theme="rose" dashed />'
);

content = content.replace(
  '<Stat label="Direction" value="Long" valueClass="text-emerald-400" />\n        <Stat label="Risk" value={pct(plan.riskPct)} valueClass="text-rose-400" />\n        <Stat label="Reward (T1)" value={pct(plan.rewardPct)} valueClass="text-emerald-400" />\n        <Stat label="Risk : reward" value={plan.rr} small />',
  '<Stat label="Direction" value="Long" valueClass="text-emerald-400" />\n        <Stat label="Risk" value={pct(plan.riskPct)} valueClass="text-rose-400 font-mono tabular-nums" />\n        <Stat label="Reward (T1)" value={pct(plan.rewardPct)} valueClass="text-emerald-400 font-mono tabular-nums" />\n        <Stat label="Risk : reward" value={String(plan.rr)} valueClass="font-mono tabular-nums" small />'
);

content = content.replace(
  'function Ladder({\n  y,\n  label,\n  price,\n  plan,\n  color,\n  dashed,\n  solid,\n  dot,\n}: {\n  y: string;\n  label: string;\n  price: number;\n  plan: TradePlanData;\n  color: string;\n  dashed?: boolean;\n  solid?: boolean;\n  dot?: boolean;\n}) {\n  return (\n    <div className="absolute inset-x-0 flex items-center" style={{ top: y }}>\n      <span\n        className="px-1.5 py-0.5 rounded text-[9px] font-bold border shrink-0 z-10"\n        style={{ color, borderColor: `${color}66`, background: "rgba(9,11,18,0.9)" }}\n      >\n        {label}\n      </span>\n      <span\n        className={`flex-1 ${dashed ? "border-t border-dashed" : solid ? "border-t-2" : ""}`}\n        style={{ borderColor: `${color}aa` }}\n      />\n      {dot && <span className="w-2 h-2 rounded-full mr-1" style={{ background: color }} />}\n      <span\n        className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold shrink-0 z-10"\n        style={{ color, border: `1px solid ${color}55`, background: "rgba(9,11,18,0.9)" }}\n      >\n        {fmt(price, plan.decimals)}\n      </span>\n    </div>\n  );\n}',
  `function Ladder({
  y,
  label,
  price,
  plan,
  theme,
  dashed,
  solid,
  dot,
}: {
  y: string;
  label: string;
  price: number;
  plan: TradePlanData;
  theme: "emerald" | "blue" | "rose";
  dashed?: boolean;
  solid?: boolean;
  dot?: boolean;
}) {
  const tokens = {
    emerald: { text: "text-emerald-400", border: "border-emerald-400/40", line: "border-emerald-400/60", bg: "bg-emerald-400" },
    blue: { text: "text-blue-400", border: "border-blue-400/40", line: "border-blue-400/60", bg: "bg-blue-400" },
    rose: { text: "text-rose-400", border: "border-rose-400/40", line: "border-rose-400/60", bg: "bg-rose-400" },
  }[theme];

  return (
    <div className="absolute inset-x-0 flex items-center" style={{ top: y }}>
      <span
        className={\`px-1.5 py-0.5 rounded text-[9px] font-bold border shrink-0 z-10 bg-[#0a0a0c]/80 backdrop-blur-sm \${tokens.text} \${tokens.border}\`}
      >
        {label}
      </span>
      <span
        className={\`flex-1 \${dashed ? "border-t border-dashed" : solid ? "border-t-2" : ""} \${tokens.line}\`}
      />
      {dot && <span className={\`w-2 h-2 rounded-full mr-1 \${tokens.bg}\`} />}
      <span
        className={\`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold shrink-0 z-10 border bg-[#0a0a0c]/80 backdrop-blur-sm \${tokens.text} \${tokens.border}\`}
      >
        {fmt(price, plan.decimals)}
      </span>
    </div>
  );
}`
);

fs.writeFileSync(file, content);
console.log('TradePlan.tsx updated successfully');
