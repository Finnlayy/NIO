export interface Topic {
  id: string;
  title: string;
  subtitle: string;
  icon: string;
  color: string;
  gradient: string;
}

export const topics: Topic[] = [
  {
    id: "autonomous-orchestrator",
    title: "Neural Network",
    subtitle: "Interactive Agent Graph & Feedback Loops",
    icon: "🧠",
    color: "from-violet-500 to-cyan-600",
    gradient: "linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)",
  },
  {
    id: "ai-agents",
    title: "AI Agents",
    subtitle: "How To Build A Team Of AI Agents",
    icon: "🤖",
    color: "from-cyan-500 to-blue-600",
    gradient: "linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)",
  },
  {
    id: "git-github",
    title: "Git & GitHub",
    subtitle: "Complete Cheat Sheet & Workflows",
    icon: "🐙",
    color: "from-green-500 to-emerald-600",
    gradient: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
  },
  {
    id: "merge-conflicts",
    title: "Merge Conflicts",
    subtitle: "Explained Finally — Day 21 & 20",
    icon: "⚠️",
    color: "from-red-500 to-orange-600",
    gradient: "linear-gradient(135deg, #ef4444 0%, #f97316 100%)",
  },
  {
    id: "ai-observability",
    title: "AI Observability",
    subtitle: "Monitor. Measure. Improve.",
    icon: "📊",
    color: "from-purple-500 to-violet-600",
    gradient: "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",
  },
  {
    id: "dev-roadmap",
    title: "Developer Roadmap",
    subtitle: "From Zero To Software Engineer",
    icon: "🚀",
    color: "from-orange-500 to-amber-600",
    gradient: "linear-gradient(135deg, #f97316 0%, #eab308 100%)",
  },
];
