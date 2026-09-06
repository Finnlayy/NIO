"use client";

import { useCallback, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup } from "framer-motion";
import { LayoutGrid } from "lucide-react";
import { useGridStore } from "./store";
import { DragSession } from "./dragSession";
import { WidgetFrame } from "./widgets/WidgetFrame";

export function GridCanvas() {
  const widgets = useGridStore((s) => s.widgets);
  const reorder = useGridStore((s) => s.reorder);
  const [draggingId, setDraggingId] = useState<string | null>(null);

  /* Drag bookkeeping lives in a pure session (stable identity — the drag
     callbacks below therefore never change reference). */
  const sessionRef = useRef<DragSession | null>(null);
  if (sessionRef.current === null) sessionRef.current = new DragSession();
  const dragSession = sessionRef.current;

  const handleDragStart = useCallback(
    (index: number, id: string) => {
      dragSession.begin(index);
      setDraggingId(id);
    },
    [dragSession],
  );
  const handleDragEnter = useCallback(
    (index: number) => {
      const move = dragSession.enter(index);
      if (move) reorder(move.from, move.to);
    },
    [dragSession, reorder],
  );
  const handleDragEnd = useCallback(() => {
    dragSession.end();
    setDraggingId(null);
  }, [dragSession]);

  return (
    <LayoutGroup>
      {widgets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/[0.12] bg-white/[0.015] py-20 text-center">
          <LayoutGrid className="w-8 h-8 text-slate-700 mx-auto mb-3" />
          <p className="text-sm text-slate-400">Canvas empty — open the Template Gallery to hydrate widgets,</p>
          <p className="text-xs text-slate-600 mt-1">
            or wait for the NIO Master Twin to dispatch <code className="text-slate-500">ui/hydrate_widget_template</code>.
          </p>
        </div>
      ) : (
        <div className="ops-grid">
          <AnimatePresence mode="popLayout">
            {widgets.map((widget, index) => (
              <WidgetFrame
                key={widget.id}
                widget={widget}
                index={index}
                dragging={draggingId === widget.id}
                onDragStart={handleDragStart}
                onDragEnter={handleDragEnter}
                onDragEnd={handleDragEnd}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </LayoutGroup>
  );
}
