"use client";

import { motion } from "framer-motion";
import { topics } from "@/data/topics";
import { Menu, X, GraduationCap } from "lucide-react";

interface NavigationProps {
  activeTopic: string;
  onTopicChange: (topicId: string) => void;
  isMobileMenuOpen: boolean;
  onMobileMenuToggle: () => void;
}

export default function Navigation({
  activeTopic,
  onTopicChange,
  isMobileMenuOpen,
  onMobileMenuToggle,
}: NavigationProps) {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass-card border-b border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => onTopicChange("home")}
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
              <GraduationCap className="w-6 h-6 text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-bold text-white">DevKnowledge Hub</h1>
              <p className="text-xs text-slate-400">Interactive Learning Platform</p>
            </div>
          </motion.div>

          {/* Desktop Nav */}
          <div className="hidden lg:flex items-center gap-2">
            {topics.map((topic) => (
              <motion.button
                key={topic.id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => onTopicChange(topic.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 ${
                  activeTopic === topic.id
                    ? "bg-gradient-to-r " + topic.color + " text-white shadow-lg"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <span>{topic.icon}</span>
                <span>{topic.title}</span>
              </motion.button>
            ))}
          </div>

          {/* Mobile menu button */}
          <button
            onClick={onMobileMenuToggle}
            className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="lg:hidden pb-4 space-y-2"
          >
            {topics.map((topic) => (
              <button
                key={topic.id}
                onClick={() => {
                  onTopicChange(topic.id);
                  onMobileMenuToggle();
                }}
                className={`w-full px-4 py-3 rounded-lg text-left font-medium transition-all flex items-center gap-3 ${
                  activeTopic === topic.id
                    ? "bg-gradient-to-r " + topic.color + " text-white"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <span className="text-xl">{topic.icon}</span>
                <span>{topic.title}</span>
              </button>
            ))}
          </motion.div>
        )}
      </div>
    </nav>
  );
}
