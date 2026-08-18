"use client";

import { motion } from "framer-motion";
import { topics } from "@/data/topics";
import { ArrowRight, Sparkles, BookOpen, Zap, Users, Trophy } from "lucide-react";

interface HomePageProps {
  onTopicSelect: (topicId: string) => void;
}

export default function HomePage({ onTopicSelect }: HomePageProps) {
  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Hero Section */}
      <motion.section
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="text-center mb-20"
      >
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: "spring" }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-purple-500/20 text-sm text-slate-300 mb-6"
        >
          <Sparkles className="w-4 h-4 text-yellow-400" />
          Interactive Developer Learning Platform
          <Sparkles className="w-4 h-4 text-yellow-400" />
        </motion.div>

        <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold mb-6">
          <span className="gradient-text">Master Modern</span>
          <br />
          <span className="text-white">Development Skills</span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-400 max-w-3xl mx-auto mb-10">
          Comprehensive interactive guides covering AI Agents, Git/GitHub,
          Software Engineering, and your complete path from beginner to professional developer.
        </p>

        {/* Quick Stats */}
        <div className="flex flex-wrap justify-center gap-8 mb-12">
          <div className="flex items-center gap-2 text-slate-300">
            <BookOpen className="w-5 h-5 text-cyan-400" />
            <span><strong className="text-white">7</strong> Learning Modules</span>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <Zap className="w-5 h-5 text-yellow-400" />
            <span><strong className="text-white">100+</strong> Interactive Topics</span>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <Users className="w-5 h-4 text-green-400" />
            <span><strong className="text-white">Step-by-Step</strong> Guides</span>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <Trophy className="w-5 h-5 text-orange-400" />
            <span><strong className="text-white">Real World</strong> Examples</span>
          </div>
        </div>
      </motion.section>

      {/* Topic Cards Grid */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {topics.map((topic, index) => (
          <motion.div
            key={topic.id}
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 + 0.3, duration: 0.5 }}
            whileHover={{ scale: 1.02, y: -5 }}
            onClick={() => onTopicSelect(topic.id)}
            className="group cursor-pointer glass-card rounded-2xl p-6 hover:border-opacity-50 transition-all duration-300"
            style={{
              borderColor: topic.gradient.replace("linear-gradient", "linear-gradient").includes("cyan")
                ? "rgba(6,182,212,0.3)"
                : topic.gradient.includes("green")
                ? "rgba(16,185,129,0.3)"
                : topic.gradient.includes("red")
                ? "rgba(239,68,68,0.3)"
                : topic.gradient.includes("purple")
                ? "rgba(139,92,246,0.3)"
                : topic.gradient.includes("orange")
                ? "rgba(249,115,22,0.3)"
                : "rgba(255,255,255,0.1)",
            }}
          >
            <div className="flex items-start justify-between mb-4">
              <span className="text-4xl">{topic.icon}</span>
              <ArrowRight className="w-5 h-5 text-slate-500 group-hover:text-white group-hover:translate-x-1 transition-all" />
            </div>

            <h3 className={`text-xl font-bold bg-gradient-to-r ${topic.color} bg-clip-text text-transparent mb-2`}>
              {topic.title}
            </h3>
            <p className="text-slate-400 text-sm">{topic.subtitle}</p>

            <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
              <span className="text-xs text-slate-500 uppercase tracking-wider">Explore Now →</span>
              <div
                className="w-8 h-1 rounded-full bg-gradient-to-r opacity-60 group-hover:opacity-100 transition-opacity"
                style={{ backgroundImage: topic.gradient }}
              />
            </div>
          </motion.div>
        ))}
      </section>

      {/* Quote Section */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        className="mt-20 text-center"
      >
        <div className="glass-card rounded-2xl p-8 md:p-12 max-w-4xl mx-auto glow-purple">
          <blockquote className="text-xl md:text-2xl font-light text-slate-200 italic">
            &ldquo;The best time to start was yesterday. The second best time is now.&rdquo;
          </blockquote>
          <div className="mt-6 flex items-center justify-center gap-2 text-slate-400">
            <Sparkles className="w-4 h-4" />
            <span>Start your learning journey today</span>
            <Sparkles className="w-4 h-4" />
          </div>
        </div>
      </motion.section>
    </div>
  );
}
