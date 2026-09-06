"use strict";
/**
 * Dev utility (not run by node --test): prints the DOM node budget of the
 * default 10-widget layout — total and per-widget — for before/after deltas.
 *
 *   node .test-build/__tests__/measure-report.js
 */
const { React, renderToStaticMarkup, seedDefaultLayout, resetStore, countOpenTags } = require("./helpers");
const { useGridStore } = require("../ops/store");
const { WidgetFrame } = require("../ops/widgets/WidgetFrame");
const { renderWidget } = require("../ops/widgets");

const noop = () => {};
seedDefaultLayout();
let total = 0;
const rows = [];
for (const [i, widget] of useGridStore.getState().widgets.entries()) {
  const html = renderToStaticMarkup(
    React.createElement(WidgetFrame, {
      widget,
      index: i,
      dragging: false,
      onDragStart: noop,
      onDragEnter: noop,
      onDragEnd: noop,
      children: renderWidget(widget),
    }),
  );
  const nodes = countOpenTags(html);
  total += nodes;
  rows.push(`  [${String(nodes).padStart(3)}] ${widget.title}`);
}
resetStore();
console.log(`default layout: ${total} DOM nodes (10 widgets)`);
console.log(rows.join("\n"));
