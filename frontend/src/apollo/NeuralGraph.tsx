"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { NODE_CATEGORY_STYLE, NODE_STATE_STYLE, PALETTE } from "./catalog";
import {
  axonCurve,
  bowFor,
  clamp01,
  cubicAt,
  easeInOutCubic,
  easeOutCubic,
  ellipseFor,
  fitEllipse,
  hexToRgba,
  springStep,
  toPixels,
  type Ellipse,
  type Point,
  type SpringState,
} from "./graph";
import { useApolloStore } from "./store";
import type { Impulse, NioNode } from "./types";

const IMPULSE_COLORS: Record<Impulse["kind"], { from: string; to: string }> = {
  outbound: { from: PALETTE.cyan, to: "#7dd3fc" },
  inbound: { from: PALETTE.emerald, to: PALETTE.magenta },
  failover: { from: PALETTE.amber, to: PALETTE.emerald },
  handshake: { from: PALETTE.emerald, to: PALETTE.cyan },
};

function lerpHex(a: string, b: string, t: number): string {
  const parse = (hex: string) => {
    const v = hex.replace("#", "");
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = parse(a);
  const [r2, g2, b2] = parse(b);
  return `rgb(${Math.round(r1 + (r2 - r1) * t)}, ${Math.round(g1 + (g2 - g1) * t)}, ${Math.round(b1 + (b2 - b1) * t)})`;
}

export function NeuralGraph({ children }: { children: React.ReactNode }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const seenAt = useRef(new Map<string, number>());
  const vesicles = useRef(new Map<string, SpringState>());
  const filterId = `gooey-lymp-filter-${useId().replace(/:/g, "")}`;
  const nodes = useApolloStore((s) => s.nodes);

  /* Cards are 196 x ~96 and are centred on the ring, so the ring radius has to
     leave half a card plus a margin on every side — and grow when `/spawn`
     pushes past the eight seed nodes. `fitEllipse` walks the radius out until
     every card clears its neighbours; if the scene is simply too small it
     reports `crowded` and the nodes fall back to the board below. */
  const measured = size.width > 1 && size.height > 1;
  const geometry = useMemo(() => {
    const positions = nodes.map((node) => node.position);
    // Before the ResizeObserver reports, fall back to a nominal desktop scene so
    // the server and the first client render agree: a 0x0 scene reads as
    // "crowded", which used to flip the markup to the board and fail hydration.
    if (!measured) return { ellipse: ellipseFor(1440, 720), scale: 1, crowded: false };
    return fitEllipse(positions, size.width, size.height);
  }, [nodes, size, measured]);
  const { ellipse, scale, crowded } = geometry;

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (box) setSize({ width: box.width, height: box.height });
    });
    observer.observe(element);
    setSize({ width: element.clientWidth, height: element.clientHeight });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.width === 0 || size.height === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(size.width * dpr);
    canvas.height = Math.round(size.height * dpr);
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;

    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let raf = 0;
    let last = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const store = useApolloStore.getState();
      const { nodes, impulses, vesicles: storeVesicles } = store;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size.width, size.height);

      const orbPoint: Point = { x: ellipse.cx, y: ellipse.cy };
      const activeIds = new Set(nodes.map((node) => node.id));
      for (const key of seenAt.current.keys()) if (!activeIds.has(key)) seenAt.current.delete(key);

      /* ---------------------------------------------------------- axons */
      const positions = new Map<string, Point>();
      for (const node of nodes) {
        positions.set(node.id, toPixels(node.position, ellipse));
      }

      for (const node of nodes) {
        const to = positions.get(node.id);
        if (!to) continue;
        const first = seenAt.current.get(node.id) ?? now;
        if (!seenAt.current.has(node.id)) seenAt.current.set(node.id, now);
        const lock = clamp01((now - first) / 700);
        if (lock <= 0) continue;

        const bow = bowFor(node.id);
        const [p0, p1, p2, p3] = axonCurve(orbPoint, to, bow);
        const style = NODE_CATEGORY_STYLE[node.category];
        const nodeState = NODE_STATE_STYLE[node.state];

        // base axon: fades in while locking
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.bezierCurveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
        ctx.lineWidth = 1.3;
        ctx.strokeStyle = hexToRgba(style.color, 0.42 * lock);
        ctx.stroke();
        // soft outer glow so the axon reads on the dark stage
        ctx.lineWidth = 4;
        ctx.globalAlpha = 0.10 * lock;
        ctx.strokeStyle = style.color;
        ctx.stroke();
        ctx.globalAlpha = 1;

        // travelling lock-in highlight on spawn
        if (lock < 1) {
          const head = easeOutCubic(lock);
          ctx.setLineDash([size.width * 0.09, size.width * 0.9]);
          ctx.lineDashOffset = -head * size.width * 0.99;
          ctx.strokeStyle = hexToRgba(style.color, 0.9);
          ctx.lineWidth = 1.6;
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // active node: brighter running energy
        if (node.state !== "IDLE" && node.state !== "LYMP_SPAWNING") {
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.bezierCurveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
          ctx.strokeStyle = hexToRgba(nodeState.color, 0.42);
          ctx.lineWidth = 1.8;
          ctx.shadowColor = nodeState.color;
          ctx.shadowBlur = 12;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
        ctx.restore();
      }

      /* ------------------------------------------------- Lymp vesicles */
      for (const vesicle of storeVesicles) {
        const target = toPixels(vesicle.to, ellipse);
        let spring = vesicles.current.get(vesicle.id);
        if (!spring) {
          spring = { x: orbPoint.x, y: orbPoint.y, vx: 0, vy: 0 };
          vesicles.current.set(vesicle.id, spring);
        }
        const next = springStep(spring, target, dt, 78, 11.5);
        vesicles.current.set(vesicle.id, next);
        const t = clamp01((now - vesicle.startedAt) / vesicle.durationMs);

        // tether: the membrane thread that is still stretching
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(orbPoint.x, orbPoint.y);
        ctx.arc(next.x, next.y, 1.2, 0, Math.PI * 2);
        ctx.strokeStyle = hexToRgba(vesicle.hue, 0.35 * (1 - t));
        ctx.lineWidth = 1 + (1 - t) * 2.2;
        ctx.stroke();

        // droplet: soft gooey blob with a wobbling silhouette
        const wobble = 1 + Math.sin(now / 90 + t * 6) * 0.13;
        const radius = (15 + 26 * easeOutCubic(t)) * wobble * (1 - t * 0.35);
        const gradient = ctx.createRadialGradient(
          next.x - radius * 0.25,
          next.y - radius * 0.3,
          radius * 0.1,
          next.x,
          next.y,
          radius,
        );
        gradient.addColorStop(0, hexToRgba(vesicle.hue, 0.95));
        gradient.addColorStop(0.55, hexToRgba(vesicle.hue, 0.55));
        gradient.addColorStop(1, hexToRgba(vesicle.hue, 0.05));
        ctx.beginPath();
        ctx.arc(next.x, next.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.shadowColor = vesicle.hue;
        ctx.shadowBlur = 26;
        ctx.fill();
        ctx.shadowBlur = 0;

        // nucleus
        ctx.beginPath();
        ctx.arc(next.x, next.y, Math.max(1.5, radius * 0.22), 0, Math.PI * 2);
        ctx.fillStyle = hexToRgba("#ffffff", 0.75);
        ctx.fill();
        ctx.restore();
      }
      for (const key of vesicles.current.keys()) {
        if (!storeVesicles.some((v) => v.id === key)) vesicles.current.delete(key);
      }

      /* -------------------------------------------------- impulse packets */
      for (const impulse of impulses) {
        const to = positions.get(impulse.nodeId);
        if (!to) continue;
        const t = clamp01((now - impulse.startedAt) / impulse.durationMs);
        if (t >= 1) continue;
        const [p0, p1, p2, p3] = axonCurve(orbPoint, to, bowFor(impulse.nodeId));
        const eased = easeInOutCubic(t);
        const along = impulse.direction === "node-to-orbit" ? 1 - eased : eased;
        const colors = IMPULSE_COLORS[impulse.kind];

        // trail: previous few samples, fading out
        for (let i = 1; i <= 5; i++) {
          const back = Math.max(0, along - i * 0.022);
          const point = cubicAt(p0, p1, p2, p3, back);
          const alpha = 0.42 * (1 - i / 6);
          const radius = Math.max(1.2, 4.6 - i * 0.65);
          ctx.beginPath();
          ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
          ctx.fillStyle = hexToRgba(colors.from, alpha);
          ctx.fill();
        }

        const head = cubicAt(p0, p1, p2, p3, along);
        const headColor = lerpHex(colors.from, colors.to, eased);
        ctx.save();
        ctx.beginPath();
        ctx.arc(head.x, head.y, 3.4, 0, Math.PI * 2);
        ctx.fillStyle = headColor;
        ctx.shadowColor = headColor;
        ctx.shadowBlur = 18;
        ctx.fill();
        ctx.shadowBlur = 0;

        // ring pulse
        ctx.beginPath();
        ctx.arc(head.x, head.y, 7 + Math.sin(now / 60) * 1.6, 0, Math.PI * 2);
        ctx.strokeStyle = hexToRgba(colors.to, 0.35);
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [size, ellipse]);

  /* Under ~720 px eight 196 px cards cannot sit on a ring without colliding, so
     the graph folds into a column: orb on top, nodes in a scrollable grid.
     The axons are a wide-screen affordance and are skipped there. */
  const compact = measured && size.width < 720;
  const layout = compact ? "compact" : crowded ? "board" : "radial";

  return (
    <div
      ref={containerRef}
      className="absolute inset-0"
      data-testid="neural-graph"
      data-layout={layout}
    >
      {layout === "radial" && (
        <svg aria-hidden className="pointer-events-none absolute h-0 w-0">
          <defs>
            <filter id={filterId} colorInterpolationFilters="sRGB">
              <feGaussianBlur in="SourceGraphic" stdDeviation="9" result="blur" />
              <feColorMatrix
                in="blur"
                mode="matrix"
                values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 24 -11"
                result="goo"
              />
              <feBlend in="SourceGraphic" in2="goo" />
            </filter>
          </defs>
        </svg>
      )}

      {layout === "radial" && (
        <canvas ref={canvasRef} className="pointer-events-none absolute inset-0" aria-hidden />
      )}

      {layout === "board" ? (
        <div
          className="absolute inset-0 z-[6] overflow-y-auto overscroll-contain bg-[#05070d] px-3 pb-6 pt-3 sm:px-4"
          data-testid="node-board"
        >
          <p className="mb-2 font-mono text-[9.5px] uppercase tracking-[0.2em] text-slate-400">
            Node board · {nodes.length} live · ring at capacity
          </p>
          <NodeCards variant="grid" positions={ellipse} gooeyFilter={`url(#${filterId})`} />
        </div>
      ) : compact ? (
        <div className="absolute inset-0 overflow-y-auto overscroll-contain px-3 pb-4 pt-1">
          <div className="relative mx-auto h-[min(62vw,300px)] w-full max-w-[340px]">{children}</div>
          <NodeCards variant="grid" positions={ellipse} gooeyFilter={`url(#${filterId})`} />
        </div>
      ) : (
        <>
          {children}
          <NodeCards variant="radial" positions={ellipse} scale={scale} gooeyFilter={`url(#${filterId})`} />
        </>
      )}
    </div>
  );
}

/* ==================================================================== */
/* Node cards                                                            */
/* ==================================================================== */

function NodeCards({
  positions,
  gooeyFilter,
  variant,
  scale = 1,
}: {
  positions: Ellipse;
  gooeyFilter: string;
  variant: "radial" | "grid";
  /** Radius cards step down to when the ring is crowded. */
  scale?: number;
}) {
  const nodes = useApolloStore((s) => s.nodes);
  const dispatch = useApolloStore((s) => s.dispatch);
  const [hovered, setHovered] = useState<string | null>(null);
  const grid = variant === "grid";

  return (
    <div className={grid ? "relative grid grid-cols-1 gap-2 sm:grid-cols-2" : "absolute inset-0"}>
      {nodes.map((node) => {
        if (grid) {
          return (
            <div key={node.id} className="min-w-0">
              <NodeCard
                node={node}
                gooeyFilter={gooeyFilter}
                hovered={hovered === node.id}
                onHover={setHovered}
                onDispatch={() => dispatch(node.id, { probe: "layout", at: new Date().toISOString() })}
                fluid
              />
            </div>
          );
        }

        const point = toPixels(node.position, positions);
        // Fixed precision: Math.cos/sin differ by an ulp between Node and the
        // browser, which is enough to make React report a hydration mismatch
        // on the inline style string.
        const pct = (value: number, total: number) =>
          total === 0 ? "50%" : `${((value / total) * 100).toFixed(3)}%`;
        const left = pct(point.x, positions.cx * 2);
        const top = pct(point.y, positions.cy * 2);
        return (
          <div
            key={node.id}
            className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
            style={{ left, top }}
          >
            {/* Scaling an inner box keeps the card centred on its ring slot;
                scaling the positioned box shifts it by the translate amount. */}
            <div style={scale === 1 ? undefined : { transform: `scale(${scale})` }}>
              <NodeCard
                node={node}
                gooeyFilter={gooeyFilter}
                hovered={hovered === node.id}
                onHover={setHovered}
                onDispatch={() => dispatch(node.id, { probe: "layout", at: new Date().toISOString() })}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NodeCard({
  node,
  gooeyFilter,
  hovered,
  onHover,
  onDispatch,
  fluid = false,
}: {
  node: NioNode;
  gooeyFilter: string;
  hovered: boolean;
  onHover: (id: string | null) => void;
  onDispatch: () => void;
  /** Fill the grid cell instead of the fixed 196 px ring card. */
  fluid?: boolean;
}) {
  const style = NODE_CATEGORY_STYLE[node.category];
  const state = NODE_STATE_STYLE[node.state];
  const spawning = node.state === "LYMP_SPAWNING";
  const load = Math.round((node.metrics?.load ?? 0) * 100);

  return (
    <div
      className={`relative transition-transform duration-300 ${hovered ? "scale-[1.03]" : "scale-100"}`}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      data-node-id={node.id}
      data-node-state={node.state}
      data-node-category={node.category}
    >
      {/* gooey membrane layer: this is what wobbles, not the readable card */}
      <div
        aria-hidden
        className={`pointer-events-none absolute -inset-3 ${spawning ? "apollo-lymp-blob" : "opacity-0"}`}
        style={{
          background: `radial-gradient(circle at 50% 45%, ${hexToRgba(style.color, 0.85)} 0%, ${hexToRgba(style.color, 0.35)} 45%, transparent 72%)`,
          filter: gooeyFilter,
        }}
      />

      <div
        className={`relative ${fluid ? "w-full" : "w-[196px]"} rounded-xl border px-3 py-2.5 backdrop-blur-md transition-opacity duration-500 ${
          spawning ? "apollo-crystallise" : "opacity-100"
        }`}
        style={{
          borderColor: hexToRgba(style.color, spawning ? 0.1 : node.state === "IDLE" ? 0.28 : 0.55),
          background: `linear-gradient(150deg, ${hexToRgba(PALETTE.obsidian, 0.94)} 0%, ${hexToRgba("#050810", 0.96)} 100%)`,
          boxShadow:
            node.state === "IDLE"
              ? `0 10px 26px rgba(0,0,0,0.42), inset 0 0 0 1px ${hexToRgba(style.color, 0.06)}`
              : `0 0 0 1px ${hexToRgba(state.color, 0.35)}, 0 12px 34px ${hexToRgba(state.color, 0.18)}`,
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[11px]"
            style={{ background: hexToRgba(style.color, 0.14), color: style.color }}
            aria-hidden
          >
            {style.glyph}
          </span>
          <div className="min-w-0 flex-1">
            <div
              className="text-[12px] font-semibold leading-[1.15] text-slate-100"
              title={node.label}
              style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
            >
              {node.label}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-400">
              {style.short}
            </div>
          </div>
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-full ${node.state === "PROCESSING" || node.state === "STREAMING" || spawning ? "pulse-dot" : ""}`}
            style={{ background: state.color, boxShadow: `0 0 8px ${state.color}` }}
            title={state.label}
          />
        </div>

        <div className="mt-1.5 flex items-center justify-between gap-2 font-mono text-[10px] text-slate-400">
          <span style={{ color: node.state === "IDLE" ? undefined : state.color }}>{state.label}</span>
          <span className="tabular-nums">{Math.round(node.metrics?.latencyMs ?? 0)} ms</span>
        </div>

        {node.metrics?.activeProvider && (
          <div className="mt-0.5 truncate font-mono text-[10px] text-slate-400" title={node.metrics.activeProvider}>
            {node.metrics.activeProvider}
          </div>
        )}

        <div className="relative mt-1.5 h-[3px] overflow-hidden rounded-full bg-white/5">
          <div
            className="absolute inset-y-0 left-0 h-full w-full origin-left rounded-full transition-transform duration-700"
            style={{ transform: `scaleX(${Math.max(3, load) / 100})`, background: hexToRgba(style.color, 0.75) }}
          />
        </div>

        {hovered && !spawning && (
          <button
            type="button"
            onClick={onDispatch}
            className="mt-2 w-full rounded-md border border-white/10 bg-white/5 py-1 font-mono text-[9px] uppercase tracking-[0.18em] text-slate-300 transition-colors hover:border-cyan-400/40 hover:text-cyan-200"
          >
            dispatch probe
          </button>
        )}
      </div>
    </div>
  );
}
