"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  roadmapSteps,
  techStackOverview,
  essentialSkills,
  careerPaths,
  learningJourney,
} from "@/data/dev-roadmap";
import {
  Rocket,
  CheckCircle2,
  Code,
  GraduationCap,
  Calendar,
  Users,
  TrendingUp,
  BookOpen,
  Zap,
  Crown,
  ChevronRight,
} from "lucide-react";

export default function DevRoadmapPage() {
  const [activeStep, setActiveStep] = useState<number | null>(null);
  const [hoveredSkill, setHoveredSkill] = useState<string | null>(null);

  const stepColors: Record<number, string> = {
    1: "from-orange-500 to-amber-500",
    2: "from-cyan-500 to-blue-600",
    3: "from-green-500 to-emerald-600",
    4: "from-purple-500 to-violet-600",
    5: "from-yellow-500 to-orange-500",
    6: "from-pink-500 to-rose-600",
    7: "from-indigo-500 to-blue-700",
    8: "from-red-500 to-pink-600",
  };

  const stepIcons: Record<number, string> = {
    1: "🌐",
    2: "⚛️",
    3: "⚡",
    4: "🗄️",
    5: "☁️",
    6: "🧠",
    7: "🏗️",
    8: "🚀",
  };

  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-orange-500/10 border border-orange-500/20 text-sm text-orange-400 mb-4">
          📚 THE COMPLETE
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4">
          Developer{" "}
          <span className="bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            Roadmap
          </span>
        </h1>
        <p className="text-slate-400 max-w-3xl mx-auto text-lg">
          From Zero To Software Engineer — Your step-by-step journey to build modern web apps and launch an amazing tech career.
        </p>

        {/* Tags */}
        <div className="flex flex-wrap justify-center gap-3 mt-6">
          {[
            { label: "Practical", icon: "🎯", desc: "Build real projects" },
            { label: "Modern", icon: "💻", desc: "In-demand skills" },
            { label: "Structured", icon: "📋", desc: "Step-by-step path" },
            { label: "Career Focused", icon: "💰", desc: "High-paying jobs" },
          ].map((tag) => (
            <div key={tag.label} className="flex items-center gap-2 px-4 py-2 bg-white/5 rounded-full border border-white/10">
              <span>{tag.icon}</span>
              <span className="text-sm font-medium text-slate-300">{tag.label}</span>
              <span className="text-xs text-slate-500 hidden sm:inline">— {tag.desc}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Main Roadmap - Timeline */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-12"
      >
        <div className="relative">
          {/* Timeline line (desktop) */}
          <div className="absolute left-8 md:left-1/2 md:-translate-x-px top-0 bottom-0 w-0.5 bg-gradient-to-b from-orange-500 via-purple-500 to-red-500 hidden md:block" />
          
          <div className="space-y-8 md:space-y-12">
            {roadmapSteps.map((step, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: idx % 2 === 0 ? -50 : 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + idx * 0.08 }}
                className={`relative flex flex-col md:flex-row ${
                  idx % 2 === 0 ? "md:flex-row-reverse" : ""
                } gap-8`}
              >
                {/* Timeline node */}
                <div className="absolute left-8 md:left-1/2 -translate-x-1/2 w-[60px] h-[60px] z-10 hidden md:flex">
                  <motion.div
                    whileHover={{ scale: 1.15, rotate: 360 }}
                    transition={{ duration: 0.5 }}
                    onClick={() => setActiveStep(activeStep === step.step ? null : step.step)}
                    className={`w-full h-full rounded-2xl bg-gradient-to-br ${stepColors[step.step]} flex items-center justify-center cursor-pointer shadow-lg`}
                  >
                    <span className="text-2xl">{stepIcons[step.step]}</span>
                  </motion.div>
                </div>
                
                {/* Content Card */}
                <motion.div
                  layout
                  onClick={() => setActiveStep(activeStep === step.step ? null : step.step)}
                  className={`w-full md:w-[calc(50%-40px)] glass-card rounded-2xl p-6 hover:border-opacity-40 transition-all cursor-pointer group ${
                    activeStep === step.step
                      ? `border-l-4 ${stepColors[step.step].includes("orange") ? "border-orange-500" : stepColors[step.step].includes("cyan") ? "border-cyan-500" : stepColors[step.step].includes("green") ? "border-green-500" : stepColors[step.step].includes("purple") ? "border-purple-500" : stepColors[step.step].includes("yellow") ? "border-yellow-500" : stepColors[step.step].includes("pink") ? "border-pink-500" : stepColors[step.step].includes("indigo") ? "border-indigo-500" : "border-red-500"}`
                      : "border border-white/10"
                  }`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 md:hidden rounded-xl bg-gradient-to-br ${stepColors[step.step]} flex items-center justify-center`}>
                        <span className="text-xl">{stepIcons[step.step]}</span>
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2.5 py-1 rounded-full bg-gradient-to-r ${stepColors[step.step]} text-black text-sm font-bold`}>
                            {String(step.step).padStart(2, '0')}
                          </span>
                        </div>
                        <h3 className={`text-lg font-bold mt-2 bg-gradient-to-r ${stepColors[step.step]} bg-clip-text text-transparent`}>
                          {step.title}
                        </h3>
                        <p className="text-sm text-slate-400">{step.subtitle}</p>
                      </div>
                    </div>
                    <ChevronRight className={`w-5 h-5 text-slate-500 group-hover:text-white transition-all ${
                      activeStep === step.step ? "rotate-90" : ""
                    }`} />
                  </div>

                  {/* Technologies */}
                  {step.technologies.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-4">
                      {step.technologies.map((tech, i) => (
                        <span key={i} className="px-3 py-1.5 bg-white/5 rounded-lg text-sm text-slate-300 border border-white/10">
                          {tech.icon && <span className="mr-1">{tech.icon}</span>}
                          {tech.name}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Project badge */}
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-purple-500/20 rounded-lg border border-purple-500/30">
                    <Rocket className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-purple-300">Project: {step.project}</span>
                  </div>

                  {/* Expanded content */}
                  <AnimatePresence>
                    {activeStep === step.step && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="mt-4 pt-4 border-t border-white/10"
                      >
                        <h4 className="font-semibold text-white mb-3">What You'll Learn:</h4>
                        <ul className="space-y-2">
                          {step.whatYouLearn.map((item, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                              <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.section>

      {/* Tech Stack Overview + Skills Grid */}
      <div className="grid lg:grid-cols-2 gap-8 mb-12">
        {/* Tech Stack Overview */}
        <motion.section
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card rounded-2xl p-6 border border-slate-700"
        >
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <Code className="w-6 h-6 text-cyan-400" />
            Tech Stack Overview
          </h2>
          
          {Object.entries(techStackOverview).map(([category, skills]) => (
            <div key={category} className="mb-4 last:mb-0">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2 capitalize">
                {category.replace(/([A-Z])/g, " $1")}
              </h3>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill) => (
                  <span
                    key={skill}
                    onMouseEnter={() => setHoveredSkill(skill)}
                    onMouseLeave={() => setHoveredSkill(null)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-default ${
                      hoveredSkill === skill
                        ? "bg-cyan-500/30 text-cyan-300 scale-105"
                        : "bg-white/5 text-slate-300 hover:bg-white/10"
                    }`}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </motion.section>

        {/* Essential Skills */}
        <motion.section
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.55 }}
          className="glass-card rounded-2xl p-6 border border-slate-700"
        >
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-400" />
            Essential Skills
          </h2>
          
          <div className="space-y-3">
            {essentialSkills.map((skill, idx) => (
              <motion.div
                key={skill}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + idx * 0.05 }}
                className="flex items-center gap-3 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors group"
              >
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center flex-shrink-0">
                  <CheckCircle2 className="w-4 h-4 text-white" />
                </div>
                <span className="font-medium text-slate-200 group-hover:text-white transition-colors">
                  {skill}
                </span>
              </motion.div>
            ))}
          </div>
        </motion.section>
      </div>

      {/* Learning Journey Timeline */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="glass-card rounded-2xl p-8 mb-12 glow-purple border border-purple-500/20"
      >
        <h2 className="text-2xl font-bold text-white text-center mb-8">Your Learning Journey</h2>
        
        <div className="relative overflow-x-auto pb-4">
          <div className="min-w-[800px]">
            {/* Line connecting phases */}
            <div className="absolute top-14 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500 hidden lg:block mx-auto max-w-4xl" />
            
            <div className="flex justify-between relative max-w-4xl mx-auto">
              {learningJourney.map((phase, idx) => (
                <motion.div
                  key={phase.phase}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.65 + idx * 0.08 }}
                  className="flex flex-col items-center text-center px-2"
                >
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-white/10 flex items-center justify-center mb-4 shadow-lg z-10">
                    {[BookOpen, Code, Zap, Rocket, GraduationCap, Users][idx]?.({ className: "w-7 h-7 text-" + ["cyan", "blue", "green", "purple", "pink", "yellow"][idx] + "-400" }) || <Zap className="w-7 h-7 text-white" />}
                  </div>
                  <h3 className="font-bold text-white text-sm">{phase.phase}</h3>
                  <p className="text-xs text-slate-400 mt-1">{phase.desc}</p>
                  
                  {/* Arrow between phases except last */}
                  {idx < learningJourney.length - 1 && (
                    <ChevronRight className="absolute top-14 text-slate-600 hidden lg:block" style={{ left: `calc(${(idx + 0.65) * (100 / learningJourney.length)}%)`, transform: 'translateX(-50%)' }} />
                  )}
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </motion.section>

      {/* Career Paths & Time Info Grid */}
      <div className="grid md:grid-cols-2 gap-8 mb-12">
        {/* Career Paths */}
        <motion.section
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.7 }}
          className="glass-card rounded-2xl p-6 border border-slate-700"
        >
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-green-400" />
            Career Paths
          </h2>
          
          <div className="space-y-3">
            {careerPaths.map((path) => (
              <div
                key={path.role}
                className="flex items-center justify-between p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <Crown className="w-5 h-5 text-yellow-500" />
                  <span className="font-medium text-slate-200">{path.role}</span>
                </div>
                <span className="font-mono text-green-400 font-semibold">${path.salary.split("-")[1]}</span>
              </div>
            ))}
          </div>
        </motion.section>

        {/* Time to Master */}
        <motion.section
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.75 }}
          className="glass-card rounded-2xl p-6 border border-slate-700"
        >
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <Calendar className="w-6 h-6 text-purple-400" />
            Time To Master
          </h2>
          
          <div className="text-center py-6">
            <p className="text-6xl font-bold gradient-text mb-2">12 - 18</p>
            <p className="text-xl text-slate-400">Months</p>
            <p className="text-sm text-slate-500 mt-2">With Consistent Effort</p>
            
            {/* Visual progress bar */}
            <div className="mt-8 space-y-3">
              {[
                { label: "Frontend", progress: 100 },
                { label: "Backend", progress: 80 },
                { label: "Databases", progress: 70 },
                { label: "DevOps", progress: 60 },
                { label: "AI Integration", progress: 45 },
                { label: "System Design", progress: 35 },
                { label: "Soft Skills", progress: 25 },
              ].map((item) => (
                <div key={item.label} className="group">
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span>{item.label}</span>
                    <span>{item.progress}%</span>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${item.progress}%` }}
                      transition={{ delay: 0.9 + item.progress * 0.005, duration: 0.8 }}
                      className="h-full bg-gradient-to-r from-cyan-500 to-purple-500 rounded-full"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      </div>

      {/* Remember Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.85 }}
        className="glass-card rounded-2xl p-8 glow-purple border border-purple-500/20"
      >
        <h2 className="text-xl font-bold text-yellow-400 mb-4">🚀 Remember</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { title: "Be Consistent", desc: "Small steps daily", icon: "✅" },
            { title: "Build In Public", desc: "Share your journey", icon: "🌐" },
            { title: "Never Stop Learning", desc: "Stay curious", icon: "📚" },
            { title: "Help Others Create", desc: "Give back to the community", icon: "🤝" },
          ].map((item) => (
            <div key={item.title} className="p-4 bg-white/5 rounded-xl text-center hover:bg-white/10 transition-colors">
              <span className="text-3xl block mb-2">{item.icon}</span>
              <h3 className="font-bold text-white text-sm">{item.title}</h3>
              <p className="text-xs text-slate-400 mt-1">{item.desc}</p>
            </div>
          ))}
        </div>

        <blockquote className="mt-8 text-center text-lg italic text-slate-300 border-t border-white/10 pt-6">
          &ldquo;The best time to start was yesterday. The second best time is now.&rdquo;
        </blockquote>
      </motion.section>
    </div>
  );
}
