export interface RoadmapStep {
  step: number;
  title: string;
  subtitle: string;
  icon: string;
  color: string;
  technologies: { name: string; icon: string }[];
  whatYouLearn: string[];
  project: string;
}

export const roadmapSteps: RoadmapStep[] = [
  {
    step: 1,
    title: "Frontend Foundations",
    subtitle: "Start Here",
    icon: "🌐",
    color: "from-orange-500 to-amber-500",
    technologies: [
      { name: "HTML", icon: "5" },
      { name: "CSS", icon: "3" },
      { name: "JavaScript", icon: "JS" },
    ],
    whatYouLearn: ["Structure with HTML", "Style with CSS", "Interactivity with JavaScript", "Build responsive layouts"],
    project: "Personal Portfolio Website",
  },
  {
    step: 2,
    title: "Frontend Library",
    subtitle: "Build Dynamic UIs",
    icon: "⚛️",
    color: "from-cyan-500 to-blue-600",
    technologies: [
      { name: "React", icon: "⚛️" },
    ],
    whatYouLearn: ["Components & Props", "State & Hooks", "Routing", "Context API"],
    project: "Task Management App",
  },
  {
    step: 3,
    title: "Backend Development",
    subtitle: "Power Your App",
    icon: "⚡",
    color: "from-green-500 to-emerald-600",
    technologies: [
      { name: "Node.js", icon: "N" },
      { name: "Express.js", icon: "EX" },
      { name: "REST API", icon: "API" },
    ],
    whatYouLearn: ["Server-side JavaScript", "RESTful APIs", "Authentication", "Middleware & Routes"],
    project: "Blog API with Auth",
  },
  {
    step: 4,
    title: "Databases",
    subtitle: "Store & Manage Data",
    icon: "🗄️",
    color: "from-purple-500 to-violet-600",
    technologies: [
      { name: "MongoDB", icon: "🍃" },
      { name: "SQL", icon: "db" },
      { name: "Redis", icon: "R" },
    ],
    whatYouLearn: ["NoSQL with MongoDB", "SQL Basics", "Relationships", "Data Modeling"],
    project: "User Data Analytics Dashboard",
  },
  {
    step: 5,
    title: "Cloud Computing",
    subtitle: "Deploy & Scale",
    icon: "☁️",
    color: "from-yellow-500 to-orange-500",
    technologies: [
      { name: "AWS", icon: "☁️" },
      { name: "Firebase", icon: "🔥" },
      { name: "Docker", icon: "🐳" },
    ],
    whatYouLearn: ["Cloud Hosting", "CI/CD Basics", "Docker Containers", "Environment Management"],
    project: "Deploy Full Stack App to Cloud",
  },
  {
    step: 6,
    title: "AI Tools & Integration",
    subtitle: "Add Intelligence",
    icon: "🧠",
    color: "from-pink-500 to-rose-600",
    technologies: [
      { name: "OpenAI API", icon: "🤖" },
      { name: "LangChain", icon: "L" },
      { name: "Vector DB", icon: "V" },
    ],
    whatYouLearn: ["Integrate AI APIs", "LLM Basics", "Prompt Engineering", "Build AI Features"],
    project: "AI Chatbot Assistant",
  },
  {
    step: 7,
    title: "System Design",
    subtitle: "Design Scalable Apps",
    icon: "🏗️",
    color: "from-indigo-500 to-blue-700",
    technologies: [],
    whatYouLearn: ["System Design Basics", "Scalability Concepts", "Caching Strategies", "Microservices Intro"],
    project: "Design a Scalable System",
  },
  {
    step: 8,
    title: "Software Engineering",
    subtitle: "Launch Your Career",
    icon: "🚀",
    color: "from-red-500 to-pink-600",
    technologies: [
      { name: "Git & GitHub", icon: "📦" },
      { name: "Testing", icon: "✅" },
      { name: "Best Practices", icon: "📋" },
    ],
    whatYouLearn: ["Version Control", "Testing & Debugging", "Code Quality", "Agile & Teamwork"],
    project: "Contribute to Open Source",
  },
];

export const techStackOverview = {
  frontend: ["HTML", "CSS", "JavaScript", "TypeScript", "React", "Next.js"],
  backend: ["Node.js", "Express.js", "REST API", "GraphQL"],
  database: ["MongoDB", "SQL", "PostgreSQL", "Redis"],
  devopsCloud: ["AWS", "Docker", "Firebase", "Vercel"],
  aiTools: ["OpenAI", "LangChain", "Vector DB", "Pinecone"],
};

export const essentialSkills = [
  "Problem Solving",
  "Data Structures",
  "Web Development",
  "System Design",
  "Version Control",
  "Testing",
  "Cloud Deployment",
  "AI & Automation",
  "Communication",
];

export const careerPaths = [
  { role: "Frontend Developer", salary: "$70K - $130K" },
  { role: "Full Stack Developer", salary: "$100K - $160K" },
  { role: "Backend Developer", salary: "$90K - $150K" },
  { role: "DevOps Engineer", salary: "$100K - $160K" },
  { role: "AI Engineer", salary: "$120K - $200K" },
  { role: "Software Engineer", salary: "$100K - $180K" },
];

export const learningJourney = [
  { phase: "LEARN", desc: "Fundamentals" },
  { phase: "BUILD", desc: "Projects" },
  { phase: "PRACTICE", desc: "Consistently" },
  { phase: "DEPLOY", desc: "Your Apps" },
  { phase: "GROW", desc: "Your Career" },
  { phase: "INSPIRE", desc: "Others" },
];
