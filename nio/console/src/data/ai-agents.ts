export interface AgentType {
  name: string;
  description: string;
  icon: string;
}

export const agentTypes: AgentType[] = [
  {
    name: "Research Agent",
    description: "Searches the web and summarizes findings",
    icon: "🔍",
  },
  {
    name: "Customer Support Agent",
    description: "Reads messages, checks data, writes responses",
    icon: "🎧",
  },
  {
    name: "Lead Qualification Agent",
    description: "Scores leads against your criteria and outreach in your CRM",
    icon: "🎯",
  },
  {
    name: "Data Enrichment Agent",
    description: "Fills in company, and industry fields automatically",
    icon: "📊",
  },
  {
    name: "Outreach Agent",
    description: "Writes personalized emails or messages for each prospect",
    icon: "✉️",
  },
  {
    name: "Reporting Agent",
    description: "Pulls numbers from multiple sources and formats a weekly report",
    icon: "📈",
  },
  {
    name: "Content Agent",
    description: "Writes posts, articles, or newsletters from a brief",
    icon: "📝",
  },
  {
    name: "QA Agent",
    description: "Reviews other agents' outputs for accuracy before delivery",
    icon: "✅",
  },
];

export const agentAnatomy = [
  {
    title: "The Brain",
    description: "The AI model powering is reasoning - GPT-4o, Claude, Gemini, and others. Different models suit different tasks.",
    icon: "🧠",
  },
  {
    title: "The Knowledge Base",
    description: "Documents, data sources, or databases the agent can draw from to produce accurate, context-aware outputs.",
    icon: "🗄️",
  },
  {
    title: "The Instructions",
    description: "Written in plain English, this defines the agent's role, behavior, tone, and goals.",
    icon: "📋",
  },
  {
    title: "The Tools",
    description: "The actions it can take: Send an email, Update a CRM, Search the web, Write to a Google Doc. The more tools connected, the more it can do.",
    icon: "🔧",
  },
];

export const platformComparison = [
  {
    name: "RELEVANCE AI",
    bestFor: "Full AI workforce for sales and CRM teams",
    features: ["Build teams on a visual canvas", "Invariant feature for plain English setup", "Pre-built templates for BDR, Lead Qual, Support", "Node-based drag-and-drop canvas"],
    pricing: "Free plan available. Paid from $98/month.",
  },
  {
    name: "GUMLOOP",
    bestFor: "Visual multi-agent workflows with Slack and Teams integration",
    features: ["Pre-built templates for 60+ use cases", "Describe workflow in plain language", "Deploy directly to Slack/teams", "Open source"],
    pricing: "Used by teams at Shopify, Instacart, Mercari.",
  },
  {
    name: "ZAPIER",
    bestFor: "Non-technical teams with existing large app stacks",
    features: ["Connects to 8,000+ apps", "Low/No-code visual builder", "Widest integration library", "Simple to use"],
    pricing: "From $19.99/month.",
  },
  {
    name: "LINDY",
    bestFor: "Beginners and personal AI teammates",
    features: ["Describe in plain English, running in under a minute", "Scheduling, Lead Qual, Notes summarization", "Strongest human-in-the-loop controls", "Easy to learn"],
    pricing: "From $19.99/month.",
  },
  {
    name: "RELAY.APP",
    bestFor: "Workflows where a human must approve before any agents executes",
    features: ["Ideal for compliance-sensitive workflows", "Human-in-the-loop required", "Visual builder with optional code", "Simple to use"],
    pricing: "Self-hosted Community Edition is free.",
  },
  {
    name: "NBN",
    bestFor: "Technical users who want full control and self-hosting",
    features: ["Supports four agent architectures, including parallel execution", "Connects to documents, wikis, databases", "Python-based SDK", "Works across Salesforce, Slack, teams"],
    pricing: "Cloud plans from $20/month.",
  },
  {
    name: "CASSIDY",
    bestFor: "Agents that need to understand your company's internal knowledge",
    features: ["Connects to documents, wikis, data sources", "Truly syncs knowledge base with agents", "Custom instructions per agent", "Works across Salesforce, Slack, teams"],
    pricing: "Pricing available on request.",
  },
];

export const buildSteps = [
  {
    step: 1,
    title: "Map The Workflow On Paper",
    details: ["List every step, identify inputs, actions, and outputs.", "This is your team design."],
  },
  {
    step: 2,
    title: "Define Each Agent's Role",
    details: ["Give one clear job, role it, specify trigger(s), action(s), and output."],
  },
  {
    step: 3,
    title: "Choose Your Platform",
    details: ["Select based on need (e.g., Sales/GTM, Slack integration, App Library).", "Human approval. Self-hosting.", "Knowledge base.", "Beginner setup."],
  },
  {
    step: 4,
    title: "Build And Test Each Agent Individually",
    details: ["Name, role, model, instructions, knowledge base, tools.", "Test each input → confirm output."],
  },
  {
    step: 5,
    title: "Connect Agents Into A Team",
    details: ["Open multi-agent canvas.", "Wire them together.", "Define handoff logic (sequential, conditional, human-gated)."],
  },
  {
    step: 6,
    title: "Set The Trigger",
    details: ["Choose activator (e.g., new form entry, email, schedule, Slack message)."],
  },
  {
    step: 7,
    title: "Test The Full Workflow",
    details: ["Run end-to-end with real input.", "Check handoffs.", "Fix issues in visual interface."],
  },
  {
    step: 8,
    title: "Monitor And Refine",
    details: ["Check run logs weekly.", "Fix failures, adjust instructions and logic.", "Team improves over time."],
  },
];

export const commonMistakes = [
  "One agent doing everything — Split overloaded agents. One job per agent.",
  "No workflow map before building — Draw the process on paper first, always.",
  "Testing the full team before testing individuals — Test each agent alone before connecting.",
  "Vague instructions — Tell the agent exactly what to look for, what format to use, what length to produce.",
  "Ignoring logs after launch — Check your agent activity weekly. Silent failures are the most expensive kind.",
];
