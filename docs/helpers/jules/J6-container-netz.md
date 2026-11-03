# J6: Hardened container start and agent network (NIO)

Branch: `jules/j6-container-netz`

Files: `limbs/container.py` (new), `docker/egress-proxy/` (new), `scripts/agents_network.sh` (new), `docs/OPERATIONS.md`, tests under `tests/`.

## Gaps

- `limbs/openmanus_limb.py` builds its own hardened `docker run` arguments. Every further agent would have to copy them.
- There is no way for a container to reach the web through a controlled path. `orchestrator/kanban/config.py` knows only `none` or full network.

Read `limbs/openmanus_limb.py` as the reference, but do not change it. Moving it to the new helper is a later step.

## Required result

- `limbs/container.py` builds the `docker run` argv from a small dataclass. Always set: `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, a non-root user, memory, CPU and pid limits, `--rm` or a stated cleanup, and a label `nio.agent=<name>`.
- Mounts are per run only. The helper refuses `docker.sock`, `$HOME`, `workspace/`, the repo root and any path outside the run directory. Unsafe input raises an error instead of being dropped.
- `scripts/agents_network.sh` creates the internal Docker network `nio-agents` and connects the FreeLLMAPI container. It is safe to run twice. It stays free of secrets.
- `docker/egress-proxy/` is a small forward proxy image using only the Python standard library. It handles HTTP CONNECT, allows only hosts on a per-run allowlist given at start, and denies everything else, including private, loopback and link-local addresses after DNS resolution. Each decision is logged without headers or bodies.
- A container with no allowlist has no proxy at all, so it reaches only FreeLLMAPI.
- `docs/OPERATIONS.md` explains setup and how to check it.
- Tests cover the argv builder, refused mounts and the proxy decision logic without Docker. Docker tests are skipped when Docker is missing, and the PR says so.
