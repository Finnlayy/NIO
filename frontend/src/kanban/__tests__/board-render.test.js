const { test } = require("node:test");
const assert = require("node:assert");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { STATUS_LABELS } = require("../kanban/types");

// Import components (which have been compiled to commonjs in the test build)
const { TaskCard } = require("../kanban/TaskCard");

const dummyTask = {
  id: "t1",
  title: "Test Task",
  description: "",
  labelIds: [],
  assigneeId: null,
  dueDate: null,
  checklist: [],
  status: "backlog",
  order: 0,
  createdAt: "2023-01-01T00:00:00Z",
  updatedAt: "2023-01-01T00:00:00Z"
};

test("TaskCard: no due date yields no date/overdue text", () => {
  const html = renderToStaticMarkup(React.createElement(TaskCard, {
    task: dummyTask,
    labels: [],
    assignee: null,
    visibleIds: ["t1"],
    currentIndex: 0,
    onOpenEditor: () => {}
  }));

  assert.ok(!html.includes("überfällig"), "should not contain überfällig");
});

test("TaskCard: overdue card renders overdue warning", () => {
  const overdueTask = {
    ...dummyTask,
    dueDate: "2000-01-01",
  };

  const html = renderToStaticMarkup(React.createElement(TaskCard, {
    task: overdueTask,
    labels: [],
    assignee: null,
    visibleIds: ["t1"],
    currentIndex: 0,
    onOpenEditor: () => {}
  }));

  assert.ok(html.includes("überfällig"), "should contain überfällig class or sr-only text");
});

test("TaskCard: renders title and overflow label indicator", () => {
  const taskWithLabels = {
    ...dummyTask,
    labelIds: ["l1", "l2", "l3", "l4"]
  };
  const labels = [
    { id: "l1", name: "A", color: "#f00" },
    { id: "l2", name: "B", color: "#0f0" },
    { id: "l3", name: "C", color: "#00f" },
    { id: "l4", name: "D", color: "#ff0" }
  ];

  const html = renderToStaticMarkup(React.createElement(TaskCard, {
    task: taskWithLabels,
    labels: labels,
    assignee: null,
    visibleIds: ["t1"],
    currentIndex: 0,
    onOpenEditor: () => {}
  }));

  assert.ok(html.includes("Test Task"));
  assert.ok(html.includes("+1"));
});
