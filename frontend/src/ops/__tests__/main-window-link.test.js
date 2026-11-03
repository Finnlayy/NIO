"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { MainWindowLink } = require("../components/MainWindowLink");

test("subpages have an explicit, labeled main-window link independent of history", () => {
  const html = renderToStaticMarkup(React.createElement(MainWindowLink));
  assert.match(html, /href="\/"/);
  assert.match(html, /Zurück zu Apollo/);
  assert.doesNotMatch(html, /class="[^"]*\bhidden\b/);
});
