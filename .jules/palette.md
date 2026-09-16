## 2026-09-24 - [ActivityFeed List Accessibility]
**Learning:** Dynamically updating lists like event feeds must be wrapped in `role="log"` with `aria-live="polite"` to pass WCAG AAA standards and ensure screen reader users are not abruptly interrupted but are informed of feed updates.
**Action:** Add `role="log"` and `aria-live="polite"` to dynamic event list wrappers such as ActivityFeed.

## 2026-09-24 - [Disabled Button Tooltip Explanations]
**Learning:** Disabled `<button>` tags often do not register hover events to display standard HTML `title` tooltips, meaning keyboard users and mouse users get no context why a button is disabled.
**Action:** Wrap disabled buttons in standard elements like a `div` and apply the `title` attribute on the wrapper to effectively surface the disabled explanation context.

## 2026-09-24 - [Toggle Button State Announcement]
**Learning:** Filter buttons functioning as toggles must explicitly use `aria-pressed={active}` to inform screen readers of their toggled state.
**Action:** Apply `aria-pressed` dynamically to all toggle buttons.