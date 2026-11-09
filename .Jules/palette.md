## 2026-09-12 - Keyboard Shortcut and Modal Close Accessibility
**Learning:** We realized that global keyboard shortcuts in the dashboard were hijacking inputs for users trying to use forms (specifically in elements with `isContentEditable` set). Additionally, drawer/modal components were missing standard Escape key listeners, forcing users to click close buttons or the backdrop, thus limiting keyboard navigation.
**Action:** Always verify `document.activeElement?.isContentEditable` alongside input and textarea tags when writing custom keyboard shortcut hooks. Furthermore, all overlay menus must pair with an `Escape` key close listener to support non-mouse accessibility.

## 2026-09-14 - Visual Keyboard Shortcut Hints
**Learning:** Hidden power-user shortcuts (like 'C' for new card or 'Ctrl+Enter' to save) go unused if users don't know they exist. Displaying small `<kbd>` badges inside primary buttons is an effective way to train users on these shortcuts without cluttering the UI.
**Action:** Always provide visual keyboard-shortcut badges for exposed global commands and form submit actions where shortcuts exist.
## 2025-02-12 - Added ARIA attributes to Map Iterated Toggle Buttons
**Learning:** For dynamic toggle buttons mapped over arrays (like domain filters), using `aria-pressed={active}` and `type="button"` combined with an explicit `aria-label` provides a massive accessibility win for screen readers. Simply showing visual background colors is insufficient.
**Action:** Always add semantic `aria-pressed` states to toggle buttons, ensure they have `type="button"` to avoid form submission side-effects, and include a descriptive `aria-label` when the button text alone (like "All") doesn't provide enough context.
