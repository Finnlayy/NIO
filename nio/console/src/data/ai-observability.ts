export interface Metric {
  name: string;
  icon: string;
  value: string;
  trend: "up" | "down" | "stable";
  description: string;
}

export const metricsToMonitor: Metric[] = [
  {
    name: "Response Time",
    icon: "⏱️",
    value: "412 ms",
    trend: "down",
    description: "Track latency and p95/p99 for all requests.",
  },
  {
    name: "Accuracy",
    icon: "🎯",
    value: "92.6%",
    trend: "up",
    description: "Evaluate response quality with automated metrics.",
  },
  {
    name: "Token Consumption",
    icon: "🪙",
    value: "128K",
    trend: "stable",
    description: "Monitor prompt + completion tokens in real time.",
  },
  {
    name: "Throughput",
    icon: "📊",
    value: "1.2k/s",
    trend: "up",
    description: "Track requests per second and system capacity.",
  },
  {
    name: "Failure Rate",
    icon: "⚠️",
    value: "1.2%",
    trend: "down",
    description: "Detect failures, timeouts and failed generations.",
  },
  {
    name: "Cost Per Request",
    icon: "💰",
    value: "$0.018",
    trend: "down",
    description: "Track spending per request to optimize costs.",
  },
  {
    name: "User Feedback",
    icon: "😊",
    value: "4.7/5",
    trend: "up",
    description: "Collect feedback and analyze sentiment.",
  },
];

export const benefits = [
  { title: "Faster Troubleshooting", desc: "Identify issues before users report them." },
  { title: "Better Performance", desc: "Optimize latency, accuracy, and throughput." },
  { title: "Lower Costs", desc: "Reduce unnecessary token usage and spend." },
  { title: "Improved Reliability", desc: "Build trust with consistent and stable outputs." },
  { title: "Continuous Optimization", desc: "Data-driven improvements at every step." },
  { title: "Production Readiness", desc: "Operate AI systems with confidence at scale." },
];

export const withoutObservability = [
  { item: "Unknown performance", status: false },
  { item: "Hidden failures", status: false },
  { item: "Rising costs", status: false },
  { item: "Difficult debugging", status: false },
];

export const withObservability = [
  { item: "Real-time monitoring", status: true },
  { item: "Actionable insights", status: true },
  { item: "Better optimization", status: true },
  { item: "Reliable AI systems", status: true },
];

export const realWorldApplications = [
  { name: "AI Agents", icon: "🤖" },
  { name: "RAG Pipelines", icon: "📚" },
  { name: "Customer Support Bots", icon: "🎧" },
  { name: "Enterprise AI Platforms", icon: "🏢" },
  { name: "Analytics Systems", icon: "📈" },
  { name: "AI Automation Workflows", icon: "⚙️" },
];

export const expertTip = "Monitoring isn't an afterthought — if you can't observe your AI system, you can't improve it. It's a core part of AI engineering.";
