"""Hilfsfunktionen zur Erstellung abgesicherter Docker-Container-Parameter.

Stellt sicher, dass alle Agent-Laufe einheitlich limitiert und abgeriegelt sind.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

class ConfigError(Exception):
    """Wird geworfen, wenn die Container-Konfiguration unsicher ist (Fail Closed)."""
    pass

@dataclass(frozen=True)
class ContainerConfig:
    name: str
    image: str
    run_dir: Path
    agent_name: str
    cpus: str = "2"
    memory: str = "3g"
    memory_swap: str = "3g"
    pids_limit: int = 256
    network: str = "nio-agents"
    user: str = f"{os.getuid()}:{os.getgid()}"
    mounts: dict[Path, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    tmpfs: list[str] = field(default_factory=list)
    remove: bool = True

def build_docker_run_args(config: ContainerConfig) -> tuple[list[str], dict[str, str]]:
    """Baut die hardened `docker run` Argumente.

    Gibt ein Tupel zurueck: (args_liste, env_dict_fuer_subprocess)
    """

    # 1. Netzwerk validieren
    if config.network not in ("nio-agents", "none"):
        raise ConfigError(f"Netzwerk {config.network} ist verboten. Nur nio-agents oder none.")

    # 2. User validieren
    try:
        uid = int(config.user.split(":")[0])
        if uid == 0:
            raise ConfigError("User id 0 (root) ist verboten.")
    except ValueError:
        if config.user == "root":
            raise ConfigError("User root ist verboten.")
    except IndexError:
        pass

    # 3. Validiere run_dir streng (Fail Closed)
    try:
        run_dir_resolved = config.run_dir.resolve(strict=False)
    except OSError:
        raise ConfigError("run_dir nicht aufloesbar.")

    workspace = (_REPO_ROOT / "workspace").resolve(strict=False)
    agents_dir = (_REPO_ROOT / "runtime" / "agents").resolve(strict=False)

    # Pruefe run_dir Einschraenkungen
    if run_dir_resolved == Path("/"):
        raise ConfigError("run_dir / ist verboten.")

    home = os.environ.get("HOME")
    if home:
        home_resolved = Path(home).resolve(strict=False)
        if run_dir_resolved == home_resolved:
            raise ConfigError("run_dir $HOME ist verboten.")

    if run_dir_resolved == _REPO_ROOT:
        raise ConfigError("run_dir Repo Root ist verboten.")

    if run_dir_resolved == workspace or run_dir_resolved.is_relative_to(workspace):
        raise ConfigError("run_dir in workspace/ ist verboten.")

    if not run_dir_resolved.is_relative_to(agents_dir):
        raise ConfigError(f"run_dir muss innerhalb von {agents_dir} liegen, ist aber {run_dir_resolved}.")

    for host_path, container_path in config.mounts.items():
        if ":" in str(host_path):
             raise ConfigError(f"Doppelpunkt in Host-Pfad verboten: {host_path}")
        if ":" in str(container_path):
             raise ConfigError(f"Doppelpunkt in Container-Pfad verboten: {container_path}")

        try:
            resolved_host = host_path.resolve(strict=False)
        except OSError:
            raise ConfigError(f"Mount-Pfad nicht aufloesbar: {host_path}")

        # Verbotene Pfade pruefen (auf resolved_host)
        if "docker.sock" in str(resolved_host):
            raise ConfigError("docker.sock Mount ist verboten.")

        if home:
            if resolved_host == home_resolved or resolved_host.is_relative_to(home_resolved):
                raise ConfigError("$HOME Mount ist verboten.")

        if resolved_host == workspace or resolved_host.is_relative_to(workspace):
            raise ConfigError("workspace/ Mount ist verboten.")

        if resolved_host == _REPO_ROOT:
            raise ConfigError("Repo Root Mount ist verboten.")

        # Pfad muss zwingend innerhalb des run_dir liegen
        if not resolved_host.is_relative_to(run_dir_resolved):
            raise ConfigError(f"Mount {resolved_host} liegt ausserhalb des run_dir {run_dir_resolved}.")

    args = [
        "run",
        "--detach",
        "--name", config.name,
        "--label", f"nio.agent={config.agent_name}",
        "--user", config.user,
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--cpus", config.cpus,
        "--memory", config.memory,
        "--memory-swap", config.memory_swap,
        "--pids-limit", str(config.pids_limit),
        "--network", config.network,
    ]

    if config.remove:
        args.append("--rm")

    for tmp in config.tmpfs:
        args.extend(["--tmpfs", tmp])

    for host_path, container_path in config.mounts.items():
        resolved_host = host_path.resolve(strict=False)
        args.extend(["--volume", f"{resolved_host}:{container_path}"])

    sub_env = {}
    for k, v in config.env.items():
        args.extend(["--env", k])
        sub_env[k] = v

    args.append(config.image)
    return args, sub_env
