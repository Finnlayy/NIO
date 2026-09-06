"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Library, Plus, X, Zap } from "lucide-react";
import { widgetTemplates } from "./widgetRegistry";
import { dispatchHydrateTemplate, dispatchOrchestratorScenario, useGridStore } from "./store";

const categoryColor: Record<string, string> = {
  Market: "text-emerald-300 bg-emerald-400/10 border-emerald-400/20",
  Execution: "text-blue-300 bg-blue-400/10 border-blue-400/20",
  System: "text-amber-300 bg-amber-400/10 border-amber-400/20",
  Data: "text-violet-300 bg-violet-400/10 border-violet-400/20",
};

export function GalleryDrawer() {
  const open = useGridStore((s) => s.galleryOpen);
  const setOpen = useGridStore((s) => s.setGalleryOpen);
  const widgetCount = useGridStore((s) => s.widgets.length);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-40"
            onClick={() => setOpen(false)}
          />
          <motion.aside
            initial={{ x: 380 }}
            animate={{ x: 0 }}
            exit={{ x: 380 }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md bg-[#0c0f18] border-l border-white/[0.08] flex flex-col"
          >
            <div className="flex items-center gap-2.5 px-5 h-14 border-b border-white/[0.07]">
              <Library className="w-4 h-4 text-cyan-300" />
              <h2 className="text-sm font-semibold text-white">Widget Template Gallery</h2>
              <span className="text-[10px] text-slate-500">{widgetTemplates.length} blueprints</span>
              <button
                onClick={() => setOpen(false)}
                className="ml-auto p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.07]"
                aria-label="Close gallery"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
              <button
                onClick={() => dispatchOrchestratorScenario()}
                className="w-full text-left rounded-xl border border-amber-400/25 bg-amber-400/[0.06] p-3.5 hover:bg-amber-400/10 transition-colors"
              >
                <p className="flex items-center gap-2 text-[12px] font-semibold text-amber-200">
                  <Zap className="w-3.5 h-3.5" />
                  Simulate Master-Twin scenario
                </p>
                <p className="text-[11px] text-amber-200/60 mt-1 leading-relaxed">
                  “Geopolitical shock detected → needs Liquidity Radar” — dispatches
                  <code className="mx-1 text-amber-300/80">ui/hydrate_widget_template</code>
                  from the orchestrator.
                </p>
              </button>

              {widgetTemplates.map((tpl) => (
                <div
                  key={tpl.id}
                  className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3.5 flex items-start gap-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-mono text-cyan-300/80">{tpl.id}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${categoryColor[tpl.category]}`}>
                        {tpl.category}
                      </span>
                    </div>
                    <p className="text-[13px] font-semibold text-slate-100 mt-1">{tpl.title}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{tpl.tagline}</p>
                    <p className="text-[10px] text-slate-600 font-mono mt-1.5 truncate">
                      key: {tpl.key} · span {tpl.defaultSpan}/6 · {tpl.defaultHeight}
                    </p>
                  </div>
                  <button
                    onClick={() => dispatchHydrateTemplate(tpl.id)}
                    className="shrink-0 inline-flex items-center gap-1 px-2.5 py-2 rounded-lg bg-cyan-400/10 border border-cyan-400/25 text-cyan-200 text-[11px] font-medium hover:bg-cyan-400/20 transition-colors"
                    title={`Hydrate ${tpl.id} from template`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Hydrate
                  </button>
                </div>
              ))}
            </div>

            <p className="px-5 py-3 border-t border-white/[0.07] text-[10px] text-slate-600 leading-relaxed">
              Templates are declarative blueprints. Hydration sends a JSON-RPC payload with the
              template key + live state; the canvas materializes the widget with a spring animation.
            </p>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
