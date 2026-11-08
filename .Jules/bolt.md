## 2024-09-25 - Centralized Keyboard Handlers & Modal Ergonomics
**Learning:** Adding local keydown listeners for Escape inside modals bypasses global input guards and can indiscriminately steal keystrokes. Modals also lack inherent keyboard traversability without proper roles and autofocus targets.
**Action:** Remove redundant local Escape listeners in favor of a centralized `opsHotkey` global handler with `isTypingTarget` guard explicitly wiring the `close-panels` action. Ensure all modals use `role="dialog"`, `aria-modal="true"`, and `autoFocus` on the primary dismiss element for accessibility and speed.

## 2025-02-12 - Task Console Ergonomics & Global Execution
**Learning:** The "Run through Neural Core" shortcut (Cmd/Ctrl+Enter) in `TaskConsole.tsx` only fires when the user is focused directly inside the `<textarea>`. This breaks the workflow speed principle, as users expecting a fast dispatch must manually click into the textarea first.
**Action:** Bind context-independent global execution shortcuts via a top-level `useEffect` keyboard listener in the parent layout, enabling users to execute workflows rapidly regardless of focus (safeguarded appropriately if focused in irrelevant fields, or intentionally wired to trigger the console's action).
## 2024-11-08 - [O(1) Map Lookups for Widget Templates]
**Learning:** O(N) array finds (`find()`) in tightly-looped operations can cause massive CPU bottlenecks and slow performance over thousands of iterations.
**Action:** Replaced O(N) array lookups in `frontend/src/ops/widgetRegistry.ts` (`templateByKey` and `templateById`) with O(1) Map lookups, dramatically increasing read performance (roughly 50% CPU time reduction based on benchmarks).
