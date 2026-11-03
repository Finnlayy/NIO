# J9: Apollo as control room (NIO)

Branch: `jules/j9-apollo-leitstand`

Files: `frontend/src/app/api/apollo/kanban/` (new), `frontend/src/apollo/store.ts`, `frontend/src/apollo/commands.ts`, new components under `frontend/src/apollo/`, `orchestrator/kanban/api.py` (only for the stop routes), frontend tests.

## Gap

Apollo does not talk to Kanban or the orchestrator. `/spawn` and `/dispatch` act only locally (`frontend/src/apollo/store.ts`, `runCommand`).

## Required result

- A server-side route under `frontend/src/app/api/apollo/kanban/` proxies an explicit allowlist of Kanban API calls. The operator token is read on the server from the same environment variable `orchestrator/kanban/config.py` uses for `api_token`. It never reaches the browser and never uses a `NEXT_PUBLIC_` name. With no token set, the route returns 503.
- The target is the local Kanban API only, never a URL from the request.
- `/spawn` and `/dispatch` create real tasks. Nodes show real workers.
- New commands: `/agent`, `/runs`, `/approve`, `/deny`, `/stop`, `/stopall`.
- An approval card shows action, target, cost, data outflow and expiry. Nothing is approved automatically, and voice input can never approve.
- `/approve` calls `POST /api/v1/approvals/issue`, body `{"intent": {...}, "ttl_seconds": N}`, response `{"ticket", "expires_at", "intent_hash"}`. That route is being built in package J4. If it answers 404, show a clear message.
- A visible emergency stop button and a run view with cost and artifacts.
- The stop must work without a ticket. Add operator-authenticated routes to `orchestrator/kanban/api.py` that create and remove `runtime/STOP`. Package J3 adds the same file for the CLI, so use exactly that path.
- With the backend down, Apollo shows an error. It never shows invented data.
- Tests cover the allowlist, a missing token, the token never appearing in responses, and each command.

Package J1 adds `frontend/src/proxy.ts` as a guard for `/api/*`, so do not add your own global guard.
