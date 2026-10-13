## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-13 - [IPC/API Integration Insight]
**Learning:** Next.js hot reloads can leave orphaned UDS child processes when global instance handlers are not explicitly cleaned up, leading to orphaned sockets blocking the event loop.
**Action:** When attaching Node process event listeners (e.g. exit, SIGINT, SIGTERM) to Next.js server-side singletons, track binding status via a global symbol on the `globalThis` holder to ensure robust UDS socket cleanup.
