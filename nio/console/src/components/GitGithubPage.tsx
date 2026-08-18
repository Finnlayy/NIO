"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  gitBasics,
  undoCommands,
  stashCommands,
  tagCommands,
  remoteCommands,
  viewSearchCommands,
  githubEssentials,
  workflows,
  bestPractices,
} from "@/data/git-github";
import {
  Copy,
  Check,
  Terminal,
  GitBranch,
  BookOpen,
  Star,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  Search,
  Globe,
} from "lucide-react";

export default function GitGithubPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState("basics");
  const [showWorkflow, setShowWorkflow] = useState<number | null>(0);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCommand(text);
    setTimeout(() => setCopiedCommand(null), 2000);
  };

  const categories = [
    { id: "basics", label: "Basics", icon: GitBranch, commands: gitBasics },
    { id: "undo", label: "Undo Changes", icon: terminalIcon, commands: undoCommands },
    { id: "stash", label: "Stash Commands", icon: FolderIcon, commands: stashCommands },
    { id: "tags", label: "Tag Commands", icon: TagIcon, commands: tagCommands },
    { id: "remote", label: "Remote Commands", icon: CloudIcon, commands: remoteCommands },
    { id: "view", label: "View & Search", icon: Search, commands: viewSearchCommands },
  ];

  const filteredCommands = categories
    .find((c) => c.id === activeCategory)
    ?.commands.filter(
      (cmd) =>
        cmd.command.toLowerCase().includes(searchTerm.toLowerCase()) ||
        cmd.description.toLowerCase().includes(searchTerm.toLowerCase())
    ) || [];

  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/10 border border-green-500/20 text-sm text-green-400 mb-4">
          <GitBranch className="w-4 h-4" />
          GITHUB CHEAT SHEET
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4">
          Complete{" "}
          <span className="bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">
            Git & GitHub
          </span>{" "}
          Guide
        </h1>
        <p className="text-slate-400 max-w-3xl mx-auto">
          Essential Git & GitHub Commands, Workflows & Best Practices for every developer
        </p>
      </motion.div>

      {/* Main Grid */}
      <div className="grid lg:grid-cols-3 gap-8">
        {/* Left Column - Git Commands */}
        <div className="lg:col-span-2 space-y-6">
          {/* Search and Categories */}
          <motion.section
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card rounded-2xl p-6 border border-green-500/20"
          >
            <div className="flex flex-col sm:flex-row gap-4 mb-6">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search commands..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-green-500 transition-colors"
                />
              </div>
              {/* Category Tabs */}
              <div className="flex gap-2 overflow-x-auto pb-1">
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setActiveCategory(cat.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                      activeCategory === cat.id
                        ? "bg-green-500 text-black"
                        : "bg-white/5 text-slate-400 hover:text-white"
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Command List */}
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-2">
              {filteredCommands.map((cmd, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.02 }}
                  className="group p-3 rounded-lg bg-black/30 hover:bg-black/50 transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <code className="code-font text-sm text-cyan-300 bg-slate-800 px-3 py-1.5 rounded-md whitespace-pre-wrap break-all">
                      {cmd.command}
                    </code>
                    <button
                      onClick={() => copyToClipboard(cmd.command)}
                      className="p-2 rounded-lg hover:bg-white/10 transition-colors flex-shrink-0"
                    >
                      {copiedCommand === cmd.command ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4 text-slate-400 group-hover:text-white" />
                      )}
                    </button>
                  </div>
                  <p className="text-sm text-slate-400 mt-2">{cmd.description}</p>
                </motion.div>
              ))}
              {filteredCommands.length === 0 && (
                <p className="text-center text-slate-500 py-8">No commands found</p>
              )}
            </div>
          </motion.section>

          {/* Workflows Section */}
          <motion.section
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card rounded-2xl p-6 border border-purple-500/20"
          >
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <WorkflowIcon className="w-6 h-6 text-purple-400" />
              Common GitHub Workflows
            </h2>
            <div className="space-y-4">
              {workflows.map((workflow, idx) => (
                <div key={idx} className="bg-white/5 rounded-xl overflow-hidden">
                  <button
                    onClick={() => setShowWorkflow(showWorkflow === idx ? null : idx)}
                    className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
                  >
                    <span className="font-semibold text-white">{workflow.title}</span>
                    {showWorkflow === idx ? (
                      <ChevronUp className="w-5 h-5 text-purple-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-slate-400" />
                    )}
                  </button>
                  <AnimatePresence>
                    {showWorkflow === idx && (
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: "auto" }}
                        exit={{ height: 0 }}
                        className="px-4 pb-4"
                      >
                        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4">
                          {workflow.steps.map((step, i) => (
                            <div key={i} className="flex items-center">
                              <div className="px-3 py-2 bg-purple-500/20 border border-purple-500/30 rounded-lg text-center min-w-[100px]">
                                <div className="font-semibold text-purple-300 text-xs">{step}</div>
                              </div>
                              {i < workflow.steps.length - 1 && (
                                <ArrowIcon className="w-5 h-5 text-purple-500/50 mx-1 hidden sm:block" />
                              )}
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>
          </motion.section>

          {/* Best Practices */}
          <motion.section
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.25 }}
            className="glass-card rounded-2xl p-6 border border-yellow-500/20"
          >
            <h2 className="text-xl font-bold text-yellow-400 mb-4 flex items-center gap-2">
              <Lightbulb className="w-6 h-6" />
              Best Practices
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {bestPractices.map((practice, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20"
                >
                  <Check className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-slate-300">{practice}</span>
                </div>
              ))}
            </div>
          </motion.section>
        </div>

        {/* Right Column - GitHub Essentials */}
        <div className="space-y-6">
          <motion.section
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card rounded-2xl p-6 border border-emerald-500/20"
          >
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <Globe className="w-6 h-6 text-emerald-400" />
              GitHub Essentials
            </h2>
            <div className="space-y-3">
              {githubEssentials.map((item, idx) => (
                <div
                  key={idx}
                  className="p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group cursor-pointer"
                >
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{item.icon}</span>
                    <div>
                      <h3 className="font-semibold text-white text-sm">{item.name}</h3>
                      <p className="text-xs text-slate-400 mt-1">{item.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.section>

          {/* Pro Tip */}
          <motion.section
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card rounded-2xl p-6 glow-green border border-green-500/20"
          >
            <div className="flex items-start gap-3">
              <Lightbulb className="w-8 h-8 text-yellow-400 flex-shrink-0" />
              <div>
                <h3 className="font-bold text-yellow-400 mb-2">Pro Tip</h3>
                <p className="text-sm text-slate-300">
                  Practice regularly, explore open source projects and build your portfolio.
                  Consistency is the key to becoming a better developer!
                </p>
              </div>
            </div>
          </motion.section>

          {/* README Template Preview */}
          <motion.section
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.25 }}
            className="glass-card rounded-2xl p-6 border border-blue-500/20"
          >
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-blue-400" />
              README Template
            </h2>
            <pre className="code-font text-xs bg-black/40 p-4 rounded-lg text-slate-300 overflow-x-auto">
{`# Project Title

A short description of your project.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)

## Features
- Feature 1
- Feature 2

## Installation
\`\`\`
git clone repo_url
npm install
\`\`\`

## Usage
Explain how to use your project.

## License
This project is licensed under MIT.`}
            </pre>
          </motion.section>
        </div>
      </div>

      {/* Bottom Quote */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.35 }}
        className="mt-12 text-center glass-card rounded-2xl p-8 glow-green"
      >
        <p className="text-xl md:text-2xl font-light text-slate-200 italic">
          &ldquo;Code + Commit + Push = Progress&rdquo;
        </p>
        <div className="mt-4 flex items-center justify-center gap-2 text-green-400">
          <Star className="w-5 h-5 fill-current" />
          <span>Keep pushing forward</span>
        </div>
      </motion.div>
    </div>
  );
}

// Icon components
function terminalIcon(props: any) {
  return <Terminal {...props} />;
}
function FolderIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" {...props}>
      <path fill="none" stroke="currentColor" strokeWidth="2" d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
  );
}
function TagIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" {...props}>
      <path fill="none" stroke="currentColor" strokeWidth="2" d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01"/>
    </svg>
  );
}
function CloudIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" {...props}>
      <path fill="none" stroke="currentColor" strokeWidth="2" d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
    </svg>
  );
}
function WorkflowIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" {...props}>
      <path fill="none" stroke="currentColor" strokeWidth="2" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8" stroke="currentColor" fill="none" strokeWidth="2"/>
      <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="2"/>
      <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="2"/>
    </svg>
  );
}
function ArrowIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" {...props}>
      <polyline points="9 18 15 12 9 6" fill="none" stroke="currentColor" strokeWidth="2"/>
    </svg>
  );
}
