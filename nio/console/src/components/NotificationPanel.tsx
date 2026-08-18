"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, X } from "lucide-react";
import { fetchCodySupervisor } from "@/lib/nio-client";
import type { FormattedInterAgentLine } from "@/lib/manifest-types";
import { filterByScope, countRelevantUnread } from "@/components/comms/comms-filter";
import { openCodyPet } from "@/hooks/useCodyPet";
import { COMMS_READ_KEY, openCommsView } from "@/hooks/useCommsAudit";

function formatWhen(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function severityDot(severity: FormattedInterAgentLine["severity"]): string {
  switch (severity) {
    case "error":
      return "bg-rose-400";
    case "warning":
      return "bg-amber-400";
    case "success":
      return "bg-emerald-400";
    default:
      return "bg-cyan-400";
  }
}

export default function NotificationPanel() {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<FormattedInterAgentLine[]>([]);
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const sup = await fetchCodySupervisor();
      const timeline = sup.interAgentTimeline ?? [];
      const relevant = filterByScope(timeline, "relevant").slice(0, 12);
      setLines(relevant);
      const readAt = localStorage.getItem(COMMS_READ_KEY);
      setUnreadCount(countRelevantUnread(timeline, readAt));
    } catch {
      setLines([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadNotifications();
    const id = setInterval(() => void loadNotifications(), 15000);
    return () => clearInterval(id);
  }, [loadNotifications]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      void loadNotifications();
    }
  };

  const handleItemClick = () => {
    setOpen(false);
    openCommsView();
  };

  const handleViewAll = () => {
    setOpen(false);
    openCommsView();
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={open}
        aria-label="Notifications"
        className="relative p-2 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 ? (
          <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-cyan-400 text-[9px] leading-4 text-slate-950 font-bold">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-full mt-2 w-[min(100vw-2rem,380px)] rounded-xl border border-white/10 bg-[#0d0f16]/98 backdrop-blur-xl shadow-2xl shadow-black/50 z-50 overflow-hidden">
          <header className="flex items-center justify-between px-4 py-3 border-b border-white/[0.07]">
            <div>
              <p className="text-sm font-semibold text-white">Notifications</p>
              <p className="text-[10px] text-slate-500">User-relevant comms · gates · Cody</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-1 text-slate-500 hover:text-white"
              aria-label="Close notifications"
            >
              <X className="w-4 h-4" />
            </button>
          </header>

          <div className="max-h-[360px] overflow-y-auto p-2">
            {loading && lines.length === 0 ? (
              <p className="text-xs text-slate-500 px-2 py-6 text-center">Loading…</p>
            ) : lines.length === 0 ? (
              <p className="text-xs text-slate-500 px-2 py-6 text-center">No relevant notifications yet.</p>
            ) : (
              <ul className="space-y-1">
                {lines.map((line) => (
                  <li key={line.messageId}>
                    <button
                      type="button"
                      onClick={handleItemClick}
                      className="w-full text-left rounded-lg px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                    >
                      <div className="flex items-start gap-2">
                        <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${severityDot(line.severity)}`} />
                        <div className="min-w-0 flex-1">
                          <div className="flex justify-between gap-2">
                            <span className="text-xs font-medium text-white">{line.headline}</span>
                            <span className="text-[10px] text-slate-600 shrink-0">{formatWhen(line.timestamp)}</span>
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed line-clamp-2">
                            {line.body.replace(/\*\*/g, "")}
                          </p>
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <footer className="px-4 py-2 border-t border-white/[0.07] flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={handleViewAll}
              className="text-[11px] text-amber-300 hover:text-amber-200"
            >
              View full audit →
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                openCodyPet();
              }}
              className="text-[11px] text-slate-500 hover:text-slate-300"
            >
              Open Cody
            </button>
          </footer>
        </div>
      ) : null}
    </div>
  );
}
