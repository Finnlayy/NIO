## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-10-12 - Accessible Disabled Buttons
**Learning:** Native `:disabled` attributes swallow pointer events and prevent keyboard focus, making it impossible to show informative tooltips or titles explaining *why* a button is disabled (e.g., "Task is running" or "Please enter input").
**Action:** Replace `disabled={condition}` with `aria-disabled={condition}` on buttons, add a descriptive `title` or tooltip, explicitly guard the `onClick` handler with an early return, and map CSS disabled styling (opacity, cursor) and hover guards to the `[aria-disabled="true"]` selector.
