# J11: Cua spike, findings only (NIO)

Branch: `jules/j11-cua-spike`

Files: `docs/helpers/CUA_SPIKE.md` (new). No other file changes.

## Goal

The plan is to build the image `libs/xfce-cua` from a pinned commit of https://github.com/trycua/cua and to control it through the included `cua-driver` (MIT). Check whether this works, before any limb is written.

## Required result

`docs/helpers/CUA_SPIKE.md` answers, each with evidence from source or from a command you ran:

1. Which commit was read, and the license of each part the plan would use.
2. Does the image build, and how large is it? If Docker is missing in your VM, say so and estimate from the Dockerfile, marked as an estimate.
3. Is `cua-driver` inside the image reachable over MCP or another protocol from another container? Which port and which transport?
4. What are the defaults for VNC password, noVNC binding and telemetry? How do `VNC_PW`, `DO_NOT_TRACK=1` and `CUA_TELEMETRY=0` act, read from the source?
5. Does the image need privileges, `/dev/kvm`, or anything that conflicts with `--cap-drop ALL`, `--read-only` or a non-root user?
6. What does it download at runtime, from where?
7. A verdict: go, go with changes, or no-go, with the reasons.

Do not run `cua-driver` outside a container. Do not add the code to this repo. Do not add a limb.
