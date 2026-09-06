"use strict";
/**
 * Shared helpers for the zero-dependency UI tests.
 *
 * Two rendering strategies, both DOM-free:
 *  - `mount(fn).render(Component)` calls a component function directly with a
 *    fake React dispatcher. Hook state persists across renders of the same
 *    mount (simulating re-renders), and `useSyncExternalStore` returns the
 *    LIVE store snapshot — so tests observe exactly what a client re-render
 *    would see, including prop references passed to memoized children.
 *  - `renderToStaticMarkup` (react-dom/server) for DOM-structure, style-
 *    isolation and aria assertions on components that take data via props.
 */
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { useGridStore } = require("../ops/store");
const { widgetTemplates } = require("../ops/widgetRegistry");

const internals = React.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;

/** React.memo's default comparator (shallow equality). */
function shallowEqual(a, b) {
  if (Object.is(a, b)) return true;
  if (typeof a !== "object" || a === null || typeof b !== "object" || b === null) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  for (const key of keysA) {
    if (!Object.prototype.hasOwnProperty.call(b, key) || !Object.is(a[key], b[key])) return false;
  }
  return true;
}

/**
 * A fake dispatcher that mirrors the hooks the UI components use. `render`
 * may be called repeatedly: useState/useRef/useCallback/useMemo state persists
 * (like a real re-render), while useSyncExternalStore re-reads live state.
 */
function mount() {
  const states = [];
  const refs = [];
  const cbs = [];
  const memos = [];
  let snapshots = [];
  let index = 0;

  const dispatcher = {
    useState(initial) {
      const i = index++;
      if (!(i in states)) states[i] = typeof initial === "function" ? initial() : initial;
      return [
        states[i],
        (update) => {
          states[i] = typeof update === "function" ? update(states[i]) : update;
        },
      ];
    },
    useRef(initial) {
      const i = index++;
      if (!(i in refs)) refs[i] = { current: initial };
      return refs[i];
    },
    useCallback(fn, deps) {
      const i = index++;
      if (i in cbs && deps !== undefined && shallowEqual(deps, cbs[i].deps)) return cbs[i].fn;
      cbs[i] = { deps, fn };
      return fn;
    },
    useMemo(fn, deps) {
      const i = index++;
      if (i in memos && deps !== undefined && shallowEqual(deps, memos[i].deps)) return memos[i].value;
      memos[i] = { deps, value: fn() };
      return memos[i].value;
    },
    /* Prefer the LIVE snapshot: a direct component call simulates a client
       re-render, not SSR (SSR would use getServerSnapshot = initial state).
       Values are recorded so tests can audit which state a component
       actually subscribes to. */
    useSyncExternalStore(_subscribe, getSnapshot) {
      index++;
      const value = getSnapshot();
      snapshots.push(value);
      return value;
    },
    useContext(context) {
      index++;
      return context && context._currentValue !== undefined ? context._currentValue : context && context.defaultValue;
    },
    useId() {
      index++;
      return "«test-id»";
    },
    /* Every hook consumes a slot, so call order maps 1:1 to real React. */
    useEffect() {
      index++;
    },
    useLayoutEffect() {
      index++;
    },
    useDebugValue() {
      index++;
    },
  };

  return {
    /** Call the component function; returns the element tree it produced. */
    render(fn) {
      const prev = internals.H;
      internals.H = dispatcher;
      index = 0;
      snapshots = [];
      try {
        return fn();
      } finally {
        internals.H = prev;
      }
    },
    /** Store snapshots read during the last render (subscription audit). */
    get lastSnapshots() {
      return snapshots;
    },
  };
}

/** Seed the store with the full default 10-widget layout (same data factories the boot sequence uses). */
function seedDefaultLayout() {
  const widgets = widgetTemplates.map((tpl, i) => ({
    id: `test-w-${i}`,
    templateId: tpl.id,
    title: tpl.defaultSymbol ? `${tpl.title} · ${tpl.defaultSymbol}` : tpl.title,
    symbol: tpl.defaultSymbol,
    span: tpl.defaultSpan,
    height: tpl.defaultHeight,
    minimized: false,
    pinned: false,
    data: tpl.dataFactory(),
  }));
  useGridStore.setState({ widgets, mcpLog: [] });
  return widgets;
}

function resetStore() {
  useGridStore.setState({ widgets: [], mcpLog: [], consoleOpen: false, galleryOpen: false });
}

/** Count opening tags in an HTML string (elements + SVG nodes). */
function countOpenTags(html) {
  return (html.match(/<[a-zA-Z][a-zA-Z0-9-]*/g) ?? []).length;
}

/**
 * JSX children can be nested arrays (e.g. `{list.map(...)}` + a sibling),
 * so every tree walker must recurse into arrays, not just direct elements.
 */
function forEachChild(children, fn) {
  if (children === null || children === undefined || children === false || children === true) return;
  if (Array.isArray(children)) {
    children.forEach((c) => forEachChild(c, fn));
    return;
  }
  fn(children);
}

/** Walk an element tree and collect elements whose type is `type` (identity). */
function collectByType(node, type, out = []) {
  if (!React.isValidElement(node)) return out;
  if (node.type === type) out.push(node);
  forEachChild(node.props && node.props.children, (c) => collectByType(c, type, out));
  return out;
}

/**
 * Walk an element tree and collect the WidgetFrame elements, in document
 * order. The canvas nests frames under LayoutGroup > div.ops-grid >
 * AnimatePresence, so the frames are not the direct children of the root.
 */
function collectFrames(node, out = []) {
  if (!React.isValidElement(node)) return out;
  if (typeof node.type === "function" && node.type.name === "WidgetFrame") out.push(node);
  forEachChild(node.props && node.props.children, (c) => collectFrames(c, out));
  return out;
}

/** Recursively check whether an element tree contains a given text fragment. */
function hasText(node, text) {
  if (typeof node === "string" || typeof node === "number") return String(node).includes(text);
  if (!React.isValidElement(node)) return false;
  let found = false;
  forEachChild(node.props && node.props.children, (c) => {
    if (hasText(c, text)) found = true;
  });
  return found;
}

module.exports = {
  React,
  renderToStaticMarkup,
  mount,
  shallowEqual,
  useGridStore,
  widgetTemplates,
  seedDefaultLayout,
  resetStore,
  countOpenTags,
  collectFrames,
  collectByType,
  hasText,
};
