# Sigma runtime patch (work in progress)

`sigma-runtime.patch` applies to Sigma commit
`40720b6657b70cf39c51b26c7c25d5d597056844` with `git apply` from the Sigma
repository root. Sigma under `workspace/` is ignored by NIO, so the patch is the
tracked copy of these changes.

This patch is **not a complete implementation of Phase 0**: Redis-backed daily
PnL and a secure frontend flow for releasing the safety switch are outstanding.
Do not treat it as a production-ready safety implementation. Phases 1–5 and the
hybrid polling/SSE control plane are also outstanding.
