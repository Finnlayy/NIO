"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  metricsToMonitor,
  benefits,
  withoutObservability,
  withObservability,
  realWorldApplications,
  expertTip,
} from "@/data/ai-observability";
import {
  Clock,
  Target,
  Coins,
  BarChart3,
  AlertTriangle,
  DollarSign,
  Smile,
  CheckCircle,
  XCircle,
  Lightbulb,
  Zap,
  ArrowDown,
  ArrowUp,
  Minus,
  Brain,
} from "lucide-react";

const iconMap: Record<string, React.ReactNode> = {
  "⏱️": <Clock className="w-6 h-6" />,
  "🎯": <Target className="w-6 h-6" />,
  "🪙": <Coins className="w-6 h-6" />,
  "📊": <BarChart3 className="w-6 h-6" />,
  "⚠️": <AlertTriangle className="w-6 h-6" />,
  "💰": <DollarSign className="w-6 h-6" />,
  "😊": <Smile className="w-6 h-6" />,
};

function TrendIcon({ trend }: { trend: "up" | "down" | "stable" }) {
  if (trend === "up") return <ArrowUp className="w-4 h-4 text-green-400" />;
  if (trend === "down") return <ArrowDown className="w-4 h-4 text-red-400" />;
  return <Minus className="w-4 h-4 text-slate-400" />;
}

// Animated counter component
function AnimatedCounter({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    const duration = 1500;
    const steps = 60;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setCount(value);
        clearInterval(timer);
      } else {
        setCount(current);
      }
    }, duration / steps);
    
    return () => clearInterval(timer);
  }, [value]);
  
  return (
    <span>
      {suffix === "$" ? "$" : ""}
      {typeof count === 'number' ? count.toFixed(value % 1 === 0 ? 0 : 1) : count}
      {suffix === "%" ? "%" : suffix === "/s" ? "/s" : suffix === "K" && !String(value).includes(".") ? "K" : !["$","%","/s"].includes(suffix) || String(value).includes(".") ? suffix : ""}
    </span>
  );
}

