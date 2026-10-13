## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-10-13 - Animating Collapsible Containers without Losing State
**Learning:** When minimizing widgets by unmounting their children conditionally (e.g. `{!widget.minimized && ...}`), internal React state such as unsubmitted form inputs or scroll positions is lost. However, simply animating `height: 0` while keeping the DOM elements mounted leaves them in the keyboard tab order, creating invisible focus traps.
**Action:** To preserve state while maintaining accessibility, keep the elements mounted but use CSS `display: none` (or Framer-Motion's `transitionEnd: { display: 'none' }`) after the height/opacity animation finishes, and apply `aria-hidden={true}` while minimized.

## 2024-05-24 - Framer Motion State Persistence
**Learning:** When using Framer Motion to preserve internal component state across hide/show toggles by hiding elements (`display: none`), putting `display: widget.minimized ? "none" : "block"` within `transitionEnd` causes visual regressions during expansion because the "block" layout is delayed until the end of the transition.
**Action:** Always place `display: "block"` directly inside the `animate` object during the expansion state so that it applies immediately at the start of the animation, and only use `transitionEnd` for `display: "none"` when hiding the element.
