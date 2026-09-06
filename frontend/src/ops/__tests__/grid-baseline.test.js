"use strict";
/**
 * Grid baseline — behavior + DOM-budget guard for the ops canvas.
 * These assertions must hold across every optimization cycle: the rendered
 * structure, accessibility attributes and DOM size stay stable.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const {
  React,
  renderToStaticMarkup,
  mount,
  seedDefaultLayout,
  resetStore,
  countOpenTags,
  collectFrames,
} = require("./helpers");
const { GridCanvas } = require("../ops/GridCanvas");
const { WidgetFrame } = require("../ops/widgets/WidgetFrame");

const noop = () => {};

function frameHtml(widget, index, extra = {}) {
  return renderToStaticMarkup(
    React.createElement(WidgetFrame, {
      widget,
      index,
      dragging: false,
      onDragStart: noop,
      onDragEnter: noop,
      onDragEnd: noop,
      ...extra,
    }),
  );
}

test("renders the full 10-widget default layout with one frame per widget", () => {
  const widgets = seedDefaultLayout();
  const frames = collectFrames(mount().render(GridCanvas));
  resetStore();
  assert.equal(frames.length, 10);
  assert.deepEqual(frames.map((f) => f.key), widgets.map((w) => w.id));
});

test("empty canvas renders the hydration hint", () => {
  resetStore();
  const tree = mount().render(GridCanvas);
  const html = renderToStaticMarkup(tree);
  assert.ok(html.includes("Canvas empty"), "empty-state copy");
  assert.ok(html.includes("ui/hydrate_widget_template"), "boot event hint");
});

test("widget shells expose span, drag affordances and aria labels", () => {
  const widgets = seedDefaultLayout();
  const noop2 = () => {};
  for (const [i, widget] of widgets.entries()) {
    const html = frameHtml(widget, i);
    // React escapes `&` in attribute values.
    assert.ok(html.includes(`aria-label="${widget.title.replace(/&/g, "&amp;")}"`), `aria-label for ${widget.title}`);
    assert.ok(
      html.includes(`grid-column:span ${widget.span} / span ${widget.span}`),
      `grid span for ${widget.title}`,
    );
    assert.ok(html.includes("Drag to reorder"), `grip for ${widget.title}`);
    assert.ok(html.includes("Live data"), `live pulse for ${widget.title}`);
    assert.ok(html.includes("Refresh data"), `refresh for ${widget.title}`);
    assert.ok(html.includes("Widget options"), `options for ${widget.title}`);
    assert.ok(html.includes(widget.title.replace(/&/g, "&amp;")), `body content for ${widget.title}`);
  }
  resetStore();
});

test("pinned widgets lock reordering affordances", () => {
  const widgets = seedDefaultLayout();
  const pinned = { ...widgets[1], pinned: true };
  const html = frameHtml(pinned, 1, { widget: pinned });
  assert.ok(html.includes("Pinned — reordering locked"), "pin notice");
  assert.ok(!html.includes("Drag to reorder"), "no grip while pinned");
  assert.ok(html.includes("ops-widget-pinned"), "pinned styling class");
  resetStore();
});

test("minimized widgets keep the expand control and drop the body", () => {
  const widgets = seedDefaultLayout();
  const minimized = { ...widgets[2], minimized: true };
  const html = frameHtml(minimized, 2, { widget: minimized });
  assert.ok(html.includes("Expand"), "expand control");
  resetStore();
});

/**
 * DOM budget guard: the default 10-widget layout must not bloat.
 * Baseline 2026-09-06: 1065 nodes (heaviest: Market Breadth Radar 218,
 * Composite Rankings 146, Key Levels Table 110).
 */
test("DOM node budget of the default layout is stable (1065)", () => {
  const widgets = seedDefaultLayout();
  let total = 0;
  for (const [i, widget] of widgets.entries()) {
    total += countOpenTags(frameHtml(widget, i));
  }
  resetStore();
  assert.equal(total, 1065, "default layout DOM node count");
});
