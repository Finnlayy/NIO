#!/usr/bin/env bash
# Richtet NIO aus diesem Checkout als Dauerdienst ein. Mehrfach ausfuehrbar:
# Vorhandene Geheimnisse bleiben stehen, Dienste starten mit dem neuen Stand neu.
# Mit --ohne-dienste bleibt systemd unberuehrt: Dann wird nur alles vorbereitet.
set -euo pipefail

SERVICES=1
[ "${1:-}" = "--ohne-dienste" ] && SERVICES=0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$HOME/.config/nio"
ENV_FILE="$CONFIG/kanban.env"
UNITS="$HOME/.config/systemd/user"
VAULT="${NIO_OBSIDIAN_VAULT:-$ROOT/workspace/obsidian}"

mkdir -p "$CONFIG" "$UNITS"
chmod 700 "$CONFIG"

echo "[1/6] Python-Umgebung"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -q "fastapi>=0.110" "uvicorn>=0.29" "pydantic>=2"

echo "[2/6] Apollo bauen (eigener Release-Ordner, der laufende Build bleibt unberuehrt)"
RELEASE="$(bash "$ROOT/deploy/release_apollo.sh" "$ROOT" "$CONFIG" | tail -n 1)"
echo "      Release $RELEASE"

echo "[3/6] Worker-Image und Agentennetz"
docker build -q -t nio-worker:1 "$ROOT/docker/kanban-worker"
bash "$ROOT/scripts/agents_network.sh"

echo "[4/6] Konfiguration"
bash "$ROOT/deploy/write_env.sh" "$ROOT" "$CONFIG" "$VAULT"

if [ "$SERVICES" = 1 ]; then
  echo "[5/6] Dienste"
  NPX="$(command -v npx)"
  for unit in nio-kanban nio-apollo; do
    sed -e "s|@ROOT@|$ROOT|g" -e "s|@NPX@|$NPX|g" "$ROOT/deploy/systemd/$unit.service" > "$UNITS/$unit.service"
  done
  systemctl --user daemon-reload
  systemctl --user enable -q nio-kanban nio-apollo
  systemctl --user restart nio-kanban
  systemctl --user restart nio-apollo

  # Rauchtest: antwortet Apollo nicht, geht es automatisch auf das vorige Release zurueck.
  apollo_up() {
    for _ in $(seq 1 30); do
      [[ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:4001/apollo)" =~ ^2[0-9][0-9]$ ]] && return 0
      sleep 1
    done
    return 1
  }
  if ! apollo_up; then
    echo "Apollo antwortet nicht mit Release $RELEASE -- Rollback" >&2
    if bash "$ROOT/deploy/release_apollo.sh" "$ROOT" "$CONFIG" --rollback; then
      systemctl --user restart nio-apollo
    fi
    exit 1
  fi
else
  echo "[5/6] Dienste uebersprungen"
fi

echo "[6/6] Protokoll-Worker"
set -a; . "$ENV_FILE"; set +a
cd "$ROOT"
if ! "$ROOT/.venv/bin/python" -m orchestrator kanban worker list | grep -q '^protokoll '; then
  "$ROOT/.venv/bin/python" -m orchestrator kanban worker create protokoll --soul-file deploy/workers/protokoll.soul.md
fi

echo "Fertig. Pruefen mit: make health"
