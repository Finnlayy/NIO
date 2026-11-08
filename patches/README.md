# Sigma runtime patch (work in progress)

`sigma-runtime.patch` applies to Sigma commit
`40720b6657b70cf39c51b26c7c25d5d597056844` with `git apply` from the Sigma
repository root. Sigma under `workspace/` is ignored by NIO, so the patch is the
tracked copy of these changes.

This patch is **not a complete implementation of Phase 0**: Redis-backed daily
PnL and a secure frontend flow for releasing the safety switch are outstanding.
Do not treat it as a production-ready safety implementation. Phases 1–5 and the
hybrid polling/SSE control plane are also outstanding.

Applied to `workspace/sigma` on 2026-11-02 with `patch -p1` (that directory has
no git repository of its own). The patch also updates
`tests/test_api_contract.py`, because releasing the safety switch now needs the
operator token. Backup of the state before: `~/nio-sicherung/`. The token lives
in `~/.config/nio/sigma.env`, not in this repository.
