## 2025-02-12 - Added ARIA attributes to Map Iterated Toggle Buttons
**Learning:** For dynamic toggle buttons mapped over arrays (like domain filters), using `aria-pressed={active}` and `type="button"` combined with an explicit `aria-label` provides a massive accessibility win for screen readers. Simply showing visual background colors is insufficient.
**Action:** Always add semantic `aria-pressed` states to toggle buttons, ensure they have `type="button"` to avoid form submission side-effects, and include a descriptive `aria-label` when the button text alone (like "All") doesn't provide enough context.

## 2026-11-07 - Consistent Focus Indicators on Interactive Grid Elements
**Learning:** The dashboard grid contains a variety of interactive components (buttons, links, labels enclosing inputs) that lack consistent visual feedback during keyboard navigation. This inconsistency breaks the user's mental model of where focus is and reduces accessibility.
**Action:** Apply consistent `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60` classes to all custom interactive elements, or their parent container via `focus-within`, ensuring the focus indicator matches the application's design system.
