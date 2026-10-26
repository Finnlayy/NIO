"use client";

import type { ReactNode } from "react";

/* ==================================================================== */
/* Shared primitives for the Apollo deck and terminal                    */
/* ==================================================================== */

export type Tone = "cyan" | "violet" | "emerald" | "amber" | "crimson" | "slate";

const TONES: Record<Tone, string> = {
  cyan: "text-cyan-300 border-cyan-400/30 bg-cyan-400/10",
  violet: "text-violet-300 border-violet-400/30 bg-violet-400/10",
  emerald: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
  amber: "text-amber-300 border-amber-400/30 bg-amber-400/10",
  crimson: "text-rose-300 border-rose-400/30 bg-rose-400/10",
  slate: "text-slate-400 border-white/10 bg-white/[0.04]",
};

export function Badge({
  tone = "slate",
  children,
  dot = false,
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[8px] font-bold uppercase tracking-[0.14em] ${TONES[tone]}`}
    >
      {dot && <span className="h-1 w-1 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function SectionCard({
  title,
  hint,
  right,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-white/[0.07] bg-white/[0.02] p-3.5 ${className}`}>
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-mono text-[10px] uppercase tracking-[0.26em] text-slate-400">{title}</h3>
          {hint && <p className="mt-1 max-w-xl text-[11px] leading-relaxed text-slate-400">{hint}</p>}
        </div>
        {right}
      </header>
      {children}
    </section>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  detail,
  disabled,
  id,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  detail?: string;
  disabled?: boolean;
  id: string;
}) {
  return (
    <label
      htmlFor={id}
      className={`flex cursor-pointer items-start justify-between gap-3 rounded-lg border border-white/[0.06] bg-white/[0.015] px-3 py-2 transition-colors hover:border-white/15 ${
        disabled ? "cursor-not-allowed opacity-50" : ""
      }`}
    >
      <span className="min-w-0">
        <span className="block text-[12px] font-medium text-slate-200">{label}</span>
        {detail && <span className="mt-0.5 block text-[10.5px] leading-relaxed text-slate-400">{detail}</span>}
      </span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-[18px] w-8 shrink-0 rounded-full transition-colors duration-200 ${
          checked ? "bg-cyan-400/80" : "bg-white/10"
        }`}
      >
        <span
          className={`absolute top-[2px] h-[14px] w-[14px] rounded-full bg-[#0a0f1d] transition-transform duration-200 ${
            checked ? "translate-x-[16px]" : "translate-x-[2px]"
          }`}
        />
      </button>
    </label>
  );
}

export function Slider({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  format,
  hint,
  accent = "#22d3ee",
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (next: number) => void;
  format?: (value: number) => string;
  hint?: string;
  accent?: string;
}) {
  const pct = max === min ? 0 : ((value - min) / (max - min)) * 100;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11.5px] text-slate-300">{label}</span>
        <span className="font-mono text-[11px] tabular-nums" style={{ color: accent }}>
          {format ? format(value) : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(event) => onChange(Number(event.target.value))}
        className="apollo-range mt-1.5 w-full"
        style={{
          ["--range-accent" as string]: accent,
          ["--range-pct" as string]: `${pct}%`,
        }}
      />
      {hint && <p className="mt-1 text-[10px] leading-relaxed text-slate-400">{hint}</p>}
    </div>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T;
  onChange: (next: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1 rounded-lg border border-white/[0.06] bg-black/25 p-1">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={`flex-1 rounded-md px-2 py-1.5 text-[10.5px] font-medium transition-colors ${
              active ? "bg-cyan-400/15 text-cyan-200" : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block font-mono text-[9.5px] uppercase tracking-[0.2em] text-slate-400">
        {label}
      </label>
      {children}
      {hint && <p className="text-[10px] leading-relaxed text-slate-400">{hint}</p>}
    </div>
  );
}

export function TextInput({
  value,
  onChange,
  placeholder,
  id,
  mono = false,
  type = "text",
  ariaLabel,
}: {
  value: string | number;
  onChange: (next: string) => void;
  placeholder?: string;
  id?: string;
  mono?: boolean;
  type?: "text" | "url" | "number" | "password";
  ariaLabel?: string;
}) {
  return (
    <input
      id={id}
      type={type}
      aria-label={ariaLabel}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      className={`w-full rounded-lg border border-white/[0.08] bg-black/30 px-2.5 py-1.5 text-[12px] text-slate-100 outline-none transition-colors placeholder:text-slate-400 focus:border-cyan-400/50 focus:bg-cyan-400/[0.04] ${
        mono ? "font-mono" : ""
      }`}
    />
  );
}

export function MiniBar({ value, color, height = 3 }: { value: number; color: string; height?: number }) {
  return (
    <div className="overflow-hidden rounded-full bg-white/5" style={{ height }}>
      <div
        className="h-full rounded-full transition-[width] duration-500"
        style={{ width: `${Math.max(2, Math.min(100, value))}%`, background: color }}
      />
    </div>
  );
}

export function EmptyHint({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-white/10 bg-white/[0.01] px-3 py-3 text-[11px] leading-relaxed text-slate-400">
      {children}
    </p>
  );
}
