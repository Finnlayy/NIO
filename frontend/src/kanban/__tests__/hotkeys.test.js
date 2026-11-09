const test = require("node:test");
const assert = require("node:assert/strict");
const { kanbanHotkey } = require("../kanban/hotkeys");

test("hotkeys: c -> new-card", () => {
  const e = { key: "c", metaKey: false, ctrlKey: false, target: null };
  const ctx = { dialogOpen: false, menuOpen: false };
  assert.equal(kanbanHotkey(e, ctx), "new-card");

  e.key = "C"; // shift implicit in uppercase, but key is C
  assert.equal(kanbanHotkey(e, ctx), "new-card");
});

test("hotkeys: mod+c -> null", () => {
  const e = { key: "c", metaKey: true, ctrlKey: false, target: null };
  const ctx = { dialogOpen: false, menuOpen: false };
  assert.equal(kanbanHotkey(e, ctx), null);

  e.metaKey = false;
  e.ctrlKey = true;
  assert.equal(kanbanHotkey(e, ctx), null);
});

test("hotkeys: repeat/composing/typing -> null", () => {
  const ctx = { dialogOpen: false, menuOpen: false };

  assert.equal(kanbanHotkey({ key: "c", metaKey: false, ctrlKey: false, repeat: true, target: null }, ctx), null);
  assert.equal(kanbanHotkey({ key: "c", metaKey: false, ctrlKey: false, isComposing: true, target: null }, ctx), null);

  // typing target
  assert.equal(kanbanHotkey({ key: "c", metaKey: false, ctrlKey: false, target: { tagName: "INPUT" } }, ctx), null);
  assert.equal(kanbanHotkey({ key: "c", metaKey: false, ctrlKey: false, target: { isContentEditable: true, tagName: "DIV" } }, ctx), null);
});

test("hotkeys: dialog/menu open -> null for c", () => {
  const e = { key: "c", metaKey: false, ctrlKey: false, target: null };
  assert.equal(kanbanHotkey(e, { dialogOpen: true, menuOpen: false }), null);
  assert.equal(kanbanHotkey(e, { dialogOpen: false, menuOpen: true }), null);
});

test("hotkeys: mod+Enter only with dialog -> save", () => {
  const e = { key: "Enter", metaKey: true, ctrlKey: false, target: null };
  assert.equal(kanbanHotkey(e, { dialogOpen: true, menuOpen: false }), "save");
  assert.equal(kanbanHotkey(e, { dialogOpen: false, menuOpen: false }), null);
});

test("hotkeys: Escape order", () => {
  const e = { key: "Escape", metaKey: false, ctrlKey: false, target: null };

  // menu closes first if both open
  assert.equal(kanbanHotkey(e, { dialogOpen: true, menuOpen: true }), "close-menu");

  // dialog closes if menu closed
  assert.equal(kanbanHotkey(e, { dialogOpen: true, menuOpen: false }), "close-dialog");

  // null if neither
  assert.equal(kanbanHotkey(e, { dialogOpen: false, menuOpen: false }), null);
});
