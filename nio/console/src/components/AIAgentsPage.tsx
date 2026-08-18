"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  agentTypes,
  agentAnatomy,
  platformComparison,
  buildSteps,
  commonMistakes,
} from "@/data/ai-agents";
import {
  Bot,
  Brain,
  Database,
  FileText,
  Wrench,
  ArrowRight,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Layers,
  Workflow,
} from "lucide-react";

export default function AIAgentsPage() {
  const [selectedAgentType, setSelectedAgentType] = useState<number | null>(null);
  const [selectedStep, setSelectedStep] = useState<number | null>(null);
  const [showMistakes, setShowMistakes] = useState(false);

  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-sm text-cyan-400 mb-4">
          <Bot className="w-4 h-4" />
          AI AGENTS GUIDE
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4">
          How To Build A Team Of{" "}
          <span className="gradient-text">AI Agents</span>
        </h1>
        <p className="text-slate-400 max-w-3xl mx-auto">
          By Shushant Lakhiani — Learn to build intelligent AI agent teams that automate your entire workflow
        </p>
      </motion.div>

      {/* What is an AI Agent */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card rounded-2xl p-8 mb-8 glow-cyan border border-cyan-500/20"
      >
        <div className="flex items-start gap-4 mb-6">
          <Bot className="w-10 h-10 text-cyan-400 flex-shrink-0 mt-1" />
          <div>
            <h2 className="text-2xl font-bold text-white mb-3">What Is An AI Agent?</h2>
            <p className="text-slate-300 mb-4">
              An AI agent is a software system that reasons, plans, and takes action on its own.
              It reads context, makes decisions, uses tools, and completes tasks without you doing each step manually.
            </p>
            <p className="text-cyan-300 font-medium">
              One agent handles one job. A team of agents handles your entire workflow.
            </p>
          </div>
        </div>

        {/* Agent Flow Diagram */}
        <div className="bg-black/30 rounded-xl p-6 overflow-x-auto">
          <div className="flex items-center justify-between min-w-[600px]">
            {["Input", "Reasoning/Planning", "Tool Use", "Action", "Output"].map((step, i) => (
              <div key={step} className="flex items-center">
                <div className={`px-4 py-2 rounded-lg ${i === 0 ? 'bg-blue-500/20 text-blue-400' : i === 4 ? 'bg-green-500/20 text-green-400' : 'bg-purple-500/20 text-purple-400'} font-medium text-sm`}>
                  {step}
                </div>
                {i < 4 && (
                  <ArrowRight className="w-5 h-5 text-slate-500 mx-2 flex-shrink-0" />
                )}
              </div>
            ))}
            <div className="ml-4 px-4 py-2 rounded-lg bg-slate-700/50 text-slate-300 text-sm">
              🤖 Agent
            </div>
          </div>
        </div>
      </motion.section>

      {/* Two Column Layout: What is a team + What makes a team */}
      <div className="grid md:grid-cols-2 gap-8 mb-8">
        {/* What is a Team of AI Agents */}
        <motion.section
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-2xl p-6 border border-green-500/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <Layers className="w-8 h-8 text-green-400" />
            <h2 className="text-xl font-bold text-white">What Is A Team Of AI Agents?</h2>
          </div>
          <p className="text-slate-300 text-sm mb-4">
            A group of specialized agents working together on a shared goal. Each agent owns one part of the process and passes its output to the next.
          </p>
          <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
            <p className="text-xs text-green-400 font-semibold mb-2">📌 Real example:</p>
            <p className="text-sm text-slate-300">
              A marketing team runs one agent to monitor competitor pricing, one to draft weekly summaries, and one for reporting. Each agent does one job instead of one agent doing everything poorly.
            </p>
          </div>
        </motion.section>

        {/* Anatomy of One Agent */}
        <motion.section
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.25 }}
          className="glass-card rounded-2xl p-6 border border-purple-500/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <Workflow className="w-8 h-8 text-purple-400" />
            <h2 className="text-xl font-bold text-white">The Anatomy Of One Agent</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {agentAnatomy.map((part, idx) => (
              <div key={idx} className="bg-white/5 rounded-lg p-3 hover:bg-white/10 transition-colors">
                <span className="text-2xl">{part.icon}</span>
                <h4 className="font-semibold text-white text-sm mt-1">{part.title}</h4>
                <p className="text-xs text-slate-400 mt-1">{part.description}</p>
              </div>
            ))}
          </div>
        </motion.section>
      </div>

      {/* Types of Agents You Can Build */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-cyan-500/20"
      >
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <Bot className="w-7 h-7 text-cyan-400" />
          Types Of Agents You Can Build
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {agentTypes.map((agent, idx) => (
            <motion.div
              key={idx}
              whileHover={{ scale: 1.03 }}
              onClick={() => setSelectedAgentType(selectedAgentType === idx ? null : idx)}
              className={`cursor-pointer rounded-xl p-4 transition-all ${
                selectedAgentType === idx
                  ? "bg-cyan-500/20 border-cyan-400 border"
                  : "bg-white/5 border border-transparent hover:bg-white/10"
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="text-3xl">{agent.icon}</span>
                <div>
                  <h3 className="font-semibold text-white text-sm">{agent.name}</h3>
                  <p className="text-xs text-slate-400 mt-1">{agent.description}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.section>

      {/* Build Steps - Interactive */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-pink-500/20"
      >
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          🔢 How To Build Your Agent Team: Step By Step
        </h2>
        <div className="space-y-3">
          {buildSteps.map((step) => (
            <motion.div
              key={step.step}
              onClick={() => setSelectedStep(selectedStep === step.step ? null : step.step)}
              className="cursor-pointer rounded-xl overflow-hidden bg-white/5 hover:bg-white/10 transition-all"
            >
              <div className="flex items-center gap-4 p-4">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center font-bold text-white flex-shrink-0">
                  {step.step}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-white">{step.title}</h3>
                </div>
                {selectedStep === step.step ? (
                  <ChevronUp className="w-5 h-5 text-slate-400" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-slate-400" />
                )}
              </div>
              <AnimatePresence>
                {selectedStep === step.step && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="px-4 pb-4"
                  >
                    <ul className="space-y-2 ml-14">
                      {step.details.map((detail, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                          <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                          {detail}
                        </li>
                      ))}
                    </ul>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </motion.section>

      {/* No-Code Platforms Comparison */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-yellow-500/20"
      >
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          💻 The Best No-Code Platforms (May 2026)
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left p-3 text-yellow-400 font-semibold">Platform</th>
                <th className="text-left p-3 text-yellow-400 font-semibold hidden sm:table-cell">Best For</th>
                <th className="text-left p-3 text-yellow-400 font-semibold hidden md:table-cell">Key Features</th>
                <th className="text-left p-3 text-yellow-400 font-semibold hidden lg:table-cell">Pricing</th>
              </tr>
            </thead>
            <tbody>
              {platformComparison.map((platform, idx) => (
                <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer">
                  <td className="p-3">
                    <span className="font-semibold text-white">{platform.name}</span>
                  </td>
                  <td className="p-3 text-slate-400 hidden sm:table-cell">{platform.bestFor}</td>
                  <td className="p-3 hidden md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {platform.features.slice(0, 2).map((f, i) => (
                        <span key={i} className="px-2 py-0.5 bg-white/10 rounded text-xs text-slate-300">{f}</span>
                      ))}
                      {platform.features.length > 2 && (
                        <span className="px-2 py-0.5 bg-yellow-500/10 text-yellow-400 rounded text-xs">+{platform.features.length - 2}</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-slate-400 hidden lg:table-cell">{platform.pricing}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.section>

      {/* Common Mistakes */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45 }}
        className="glass-card rounded-2xl p-6 border border-red-500/20"
      >
        <button
          onClick={() => setShowMistakes(!showMistakes)}
          className="w-full flex items-center justify-between"
        >
          <h2 className="text-2xl font-bold text-red-400 flex items-center gap-3">
            ⚠️ Common Mistakes To Avoid
          </h2>
          {showMistakes ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>
        <AnimatePresence>
          {showMistakes && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-4 space-y-3"
            >
              {commonMistakes.map((mistake, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                  <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-slate-300">{mistake}</p>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.section>
    </div>
  );
}
