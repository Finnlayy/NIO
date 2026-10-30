import React, { useEffect } from "react";
import { useKanbanStore } from "./useKanbanStore";

export const UndoToast: React.FC = () => {
  const lastRemoved = useKanbanStore(s => s.lastRemoved);
  const undoRemove = useKanbanStore(s => s.undoRemove);

  // Visible for ~6 s after each delete; a newer delete restarts the timer (undo applies to the latest one).
  const [visible, setVisible] = React.useState(false);
  const [removedTask, setRemovedTask] = React.useState(lastRemoved);

  useEffect(() => {
    if (lastRemoved) {
      setRemovedTask(lastRemoved);
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
      }, 6000);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
    }
  }, [lastRemoved]);

  if (!visible || !removedTask) return null;

  return (
    <div 
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 px-4 py-3 bg-[#0f111a] border border-white/[0.08] shadow-xl rounded-lg pointer-events-auto"
      role="status"
      aria-live="polite"
    >
      <span className="text-sm text-slate-200">Karte gelöscht</span>
      <button
        onClick={() => {
          undoRemove();
          setVisible(false);
        }}
        className="text-sm font-medium text-cyan-400 hover:text-cyan-300 focus:outline-none focus:ring-1 focus:ring-cyan-500 rounded px-1 -mx-1"
      >
        Rückgängig
      </button>
    </div>
  );
};
