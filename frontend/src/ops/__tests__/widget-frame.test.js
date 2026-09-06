"use strict";
/**
 * Cycle 1 — memoized widget content boundary + stable drag handlers.
 *
 * Verifies the re-render reduction contract end-to-end through the real
 * component code: a telemetry tick or a drag session must churn only the
 * frames whose own data changed, while drag semantics (which swap happens,
 * pinned resistance, session teardown) stay intact.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const {
  mount,
  shallowEqual,
  useGridStore,
  seedDefaultLayout,
  resetStore,
  collectFrames,
} = require("./helpers");
const { GridCanvas } = require("../ops/GridCanvas");
const { WidgetFrameContent } = require("../ops/widgets/WidgetFrame");
const { DragSession } = require("../ops/dragSession");

test("WidgetFrameContent is a memoized boundary", () => {
  assert.equal(WidgetFrameContent.$$typeof, Symbol.for("react.memo"), "content must be React.memo-wrapped");
});

test("live tick churns exactly 1 of 10 frames (the ticked widget)", () => {
  seedDefaultLayout();
  const m = mount();
  const before = collectFrames(m.render(GridCanvas));
  const target = useGridStore.getState().widgets.find((w) => w.templateId === "TPL_02");
  const spark = target.data.spark.map((v) => Math.min(0.98, Math.max(0.02, v + 0.01)));
  useGridStore.getState().mergeData(target.id, { spark });
  const after = collectFrames(m.render(GridCanvas));

  const changed = [];
  for (let i = 0; i < before.length; i++) {
    if (!shallowEqual(before[i].props, after[i].props)) changed.push(i);
  }
  assert.deepEqual(
    changed.map((i) => useGridStore.getState().widgets[i].id),
    [target.id],
    "only the ticked widget's frame may see prop churn",
  );
  resetStore();
});

test("drag start churns only the dragged frame; handlers keep identity", () => {
  seedDefaultLayout();
  const m = mount();
  const before = collectFrames(m.render(GridCanvas));
  before[3].props.onDragStart(3, before[3].props.widget.id);
  const after = collectFrames(m.render(GridCanvas));

  assert.equal(after[3].props.dragging, true, "dragged frame flips dragging");
  for (const i of [0, 1, 2, 4, 5]) {
    assert.ok(
      shallowEqual(before[i].props, after[i].props),
      `frame ${i} props must be shallow-stable while another widget is picked up`,
    );
  }
  // stable callback identity across unrelated re-renders
  assert.equal(after[0].props.onDragStart, before[0].props.onDragStart);
  assert.equal(after[0].props.onDragEnter, before[0].props.onDragEnter);
  assert.equal(after[0].props.onDragEnd, before[0].props.onDragEnd);
  resetStore();
});

test("drag enter applies the swap; drag end clears the session", () => {
  seedDefaultLayout();
  const m = mount();
  const ids = useGridStore.getState().widgets.map((w) => w.id);
  const before = collectFrames(m.render(GridCanvas));

  before[3].props.onDragStart(3, before[3].props.widget.id);
  collectFrames(m.render(GridCanvas))[0].props.onDragEnter(0);

  const order = useGridStore.getState().widgets.map((w) => w.id);
  assert.equal(order[0], ids[3], "widget moved to front");
  assert.deepEqual(order.slice(1, 4), ids.slice(0, 3), "preceding widgets shifted");
  assert.deepEqual(order.slice(4), ids.slice(4), "trailing widgets untouched");

  const frames = collectFrames(m.render(GridCanvas));
  assert.equal(frames.some((f) => f.props.dragging), true, "still dragging mid-session");
  frames[0].props.onDragEnd();
  const final = collectFrames(m.render(GridCanvas));
  assert.ok(final.every((f) => f.props.dragging === false), "dragging cleared after drop");
  resetStore();
});

test("repeated enters track the moving position", () => {
  seedDefaultLayout();
  const m = mount();
  const ids = useGridStore.getState().widgets.map((w) => w.id);
  const before = collectFrames(m.render(GridCanvas));
  before[3].props.onDragStart(3, before[3].props.widget.id);
  collectFrames(m.render(GridCanvas))[0].props.onDragEnter(0);
  // dragged widget now sits at 0; entering 2 moves it 0 -> 2
  collectFrames(m.render(GridCanvas))[2].props.onDragEnter(2);
  const order = useGridStore.getState().widgets.map((w) => w.id);
  assert.equal(order[2], ids[3]);
  assert.equal(order[0], ids[0]);
  resetStore();
});

test("pinned widgets resist reordering (store contract)", () => {
  seedDefaultLayout();
  const store = useGridStore.getState();
  store.togglePin(store.widgets[1].id);
  const before = store.widgets.map((w) => w.id);
  store.reorder(1, 5);
  assert.deepEqual(useGridStore.getState().widgets.map((w) => w.id), before, "pinned widget must not move");
  store.reorder(0, 5);
  const after = useGridStore.getState().widgets.map((w) => w.id);
  assert.equal(after[5], before[0], "unpinned widget moves");
  resetStore();
});

test("DragSession: begin/enter/end contract", () => {
  const s = new DragSession();
  assert.equal(s.active, false);
  assert.equal(s.enter(2), null, "no drag active yet");
  s.begin(2);
  assert.equal(s.active, true);
  assert.equal(s.enter(2), null, "same slot — no swap");
  assert.deepEqual(s.enter(0), { from: 2, to: 0 });
  assert.deepEqual(s.enter(1), { from: 0, to: 1 }, "session tracks the moving position");
  s.end();
  assert.equal(s.active, false);
  assert.equal(s.enter(3), null, "ended session is inert");
});
