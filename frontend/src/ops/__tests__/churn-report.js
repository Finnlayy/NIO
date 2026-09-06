"use strict";
/**
 * Dev utility (not run by node --test): measures how many widget frames see
 * prop churn across one live telemetry tick — the unit of re-render waste.
 *
 *   node .test-build/__tests__/churn-report.js
 *
 * With a memoized widget content boundary + stable drag handlers, a tick that
 * only updates the Envelope Chart's spark must churn exactly 1 of 10 frames.
 */
const { mount, shallowEqual, useGridStore, seedDefaultLayout, resetStore, collectFrames } = require("./helpers");
const { GridCanvas } = require("../ops/GridCanvas");

seedDefaultLayout();
const m = mount();
const before = collectFrames(m.render(GridCanvas));

/* Simulate the live-tick from ops/page.tsx: only the envelope chart (TPL_02) data changes. */
const target = useGridStore.getState().widgets.find((w) => w.templateId === "TPL_02");
const spark = (target.data.spark ?? []).map((v) => Math.min(0.98, Math.max(0.02, v + 0.01)));
useGridStore.getState().mergeData(target.id, { spark });

const after = collectFrames(m.render(GridCanvas));

let churn = 0;
const changed = [];
for (let i = 0; i < before.length; i++) {
  if (!shallowEqual(before[i].props, after[i].props)) {
    churn++;
    changed.push(useGridStore.getState().widgets[i].title);
  }
}
resetStore();
console.log(`prop churn per live tick: ${churn}/${before.length} widget frames`);
if (changed.length) console.log(`  changed: ${changed.join(", ")}`);
