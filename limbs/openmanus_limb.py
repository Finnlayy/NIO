"""OpenManus-Limb (Phase 6) -- lokaler Agent, nur im Container.

OpenManus fuehrt beliebigen Code aus. Deshalb gilt hier: Der Container ist die
Sandbox. Er laeuft ohne Root, read-only, ohne Capabilities, mit Limits und nur im
internen Docker-Netz ``nio-agents``, das nichts ausser dem Modell-Endpunkt erreicht.
Gemountet werden nur der Arbeitsordner und die Konfiguration des einen Laufs, nie
``$HOME``, ``docker.sock``, Keys oder ``workspace/``.

SPERRE: Der Limb steht im Register auf ``planned``. Der Orchestrator lehnt ihn ab,
bis ein Mensch ihn freischaltet (Deployment-Plan, Stufe 4).

Der Modell-Key liegt nur fuer die Dauer des Laufs in ``config.toml``. Provider-Keys
kommen nie in den Container, nur der Key des lokalen Gateways.

Aufruf: ``python3 limbs/openmanus_limb.py --intent runtime/inbox/openmanus/<id>.json``
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# Zwei Aufrufwege, ein Modul -- Begruendung steht in ``echo_limb.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(Path(__file__).resolve().parent), str(_REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

if __package__ in (None, ""):  # direkter Skriptaufruf durch den Orchestrator
    from agent_base import FAILED, RUNNING, SUCCEEDED, TIMED_OUT, AgentLimb, Poll, ServiceDown  # type: ignore[import-not-found]
    from base import LimbContext, LimbError  # type: ignore[import-not-found]
    from container import ConfigError, ContainerConfig, build_docker_run_args  # type: ignore[import-not-found]
else:  # Import als Paket (Tests, Tooling)
    from limbs.agent_base import FAILED, RUNNING, SUCCEEDED, TIMED_OUT, AgentLimb, Poll, ServiceDown
    from limbs.base import LimbContext, LimbError
    from limbs.container import ConfigError, ContainerConfig, build_docker_run_args

from core.protocol import ErrorCode  # noqa: E402

IMAGE = "nio-openmanus:3309bf4"
NETWORK = "nio-agents"
NETWORK_CHECK = '{{.Internal}} {{index .Options "com.docker.network.bridge.inhibit_ipv4"}}'
DEFAULT_LLM_URL = "http://freellmapi-freellmapi-1:3001/v1"
CONTAINER_ROOT = "/app/OpenManus"
MAX_PROMPT_CHARS = 16_000
DEFAULT_RUNTIME_S = 1800
MAX_RUNTIME_S = 7200
DEFAULT_STEPS = 20
MAX_STEPS = 60
DOCKER_TIMEOUT_S = 30
MAX_ARTIFACTS = 200

CONFIG = """[llm]
model = {model}
base_url = {url}
api_key = {key}
max_tokens = 4096
temperature = 0.0