export default function AIObservabilityPage() {
  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 text-sm text-purple-400 mb-4">
          ⏱️ DAY 48 — AI ENGINEERING JOURNEY (90-DAY)
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4">
          AI{" "}
          <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            Observability
          </span>
        </h1>
        <p className="text-xl text-slate-300">Monitor. Measure. Improve.</p>
        
        {/* Quote */}
        <blockquote className="mt-8 max-w-2xl mx-auto text-lg italic text-slate-400">
          &ldquo;You can&apos;t improve what you don&apos;t measure.&rdquo;
        </blockquote>
        <p className="mt-4 text-slate-500 max-w-2xl mx-auto">
          Observability turns your AI system into a reliable, production-ready solution.
        </p>
      </motion.div>

      {/* Flow Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card rounded-2xl p-8 mb-8"
      >
        <div className="flex flex-col md:flex-row items-center justify-center gap-4 md:gap-8">
          {[
            { label: "User Request", sublabel: "User interacts with your AI application", icon: "👤" },
            { label: "AI Application", sublabel: "LLM, Agents, RAG pipelines, or automation workflows", icon: "🧠" },
            { label: "Observability Platform", sublabel: "Collects, analyzes and visualizes key metrics in real time.", icon: "📊" },
            { label: "Optimization & Better AI System", sublabel: "Continuously optimized, reliable and scalable AI", icon: "🚀" },
          ].map((step, idx) => (
            <div key={idx} className="flex items-center gap-4 md:flex-col md:text-center">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center text-3xl ${
                idx === 0 ? 'bg-blue-500/20' : 
                idx === 1 ? 'bg-purple-500/20' :
                idx === 2 ? 'bg-cyan-500/20' :
                'bg-green-500/20'
              }`}>
                {step.icon}
              </div>
              <div className="max-w-[180px]">
                <h3 className="font-bold text-white text-sm">{step.label}</h3>
                <p className="text-xs text-slate-400 mt-1">{step.sublabel}</p>
              </div>
              {idx < 3 && (
                <ArrowDown className="w-5 h-5 text-purple-500 md:hidden rotate-90" />
              )}
              {idx < 3 && (
                <ArrowRight className="w-5 h-5 text-purple-500 hidden md:block absolute right-0 translate-x-1/2" style={{ position: 'relative' }} />
              )}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Metrics Dashboard */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-purple-500/20 glow-purple"
      >
        <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
          📊 Observability Platform — Key Metrics in Real Time
        </h2>
        
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {metricsToMonitor.map((metric, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 + idx * 0.05 }}
              whileHover={{ scale: 1.03 }}
              className="bg-black/30 rounded-xl p-4 hover:bg-black/50 transition-all group cursor-pointer relative overflow-hidden"
            >
              {/* Background glow effect */}
              <div className={`absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity ${
                metric.name.includes("Response") ? "bg-blue-500" :
                metric.name.includes("Accuracy") ? "bg-green-500" :
                metric.name.includes("Token") ? "bg-yellow-500" :
                metric.name.includes("Throughput") ? "bg-cyan-500" :
                metric.name.includes("Failure") ? "bg-red-500" :
                metric.name.includes("Cost") ? "bg-orange-500" :
                "bg-pink-500"
              }`} />
              
              <div className="relative flex items-start justify-between mb-3">
                <div className="p-2 rounded-lg bg-white/5 group-hover:bg-white/10 transition-colors">
                  {iconMap[metric.icon] || <BarChart3 className="w-6 h-6" />}
                </div>
                <TrendIcon trend={metric.trend} />
              </div>
              
              <div className="relative">
                <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">{metric.name}</p>
                <p className="text-2xl font-bold text-white mt-1 code-font">
                  <AnimatedCounter 
                    value={
                      metric.value.includes("ms") ? parseFloat(metric.value) :
                      metric.value.includes("%") ? parseFloat(metric.value) :
                      metric.value.includes("$") ? parseFloat(metric.value.replace("$","").replace("/","")) :
                      metric.value.includes("K") ? parseFloat(metric.value.replace("K","")) :
                      0
                    }
                    suffix={
                      metric.value.includes("ms") ? " ms" :
                      metric.value.includes("%") ? "%" :
                      metric.value.includes("$") ? "$" + (metric.value.includes("/") ? "/" : "") :
                      metric.value.includes("/s") ? "/s" :
                      "K"
                    }
                  />
                  {!metric.value.match(/[ms$%K\/]/) && metric.value}
                </p>
                
                {/* Mini chart visualization */}
                <div className="mt-2 flex items-end gap-0.5 h-8">
                  {[...Array(12)].map((_, i) => (
                    <div
                      key={i}
                      className={`flex-1 rounded-sm transition-all duration-300 group-hover:opacity-80`}
                      style={{
                        height: `${Math.random() * 70 + 10}%`,
                        backgroundColor:
                          metric.trend === "up"
                            ? i > 8
                              ? "#22c55e"
                              : "rgba(34,197,94,0.3)"
                            : metric.trend === "down"
                            ? i > 8
                              ? "#ef4444"
                              : "rgba(239,68,68,0.3)"
                            : "rgba(148,163,184,0.3)",
                      }}
                    />
                  ))}
                </div>
              </div>
              
              <p className="relative text-xs text-slate-500 mt-3">{metric.description}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      {/* Two Column Layout */}
      <div className="grid lg:grid-cols-3 gap-8 mb-8">
        {/* What to Monitor Column */}
        <motion.section
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-1 glass-card rounded-2xl p-6 border border-cyan-500/20"
        >
          <h2 className="text-lg font-bold text-cyan-400 mb-4">🔍 What To Monitor</h2>
          
          <div className="space-y-4">
            {[
              { title: "Response Time", desc: "Track latency and p95/p99 for all requests." },
              { title: "Accuracy", desc: "Evaluate response quality with automated metrics." },
              { title: "Token Consumption", desc: "Monitor prompt + completion tokens in real time." },
              { title: "Throughput", desc: "Track requests per second and system capacity." },
              { title: "Failure Rate", desc: "Detect failures, timeouts and failed generations." },
              { title: "User Satisfaction", desc: "Collect feedback and analyze sentiment." },
            ].map((item, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
                <Clock className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white text-sm">{item.title}</h4>
                  <p className="text-xs text-slate-400 mt-0.5">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.section>

        {/* Benefits Column */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="lg:col-span-1 glass-card rounded-2xl p-6 border border-green-500/20"
        >
          <h2 className="text-lg font-bold text-green-400 mb-4">✨ Benefits</h2>
          
          <div className="space-y-3">
            {benefits.map((benefit, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 bg-green-500/10 rounded-lg border border-green-500/20 hover:bg-green-500/15 transition-colors">
                <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white text-sm">{benefit.title}</h4>
                  <p className="text-xs text-slate-400 mt-0.5">{benefit.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.section>

        {/* Real World Applications */}
        <motion.section
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="lg:col-span-1 glass-card rounded-2xl p-6 border border-purple-500/20"
        >
          <h2 className="text-lg font-bold text-purple-400 mb-4">🌐 Real-World Applications</h2>
          
          <div className="grid grid-cols-2 gap-3">
            {realWorldApplications.map((app, idx) => (
              <motion.div
                key={idx}
                whileHover={{ scale: 1.05 }}
                className="p-4 bg-white/5 rounded-xl text-center hover:bg-white/10 transition-colors cursor-pointer"
              >
                <span className="text-3xl block mb-2">{app.icon}</span>
                <span className="text-xs text-slate-300 font-medium">{app.name}</span>
              </motion.div>
            ))}
          </div>
        </motion.section>
      </div>

      {/* Without vs With Observability */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="glass-card rounded-2xl p-6 mb-8 border border-red-500/20"
      >
        <div className="grid md:grid-cols-2 gap-8">
          {/* Without Observability - Bad */}
          <div className="rounded-xl overflow-hidden">
            <div className="bg-gradient-to-r from-red-900/40 to-red-800/20 px-6 py-4 text-center border-b border-red-500/30">
              <h2 className="text-lg font-bold text-red-400">❌ Without Observability</h2>
            </div>
            
            {/* Mini "bad" chart */}
            <div className="bg-red-950/20 p-6 h-32 relative overflow-hidden">
              <svg viewBox="0 0 300 80" className="w-full h-full">
                <polyline
                  points="0,40 30,35 60,55 90,45 120,65 150,50 180,70 210,55 240,75 270,60 300,68"
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth="2"
                />
                <polygon
                  points="0,80 0,40 30,35 60,55 90,45 120,65 150,50 180,70 210,55 240,75 270,60 300,68 300,80"
                  fill="url(#redGradient)"
                  opacity="0.2"
                />
                <defs>
                  <linearGradient id="redGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity="0.5"/>
                    <stop offset="100%" stopColor="#ef4444" stopOpacity="0"/>
                  </linearGradient>
                </defs>
              </svg>
              <AlertTriangle className="absolute top-4 right-4 w-8 h-8 text-red-400" />
            </div>
            
            <div className="p-4 space-y-2">
              {withoutObservability.map((item, idx) => (
                <div key={idx} className="flex items-center gap-3 text-sm">
                  <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <span className="text-slate-300">{item.item}</span>
                </div>
              ))}
            </div>
          </div>
          
          {/* VS Badge */}
          <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 w-14 h-14 rounded-full bg-slate-800 border-2 border-slate-600 items-center justify-center font-bold text-white shadow-xl">
            VS
          </div>
          
          {/* With Observability - Good */}
          <div className="rounded-xl overflow-hidden">
            <div className="bg-gradient-to-r from-green-900/40 to-green-800/20 px-6 py-4 text-center border-b border-green-500/30">
              <h2 className="text-lg font-bold text-green-400">✅ With Observability</h2>
            </div>
            
            {/* Mini "good" chart */}
            <div className="bg-green-950/20 p-6 h-32 relative overflow-hidden">
              <svg viewBox="0 0 300 80" className="w-full h-full">
                <polyline
                  points="0,60 30,55 60,45 90,50 120,38 150,42 180,32 210,28 240,25 270,22 300,18"
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth="2"
                />
                <polygon
                  points="0,80 0,60 30,55 60,45 90,50 120,38 150,42 180,32 210,28 240,25 270,22 300,18 300,80"
                  fill="url(#greenGradient)"
                  opacity="0.2"
                />
                <defs>
                  <linearGradient id="greenGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity="0.5"/>
                    <stop offset="100%" stopColor="#22c55e" stopOpacity="0"/>
                  </linearGradient>
                </defs>
              </svg>
              <CheckCircle className="absolute top-4 right-4 w-8 h-8 text-green-400" />
            </div>
            
            <div className="p-4 space-y-2">
              {withObservability.map((item, idx) => (
                <div key={idx} className="flex items-center gap-3 text-sm">
                  <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                  <span className="text-slate-300">{item.item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.section>

      {/* Expert Tip */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass-card rounded-2xl p-8 glow-purple border border-purple-500/20"
      >
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
            <Lightbulb className="w-7 h-7 text-yellow-400" />
          </div>
          <div>
            <h3 className="font-bold text-yellow-400 mb-2">💡 Expert Tip</h3>
            <p className="text-lg text-slate-200 leading-relaxed">{expertTip}</p>
            <p className="text-sm text-purple-400 mt-3 font-medium">
              WHICH METRIC WOULD YOU MONITOR FIRST IN A PRODUCTION AI SYSTEM: LATENCY, ACCURACY, OR TOKEN COST?
            </p>
          </div>
        </div>
      </motion.section>

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.45 }}
        className="mt-12 text-center"
      >
        <div className="glass-card rounded-2xl p-6 inline-block">
          <p className="text-sm text-slate-400 uppercase tracking-wider mb-2">
            🎯 90-Day AI Engineering Journey — Day 48
          </p>
          <p className="text-lg font-bold gradient-text">OWUFYSTACK — AI AUTOMATION | RAG | LLM SYSTEMS</p>
        </div>
      </motion.div>
    </div>
  );
}

function ArrowRight(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" {...props}>
      <polyline points="9 18 15 12 9 6" fill="none" stroke="currentColor" strokeWidth="2"/>
    </svg>
  );
}
