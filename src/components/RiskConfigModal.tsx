import React, { useState } from 'react';
import { X, Sliders, Check, RotateCcw } from 'lucide-react';
import { JudgeConfig } from '../types/trading';
import { INITIAL_JUDGE_CONFIG } from '../data/canonicalBlueprint';

interface RiskConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: JudgeConfig;
  onSaveConfig: (newConfig: JudgeConfig) => void;
}

export const RiskConfigModal: React.FC<RiskConfigModalProps> = ({
  isOpen,
  onClose,
  config,
  onSaveConfig,
}) => {
  const [formData, setFormData] = useState<JudgeConfig>({ ...config });

  if (!isOpen) return null;

  const handleResetDefaults = () => {
    setFormData({ ...INITIAL_JUDGE_CONFIG });
  };

  const handleSave = () => {
    onSaveConfig(formData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-2xl flex flex-col shadow-2xl overflow-hidden text-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-mono">
                The Judge: M8-Gate Invariant Thresholds
              </h2>
              <p className="text-xs text-slate-400">
                Tweak risk barrier parameters and allocation ceilings for the active runtime
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

        {/* Form Body */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto text-xs font-mono">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Kelly Fraction */}
            <div className="space-y-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <label className="text-slate-300 font-semibold flex justify-between">
                <span>M4: Kelly Sizing Fraction</span>
                <span className="text-cyan-400 font-bold">{formData.kellyFraction}x</span>
              </label>
              <input
                type="range"
                min="0.2"
                max="1.0"
                step="0.05"
                value={formData.kellyFraction}
                onChange={(e) => setFormData({ ...formData, kellyFraction: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
              <p className="text-[10px] text-slate-500 font-sans">
                0.5 = Half-Kelly (Standard quant safety factor)
              </p>
            </div>

            {/* Max Gross Leverage */}
            <div className="space-y-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <label className="text-slate-300 font-semibold flex justify-between">
                <span>M2: Max Gross Leverage</span>
                <span className="text-cyan-400 font-bold">{formData.maxGrossLeverage.toFixed(1)}x</span>
              </label>
              <input
                type="range"
                min="1.0"
                max="5.0"
                step="0.2"
                value={formData.maxGrossLeverage}
                onChange={(e) => setFormData({ ...formData, maxGrossLeverage: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
              <p className="text-[10px] text-slate-500 font-sans">
                Hard ceiling for total portfolio exposure / NAV
              </p>
            </div>

            {/* Max Asset Concentration */}
            <div className="space-y-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <label className="text-slate-300 font-semibold flex justify-between">
                <span>M2: Single Asset Concentration</span>
                <span className="text-cyan-400 font-bold">{formData.maxAssetConcentrationPct}%</span>
              </label>
              <input
                type="range"
                min="5"
                max="50"
                step="5"
                value={formData.maxAssetConcentrationPct}
                onChange={(e) => setFormData({ ...formData, maxAssetConcentrationPct: parseInt(e.target.value) })}
                className="w-full accent-cyan-400"
              />
              <p className="text-[10px] text-slate-500 font-sans">
                Maximum allocation into any single symbol
              </p>
            </div>

            {/* Drawdown Circuit Breaker */}
            <div className="space-y-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <label className="text-slate-300 font-semibold flex justify-between">
                <span>M5: Max Total Drawdown Stop</span>
                <span className="text-rose-400 font-bold">-{formData.maxTotalDrawdownPct}%</span>
              </label>
              <input
                type="range"
                min="2.0"
                max="12.0"
                step="0.5"
                value={formData.maxTotalDrawdownPct}
                onChange={(e) => setFormData({ ...formData, maxTotalDrawdownPct: parseFloat(e.target.value) })}
                className="w-full accent-rose-400"
              />
              <p className="text-[10px] text-slate-500 font-sans">
                Peak-to-trough trailing drawdown trigger
              </p>
            </div>

            {/* Volatility Ceiling */}
            <div className="space-y-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <label className="text-slate-300 font-semibold flex justify-between">
                <span>M3: Volatility Ratio Dampener</span>
                <span className="text-cyan-400 font-bold">{formData.volatilityCeilingAtrRatio}x</span>
              </label>
              <input
                type="range"
                min="1.5"
                max="4.5"
                step="0.25"
                value={formData.volatilityCeilingAtrRatio}
                onChange={(e) => setFormData({ ...formData, volatilityCeilingAtrRatio: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
              <p className="text-[10px] text-slate-500 font-sans">
                Turbulence ratio triggering 40% size dampening
              </p>
            </div>

            {/* 99% CVaR Risk Budget */}
            <div className="space-y-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800">
              <label className="text-slate-300 font-semibold flex justify-between">
                <span>M7: 99% CVaR Budget</span>
                <span className="text-purple-400 font-bold">${formData.cvarLimitUsd.toLocaleString()}</span>
              </label>
              <input
                type="range"
                min="10000"
                max="60000"
                step="5000"
                value={formData.cvarLimitUsd}
                onChange={(e) => setFormData({ ...formData, cvarLimitUsd: parseInt(e.target.value) })}
                className="w-full accent-purple-400"
              />
              <p className="text-[10px] text-slate-500 font-sans">
                Cornish-Fisher expected shortfall stress limit
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between text-xs">
          <button
            onClick={handleResetDefaults}
            className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Defaults</span>
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex items-center gap-1 px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition-colors shadow-sm"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Save & Apply</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
