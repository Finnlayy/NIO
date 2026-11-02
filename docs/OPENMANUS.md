# OpenManus

NIO nutzt das lokale OpenManus, keinen gehosteten Dienst. OpenManus führt beliebigen Code aus, deshalb läuft es nur im Container, und der Container ist die Sandbox. `use_sandbox` bleibt aus, verschachteltes Docker hieße `docker.sock` mounten.

**Gesperrt:** Der Limb steht auf `planned`. Das ändert sich erst, wenn Container, Netz (Harness 2.8, 2.9) und die Tickets aus J4 gemergt sind.

## Einrichten

Quelle ist der Upstream-Commit `3309bf4`, die Abhängigkeiten stehen mit Hashes in `docker/openmanus/requirements.lock`. Browser, Websuche, Torch und GPU-Pakete sind nicht im Image, es belegt rund 310 MB.

```bash
docker build -t nio-openmanus:3309bf4 docker/openmanus
```

```bash
docker network create --internal --subnet 172.30.77.0/24 --opt com.docker.network.bridge.inhibit_ipv4=true nio-agents
```

`inhibit_ipv4` ist Pflicht. Ohne die Option behält der Host eine Adresse in diesem Netz, und jeder Dienst auf `0.0.0.0` bleibt erreichbar. Beim Testen waren das Apollo und die Orchestrator-API. Der Limb startet nur, wenn beide Eigenschaften gesetzt sind.

Für echte Läufe braucht der Limb den Modell-Zugang:

```bash
docker network connect nio-agents freellmapi-freellmapi-1
```

| Variable | Bedeutung |
|---|---|
| `FREELLMAPI_KEY` | Key des lokalen Gateways, nie ein Provider-Key |
| `OPENMANUS_MODEL` | Modell-ID im Gateway |
| `OPENMANUS_LLM_URL` | Optional, Standard `http://freellmapi-freellmapi-1:3001/v1` |

## Abschottung

| Grenze | Wert |
|---|---|
| Benutzer | Nicht-Root, keine Capabilities, keine Setuid-Dateien |
| Dateisystem | `--read-only`, nur Arbeitsordner und Konfiguration des Laufs gemountet |
| Limits | 2 CPUs, 3 GB RAM, 256 Prozesse |
| Netz | Nur `nio-agents`, kein Internet, kein Host, kein LAN |
| Laufzeit | Standard 30 Minuten, höchstens 2 Stunden |

`no-new-privileges` fehlt, weil Snap-Docker damit schon `exec` abbricht. Die Laufzeitgrenze sitzt im Runner im Container und greift auch, wenn niemand `openmanus.status` abfragt. Der Key liegt nur während des Laufs in `config.toml`.

## Ablauf

1. `openmanus.start` legt `runtime/agents/<run_id>/job/` an und startet den Container.
2. `docker/openmanus/runner.py` ruft Manus auf und schreibt `workspace/out/result.json`.
3. `openmanus.status` meldet das Ende und entfernt Container und Konfiguration.
4. `openmanus.collect` liefert Zusammenfassung und Dateiliste. Die Dateien bleiben im Arbeitsordner.

Erfolg zählt nur mit `terminate` und Status `success`. Alles andere ist `failed`.

## Noch nicht drin

- Kein Webzugriff, der Egress-Proxy aus Harness 2.9 fehlt.
- Kein Browser. `OPENMANUS_DISABLE_BROWSER_USE=1` verhindert das ungepinnte `uvx browser-use`.
- Keine Token-Grenze, nur Laufzeit und Schritte.
- Laufordner werden nicht automatisch gelöscht.