[daytona]
daytona_api_key = "unused"
"""


def _toml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def docker(*args: str, timeout: int = DOCKER_TIMEOUT_S, env: Mapping[str, str] | None = None) -> str:
    """Docker-Aufruf. Ein Fehler heisst fuer das Lauf-Modell: Agent nicht erreichbar."""
    full_env = {**os.environ, **env} if env else None
    try:
        done = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False, env=full_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ServiceDown(f"docker {args[0]}: {type(exc).__name__}") from exc
    if done.returncode != 0:
        raise ServiceDown(f"docker {args[0]}: {done.stderr.strip()[:300]}")
    return done.stdout.strip()


def container_args(run_id: str, job: Path, max_runtime_s: int, max_steps: int) -> tuple[list[str], dict[str, str]]:
    """Die Abschottung kommt aus ``limbs/container.py``, hier stehen nur die Werte dieses Limbs.

    ``no-new-privileges`` bleibt aus: Unter Snap-Docker scheitert damit schon ``exec``.
    Das Image hat keine Setuid-Dateien mehr, und ``--cap-drop ALL`` nimmt alle Rechte.
    Der Container bleibt nach dem Ende stehen, damit ``poll`` seinen Status lesen kann.
    """
    built: tuple[list[str], dict[str, str]] = build_docker_run_args(ContainerConfig(
        name=f"nio-openmanus-{run_id}",
        image=IMAGE,
        run_dir=job,
        agent_name="openmanus",
        network=NETWORK,
        mounts={job / "workspace": f"{CONTAINER_ROOT}/workspace"},
        read_only_mounts={job / "config": f"{CONTAINER_ROOT}/config"},
        env={"NIO_MAX_RUNTIME_S": str(max_runtime_s), "NIO_MAX_STEPS": str(max_steps)},
        tmpfs=[
            "/tmp:rw,noexec,nosuid,size=256m",
            f"{CONTAINER_ROOT}/logs:rw,noexec,nosuid,size=64m,uid={os.getuid()},gid={os.getgid()}",
        ],
        remove=False,
        no_new_privileges=False,
    ))
    return built


class OpenManusLimb(AgentLimb):
    name = "openmanus"
    version = "1.0.0"
    max_runtime_s = DEFAULT_RUNTIME_S

    def handlers(self):
        return {**self.agent_handlers(), "openmanus.ping": self._ping}

    # ------------------------------------------------------------ Einstellungen
    def secrets(self) -> Iterable[str]:
        return (os.environ.get("FREELLMAPI_KEY", ""),)

    @staticmethod
    def _llm() -> tuple[str, str, str]:
        url = os.environ.get("OPENMANUS_LLM_URL", "").strip() or DEFAULT_LLM_URL
        return url, os.environ.get("OPENMANUS_MODEL", "").strip(), os.environ.get("FREELLMAPI_KEY", "").strip()

    @staticmethod
    def _network_problem() -> str:
        try:
            internal = docker("network", "inspect", NETWORK, "--format", NETWORK_CHECK)
        except ServiceDown:
            return f"Netz {NETWORK} fehlt, siehe docs/OPENMANUS.md."
        return "" if internal == "true true" else f"Netz {NETWORK} ist nicht abgeschottet, siehe docs/OPENMANUS.md."

    def _job(self, run_id: str) -> Path:
        job: Path = self.runs.path(run_id) / "job"
        return job

    # ------------------------------------------------------------------- Hooks
    def prepare(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        prompt = str(params.get("prompt", "")).strip()
        if not prompt or len(prompt) > MAX_PROMPT_CHARS:
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"prompt muss 1 bis {MAX_PROMPT_CHARS} Zeichen haben.")
        _, model, key = self._llm()
        if not model or not key:
            raise LimbError(ErrorCode.POLICY_DENIED, "Kein Modell konfiguriert.", hint="OPENMANUS_MODEL und FREELLMAPI_KEY setzen.")
        problem = self._network_problem()
        if problem:
            raise LimbError(ErrorCode.POLICY_DENIED, problem)
        return {
            "max_runtime_s": min(MAX_RUNTIME_S, int(params.get("max_runtime_s") or DEFAULT_RUNTIME_S)),
            "max_steps": min(MAX_STEPS, int(params.get("max_steps") or DEFAULT_STEPS)),
        }

    def launch(self, params: Mapping[str, Any], ctx: LimbContext, run: dict[str, Any]) -> None:
        job = self._job(run["run_id"])
        (job / "workspace").mkdir(parents=True)
        config = job / "config"
        config.mkdir(mode=0o700)
        (config / "task.txt").write_text(str(params["prompt"]).strip(), encoding="utf-8")
        url, model, key = self._llm()
        path = config / "config.toml"
        path.touch(mode=0o600)
        path.write_text(CONFIG.format(model=_toml(model), url=_toml(url), key=_toml(key)), encoding="utf-8")
        run["container"] = f"nio-openmanus-{run['run_id']}"
        try:
            args, env = container_args(run["run_id"], job, run["max_runtime_s"], run["max_steps"])
            docker(*args, env=env)
        except ConfigError as exc:
            self._cleanup(run)
            raise LimbError(ErrorCode.POLICY_DENIED, str(exc)) from exc
        except ServiceDown:
            self._cleanup(run)
            raise

    def poll(self, run: dict[str, Any], ctx: LimbContext) -> Poll:
        status = docker("inspect", run["container"], "--format", "{{.State.Status}}")
        if status in ("created", "running", "restarting"):
            return Poll(RUNNING)
        self._cleanup(run)
        result = self._read_result(run)
        state = str(result.get("state", ""))
        if state not in (SUCCEEDED, TIMED_OUT):  # Unklare Ergebnisse gelten als fehlgeschlagen
            state = FAILED
        return Poll(state, {"error": str(result.get("error", ""))})

    def halt(self, run: dict[str, Any], ctx: LimbContext) -> None:
        self._cleanup(run)

    def gather(self, run: dict[str, Any], ctx: LimbContext) -> dict[str, Any]:
        result = self._read_result(run)
        root = self._job(run["run_id"]) / "workspace"
        files = sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and not path.is_symlink())
        return {
            "summary": str(result.get("summary", "")),
            "steps": result.get("steps", 0),
            "artifacts": [name for name in files if name != "out/result.json"][:MAX_ARTIFACTS],
            "workspace": self._rel(root),
        }

    # ----------------------------------------------------------------- Helfer
    def _rel(self, path: Path) -> str:
        return str(path.relative_to(self.config.repo_root)) if path.is_relative_to(self.config.repo_root) else str(path)

    def _cleanup(self, run: Mapping[str, Any]) -> None:
        """Entfernt Container und Konfiguration mit Key. Klappt auch bei einem halben Start."""
        (self._job(run["run_id"]) / "config" / "config.toml").unlink(missing_ok=True)
        name = str(run.get("container", ""))
        if name and docker("ps", "--all", "--quiet", "--filter", f"name=^{name}$"):
            docker("rm", "--force", name)

    def _read_result(self, run: Mapping[str, Any]) -> dict[str, Any]:
        path = self._job(run["run_id"]) / "workspace" / "out" / "result.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"state": FAILED, "error": "Container endete ohne lesbares Ergebnis."}
        return data if isinstance(data, dict) else {"state": FAILED, "error": "Ergebnis hat kein gueltiges Format."}

    # ---------------------------------------------------------------- Handler
    def _ping(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        output: dict[str, Any] = {"limb": self.name, "version": self.version, "image": IMAGE, "network": NETWORK}
        try:
            docker("image", "inspect", IMAGE, "--format", "{{.Id}}")
            output["image_ready"] = True
        except ServiceDown:
            output["image_ready"] = False
        problem = self._network_problem()
        _, model, key = self._llm()
        output.update(network_ready=not problem, model_ready=bool(model and key))
        output["active_runs"] = len([line for line in self._active().splitlines() if line])
        return output

    @staticmethod
    def _active() -> str:
        try:
            return docker("ps", "--quiet", "--filter", "label=nio.agent=openmanus")
        except ServiceDown:
            return ""


if __name__ == "__main__":
    sys.exit(OpenManusLimb().main())
