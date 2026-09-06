"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDownUp,
  GripVertical,
  Maximize2,
  Minus,
  MoreVertical,
  Pin,
  PinOff,
  RefreshCw,
  X,
} from "lucide-react";
import type { WidgetInstance } from "../types";
import {
  dispatchRefresh,
  dispatchRemove,
  useGridStore,
} from "../store";

export function WidgetFrame({
  widget,
  index,
  onDragStart,
  onDragEnter,
  onDragEnd,
  dragging,
  children,
}: {
  widget: WidgetInstance;
  index: number;
  onDragStart: (index: number) => void;
  onDragEnter: (index: number) => void;
  onDragEnd: () => void;
  dragging: boolean;
  children: React.ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const toggleMinimize = useGridStore((s) => s.toggleMinimize);
  const togglePin = useGridStore((s) => s.togglePin);
  const cycleSpan = useGridStore((s) => s.cycleSpan);
  const cycleHeight = useGridStore((s) => s.cycleHeight);

  return (
    <motion.section
      layout
      initial={{ opacity: 0, scale: 0.96, y: 12 }}
      animate={{ opacity: dragging ? 0.6 : 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.94 }}
      transition={{ type: "spring", stiffness: 260, damping: 28 }}
      draggable={!widget.pinned}
      onDragStart={() => onDragStart(index)}
      onDragEnter={() => onDragEnter(index)}
      onDragEnd={onDragEnd}
      onDragOver={(e) => e.preventDefault()}
      className={`ops-widget ${widget.height === "tall" ? "ops-widget-tall" : "ops-widget-compact"} ${
        widget.pinned ? "ops-widget-pinned" : ""
      }`}
      style={{ gridColumn: `span ${widget.span} / span ${widget.span}` }}
      aria-label={widget.title}
    >
      <header className="flex items-center gap-2 px-3.5 h-11 border-b border-white/[0.06] shrink-0">
        {!widget.pinned ? (
          <span
            className="text-slate-700 hover:text-slate-400 cursor-grab active:cursor-grabbing touch-none"
            title="Drag to reorder"
            aria-label="Drag widget"
          >
            <GripVertical className="w-3.5 h-3.5" />
          </span>
        ) : (
          <span className="text-amber-400/70" title="Pinned — reordering locked">
            <Pin className="w-3.5 h-3.5" />
          </span>
        )}

        <h2 className="text-[12.5px] font-semibold text-slate-200 truncate flex items-center gap-2 min-w-0">
          <span className="truncate">{widget.title}</span>
          {widget.symbol && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-400 shrink-0">
              {widget.symbol}
            </span>
          )}
        </h2>

        <span className="ml-auto flex items-center gap-0.5 shrink-0 relative">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot mr-1" title="Live data" />
          <IconBtn title="Refresh data" onClick={() => dispatchRefresh(widget)}>
            <RefreshCw className="w-3.5 h-3.5" />
          </IconBtn>
          <IconBtn title={widget.minimized ? "Expand" : "Minimize"} onClick={() => toggleMinimize(widget.id)}>
            <Minus className={`w-3.5 h-3.5 transition-transform ${widget.minimized ? "rotate-180" : ""}`} />
          </IconBtn>
          <IconBtn title="Widget options" onClick={() => setMenuOpen((v) => !v)}>
            <MoreVertical className="w-3.5 h-3.5" />
          </IconBtn>

          <AnimatePresence>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.97 }}
                  transition={{ duration: 0.12 }}
                  className="absolute right-0 top-9 z-50 w-48 rounded-xl border border-white/10 bg-[#11151f] shadow-2xl p-1.5"
                >
                  <MenuItem onClick={() => { cycleSpan(widget.id); setMenuOpen(false); }} icon={<ArrowDownUp className="w-3.5 h-3.5" />}>
                    Width · {widget.span}/6
                  </MenuItem>
                  <MenuItem onClick={() => { cycleHeight(widget.id); setMenuOpen(false); }} icon={<Maximize2 className="w-3.5 h-3.5" />}>
                    Height · {widget.height}
                  </MenuItem>
                  <MenuItem onClick={() => { togglePin(widget.id); setMenuOpen(false); }} icon={widget.pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}>
                    {widget.pinned ? "Unpin" : "Pin to position"}
                  </MenuItem>
                  <MenuItem onClick={() => { dispatchRefresh(widget); setMenuOpen(false); }} icon={<RefreshCw className="w-3.5 h-3.5" />}>
                    Re-hydrate from twin
                  </MenuItem>
                  <div className="h-px bg-white/[0.07] my-1" />
                  <MenuItem danger onClick={() => dispatchRemove(widget.id)} icon={<X className="w-3.5 h-3.5" />}>
                    Remove widget
                  </MenuItem>
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </span>
      </header>

      <AnimatePresence initial={false}>
        {!widget.minimized && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="p-3.5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}

function IconBtn({
  children,
  title,
  onClick,
}: {
  children: React.ReactNode;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-white/[0.07] transition-colors"
    >
      {children}
    </button>
  );
}

function MenuItem({
  children,
  icon,
  onClick,
  danger = false,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs text-left transition-colors ${
        danger
          ? "text-rose-300 hover:bg-rose-500/10"
          : "text-slate-300 hover:bg-white/[0.06]"
      }`}
    >
      <span className="text-slate-500">{icon}</span>
      {children}
    </button>
  );
}
