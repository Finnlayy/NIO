import React from 'react';
import { X, BookOpen, Shield, Cpu, Calculator, CheckCircle2, Download } from 'lucide-react';
import { CANONICAL_BLUEPRINT_DOCS } from '../data/canonicalBlueprint';

interface BlueprintViewerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BlueprintViewer: React.FC<BlueprintViewerProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const docs = CANONICAL_BLUEPRINT_DOCS;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden text-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-mono flex items-center gap-2">
                {docs.title}
                <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-sans">
                  {docs.codename} v{docs.version}
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Rigorous mathematical architecture of the quantitative trading framework
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs leading-relaxed font-sans">
          {/* System Philosophy & Zero-Dummy Guarantee */}
          <div className="p-4 rounded-lg bg-indigo-950/30 border border-indigo-500/30 text-slate-300 space-y-2">
            <div className="flex items-center gap-2 text-indigo-400 font-mono font-bold text-sm">
              <Shield className="w-4 h-4" /> CORE ARCHITECTURAL DIRECTIVE
            </div>
            <p className="font-semibold text-white">{docs.philosophy}</p>
            <div className="p-3 rounded bg-slate-950 border border-indigo-900/50 text-[11px] font-mono text-emerald-400">
              {docs.zeroDummyDirective}
            </div>
          </div>

          {/* Mathematical Formulations */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 font-mono font-bold text-white text-sm">
              <Calculator className="w-4 h-4 text-cyan-400" />
              <span>MATHEMATICAL RIGOR & FORMULATIONS</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {docs.mathFormulas.map((math) => (
                <div key={math.name} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                  <div className="text-xs font-semibold text-cyan-300 font-mono">{math.name}</div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800 font-mono text-xs text-amber-300 font-bold overflow-x-auto">
                    {math.formula}
                  </div>
                  <p className="text-[11px] text-slate-400">{math.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* M8-Gate Pipeline Specifications */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 font-mono font-bold text-white text-sm">
              <Cpu className="w-4 h-4 text-emerald-400" />
              <span>M8-GATE INVARIANT PIPELINE SPECIFICATION</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {docs.gateSpecifications.map((gate) => (
                <div key={gate.gateId} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between font-mono">
                    <span className="text-xs font-bold text-cyan-400">{gate.gateId}: {gate.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                      {gate.strictness}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300">{gate.description}</p>
                  <div className="text-[10px] text-rose-400 font-mono">Fail Action: {gate.failAction}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between text-xs">
          <div className="text-slate-400 font-mono">
            Status: <span className="text-emerald-400">MATHEMATICALLY CLOSED & VERIFIED</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
          >
            Close Blueprint
          </button>
        </div>
      </div>
    </div>
  );
};
