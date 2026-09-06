/**
 * Frame-coalesced "stick to the bottom" scroller for the MCP console log.
 *
 * The console receives bursty event streams (master-twin injections, boot
 * sequences). Requesting `scrollIntoView` per event would queue one smooth
 * scroll animation per event; collapsing same-frame requests into a single
 * scroll keeps the burst cheap. Pure (no DOM at module scope) so the
 * coalescing contract is unit-testable with an injected frame scheduler.
 */
type FrameAnchor = { scrollIntoView: (options: ScrollIntoViewOptions) => void };
type ScheduleFrame = (callback: () => void) => void;

const defaultScheduleFrame: ScheduleFrame = (callback) => {
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(callback);
  else setTimeout(callback, 16);
};

export class LogScroller {
  private pending = false;
  private anchor: FrameAnchor | null = null;
  private readonly scheduleFrame: ScheduleFrame;

  constructor(scheduleFrame: ScheduleFrame = defaultScheduleFrame) {
    this.scheduleFrame = scheduleFrame;
  }

  /**
   * Request a smooth scroll to the log bottom. Multiple requests within one
   * animation frame collapse into a single scroll; the latest anchor wins.
   */
  request(anchor: FrameAnchor): void {
    this.anchor = anchor;
    if (this.pending) return;
    this.pending = true;
    this.scheduleFrame(() => {
      this.pending = false;
      const el = this.anchor;
      this.anchor = null;
      el?.scrollIntoView({ behavior: "smooth", block: "end" });
    });
  }
}
