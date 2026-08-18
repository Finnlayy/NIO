"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Clipboard,
  Container,
  Database,
  GitPullRequest,
  Network,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import NeuralNodeNetwork from "@/components/NeuralNodeNetwork";
import { masterPromptManifest } from "@/data/orchestrator";

export default function AutonomousOrchestratorPage() {
  return (
    <div className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-[1500px] mx-auto">
      <motion.header
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-9"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-sm text-cyan-300 mb-4">
          <Network className="w-4 h-4" />
          VISUAL SYSTEMMASTERPROMPT FRAMEWORK · UNIFIED NETWORK
        </div>
        <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4">
          Autonomous <span className="gradient-text">Neural Node Network</span>
        </h1>
        <p className="text-slate-400 max-w-4xl mx-auto text-base sm:text-lg">
          AI-Agent-Team, State Machine, Eval-Memory und Sandbox-Gates arbeiten jetzt als ein interaktiver Graph für sichere, selbstkorrigierende Code-Review- und Delivery-Workflows zusammen.
        </p>
      </motion.header>

      <NeuralNodeNetwork />

      <section className="mt-8 grid lg:grid-cols-3 gap-5">
        <motion.article initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="glass-card rounded-2xl p-6 border border-cyan-500/20">
          <div className="w-11 h-11 rounded-xl bg-cyan-500/15 grid place-items-center"><BrainCircuit className="w-5 h-5 text-cyan-300" /></div>
          <p className="text-xs uppercase tracking-[0.14em] text-cyan-300 mt-5">Agent collaboration</p>
          <h2 className="text-xl font-bold text-white mt-1">Spezialisierung statt Monolith</h2>
          <p className="text-sm leading-relaxed text-slate-400 mt-3">Zehn Rollen teilen einen Workload auf: von Repository-Kartierung über C-/Python-Reviews bis zu fachlicher Quant-Validierung, UI-Checks, CI-Evidence und Review-Synthese.</p>
        </motion.article>

        <motion.article initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }} viewport={{ once: true }} className="glass-card rounded-2xl p-6 border border-teal-500/20">
          <div className="w-11 h-11 rounded-xl bg-teal-500/15 grid place-items-center"><Database className="w-5 h-5 text-teal-300" /></div>
          <p className="text-xs uppercase tracking-[0.14em] text-teal-300 mt-5">Closed feedback loop</p>
          <h2 className="text-xl font-bold text-white mt-1">Evidence wird zu Memory</h2>
          <p className="text-sm leading-relaxed text-slate-400 mt-3">Compiler-Fehler, CI-Signale, Review-Findings und Entscheidungspfade werden im PostgreSQL-Ledger gespeichert. Vor dem nächsten Plan kann ein Vector-Adapter ähnliche Fälle abrufen.</p>
        </motion.article>

        <motion.article initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: 0.16 }} viewport={{ once: true }} className="glass-card rounded-2xl p-6 border border-red-500/20">
          <div className="w-11 h-11 rounded-xl bg-red-500/15 grid place-items-center"><ShieldCheck className="w-5 h-5 text-red-300" /></div>
          <p className="text-xs uppercase tracking-[0.14em] text-red-300 mt-5">Safety by architecture</p>
          <h2 className="text-xl font-bold text-white mt-1">Autonomie mit Grenzen</h2>
          <p className="text-sm leading-relaxed text-slate-400 mt-3">Die Policy-Gates erzwingen ephemere Sandboxen, least-privilege Tokens, Netzwerk-Isolation und menschliche Release-Freigaben. Ein Agent darf niemals direkt Produktion verändern.</p>
        </motion.article>
      </section>

      <motion.section
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="mt-8 glass-card rounded-2xl p-6 sm:p-8 border border-purple-500/20"
      >
        <div className="flex flex-col lg:flex-row gap-8 justify-between">
          <div className="max-w-2xl">
            <p className="text-xs uppercase tracking-[0.14em] text-purple-300">Execution contract</p>
            <h2 className="text-2xl font-bold text-white mt-2">Das Netzwerk folgt einem überprüfbaren Contract</h2>
            <p className="text-sm leading-relaxed text-slate-400 mt-3">Die Visualisierung ist direkt aus einem strukturierten Manifest abgeleitet. Dadurch bleiben Registry, erlaubte Übergänge, Evaluationslogik und Sicherheitsgrenzen auch für generierende Systeme eindeutig und testbar.</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-3 lg:min-w-[460px]">
            {[
              { icon: Workflow, label: "State Machine", value: "7 Gate States" },
              { icon: GitPullRequest, label: "Change Surface", value: "PR & CI Evidence" },
              { icon: Container, label: "Execution", value: "Docker / gVisor" },
              { icon: Clipboard, label: "Manifest", value: `${masterPromptManifest.agents.length} Agents · ${masterPromptManifest.eval.deployThreshold}+ Deploy` },
            ].map((item) => {
              const Icon = item.icon;
              return <div key={item.label} className="rounded-xl bg-black/25 border border-white/8 p-4"><Icon className="w-5 h-5 text-purple-300" /><p className="text-xs uppercase tracking-wider text-slate-500 mt-3">{item.label}</p><p className="text-sm font-semibold text-white mt-1">{item.value}</p></div>;
            })}
          </div>
        </div>

        <div className="mt-7 rounded-xl bg-gradient-to-r from-cyan-500/8 via-purple-500/8 to-green-500/8 border border-white/8 p-4 flex flex-col md:flex-row md:items-center gap-4 text-sm">
          <CheckCircle2 className="w-6 h-6 text-green-300 flex-shrink-0" />
          <p className="text-slate-300"><span className="font-semibold text-white">Flow:</span> Retrieve Memory <ArrowRight className="inline w-4 h-4 mx-1 text-cyan-300" /> Plan <ArrowRight className="inline w-4 h-4 mx-1 text-cyan-300" /> Execute in Sandbox <ArrowRight className="inline w-4 h-4 mx-1 text-cyan-300" /> Review <ArrowRight className="inline w-4 h-4 mx-1 text-cyan-300" /> Eval <ArrowRight className="inline w-4 h-4 mx-1 text-cyan-300" /> Deploy, Revise oder Human Escalation.</p>
        </div>
      </motion.section>
    </div>
  );
}
