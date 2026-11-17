# Local configuration and diagnostics (partial Wave A)

`neu doctor` (or `python3 -m orchestrator doctor`) inspects the local checkout
without creating runtime directories, starting workers, or opening databases.
Global options precede the command, for example:

```
python3 -m orchestrator --runtime-dir /tmp/nio-diagnostics --json doctor
python3 -m orchestrator --apollo-port 4101 doctor
```

Exit 1 means blocked; exit 0 covers ready and degraded. Each non-ready
component has a code, explanation and remediation. JSON configuration is an
allowlist, not a dump of the environment. The port check briefly binds a local
socket; service checks attempt TCP connections only to configured loopback
addresses, with a short timeout. A listening socket is **not** considered a
health check. Runtime permission checks do not prove a later write will succeed.

Settings are layered as defaults, `neu.config.json`, documented `NEU_*`
environment variables, then explicit Python/CLI overrides. `NEU_ROOT` chooses
which repository config file to read; a `--repo-root` override wins. Values in
`.env.example` are documentation, not automatically loaded. CLI options are
global and must precede the subcommand. See `core/config.py` for the supported
environment names; the example contains a safe subset.

## Important limitations

This is not the completed lifecycle release. There is no canonical stack start
or lifecycle stop command, ownership tracking, startup handshake, or shutdown
verification. Existing `neu stop` is the independent execution emergency STOP;
it writes the STOP sentinel and does not stop the UI. `neu resume` clears it.
Do not use these commands as stack lifecycle controls. There is no start-time
preflight gate yet. The doctor checks some, but not all, prerequisites: it does
not inspect Unix sockets, service protocols, database health, container ownership
or frontend/backend wiring. It does not validate the full registry schema.
Some new settings are diagnostic configuration only: they do not configure the
existing Next.js, speech Limb, or Kanban processes. Do not rely on them to
control those services. Existing execution limits/timer semantics are unchanged;
their legacy parsing is not yet uniformly strict. Manual service startup remains
as documented in the README, not a new supported lifecycle workflow.
