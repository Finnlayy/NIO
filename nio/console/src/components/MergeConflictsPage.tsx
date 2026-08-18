"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  conflictInfo,
  conflictMarkers,
  exampleConflict,
  resolutionSteps,
  quickTips,
  commonMistakesMerge,
  mergeCommandInfo,
  mergeWorkflowSteps,
} from "@/data/merge-conflicts";
import {
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Copy,
  Terminal,
  Lightbulb,
  XCircle,
  GitMerge,
  ArrowRight,
  Play,
} from "lucide-react";

export default function MergeConflictsPage() {
  const [activeStep, setActiveStep] = useState<number>(0);
  const [showBeforeCode, setShowBeforeCode] = useState(true);
  const [copied, setCopied] = useState<string | null>(null);

  const copyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 border border-red-500/20 text-sm text-red-400 mb-4">
          <AlertTriangle className="w-4 h-4" />
          DAY 20 & 21 — GIT SERIES
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4">
          Merge Conflicts & Branches{" "}
          <span className="bg-gradient-to-r from-red-400 to-orange-500 bg-clip-text text-transparent">
            Explained Finally
          </span>
        </h1>
        <p className="text-slate-400 max-w-3xl mx-auto text-lg">
          ⚠️ CONFLICTS HAPPEN. UNDERSTAND. RESOLVE. MOVE FORWARD.
        </p>
      </motion.div>

      {/* Definition Card */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-red-500/30 bg-gradient-to-br from-red-500/5 to-transparent"
      >
        <div className="flex items-start gap-4 mb-6">
          <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white mb-2">What Is A Merge Conflict?</h2>
            <p className="text-slate-300">{conflictInfo.definition}</p>
          </div>
        </div>

        {/* Visual Branch Diagram */}
        <div className="bg-black/40 rounded-xl p-6 overflow-x-auto">
          <svg viewBox="0 0 600 120" className="w-full max-w-[600px] mx-auto" style={{ minHeight: "120px" }}>
            {/* Main branch line */}
            <line x1="50" y1="40" x2="550" y2="40" stroke="#64748b" strokeWidth="3" />
            
            {/* Main branch nodes */}
            {[100, 200, 300, 400, 500].map((x) => (
              <circle key={x} cx={x} cy={40} r="8" fill="#1e293b" stroke="#64748b" strokeWidth="2" />
            ))}
            
            {/* Feature branch line (curves down then up) */}
            <path d="M 200 40 Q 250 100, 350 100 Q 450 100, 450 40" fill="none" stroke="#ef4444" strokeWidth="3" strokeDasharray="5,5" />
            
            {/* Feature branch nodes */}
            {[
              { x: 250, y: 70 },
              { x: 300, y: 90 },
              { x: 350, y: 100 },
              { x: 400, y: 90 },
            ].map((pos) => (
              <circle key={pos.x} cx={pos.x} cy={pos.y} r="7" fill="#ef4444" opacity="0.8" />
            ))}
            
            {/* Conflict marker */}
            <circle cx="450" cy="40" r="12" fill="#dc2626" stroke="#fbbf24" strokeWidth="3" />
            <text x="480" y="45" fill="#dc2626" fontSize="14" fontWeight="bold">CONFLICT!</text>
            
            {/* Labels */}
            <text x="55" y="25" fill="#94a3b8" fontSize="12">main</text>
            <text x="180" y="115" fill="#ef4444" fontSize="12">feature-login</text>
            
            {/* Legend */}
            <circle cx="80" cy="95" r="6" fill="#1e293b" stroke="#64748b" strokeWidth="2" />
            <text x="92" y="99" fill="#94a3b8" fontSize="11">Main Branch</text>
            
            <circle cx="220" cy="95" r="6" fill="#ef4444" opacity="0.8" />
            <text x="232" y="99" fill="#ef4444" fontSize="11">Feature Branch</text>
            
            <circle cx="360" cy="95" r="7" fill="#dc2626" stroke="#fbbf24" strokeWidth="2" />
            <text x="372" y="99" fill="#dc2626" fontSize="11">Conflict on Merge</text>
          </svg>
        </div>
      </motion.section>

      {/* Why conflicts happen */}
      <div className="grid md:grid-cols-2 gap-8 mb-8">
        <motion.section
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.15 }}
          className="glass-card rounded-2xl p-6 border border-orange-500/20"
        >
          <h2 className="text-lg font-bold text-orange-400 mb-4 flex items-center gap-2">
            🚨 Why Conflicts Happen
          </h2>
          <ul className="space-y-3">
            {conflictInfo.whyHappens.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-orange-400 mt-2 flex-shrink-0"></div>
                <p className="text-slate-300 text-sm">{reason}</p>
              </li>
            ))}
          </ul>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.15 }}
          className="glass-card rounded-2xl p-6 border border-cyan-500/20"
        >
          <h2 className="text-lg font-bold text-cyan-400 mb-4">📝 Same Line Edited Problem (Example)</h2>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-blue-900/20 rounded-lg p-3 border border-blue-500/30">
              <p className="text-xs font-semibold text-blue-400 mb-2">{exampleConflict.mainBranch.file}</p>
              <pre className="code-font text-xs text-slate-300 overflow-x-auto">{exampleConflict.mainBranch.code}</pre>
            </div>
            <div className="bg-green-900/20 rounded-lg p-3 border border-green-500/30">
              <p className="text-xs font-semibold text-green-400 mb-2">{exampleConflict.featureBranch.file}</p>
              <pre className="code-font text-xs text-slate-300 overflow-x-auto">{exampleConflict.featureBranch.code}</pre>
            </div>
          </div>
        </motion.section>
      </div>

      {/* Conflict Markers Explained */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-yellow-500/20"
      >
        <h2 className="text-xl font-bold text-yellow-400 mb-4">⚠️ Conflict Markers (What You Will See)</h2>
        
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-black/40 rounded-lg p-4 overflow-x-auto">
            <pre className="code-font text-sm text-slate-300 whitespace-pre-wrap">{exampleConflict.conflictResult}</pre>
          </div>
          
          <div>
            <h3 className="font-semibold text-white mb-3">Markers Explained:</h3>
            <div className="space-y-3">
              {conflictMarkers.explanation.map((marker, idx) => (
                <div key={idx} className="flex items-start gap-3 p-2 rounded-lg hover:bg-white/5">
                  <code className="code-font text-xs text-pink-400 bg-black/40 px-2 py-1 rounded flex-shrink-0">
                    {marker.marker}
                  </code>
                  <p className="text-sm text-slate-300">{marker.meaning}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.section>

      {/* Resolution Steps - Interactive */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-green-500/20"
      >
        <h2 className="text-xl font-bold text-green-400 mb-6">✅ How To Resolve A Merge Conflict (Step-by-Step)</h2>
        
        <div className="relative">
          {/* Progress Line */}
          <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-white/10 hidden sm:block" />
          
          <div className="space-y-4">
            {resolutionSteps.map((step, idx) => (
              <div key={idx} className="relative flex gap-4">
                {/* Step Number Circle */}
                <button
                  onClick={() => setActiveStep(idx)}
                  className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center font-bold transition-all flex-shrink-0 ${
                    activeStep === idx
                      ? "bg-gradient-to-br from-green-500 to-emerald-600 text-white scale-110 shadow-lg shadow-green-500/30"
                      : activeStep > idx
                      ? "bg-green-500/30 text-green-400"
                      : "bg-white/10 text-slate-400 hover:bg-white/20"
                  }`}
                >
                  {activeStep > idx ? <CheckCircle className="w-5 h-5" /> : step.step}
                </button>
                
                {/* Content */}
                <div
                  onClick={() => setActiveStep(idx)}
                  className={`flex-1 p-4 rounded-xl cursor-pointer transition-all ${
                    activeStep === idx
                      ? "bg-green-500/10 border border-green-500/30"
                      : "bg-white/5 border border-transparent hover:bg-white/10"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className={`font-bold ${activeStep === idx ? "text-green-400" : "text-white"}`}>
                        {step.title}
                      </h3>
                      <p className="text-sm text-slate-400 mt-1">{step.description}</p>
                      {step.command && (
                        <div className="mt-3 relative group">
                          <code className="code-font text-sm text-cyan-300 bg-black/50 px-3 py-2 rounded-lg inline-block">
                            {step.command}
                          </code>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              copyText(step.command);
                            }}
                            className="ml-2 p-1.5 rounded hover:bg-white/10 transition-colors"
                          >
                            <Copy className="w-4 h-4 text-slate-400 hover:text-white" />
                          </button>
                        </div>
                      )}
                    </div>
                    {activeStep !== idx && (
                      <ChevronRight className="w-5 h-5 text-slate-500 mt-1" />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Before/After Resolving */}
        <div className="mt-8 grid md:grid-cols-2 gap-6">
          <div className={`rounded-xl overflow-hidden ${showBeforeCode ? 'ring-2 ring-red-500' : ''}`}>
            <div className="bg-red-500/20 px-4 py-2 flex items-center justify-between cursor-pointer" onClick={() => setShowBeforeCode(true)}>
              <span className="font-semibold text-red-400">❌ Before Resolving</span>
              <AlertTriangle className="w-4 h-4 text-red-400" />
            </div>
            <pre className="code-font text-sm text-red-300 bg-black/60 p-4 overflow-x-auto h-48">
              {exampleConflict.conflictResult}
            </pre>
          </div>
          <div className={`rounded-xl overflow-hidden ${!showBeforeCode ? 'ring-2 ring-green-500' : ''}`}>
            <div className="bg-green-500/20 px-4 py-2 flex items-center justify-between cursor-pointer" onClick={() => setShowBeforeCode(false)}>
              <span className="font-semibold text-green-400">✅ After Resolving</span>
              <CheckCircle className="w-4 h-4 text-green-400" />
            </div>
            <pre className="code-font text-sm text-green-300 bg-black/60 p-4 overflow-x-auto h-48">
              {exampleConflict.resolvedCode}
            </pre>
          </div>
        </div>
        
        <p className="text-center text-sm text-slate-400 mt-4">
          Conflict resolved! File is clean and ready to commit.
        </p>
      </motion.section>

      {/* Merge Command Info */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-purple-500/20"
      >
        <h2 className="text-xl font-bold text-purple-400 mb-6 flex items-center gap-2">
          <GitMerge className="w-6 h-6" />
          The Merge Command
        </h2>
        
        <div className="bg-black/40 rounded-xl p-6 text-center mb-6">
          <code className="code-font text-2xl text-green-400">$ git merge feature-login</code>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div>
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
              📝 What Does It Do?
            </h3>
            <ul className="space-y-2">
              {mergeCommandInfo.whatDoesItDo.map((item, i) => (
                <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                  <span className="text-purple-400">•</span> {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
              ⭐ Why Is It Useful?
            </h3>
            <ul className="space-y-2">
              {mergeCommandInfo.whyIsItUseful.map((item, i) => (
                <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                  <span className="text-yellow-400">•</span> {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
              ⏰ When Do Developers Use It?
            </h3>
            <ul className="space-y-2">
              {mergeCommandInfo.whenToUse.map((item, i) => (
                <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                  <span className="text-cyan-400">•</span> {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </motion.section>

      {/* Merge Workflow */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-orange-500/20"
      >
        <h2 className="text-xl font-bold text-orange-400 mb-6">🔄 Merge Workflow (Step-by-Step)</h2>
        
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          {mergeWorkflowSteps.map((step, idx) => (
            <div key={idx} className="flex items-center gap-4 md:flex-col md:text-center">
              <div className="w-14 h-14 rounded-full bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center text-2xl font-bold text-white flex-shrink-0">
                {step.icon}
              </div>
              <div className="max-w-[150px]">
                <h4 className="font-bold text-white text-sm">{step.title}</h4>
                <p className="text-xs text-slate-400 mt-1">{step.desc}</p>
                {step.command && (
                  <code className="code-font text-[10px] text-cyan-400 bg-black/40 px-1.5 py-0.5 rounded mt-1 block truncate">
                    {step.command}
                  </code>
                )}
              </div>
              {idx < mergeWorkflowSteps.length - 1 && (
                <ArrowRight className="w-6 h-6 text-orange-500 hidden md:block mt-2" />
              )}
              {idx < mergeWorkflowSteps.length - 1 && (
                <ChevronRight className="w-5 h-5 text-orange-500 md:hidden flex-shrink-0" />
              )}
            </div>
          ))}
        </div>
      </motion.section>

      {/* Quick Tips & Mistakes */}
      <div className="grid md:grid-cols-2 gap-8">
        <motion.section
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-2xl p-6 border border-green-500/20"
        >
          <h2 className="text-lg font-bold text-green-400 mb-4 flex items-center gap-2">
            <Lightbulb className="w-5 h-5" /> Quick Tips
          </h2>
          <ul className="space-y-3">
            {quickTips.map((tip, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-slate-300">{tip}</span>
              </li>
            ))}
          </ul>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-2xl p-6 border border-red-500/20"
        >
          <h2 className="text-lg font-bold text-red-400 mb-4 flex items-center gap-2">
            <XCircle className="w-5 h-5" /> Common Mistakes
          </h2>
          <ul className="space-y-3">
            {commonMistakesMerge.map((mistake, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-slate-300">{mistake}</span>
              </li>
            ))}
          </ul>
        </motion.section>
      </div>

      {/* Footer Quote */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.45 }}
        className="mt-12 text-center glass-card rounded-2xl p-6 glow-cyan"
      >
        <p className="text-sm text-slate-400 uppercase tracking-wider">
          7 Days of Git | ToolSprint | Ship Projects
        </p>
        <p className="text-lg font-bold gradient-text mt-2">CONFLICTS HAPPEN. UNDERSTAND. RESOLVE. MOVE FORWARD.</p>
      </motion.div>
    </div>
  );
}
