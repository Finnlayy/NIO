import type { ReactNode } from "react";

/* ------------------------------------------------------------------ */
/* Status dot — a single glance-able health indicator                  */
/* ------------------------------------------------------------------ */
const dotColors: Record<string, string> = {
  online: "bg-emerald-400",
  active: "bg-cyan-400",
  busy: "bg-amber-400",
  error: "bg-rose-400",
  idle: "bg-slate-600",
};

export function StatusDot({
  tone = "online",
  pulse = false,
  label,
}: {
  tone?: "online" | "active" | "busy" | "error" | "idle";
  pulse?: boolean;
  label?: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-slate-500">
      <span className="relative flex h-2 w-2">
        {pulse && (
          <span
            className={`absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping ${dotColors[tone]}`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${dotColors[tone]}`} />
      </span>
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Module header — consistent title row for every grid module          */
/* ------------------------------------------------------------------ */
export function ModuleHeader({
  icon,
  title,
  meta,
  status,
}: {
  icon: ReactNode;
  title: string;
  meta?: string;
  status?: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2.5 mb-3">
      <span className="text-slate-500">{icon}</span>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        {title}
      </h3>
      {meta && <span className="text-[10px] text-slate-600 truncate">{meta}</span>}
      <span className="ml-auto flex items-center gap-2 shrink-0">{status}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tile — the modular card primitive every module is built from        */
/* ------------------------------------------------------------------ */
export function Tile({
  children,
  onClick,
  dimmed = false,
  selected = false,
  accent,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  dimmed?: boolean;
  selected?: boolean;
  /** hex color used for the top accent bar + selection ring */
  accent?: string;
  className?: string;
}) {
  const style = selected && accent ? { borderColor: `${accent}66` } : undefined;

  const content = (
    <div
      className={`tile ${selected ? "tile-selected" : ""} ${dimmed ? "tile-dimmed" : ""} ${
        onClick ? "tile-clickable" : ""
      } ${className}`}
      style={style}
    >
      {accent && <span className="tile-accent" style={{ background: accent }} />}
      {children}
    </div>
  );

  if (!onClick) return content;

  // A div with role=button (rather than a <button>) so a tile can safely
  // contain nested interactive elements (e.g. topic chips).
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return; // ignore nested controls
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
      className="rounded-[0.95rem] cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
      aria-pressed={selected}
    >
      {content}
    </div>
  );
}
