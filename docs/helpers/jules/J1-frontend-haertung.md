# J1: Harden the Apollo API routes (NIO)

Branch: `jules/j1-frontend-haertung`

Files: `frontend/src/app/api/apollo/route.ts`, `frontend/src/app/api/sandbox/route.ts`, `frontend/package.json`, one new request guard for `/api/*`, tests.

## Gaps

1. `frontend/src/app/api/apollo/route.ts` (about lines 78-95) accepts any target URL and sends `FREELLMAPI_KEY` to that host. A reachable dev server can leak the key.
2. `next dev -p 4001` has no `-H`, so Next binds all interfaces.
3. `/api/*` has no guard against requests from other hosts or browser pages.
4. `frontend/src/app/api/sandbox/route.ts` must stay inside its jail for every path.

## Required result

- The key is sent only to the configured FreeLLMAPI host. Any other target gets a 403 and nothing is forwarded. Redirects must not carry the key elsewhere.
- `dev` and `start` bind to `127.0.0.1`.
- A guard covers `/api/*`: it accepts loopback `Host` and same-origin requests and rejects the rest with 403. Use the request-interception file convention of the Next version installed in `frontend/package.json`; check it, because this convention changed in recent versions.
- The sandbox route resolves real paths and rejects `..`, absolute paths and symlinks that leave the jail. It works only behind the guard.
- Existing tests in `frontend/` still pass.
