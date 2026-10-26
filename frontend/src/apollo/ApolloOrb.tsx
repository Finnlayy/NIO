"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ORB_STATE_STYLE, PALETTE } from "./catalog";
import { hexToRgba } from "./graph";
import { FRAGMENT_SHADER, VERTEX_SHADER } from "./orbShader";
import { selectActiveModel, useApolloStore } from "./store";
import type { OrbState } from "./types";

/* ==================================================================== */
/* Per-state rendering targets                                           */
/* ==================================================================== */

interface Visual {
  energy: number;
  colA: [number, number, number];
  colB: [number, number, number];
  shock: number;
  error: number;
}

const rgb = (hex: string): [number, number, number] => {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16) / 255,
    parseInt(value.slice(2, 4), 16) / 255,
    parseInt(value.slice(4, 6), 16) / 255,
  ];
};

const CYAN = rgb(PALETTE.cyan);
const VIOLET = rgb(PALETTE.violet);
const AMBER = rgb(PALETTE.amber);
const EMERALD = rgb(PALETTE.emerald);
const CRIMSON = rgb(PALETTE.crimson);

const VISUALS: Record<OrbState, Visual> = {
  IDLE: { energy: 0.08, colA: [0.02, 0.09, 0.16], colB: CYAN, shock: 0, error: 0 },
  LISTENING: { energy: 0.22, colA: [0.03, 0.11, 0.19], colB: rgb("#38bdf8"), shock: 0, error: 0 },
  THINKING: { energy: 0.95, colA: [0.16, 0.05, 0.24], colB: VIOLET, shock: 0, error: 0 },
  FAILOVER_SWITCH: { energy: 0.55, colA: [0.18, 0.10, 0.02], colB: AMBER, shock: 1, error: 0 },
  DISPATCHING: { energy: 0.62, colA: [0.02, 0.12, 0.18], colB: rgb("#22d3ee"), shock: 0, error: 0 },
  SYNTHESIZING: { energy: 0.5, colA: [0.02, 0.15, 0.12], colB: EMERALD, shock: 0, error: 0 },
  ERROR: { energy: 0.8, colA: [0.18, 0.02, 0.04], colB: CRIMSON, shock: 0, error: 1 },
};

const mix3 = (a: [number, number, number], b: [number, number, number], t: number): [number, number, number] => [
  a[0] + (b[0] - a[0]) * t,
  a[1] + (b[1] - a[1]) * t,
  a[2] + (b[2] - a[2]) * t,
];

/* ==================================================================== */
/* WebGL renderer (returns null when unavailable)                        */
/* ==================================================================== */

interface Renderer {
  resize: () => void;
  frame: (visual: Visual, flare: number, flareAngle: number, hover: number, time: number) => void;
  dispose: () => void;
}

