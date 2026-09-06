"use client";

import { useRef, useState } from "react";
import { AnimatePresence, LayoutGroup } from "framer-motion";
import { LayoutGrid } from "lucide-react";
import { useGridStore } from "./store";
import { WidgetFrame } from "./widgets/WidgetFrame";
import { renderWidget } from "./widgets";

export function GridCanvas() {
  const widgets = useGridStore((s) => s.widgets);
  const reorder = useGridStore((s) => s.reorder);
  const dragIndex = useRef<number | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);

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
                onDragStart={(i) => {
                  dragIndex.current = i;
                  setDraggingId(widget.id);
                }}
                onDragEnter={(i) => {
                  if (dragIndex.current !== null && dragIndex.current !== i) {
                    reorder(dragIndex.current, i);
                    dragIndex.current = i;
                  }
                }}
                onDragEnd={() => {
                  dragIndex.current = null;
                  setDraggingId(null);
                }}
              >
                {renderWidget(widget)}
              </WidgetFrame>
            ))}
          </AnimatePresence>
        </div>
      )}
    </LayoutGroup>
  );
}
