## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.
## 2026-10-26 - Accessible Disabled Button States
**Learning:** Native `disabled` attributes swallow mouse events (preventing tooltips) and remove elements from the tab order, hiding crucial context from screen readers and keyboard users as to *why* a button is disabled.
**Action:** Replace `disabled` with `aria-disabled="true"`, conditionally add a `title` tooltip explaining the state, manually guard the `onClick` handler, and ensure CSS targets `[aria-disabled="true"]` to match the disabled visual state.
