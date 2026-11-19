import React, { useState, useEffect, useRef } from 'react';
import { Bell, X, ArrowUpRight, CheckCheck, Trash2, Volume2 } from 'lucide-react';
import { SoundEventType, arcadeSoundEngine } from '../services/arcadeSoundEngine';

export interface TerminalNotificationItem {
  id: string;
  timestamp: number;
  timeFormatted: string;
  category: SoundEventType;
  title: string;
  detail: string;
  symbol?: string;
  read: boolean;
}

interface TerminalNotificationBellProps {
  notifications: TerminalNotificationItem[];
  onMarkAllRead: () => void;
  onClearAll: () => void;
  onSelectNotification: (item: TerminalNotificationItem) => void;
}

const CATEGORY_META: Record<
  SoundEventType,
  { label: string; colorHex: string; borderClass: string; bgClass: string; textClass: string }
> = {
  TAKE_PROFIT: {
    label: 'TAKE-PROFIT',
    colorHex: '#089981',
    borderClass: 'border-[#089981]/60',
    bgClass: 'bg-[#089981]/15',
    textClass: 'text-[#089981]',
  },
  SUCCESS_FANFARE: {
    label: 'TAKE-PROFIT',
    colorHex: '#089981',
    borderClass: 'border-[#089981]/60',
    bgClass: 'bg-[#089981]/15',
    textClass: 'text-[#089981]',
  },
  STOP_LOSS: {
    label: 'STOP-LOSS',
    colorHex: '#F59E0B',
    borderClass: 'border-[#F59E0B]/60',
    bgClass: 'bg-[#F59E0B]/15',
    textClass: 'text-[#F59E0B]',
  },
  WARNING_MEME: {
    label: 'STOP-LOSS / WARN',
    colorHex: '#F59E0B',
    borderClass: 'border-[#F59E0B]/60',
    bgClass: 'bg-[#F59E0B]/15',
    textClass: 'text-[#F59E0B]',
  },
  ORDER_FILL: {
    label: 'ORDER-FILL',
    colorHex: '#00E5FF',
    borderClass: 'border-[#00E5FF]/60',
    bgClass: 'bg-[#00E5FF]/15',
    textClass: 'text-[#00E5FF]',
  },
  SCREENER_ALERT: {
    label: 'RVOL / VOLA',
    colorHex: '#60A5FA',
    borderClass: 'border-[#60A5FA]/60',
    bgClass: 'bg-[#3861FB]/20',
    textClass: 'text-[#60A5FA]',
  },
  UI_FEEDBACK: {
    label: 'SYSTEM',
    colorHex: '#8B95A5',
    borderClass: 'border-[#263042]',
    bgClass: 'bg-[#131924]',
    textClass: 'text-[#E6EDF3]',
  },
  CRITICAL_ALARM: {
    label: 'NOTSTOPP / ALARM',
    colorHex: '#F23645',
    borderClass: 'border-[#F23645]',
    bgClass: 'bg-[#F23645]/20',
    textClass: 'text-[#F23645]',
  },
};

