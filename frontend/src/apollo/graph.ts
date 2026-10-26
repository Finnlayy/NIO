/* ==================================================================== */
/* Geometry for the neural graph                                         */
/*                                                                       */
/* Node positions are stored in *unit ellipse* space (-1..1), so the same */
/* layout survives any viewport: the canvas multiplies by the current    */
/* radii, the DOM cards use percentages. Nothing here touches the DOM,   */
/* which is what makes it testable.                                      */
/* ==================================================================== */

export interface Point {
  x: number;
  y: number;
}

export interface Ellipse {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
}

/** Radius of the ring, as a fraction of the shorter viewport edge. */
export const RING = { rx: 0.405, ry: 0.355 } as const;

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function radialPoint(angle: number, rx = 1, ry = 1): Point {
  return { x: Math.cos(angle) * rx, y: Math.sin(angle) * ry };
}

export function angleOf(from: Point, to: Point): number {
  return Math.atan2(to.y - from.y, to.x - from.x);
}

/** Unit-ellipse position -> pixels inside the scene. */
export function toPixels(position: Point, ellipse: Ellipse): Point {
  return {
    x: ellipse.cx + position.x * ellipse.rx,
    y: ellipse.cy + position.y * ellipse.ry,
  };
}

/** How much of the short edge the ring should occupy for a given viewport. */
export function ellipseFor(width: number, height: number): Ellipse {
  const min = Math.min(width, height);
  return {
    cx: width / 2,
    cy: height / 2,
    rx: min * RING.rx,
    ry: min * RING.ry,
  };
}

/** Rendered size of a ring card, in CSS pixels (widest / tallest variant). */
export const CARD_BOX = { width: 196, height: 96 } as const;

/** Breathing room kept around a card before two of them count as colliding. */
const CARD_GAP = 10;

/** True when any two projected cards would overlap or leave the scene. */
export function cardsCollide(
  positions: readonly Point[],
  ellipse: Ellipse,
  scene: { width: number; height: number },
  box: { width: number; height: number } = CARD_BOX,
  gap = CARD_GAP,
): boolean {
  const points = positions.map((p) => toPixels(p, ellipse));
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    if (
      a.x - box.width / 2 < -1 ||
      a.x + box.width / 2 > scene.width + 1 ||
      a.y - box.height / 2 < -1 ||
      a.y + box.height / 2 > scene.height + 1
    ) {
      return true;
    }
    for (let j = i + 1; j < points.length; j += 1) {
      const b = points[j];
      if (Math.abs(a.x - b.x) < box.width + gap && Math.abs(a.y - b.y) < box.height + gap) {
        return true;
      }
    }
  }
  return false;
}

/**
 * The nominal ring is sized for the eight seed nodes. `/spawn` can add more, so
 * the ellipse is inflated until the cards clear each other — and when the scene
 * is too short for that, the cards themselves step down in size. Only when even
 * the smallest step cannot fit does the caller switch to the node board, which
 * is why `crowded` is reported instead of hidden.
 */
export function fitEllipse(
  positions: readonly Point[],
  width: number,
  height: number,
  box: { width: number; height: number } = CARD_BOX,
): { ellipse: Ellipse; scale: number; crowded: boolean } {
  const base = ellipseFor(width, height);
  const scene = { width, height };
  const scales = [1, 0.92, 0.84, 0.76];
  for (const scale of scales) {
    const scaled = { width: box.width * scale, height: box.height * scale };
    const maxRx = Math.max(40, width / 2 - scaled.width / 2 - 14);
    const maxRy = Math.max(40, height / 2 - scaled.height / 2 - 14);
    for (let step = 0; step <= 24; step += 1) {
      const k = 1 + step * 0.08;
      const ellipse = {
        ...base,
        rx: Math.min(base.rx * k, maxRx),
        ry: Math.min(base.ry * k, maxRy),
      };
      if (!cardsCollide(positions, ellipse, scene, scaled)) return { ellipse, scale, crowded: false };
    }
  }
  return { ellipse: base, scale: 1, crowded: true };
}

