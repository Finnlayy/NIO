1. **Commit read & license:**
   - Commit: `0cdcec94bc9988d41087d470b32f1fad2ba28691` (from `git log -n 1 --format="%H"` in the cloned repo).
   - License: **MIT License** for the whole repository (from `LICENSE.md`).

2. **Does the image build, and how large is it?**
   - The image failed to build in my Docker environment (a containerd overlayfs `invalid argument` error during `apt-get`).
   - **Estimate**: `python:3.13-slim-bookworm` is around 130-150MB. The `apt-get` installs `xfce4`, `firefox-esr`, `ffmpeg`, `tigervnc`, etc., which easily add ~800MB-1GB. The estimated uncompressed size is around **1.0 to 1.3 GB**.

3. **Is `cua-driver` reachable over MCP or another protocol?**
   - By default, `cua-driver serve` listens on a Unix domain socket (e.g. `~/.cache/cua-driver/cua-driver.sock` or `/tmp/cua-driver.sock` on Linux without a home directory config), according to `socket_path_for_namespace` in `cua-driver-core/src/daemon.rs`.
   - It is not reachable over TCP natively. To reach it from another container, one would need to bind-mount the Unix socket (which can have permission issues) or run something like `socat` to forward TCP to the Unix socket.

4. **Defaults for `VNC_PW`, noVNC binding and telemetry?**
   - **`VNC_PW`**: If omitted, it defaults to no password (`-SecurityTypes None --I-KNOW-THIS-IS-INSECURE`) as seen in `src/scripts/start-vnc.sh`.
   - **noVNC binding**: Binds to port `6901` (`${NOVNC_PORT:-6901}`) pointing to VNC on `5901` (`127.0.0.1:${VNC_PORT:-5901}`).
   - **Telemetry**: Cua Driver sends content-free product telemetry to PostHog by default (using `https://eu.i.posthog.com/batch/`).
   - Setting `CUA_TELEMETRY=0` or `DO_NOT_TRACK=1` disables it, as seen in `cua-telemetry/src/config.rs` where these environment variables return a `Decision` with `enabled = false`.

5. **Does the image need privileges, `/dev/kvm`, etc?**
   - No `kvm` is used. It runs TigerVNC server and `xfce4`.
   - It should not conflict with `--read-only` if volumes are provided for `/home/cua`, `/tmp`, and `/run`, though `supervisord` and `vncserver` typically write to logs and locks in those places. It does not require `--privileged` or root (the Dockerfile uses `USER root` to install packages but then runs as `cua` or configures everything for `cua`).

6. **What does it download at runtime, from where?**
   - It doesn`t dynamically download anything by default; the dependencies (`requirements.txt`) are baked in via `pip install` during the Docker build. `firefox-esr` has telemetry and first-run URLs disabled in `cua.js`.

7. **Verdict**
   - **No-go**. The image is massive because it bundles a full XFCE desktop environment and Firefox. Furthermore, `cua-driver serve` operates strictly via a Unix domain socket by default, creating complex cross-container IPC requirements (e.g., volume mounts for sockets or running socat) just to send MCP commands to it from the orchestrator.
