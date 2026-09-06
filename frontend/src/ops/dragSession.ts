/**
 * Bookkeeping for one HTML5 drag-and-drop reorder session over the widget
 * grid. Pure state machine — no React, no DOM — so the drag contract
 * (which swaps happen, when, and when the session ends) is unit-testable.
 */
export class DragSession {
  private fromIndex: number | null = null;

  /** Start tracking a drag that began at `index`. */
  begin(index: number): void {
    this.fromIndex = index;
  }

  /**
   * The dragged widget entered another slot. Returns the swap to apply
   * (null when there is nothing to move: no active drag or same slot).
   */
  enter(index: number): { from: number; to: number } | null {
    if (this.fromIndex === null || this.fromIndex === index) return null;
    const move = { from: this.fromIndex, to: index };
    this.fromIndex = index;
    return move;
  }

  /** Finish the session (drop or cancel). */
  end(): void {
    this.fromIndex = null;
  }

  get active(): boolean {
    return this.fromIndex !== null;
  }
}
