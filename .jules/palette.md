## 2024-05-18 - Disabled Button Focusability Insight
**Learning:** Standard `<button disabled>` elements completely swallow focus events in many browsers, making their `title` or `aria-describedby` attributes undiscoverable for keyboard-only users who tab through the interface.
**Action:** When a disabled button requires explanatory context (like "Enter a task description to run"), wrap the button in a standard native element like a `<div tabIndex={0} title="...">` to ensure screen readers and keyboard users can land on it and receive the explanation.