/**
 * Angles are kept sorted; a new node drops into the widest gap. That makes
 * `/spawn` deterministic and keeps cards from piling up on one side.
 */
export function widestGapAngle(existing: readonly number[]): number {
  if (existing.length === 0) return -Math.PI / 2;
  const sorted = [...existing].map((a) => normalizeAngle(a)).sort((a, b) => a - b);
  let bestStart = sorted[sorted.length - 1];
  let bestGap = sorted[0] + Math.PI * 2 - bestStart;
  for (let i = 0; i < sorted.length; i++) {
    const next = i + 1 < sorted.length ? sorted[i + 1] : sorted[0] + Math.PI * 2;
    const gap = next - sorted[i];
    if (gap > bestGap) {
      bestGap = gap;
      bestStart = sorted[i];
    }
  }
  return normalizeAngle(bestStart + bestGap / 2);
}

export function normalizeAngle(angle: number): number {
  const twoPi = Math.PI * 2;
  const wrapped = angle % twoPi;
  return wrapped < 0 ? wrapped + twoPi : wrapped;
}

/**
 * Cubic control points for an axon. The curve bows *away* from the orb by a
 * per-node amount so parallel edges never collapse into one line.
 */
export function axonCurve(from: Point, to: Point, bow = 0.18): [Point, Point, Point, Point] {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  const nx = -dy / length;
  const ny = dx / length;
  const offset = length * bow;
  return [
    from,
    { x: from.x + dx * 0.34 + nx * offset, y: from.y + dy * 0.34 + ny * offset },
    { x: from.x + dx * 0.68 + nx * offset * 0.72, y: from.y + dy * 0.68 + ny * offset * 0.72 },
    to,
  ];
}

export function cubicAt(p0: Point, p1: Point, p2: Point, p3: Point, t: number): Point {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return {
    x: a * p0.x + b * p1.x + c * p2.x + d * p3.x,
    y: a * p0.y + b * p1.y + c * p2.y + d * p3.y,
  };
}

export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/* -------------------------------------------------------------------- */
/* Vesicle spring — stage 1 of the Lymp animation                        */
/* -------------------------------------------------------------------- */

export interface SpringState {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export const VESICLE_SPRING: { stiffness: number; damping: number } = { stiffness: 92, damping: 13 };

/** Semi-implicit Euler; dt is clamped so a background tab cannot explode it. */
export function springStep(
  state: SpringState,
  target: Point,
  dt: number,
  stiffness = VESICLE_SPRING.stiffness,
  damping = VESICLE_SPRING.damping,
): SpringState {
  const step = Math.min(0.05, Math.max(0, dt));
  const ax = (target.x - state.x) * stiffness - state.vx * damping;
  const ay = (target.y - state.y) * stiffness - state.vy * damping;
  const vx = state.vx + ax * step;
  const vy = state.vy + ay * step;
  return { x: state.x + vx * step, y: state.y + vy * step, vx, vy };
}

/* -------------------------------------------------------------------- */
/* Small deterministic helpers                                           */
/* -------------------------------------------------------------------- */

/** mulberry32 — the same generator the Python acceptance gates use. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const full = value.length === 3 ? value.split("").map((c) => c + c).join("") : value;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${clamp01(alpha)})`;
}

export function shortId(seed = Math.random()): string {
  return Math.floor(seed * 0xffffff).toString(36).padStart(4, "0").slice(-4);
}

export function formatMs(ms: number): string {
  return `${Math.round(ms)} ms`;
}

/** Deterministic bow direction per node, so edges are stable across renders. */
export function bowFor(nodeId: string): number {
  let hash = 0;
  for (let i = 0; i < nodeId.length; i++) hash = (hash * 31 + nodeId.charCodeAt(i)) | 0;
  return ((hash & 1) === 0 ? 1 : -1) * (0.14 + (Math.abs(hash) % 100) / 1000);
}
