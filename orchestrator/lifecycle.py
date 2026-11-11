"""Read-only local startup diagnostics. No workers or databases are started here."""
from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
from urllib.parse import urlsplit

from core.config import NeuConfig


def preflight(config: NeuConfig, *, probe_services: bool = True) -> dict:
    components = []

    def add(name: str, state: str, code: str = "OK", explanation: str = "", remediation: str = "") -> None:
        components.append({"name": name, "state": state, "code": code, "explanation": explanation, "remediation": remediation})

    add("python", "ready")
    node = shutil.which("node")
    try:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=3, check=True).stdout.strip() if node else ""
        parts = version.removeprefix("v").split(".")
        supported = len(parts) >= 2 and (int(parts[0]), int(parts[1])) >= (20, 9)
    except (ValueError, OSError, subprocess.SubprocessError):
        supported = False
    if supported:
        add("node", "ready")
    else:
        add("node", "blocked", "NODE_UNSUPPORTED", "Next.js 16 requires Node 20.9 or newer.", "Install Node.js 20.9 or newer on PATH.")
    required = ("orchestrator/runner.py", "orchestrator/cli.py", "protocol/intent.schema.json", "frontend/package.json")
    missing = [p for p in required if not (config.repo_root / p).is_file()]
    if missing:
        add("repository", "blocked", "FILES_MISSING", "Required repository files are missing.", "Restore the tracked files: " + ", ".join(missing))
    else:
        try:
            metadata = json.loads((config.repo_root / "frontend/package.json").read_text())
            if not isinstance(metadata.get("dependencies", {}).get("next"), str):
                raise ValueError
        except (OSError, ValueError, AttributeError):
            add("repository", "blocked", "FRONTEND_METADATA_INVALID", "Frontend metadata is invalid.", "Restore frontend/package.json from the repository.")
        else:
            add("repository", "ready")
    try:
        data = json.loads(config.registry_path.read_text(encoding="utf-8"))
        limbs = data["limbs"]
        runtimes = data["runtimes"]
        if not isinstance(limbs, dict) or not limbs or not isinstance(runtimes, dict):
            raise ValueError
        if data.get("default_limb") not in limbs or limbs[data["default_limb"]].get("status") != "active":
            raise ValueError
        for item in limbs.values():
            if not isinstance(item, dict) or item.get("status") not in ("active", "planned", "deprecated"):
                raise ValueError
            if item["status"] == "active":
                entry = item.get("entrypoint")
                if not isinstance(entry, str) or not entry or item.get("runtime") not in runtimes:
                    raise ValueError
                path = (config.repo_root / entry).resolve()
                if not path.is_relative_to(config.repo_root) or not path.is_file():
                    raise ValueError
        add("registry", "ready")
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        add("registry", "blocked", "REGISTRY_INVALID", "Registry or an active entrypoint is invalid or missing.", "Restore limbs/registry.json and all active entrypoints from the repository.")
    path = config.runtime_dir
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        mode = path.stat().st_mode
        writable = path.is_dir() and bool(mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)) and os.access(path, os.W_OK | os.X_OK)
    except OSError:
        writable = False
    if writable:
        add("storage", "ready")
    else:
        add("storage", "blocked", "RUNTIME_UNWRITABLE", "Runtime directory or its nearest existing parent is not writable.", "Choose a writable --runtime-dir or fix its directory permissions.")
    if (config.repo_root / "frontend/.next/BUILD_ID").is_file() and (config.repo_root / "frontend/node_modules/next/dist/bin/next").is_file():
        add("frontend", "ready")
    else:
        add("frontend", "blocked", "FRONTEND_BUILD_MISSING", "The production frontend build or Next.js installation is missing.", "Run npm ci --prefix frontend, then npm run ui:build from the repository root.")
    for name, host, port in (("apollo_port", config.apollo_host, config.apollo_port),):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
            add(name, "ready")
        except OSError:
            add(name, "blocked", "PORT_UNAVAILABLE", "The configured port cannot be bound.", f"Free {host}:{port} or configure a different port.")
    # mypy infers the tuple incorrectly without explicit types
    s_items: tuple[tuple[str, str, int, bool], ...] = (
        ("speech", str(urlsplit(config.speech_url).hostname), int(urlsplit(config.speech_url).port or 80), bool(config.speech_required)),
        ("kanban", str(config.kanban_host), int(config.kanban_port), False),
    )
    for s_name, s_host, s_port, s_required in s_items:
        # Only TCP availability is checked; it is not a health or protocol guarantee.
        reachable = False
        if probe_services:
            try:
                with socket.create_connection((s_host, s_port), timeout=0.2):
                    reachable = True
            except OSError:
                pass
        if reachable:
            add(s_name, "blocked" if s_required else "degraded", "SERVICE_UNVERIFIED", "A socket accepts connections, but service health is not verified.", f"Verify the {s_name} service health manually; required speech cannot yet be verified by doctor.")
        else:
            add(s_name, "blocked" if s_required else "degraded", "SERVICE_UNAVAILABLE", "The service was not reachable or was not probed.", f"Start the local {s_name} service; for optional speech set NEU_SPEECH_REQUIRED=false.")
    state = "blocked" if any(x["state"] == "blocked" for x in components) else "degraded" if any(x["state"] == "degraded" for x in components) else "ready"
    return {"state": state, "components": components, "configuration": config.diagnostics()}


def render(report: dict, json_mode: bool) -> str:
    if json_mode:
        return json.dumps(report, indent=2, ensure_ascii=False)
    lines = [f"Overall: {report['state']}"]
    for item in report["components"]:
        lines.append(f"{item['name']}: {item['state']} ({item['code']})")
        if item['state'] != 'ready':
            lines.append(f"  {item['explanation']} Remediation: {item['remediation']}")
    for key, entry in report.get("configuration", {}).items():
        lines.append(f"config {key}: {entry['value']} (source: {entry['source']})")
    return "\n".join(lines)