function createWebGL(canvas: HTMLCanvasElement): Renderer | null {
  const gl =
    canvas.getContext("webgl", { antialias: false, alpha: true, premultipliedAlpha: false, depth: false }) ??
    (canvas.getContext("experimental-webgl") as WebGLRenderingContext | null);
  if (!gl) return null;

  const compile = (type: number, source: string) => {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.warn("[apollo] shader compile failed:", gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  };

  const vertex = compile(gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compile(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  if (!vertex || !fragment) return null;

  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.warn("[apollo] program link failed:", gl.getProgramInfoLog(program));
    return null;
  }
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
    gl.STATIC_DRAW,
  );
  const aPos = gl.getAttribLocation(program, "a_pos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  const uniform = (name: string) => gl.getUniformLocation(program, name);
  const u = {
    res: uniform("u_res"),
    time: uniform("u_time"),
    energy: uniform("u_energy"),
    hover: uniform("u_hover"),
    shock: uniform("u_shock"),
    error: uniform("u_error"),
    flare: uniform("u_flare"),
    flareAngle: uniform("u_flareAngle"),
    colA: uniform("u_colA"),
    colB: uniform("u_colB"),
  };

  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
  gl.clearColor(0, 0, 0, 0);

  const resize = () => {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.max(1, Math.round(canvas.clientWidth * dpr));
    const height = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    gl.viewport(0, 0, canvas.width, canvas.height);
  };

  return {
    resize,
    frame(visual, flare, flareAngle, hover, time) {
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(program);
      gl.uniform2f(u.res, canvas.width, canvas.height);
      gl.uniform1f(u.time, time);
      gl.uniform1f(u.energy, visual.energy);
      gl.uniform1f(u.hover, hover);
      gl.uniform1f(u.shock, visual.shock);
      gl.uniform1f(u.error, visual.error);
      gl.uniform1f(u.flare, flare);
      gl.uniform1f(u.flareAngle, flareAngle);
      gl.uniform3fv(u.colA, visual.colA);
      gl.uniform3fv(u.colB, visual.colB);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    },
    dispose() {
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
    },
  };
}

/* ==================================================================== */
/* Canvas2D fallback                                                     */
/* ==================================================================== */

function createCanvas2D(canvas: HTMLCanvasElement): Renderer | null {
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  let width = 0;
  let height = 0;

  const resize = () => {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    width = Math.max(1, Math.round(canvas.clientWidth * dpr));
    height = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
  };

  return {
    resize,
    frame(visual, flare, flareAngle, hover, time) {
      const size = Math.min(width, height);
      const cx = width / 2;
      const cy = height / 2;
      const r = size * 0.335;
      ctx.clearRect(0, 0, width, height);

      const glow = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, r * 2.1);
      const c = (color: [number, number, number], a: number) =>
        `rgba(${color.map((v) => Math.round(v * 255)).join(",")},${a})`;
      glow.addColorStop(0, c(visual.colB, 0.55 * (0.7 + hover * 0.5)));
      glow.addColorStop(0.42, c(visual.colB, 0.16));
      glow.addColorStop(1, c(visual.colB, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, width, height);

      const body = ctx.createRadialGradient(
        cx - r * 0.28,
        cy - r * 0.32,
        r * 0.08,
        cx,
        cy,
        r,
      );
      body.addColorStop(0, c(mix3(visual.colA, visual.colB, 0.65 + visual.energy * 0.25), 0.98));
      body.addColorStop(0.55, c(visual.colA, 0.96));
      body.addColorStop(1, c(mix3(visual.colA, visual.colB, 0.35), 0.9));
      ctx.beginPath();
      const wobble = 1 + Math.sin(time * 1.1) * 0.012 + visual.energy * 0.02;
      ctx.arc(cx, cy, r * wobble, 0, Math.PI * 2);
      ctx.fillStyle = body;
      ctx.fill();

      ctx.lineWidth = Math.max(1, size * 0.006);
      ctx.strokeStyle = c(visual.colB, 0.85);
      ctx.stroke();

      if (visual.shock > 0.001) {
        ctx.beginPath();
        ctx.arc(cx, cy, r * (1 + (1 - visual.shock) * 1.4), 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(245,158,11,${visual.shock})`;
        ctx.lineWidth = Math.max(1, size * 0.012 * visual.shock);
        ctx.stroke();
      }
      if (flare > 0.001) {
        const length = r * 2.4;
        const gradient = ctx.createLinearGradient(
          cx,
          cy,
          cx + Math.cos(flareAngle) * length,
          cy + Math.sin(flareAngle) * length,
        );
        gradient.addColorStop(0, c(visual.colB, 0.5 * flare));
        gradient.addColorStop(1, c(visual.colB, 0));
        ctx.strokeStyle = gradient;
        ctx.lineWidth = Math.max(1, size * 0.018);
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(flareAngle) * length, cy + Math.sin(flareAngle) * length);
        ctx.stroke();
      }
      if (visual.error > 0.001) {
        ctx.beginPath();
        ctx.arc(cx, cy, r * 1.02, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(239,68,68,${visual.error * 0.8})`;
        ctx.lineWidth = Math.max(1, size * 0.008);
        ctx.stroke();
      }
    },
    dispose() {},
  };
}

/* ==================================================================== */
/* Component                                                             */
/* ==================================================================== */

export function ApolloOrb({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rendererRef = useRef<Renderer | null>(null);
  const [hovered, setHovered] = useState(false);
  const hoverRef = useRef(false);
  const [mounted, setMounted] = useState(false);

  const orbState = useApolloStore((s) => s.orbState);
  const flare = useApolloStore((s) => s.flare);
  const setDeckOpen = useApolloStore((s) => s.setDeckOpen);
  const snapshot = useApolloStore((s) => s.router);
  const latency = useApolloStore((s) => s.snapshot().latencyMs);
  const activeModel = useApolloStore(selectActiveModel);
  const config = useApolloStore((s) => s.config);
  const failovers = useApolloStore((s) => s.router.failoverCount);

  const gradientId = useId().replace(/:/g, "");
  const style = ORB_STATE_STYLE[orbState];

  /* animation state lives in a ref: the render loop must not re-render React */
  const animation = useRef({
    energy: 0.08,
    colA: CYAN as [number, number, number],
    colB: CYAN as [number, number, number],
    shock: 0,
    error: 0,
    flare: 0,
    flareAngle: 0,
    hover: 0,
    state: "IDLE" as OrbState,
    flareAt: 0,
    shockAt: 0,
    errorAt: 0,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const prefersReduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const gl = createWebGL(canvas);
    const renderer = gl ?? createCanvas2D(canvas);
    // Written straight to the DOM rather than through state: this is telemetry
    // for tests and devtools, and a state update during mount would produce a
    // hydration attribute mismatch for no benefit.
    const host = canvas.closest("[data-testid='apollo-orb']");
    if (host instanceof HTMLElement) host.dataset.renderer = gl ? "webgl" : renderer ? "canvas2d" : "none";
    if (!renderer) return;
    rendererRef.current = renderer;
    renderer.resize();

    const observer = new ResizeObserver(() => renderer.resize());
    observer.observe(canvas);

    let raf = 0;
    let last = performance.now();
    const started = last;

    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const state = animation.current;
      const target = VISUALS[state.state];
      const ease = prefersReduced ? 0.25 : 1 - Math.pow(0.001, dt);

      state.energy += (target.energy - state.energy) * ease;
      state.colA = mix3(state.colA, target.colA, ease);
      state.colB = mix3(state.colB, target.colB, ease);
      state.hover += ((hoverRef.current ? 1 : 0) - state.hover) * Math.min(1, dt * 6);

      const now2 = performance.now();
      if (target.shock > 0 && now2 - state.shockAt > 2100) state.shockAt = now2;
      if (target.error > 0 && now2 - state.errorAt > 1600) state.errorAt = now2;
      state.shock = target.shock > 0 ? Math.max(0, 1 - (now2 - state.shockAt) / 1500) : Math.max(0, state.shock - dt * 3);
      state.error = target.error > 0 ? Math.max(0, 1 - (now2 - state.errorAt) / 1400) : Math.max(0, state.error - dt * 3);
      state.flare = Math.max(0, 1 - (now2 - state.flareAt) / 900);

      if (!document.hidden) {
        renderer.frame(
          {
            energy: state.energy,
            colA: state.colA,
            colB: state.colB,
            shock: state.shock,
            error: state.error,
          },
          state.flare,
          state.flareAngle,
          state.hover,
          prefersReduced ? 0.35 : (now - started) / 1000,
        );
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      renderer.dispose();
      rendererRef.current = null;
    };
  }, [mounted]);

  /* state -> animation refs (no React work per frame) */
  useEffect(() => {
    animation.current.state = orbState;
    if (orbState === "FAILOVER_SWITCH") animation.current.shockAt = performance.now();
    if (orbState === "ERROR") animation.current.errorAt = performance.now();
  }, [orbState]);

  useEffect(() => {
    if (!flare) return;
    animation.current.flareAt = performance.now();
    animation.current.flareAngle = flare.angle;
  }, [flare]);

  const quota = Math.round(snapshot.primaryQuotaPercent);
  const quotaColor = quota > 50 ? PALETTE.emerald : quota > 15 ? PALETTE.amber : PALETTE.crimson;

  const ringScale = hovered ? 1.06 : 1;

  return (
    <div
      className={`relative flex flex-col items-center ${className}`}
      data-orb-state={orbState}
      data-renderer="pending"
      data-testid="apollo-orb"
    >
      {/* ambient wash behind the orb */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `radial-gradient(circle at 50% 46%, ${hexToRgba(style.color, 0.16)} 0%, transparent 62%)`,
          transition: "background 600ms ease",
        }}
      />

      <div
        className="group relative grid place-items-center"
        style={{ width: "min(78vmin, 520px, 84vw)", height: "min(78vmin, 520px, 84vw)" }}
      >
        {/* containment rings */}
        <svg
          aria-hidden
          viewBox="0 0 400 400"
          className="pointer-events-none absolute inset-0 h-full w-full"
          style={{ transform: `scale(${ringScale})`, transition: "transform 420ms cubic-bezier(0.22,1,0.36,1)" }}
        >
          <defs>
            <radialGradient id={`ringGlow-${gradientId}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={style.color} stopOpacity="0" />
              <stop offset="58%" stopColor={style.color} stopOpacity="0" />
              <stop offset="74%" stopColor={style.color} stopOpacity="0.10" />
              <stop offset="88%" stopColor={style.color} stopOpacity="0.16" />
              <stop offset="100%" stopColor={style.color} stopOpacity="0" />
            </radialGradient>
            <linearGradient id={`dash-${gradientId}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={style.color} stopOpacity="0.9" />
              <stop offset="50%" stopColor={style.color} stopOpacity="0.15" />
              <stop offset="100%" stopColor={style.color} stopOpacity="0.75" />
            </linearGradient>
          </defs>
          <circle cx="200" cy="200" r="150" fill={`url(#ringGlow-${gradientId})`} />
          <circle
            cx="200"
            cy="200"
            r="150"
            fill="none"
            stroke={`url(#dash-${gradientId})`}
            strokeWidth="0.9"
            strokeDasharray="3 7"
            className="apollo-ring-spin"
            style={{ transformOrigin: "200px 200px" }}
          />
          <circle
            cx="200"
            cy="200"
            r="176"
            fill="none"
            stroke={hexToRgba(style.color, 0.18)}
            strokeWidth="0.7"
          />
          <circle
            cx="200"
            cy="200"
            r="190"
            fill="none"
            stroke={hexToRgba(style.color, 0.08)}
            strokeWidth="0.6"
            strokeDasharray="1 12"
            className="apollo-ring-spin-slow"
            style={{ transformOrigin: "200px 200px" }}
          />
          {/* tick marks: the quota ring, drawn as arc segments */}
          {Array.from({ length: 48 }).map((_, index) => {
            const filled = index / 48 < snapshot.primaryQuotaPercent / 100;
            const angle = (index / 48) * Math.PI * 2 - Math.PI / 2;
            const r1 = 186;
            const r2 = filled ? 193 : 190;
            // Rounded to 2 dp: trig last-bits differ between Node and the browser,
            // and React compares the serialised attribute during hydration.
            const cos = Math.round(Math.cos(angle) * 1e4) / 1e4;
            const sin = Math.round(Math.sin(angle) * 1e4) / 1e4;
            return (
              <line
                key={index}
                x1={Math.round((200 + cos * r1) * 100) / 100}
                y1={Math.round((200 + sin * r1) * 100) / 100}
                x2={Math.round((200 + cos * r2) * 100) / 100}
                y2={Math.round((200 + sin * r2) * 100) / 100}
                stroke={filled ? quotaColor : hexToRgba("#64748b", 0.35)}
                strokeWidth={filled ? 1.4 : 0.8}
                strokeLinecap="round"
              />
            );
          })}
        </svg>

        {mounted && (
          <canvas
            ref={canvasRef}
            className="absolute inset-0 h-full w-full"
            style={{ width: "100%", height: "100%" }}
            aria-hidden
          />
        )}

        {/* click target + accessible label */}
        <button
          type="button"
          onClick={() => setDeckOpen(true)}
          onMouseEnter={() => { hoverRef.current = true; setHovered(true); }}
          onMouseLeave={() => { hoverRef.current = false; setHovered(false); }}
          onFocus={() => { hoverRef.current = true; setHovered(true); }}
          onBlur={() => { hoverRef.current = false; setHovered(false); }}
          aria-label={`Apollo orchestrator core — ${style.label}. Open the Apollo control deck.`}
          className="absolute left-1/2 top-1/2 z-10 h-[58%] w-[58%] -translate-x-1/2 -translate-y-1/2 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
          style={{ cursor: "pointer" }}
        >
          <span className="sr-only">Open Apollo control deck</span>
        </button>

        {/* core caption */}
        <div className="pointer-events-none absolute inset-x-0 bottom-[30%] flex flex-col items-center gap-1 text-center">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.42em] text-slate-400">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: style.color, boxShadow: `0 0 10px ${style.color}` }} />
            Apollo Core
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.3em]" style={{ color: style.color }}>
            {style.label}
          </div>
        </div>
      </div>

      {/* micro-HUD, revealed on hover/focus */}
      <div
        className={`pointer-events-none absolute left-1/2 top-1/2 z-20 w-[240px] -translate-y-1/2 translate-x-[min(30vmin,210px)] transition-all duration-300 ${
          hovered ? "opacity-100" : "opacity-0"
        }`}
        aria-hidden={!hovered}
      >
        <div className="glass-card rounded-xl p-3 shadow-[0_18px_50px_rgba(0,0,0,0.45)]">
          <div className="mb-2 flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.24em] text-slate-500">
            <span>apollo · hud</span>
            <span style={{ color: style.color }}>{mounted ? "live" : "—"}</span>
          </div>
          <dl className="space-y-1.5 text-[11px]">
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-500">Active model</dt>
              <dd className="truncate font-medium text-slate-100" title={activeModel.name}>
                {activeModel.name}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-500">Primary quota</dt>
              <dd className="font-mono tabular-nums" style={{ color: quotaColor }}>
                {quota}%
              </dd>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{ width: `${Math.max(2, quota)}%`, background: quotaColor }}
              />
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-500">FreeLLM pool</dt>
              <dd className="font-mono text-slate-300">
                {config.freeLLMRouting.enabled ? "armed" : "off"} · {failovers} swap{failovers === 1 ? "" : "s"}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-500">Latency</dt>
              <dd className="font-mono tabular-nums text-slate-300">
                {Math.round(latency)} ms
              </dd>
            </div>
          </dl>
          <div className="mt-2 border-t border-white/5 pt-2 font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">
            click → control deck
          </div>
        </div>
      </div>
    </div>
  );
}
