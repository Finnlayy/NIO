"use strict";
/**
 * Jules PRs 15 + 19: NewsSentiment tokens and ops-grid hotkey mapping.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { mount, renderToStaticMarkup, widgetTemplates } = require("./helpers");
const { NewsSentiment } = require("../ops/widgets/NewsSentiment");
const { isTypingTarget, opsHotkey } = require("../ops/hotkeys");

test("NewsSentiment uses Tailwind tokens, not raw hex, and tabular nums", () => {
  const template = widgetTemplates.find((t) => t.id === "TPL_04");
  assert.equal(template.key, "macro-catalyst-timeline");
  const m = mount();
  const html = renderToStaticMarkup(m.render(() => NewsSentiment({ data: template.dataFactory() })));
  assert.doesNotMatch(html, /#34d399|#f87171|#94a3b8|#fbbf24|#6b7280/);
  assert.match(html, /text-emerald-400|text-rose-400|text-amber-400/);
  assert.match(html, /font-mono tabular-nums/);
  assert.match(html, /bg-rose-400/);
  assert.match(html, /bg-emerald-400/);
});

test("ops hotkeys: mod+k / mod+g / Escape, ignored while typing", () => {
  assert.equal(opsHotkey({ key: "k", metaKey: true, ctrlKey: false }), "toggle-console");
  assert.equal(opsHotkey({ key: "k", metaKey: false, ctrlKey: true }), "toggle-console");
  assert.equal(opsHotkey({ key: "g", metaKey: true, ctrlKey: false }), "toggle-gallery");
  assert.equal(opsHotkey({ key: "Escape", metaKey: false, ctrlKey: false }), "close-panels");
  assert.equal(opsHotkey({ key: "k", metaKey: false, ctrlKey: false }), null);
  assert.ok(isTypingTarget({ tagName: "INPUT" }));
  assert.ok(isTypingTarget({ tagName: "TEXTAREA" }));
  assert.ok(isTypingTarget({ tagName: "DIV", isContentEditable: true }));
  assert.equal(isTypingTarget({ tagName: "BUTTON" }), false);
  assert.equal(isTypingTarget(null), false);
});
