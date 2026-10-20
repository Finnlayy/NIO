## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-10-20 - Accessible Icon-Only Buttons
**Learning:** Adding an `aria-label` to an icon button that has hidden text on smaller viewports (`sm:inline hidden`) completely overrides the button content for screen readers across all viewports. This causes sighted keyboard shortcut hints (`<kbd>`) inside the button to be skipped by screen readers on desktop.
**Action:** When a button text is visually hidden on small screens, use a screen-reader only sibling span that is hidden on larger screens (`<span className="sr-only sm:hidden">...</span>`) instead of an `aria-label` on the parent button. This guarantees accessibility on mobile without breaking the desktop screen reader experience.
