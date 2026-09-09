## 2025-02-27 - Escapable Overlays Are Mandatory for Accessibility
**Learning:** Discovered that Next.js overlays (modals/drawers/dropdowns) in this app lack keyboard dismissal, leaving screen reader and keyboard-only users trapped. Framer Motion's `AnimatePresence` doesn't provide this by default.
**Action:** When building any modal, drawer, or dropdown with `AnimatePresence` or a custom backdrop, immediately pair it with a `useEffect` that listens for the 'Escape' key and sets the open state to false. This ensures WCAG compliance for focus/modal management.
