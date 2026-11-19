# OpenCode-Worker (ADR-001 Phase 3)

Gilt für `runtime: opencode` im SOUL-Frontmatter. Andere Runtimes ändern sich nicht.

## Bausteine

| Teil | Datei | Aufgabe |
|---|---|---|
| Aufruf | `orchestrator/kanban/worker_entry.py` (`_run_opencode`) | Startet `opencode run --format json --pure`, Zeitlimit, strukturierte Ausgabe |
| Konfiguration | `config/opencode/opencode.json` | Provider Ollama und freellmapi über den Relay, Berechtigungen, Vault-MCP |
| Image | `docker/opencode-worker/Dockerfile` | git, Node, `opencode-ai@1.19.6` per npm (Snap-Version läuft im Container nicht) |
| Relay | `docker/model-relay/` | Reicht nur Port 3001 (freellmapi) und 11434 (ollama) weiter |
| Sandbox | `orchestrator/kanban/sandbox.py` | Nur für OpenCode: internes Netz, kein Host-Gateway, Mounts nur lesend |

## Einrichtung

```bash
# Image (einmalig, ca. 1,9 GB)
docker build -t nio-opencode-worker:latest docker/opencode-worker

# Relay-Image
docker build -t nio-model-relay:latest docker/model-relay

# Internes Netz ohne Ausgang
docker network create --internal nio-opencode-model

# Relay: im Standard-Bridge-Netz starten, danach ins interne Netz hängen
docker run -d --name nio-model-relay --restart unless-stopped \
  --add-host host.docker.internal:host-gateway \
  -e NIO_RELAY_ROUTES="3001=host.docker.internal:3001,11434=host.docker.internal:11434" \
  nio-model-relay:latest
docker network connect --alias nio-model-relay nio-opencode-model nio-model-relay
```

Die lokale Konfiguration (`~/.config/nio/nio.env`, Rechte 600) braucht:

```
NIO_KANBAN_OPENCODE_IMAGE=nio-opencode-worker:latest
NIO_KANBAN_OPENCODE_NETWORK=nio-opencode-model
NIO_KANBAN_OPENCODE_TIMEOUT_S=600
NIO_KANBAN_DOCKER_NO_NEW_PRIVILEGES=0   # Snap-Docker: exec scheitert sonst auch ohne Setuid
FREELLMAPI_KEY=<Key, nie ins Repo>
NIO_KANBAN_SECRET_ALLOWLIST=FREELLMAPI_KEY
```

## Bekannte Lücke: Relay erreicht die Modelle nicht

Ollama (11434) und freellmapi (3001) hören nur auf `127.0.0.1`. Der Relay-Container erreicht sie
über das Gateway `172.17.0.1` nicht. Der Test zeigt `Ziel nicht erreichbar`. Die Isolation funktioniert,
die Weiterleitung zu den echten Diensten nicht. Zwei Wege:

1. Die Dienste auf `172.17.0.1` oder `0.0.0.0` binden (`OLLAMA_HOST`, Compose des freellmapi). Erfordert einen Neustart.
2. Einen kleinen Host-Forwarder auf `172.17.0.1:3001|11434` einrichten, der zu `127.0.0.1` weiterleitet. Dauerhafter Dienst, braucht Freigabe.

Bis dahin liefert der Worker keine Modellantwort. Der Netzschutz ist davon unabhängig geprüft.

## Berechtigungen (`config/opencode/opencode.json`)

- `edit`: `runtime/`, `.git/` und `.env*` gesperrt.
- `read`: `.env*` und `runtime/` gesperrt.
- `bash`: nur `git status|diff|log|add|commit`, `ls`, `python3 -m pytest|unittest`. `git push` und `git remote` sind ausdrücklich gesperrt.
- `webfetch`, `external_directory`, `doom_loop`: gesperrt.

## Testaufgabe (Abnahme)

Der Worker braucht ein Git-Repo im Arbeitsverzeichnis. Die Aufgabe ändert eine Datei und committet lokal:

1. Ein Repo mit Branch `worker/<uid>` in `runs/<run_id>/work/` anlegen (z. B. `git clone` des Projekts, dann `git checkout -b worker/<uid>`). Der Dispatcher legt das heute nicht selbst an.
2. Aufgabe im Kanban anlegen, z. B. „Datei `docs/test.txt` mit einer Zeile ergänzen und committen“.
3. Ergebnis prüfen: `result.json` enthält `status: completed`, `committed: true` und `head_before != head_after`.
4. Push-Versuch: `git push` ist per Berechtigung gesperrt. Im Protokoll taucht die Ablehnung auf, der Commit bleibt lokal.
5. Timeout: `NIO_KANBAN_OPENCODE_TIMEOUT_S=5` setzen, eine lange Aufgabe starten. Ergebnis: `reason: opencode_timeout`.

Der Schritt 1 wird heute nicht automatisch erledigt. Das ist ein offener Punkt.

## Verifiziert (2026-11-19)

- `pytest tests/test_kanban_*.py tests/test_llm_worker.py`: 97 bestanden, 8 übersprungen.
- `docker build docker/opencode-worker`: Exit 0, Image 1,92 GB. Im Container: git 2.47.3, opencode 1.19.6, Python 3.12.16, keine Setuid-Dateien.
- Im internen Netz: Relay → Dummy-Ziel HTTP 200. Internet und `host.docker.internal:8740` blockiert.
- Nicht verifiziert: echter Modelllauf mit Ollama oder freellmapi, Testaufgabe im Kanban-Lauf.