export const TerminalNotificationBell: React.FC<TerminalNotificationBellProps> = React.memo(
  ({ notifications, onMarkAllRead, onClearAll, onSelectNotification }) => {
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const containerRef = useRef<HTMLDivElement | null>(null);

    const unreadCount = notifications.reduce((acc, n) => acc + (n.read ? 0 : 1), 0);

    useEffect(() => {
      if (!isOpen) return;
      const handleOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
          setIsOpen(false);
        }
      };
      window.addEventListener('mousedown', handleOutside);
      return () => window.removeEventListener('mousedown', handleOutside);
    }, [isOpen]);

    const handleToggleOpen = () => {
      const next = !isOpen;
      setIsOpen(next);
      if (next && unreadCount > 0) {
        onMarkAllRead();
      }
    };

    return (
      <div ref={containerRef} className="relative flex items-center shrink-0">
        <button
          type="button"
          onClick={handleToggleOpen}
          title="Audio- & Markt-Ereignisse (TP, SL, Order-Fills, RVOL-Anomalien)"
          className={`px-2 py-1 border text-[10px] font-mono tabular-nums flex items-center gap-1.5 transition-colors whitespace-nowrap shrink-0 ${
            unreadCount > 0
              ? 'bg-[#00E5FF]/15 border-[#00E5FF] text-[#00E5FF]'
              : isOpen
              ? 'bg-[#131924] border-[#00E5FF]/60 text-[#E6EDF3]'
              : 'bg-[#07090E] border-[#1B2230] text-[#8B95A5] hover:text-[#E6EDF3] hover:border-[#263042]'
          }`}
        >
          <Bell className="w-3.5 h-3.5 text-[#00E5FF]" />
          <span className="hidden md:inline font-bold">EVENTS</span>
          <span
            className={`px-1 text-[9px] font-bold ${
              unreadCount > 0
                ? 'bg-[#00E5FF] text-[#07090E]'
                : 'text-[#8B95A5]'
            }`}
          >
            {unreadCount > 0 ? unreadCount : notifications.length}
          </span>
        </button>

        {isOpen && (
          <div className="absolute right-0 top-full mt-1.5 w-[370px] bg-[#0C1017] border border-[#263042] shadow-2xl z-50 font-mono text-xs select-none">
            <div className="px-3 py-2 border-b border-[#1B2230] bg-[#07090E] flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Bell className="w-3.5 h-3.5 text-[#00E5FF]" />
                <span className="font-bold text-[11px] text-[#E6EDF3] uppercase tracking-wider">
                  LIVE AUDIO- & MARKT-HISTORIE ({notifications.length}/30)
                </span>
              </div>
              <div className="flex items-center gap-1">
                {notifications.length > 0 && (
                  <>
                    <button
                      type="button"
                      onClick={onMarkAllRead}
                      title="Alle als gelesen markieren"
                      className="px-1.5 py-0.5 text-[9px] bg-[#0C1017] border border-[#1B2230] text-[#8B95A5] hover:text-[#00E5FF] flex items-center gap-1"
                    >
                      <CheckCheck className="w-2.5 h-2.5" />
                      <span>GELESEN</span>
                    </button>
                    <button
                      type="button"
                      onClick={onClearAll}
                      title="Historie leeren"
                      className="px-1.5 py-0.5 text-[9px] bg-[#0C1017] border border-[#1B2230] text-[#8B95A5] hover:text-[#F23645] flex items-center gap-1"
                    >
                      <Trash2 className="w-2.5 h-2.5" />
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="max-h-[340px] overflow-y-auto divide-y divide-[#1B2230]">
              {notifications.length === 0 ? (
                <div className="p-6 text-center text-[11px] text-[#8B95A5]">
                  Noch keine Audio- oder Markt-Events aufgezeichnet. Sobald Take-Profit, Stop-Loss,
                  Order-Fills oder RVOL-Spikes auftreten, erscheinen sie hier.
                </div>
              ) : (
                notifications.map((item) => {
                  const meta = CATEGORY_META[item.category] || CATEGORY_META.UI_FEEDBACK;
                  return (
                    <div
                      key={item.id}
                      onClick={() => {
                        onSelectNotification(item);
                        setIsOpen(false);
                      }}
                      className="px-3 py-2 hover:bg-[#131924] cursor-pointer transition-colors flex flex-col gap-0.5"
                    >
                      <div className="flex items-center justify-between gap-2 text-[10px] tabular-nums">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[#8B95A5]">{item.timeFormatted}</span>
                          <span className="text-[#566173]">·</span>
                          <span className={`font-bold ${meta.textClass}`}>{meta.label}</span>
                          {item.symbol && (
                            <>
                              <span className="text-[#566173]">·</span>
                              <span className="font-bold text-[#00E5FF]">{item.symbol}</span>
                            </>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            arcadeSoundEngine.play(item.category, { force: true });
                          }}
                          title="Chime für dieses Event nochmals abspielen"
                          className="text-[#566173] hover:text-[#00E5FF] p-0.5"
                        >
                          <Volume2 className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="text-[11px] font-semibold text-[#E6EDF3] leading-snug">
                        {item.title}
                      </div>
                      <div className="text-[10px] text-[#8B95A5] leading-tight">{item.detail}</div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    );
  }
);

interface LiveEventToastStackProps {
  toasts: TerminalNotificationItem[];
  onDismissToast: (id: string) => void;
  onSelectToast: (item: TerminalNotificationItem) => void;
}

export const LiveEventToastStack: React.FC<LiveEventToastStackProps> = React.memo(
  ({ toasts, onDismissToast, onSelectToast }) => {
    if (toasts.length === 0) return null;

    return (
      <div className="fixed top-11 right-3 z-40 flex flex-col gap-1.5 w-[330px] pointer-events-none font-mono select-none">
        {toasts.slice(0, 3).map((toast) => {
          const meta = CATEGORY_META[toast.category] || CATEGORY_META.UI_FEEDBACK;
          return (
            <div
              key={toast.id}
              onClick={() => onSelectToast(toast)}
              className={`pointer-events-auto bg-[#0C1017]/95 border ${meta.borderClass} shadow-2xl p-2.5 cursor-pointer transition-opacity hover:bg-[#131924]`}
            >
              <div className="flex items-center justify-between gap-2 text-[10px] tabular-nums mb-0.5">
                <div className="flex items-center gap-1.5">
                  <span className={`font-bold ${meta.textClass}`}>{meta.label}</span>
                  {toast.symbol && (
                    <>
                      <span className="text-[#566173]">·</span>
                      <span className="font-bold text-[#00E5FF] flex items-center gap-0.5">
                        {toast.symbol}
                        <ArrowUpRight className="w-2.5 h-2.5" />
                      </span>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] text-[#8B95A5]">{toast.timeFormatted}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDismissToast(toast.id);
                    }}
                    className="text-[#8B95A5] hover:text-[#E6EDF3] p-0.5"
                    title="Ausblenden"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              </div>

              <div className="text-[11px] font-bold text-[#E6EDF3] leading-snug">
                {toast.title}
              </div>
              <div className="text-[10px] text-[#8B95A5] leading-tight mt-0.5">
                {toast.detail}
              </div>

              {/* 6s visual auto-dismiss indicator line */}
              <div className="w-full h-0.5 bg-[#1B2230] mt-2 overflow-hidden">
                <div className={`w-full h-full animate-toast-6s ${meta.bgClass.replace('/15', '').replace('/20', '')}`} />
              </div>
            </div>
          );
        })}
      </div>
    );
  }
);
