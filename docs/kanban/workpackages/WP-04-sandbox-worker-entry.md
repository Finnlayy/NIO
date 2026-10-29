# WP-04: JIT-Sandbox (Docker + Subprozess), Secret-Injektion, `worker_entry.py`

Lies zuerst `00-README.md`. Du lieferst `SandboxSpec`, `SandboxResult`, `SandboxRunner`
und den Dateivertrag `in/` und `out/` exakt wie dort beschrieben. Das Paket ist
sicherheitskritisch.

## `orchestrator/kanban/sandbox.py`
Gemeinsame Basis `_ProcessSandbox`. `run()` läuft so ab:
1. Prozess per `asyncio.create_subprocess_exec(*argv, env=…, stdout=DEVNULL, stderr=PIPE, start_new_session=True)` starten.
2. Schleife alle `min(1.0, heartbeat_s)`:
   - Ändert sich die mtime von `out/heartbeat`, `await on_heartbeat()` aufrufen.
   - Bei Prozessende raus.
   - Nach `deadline_s` den Stop einleiten.
3. stderr auf die letzten 16 KiB begrenzen (Ringpuffer, `stderr_tail`).
4. `cancel(run_id)` stößt denselben Stopp-Pfad an (SIGTERM, Grace, SIGKILL) und setzt
   `cancelled=True`.

**`DockerSandbox(config)`** baut diese argv-Liste (keine Shell):
```
docker run --rm --name nio-w-{uid}-{run_id}
  --cpus {cpus} --memory {memory} --memory-swap {memory} --pids-limit {pids}
  --read-only --tmpfs /tmp:rw,size=64m --cap-drop ALL --security-opt no-new-privileges
  --user 1000:1000 --network {network}
  [--add-host host.docker.internal:host-gateway   # nur wenn network != "none"]
  -v {run_dir}/in:/nio/in:ro -v {run_dir}/out:/nio/out:rw -v {run_dir}/work:/workspace:rw
  -v {kanban_pkg}/worker_entry.py:/nio/bin/worker_entry.py:ro
  -v {kanban_pkg}/mcp_shim.py:/nio/bin/mcp_shim.py:ro
  -e NIO_KANBAN_IN=/nio/in -e NIO_KANBAN_OUT=/nio/out -e NIO_KANBAN_WORKDIR=/workspace
  -e NIO_KANBAN_HEARTBEAT_S=… -e NIO_KANBAN_API_URL={sandbox_api_url}
  -e <NAME>            # fuer JEDES Secret: nur der Name!
  {image} python3 /nio/bin/worker_entry.py
```
- **Secret-Injektion**: Die Werte stehen ausschließlich im `env=` des `docker`-CLI-Prozesses
  (`{**minimal_host_env, **spec.secrets}`). Docker übernimmt `-e NAME` ohne Wert aus der
  Umgebung des CLI. Deshalb erscheinen die Werte weder in `ps`/argv noch in
  `docker inspect … Config.Cmd`.
  - `minimal_host_env` enthält nur `PATH`, `HOME`, `DOCKER_HOST` und `DOCKER_CONFIG`,
    falls gesetzt.
- Stoppen: `docker stop -t {stop_grace_s} nio-w-…`. Docker schickt SIGTERM, wartet die
  Grace-Zeit ab und schickt dann SIGKILL; der Save-on-exit-Hook läuft also.
  Danach den CLI-Prozess abwarten.
- `out/` vorher für UID 1000 beschreibbar machen: `os.chmod(out, 0o777)` und dasselbe für
  `work/`. `in/` bleibt read-only.
- Statische Methode `build_argv(spec) -> list[str]`, damit Tests sie ohne Docker prüfen können.

**`SubprocessSandbox(config)`**: der Dev- und Test-Pfad ohne Docker.
- argv: `[sys.executable, "-I", "<pkg>/worker_entry.py"]`, `cwd=run_dir/work`.
- env enthält nur `PATH`, die `NIO_KANBAN_*`-Variablen mit echten Host-Pfaden
  (`in/`, `out/`, `work/`), `HOME=TMPDIR=run_dir/tmp` und die Secrets.
- Stoppen per `os.killpg(pgid, SIGTERM)`, nach der Grace-Zeit `SIGKILL`
  (Muster: `limbs/rea_limb.py::_kill_group`).
- Harte CPU/RAM-Limits gibt es hier bewusst nicht. Das steht im Docstring: Dieser Modus
  ist nur für Entwicklung gedacht.

