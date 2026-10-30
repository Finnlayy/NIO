const assert = require("node:assert");
const test = require("node:test");
const { createDraft, isDirty, validateDraft } = require("../kanban/dialogState");
const { TaskDialog } = require("../kanban/TaskDialog");
const { renderToStaticMarkup, hasText, collectByType, React } = require("./helpers.js");

test("dialogState: createDraft, isDirty, validateDraft", () => {
  const emptyTask = createDraft(null, "backlog", "2023-01-01");
  assert.equal(emptyTask.title, "");
  assert.equal(emptyTask.status, "backlog");
  assert.equal(emptyTask.checklist.length, 0);

  // New empty task is not dirty
  assert.equal(isDirty(emptyTask, null), false);

  emptyTask.title = " Hello ";
  // Dirty once changed
  assert.equal(isDirty(emptyTask, null), true);

  const val1 = validateDraft(emptyTask);
  assert.equal(val1.ok, true);
  assert.equal(val1.value.title, "Hello");

  // Empty title -> error
  emptyTask.title = "   ";
  const val2 = validateDraft(emptyTask);
  assert.equal(val2.ok, false);
  assert.equal(val2.errors.title, "Titel darf nicht leer sein");

  // Invalid date -> dropped
  emptyTask.title = "Valid Title";
  emptyTask.dueDate = "invalid-date";
  const val3 = validateDraft(emptyTask);
  assert.equal(val3.ok, true);
  assert.equal(val3.value.dueDate, null);

  // Valid date -> kept
  emptyTask.dueDate = "2023-12-31";
  const val4 = validateDraft(emptyTask);
  assert.equal(val4.value.dueDate, "2023-12-31");

  // Empty checklist titles dropped
  emptyTask.checklist = [
    { id: "1", title: "  ", completed: false },
    { id: "2", title: " valid ", completed: true }
  ];
  const val5 = validateDraft(emptyTask);
  assert.equal(val5.value.checklist.length, 1);
  assert.equal(val5.value.checklist[0].title, "valid");
});

test("TaskDialog: SSR markup", () => {
  // Very minimal SSR test. We don't have the Zustand store populated here,
  // but it's using the default state (empty board, no tasks).
  // So it will render in "Neue Karte" mode.
  const html = renderToStaticMarkup(
    React.createElement(TaskDialog, { taskId: null, onClose: () => {} })
  );

  assert.ok(html.includes('role="dialog"'), "must have role=dialog");
  assert.ok(html.includes('aria-modal="true"'), "must have aria-modal=true");
  assert.ok(html.includes('aria-labelledby="dialog-title"'), "must have aria-labelledby");
  assert.ok(html.includes('id="dialog-title"'), "must have heading with correct id");
  
  // Create mode should have "Neue Karte" and not "Karte löschen"
  assert.ok(html.includes('Neue Karte'), "must have 'Neue Karte' heading");
  assert.ok(!html.includes('Karte löschen'), "must NOT have 'Karte löschen' button in create mode");
});