`build_sandbox(config) -> SandboxRunner` wählt nach `config.sandbox`.

## `orchestrator/kanban/worker_entry.py` (läuft IN der Sandbox, keine NIO-Imports!)
1. Eigene `_atomic_write(path, data: bytes)`: Temp-Datei im Zielverzeichnis, `fsync`,
   `os.replace`, die Temp-Datei bei Fehler löschen.
2. Liest `in/task.json`, `in/SOUL.md` und `in/history.md`.
3. Ein Heartbeat-Daemon-Thread schreibt alle `NIO_KANBAN_HEARTBEAT_S` den ISO-Zeitstempel
   atomar nach `out/heartbeat`.
4. `signal.signal(SIGTERM, handler)`. Der Handler setzt `interrupted = True` und wirft
   `SystemExit(143)`.
5. Runtime aus dem SOUL-Frontmatter `runtime:` lesen (`noop` | `command` | `opencode`,
   Default `noop`). Das Frontmatter steht zwischen zwei `---`-Zeilen, `key: value`.
   - `noop`: Ergebnis `completed`, Payload `{"echo": task["title"]}`. Gedacht für den Smoke-Test.
   - `command`: Frontmatter `command:` ist eine JSON-argv-Liste und läuft per
     `subprocess.run(argv, cwd=workdir, timeout=…)`. Exit 0 ergibt `completed`, sonst
     `failed` mit den letzten 2 KiB stderr.
   - `opencode`: `["opencode", "run", prompt]` in `NIO_KANBAN_WORKDIR`. Der Prompt setzt
     sich aus Mission und Regeln aus der Seele, dem Task-Titel und der Beschreibung zusammen,
     plus die Anweisung, die Änderungen im Worktree zu committen.
     **Kein `git push`**: Ins Prompt-Ende kommt die Regel "never push, never open PRs".
6. **Save-on-exit** in `finally` (läuft auch bei SIGTERM und Exceptions):
   - `out/result.json` (`status: interrupted` ergibt `failed` mit `reason "SIGTERM"`).
   - `out/experience.json`: `summary` (eine Zeile: Titel und Ergebnis), `lessons` (bei
     Fehlern der Fehlertext), `skills_delta` (Frontmatter `learns:` als CSV, optional),
     `outcome`.
   - `out/SOUL.md`: die Seele mit `skills_delta` im Abschnitt `## Core Skills`, sonst
     unverändert. Format: siehe WP-05, aber hier eine **eigene** Mini-Implementierung
     wegen der Import-Freiheit.
   - Alles über `_atomic_write`, die Reihenfolge ist experience, SOUL, result.
     `result.json` zuletzt dient als Commit-Marker.
7. Exit-Code: 0 bei `completed` oder `blocked`, 1 bei `failed`, 143 bei SIGTERM.

## Tests: `tests/test_kanban_sandbox.py`
- `DockerSandbox.build_argv`:
  - Enthält `--cpus`, `--memory`, `--pids-limit`, `--read-only`, `--cap-drop ALL` und
    `--network none`.
  - **Kein Secret-Wert** in irgendeinem argv-Element (`spec.secrets={"OPENAI_API_KEY": "sk-geheim"}`
    prüfen); `-e OPENAI_API_KEY` ist vorhanden.
- `SubprocessSandbox` Ende-zu-Ende mit dem echten `worker_entry.py`:
  - `noop` ergibt Exit 0, `out/result.json` mit `completed` und eine Experience.
  - `command` mit einem `["python3","-c","import time; time.sleep(30)"]`-Lauf, nach 1 s
    `cancel()`. Erwartet: `cancelled=True`, `result.json` mit `failed`/`SIGTERM`,
    `experience.json` vorhanden, kein `*.tmp` in `out/`.
  - `on_heartbeat` wird mindestens einmal gerufen (`NIO_KANBAN_HEARTBEAT_S=0.2`).
- Docker-Integrationstest nur mit `@skipUnless(shutil.which("docker") and os.environ.get("NIO_KANBAN_TEST_DOCKER"))`:
  - `noop`-Lauf mit `python:3.12-slim`.
  - Prüfen, dass `docker inspect` während des Laufs den Secret-Wert nicht in `Config.Cmd` zeigt.

## Fertig, wenn
Die Abnahme ist grün und ein `grep -rn "shell=True" orchestrator/kanban` findet nichts.
