#!/usr/bin/env bash
# Richtet NIO aus diesem Checkout als Dauerdienst ein. Mehrfach ausfuehrbar:
# Vorhandene Geheimnisse bleiben stehen, Dienste starten mit dem neuen Stand neu.
# Mit --ohne-dienste bleibt systemd unberuehrt: Dann wird nur alles vorbereitet.
set -euo pipefail

SERVICES=1
[ "${1:-}" = "--ohne-dienste" ] && SERVICES=0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$HOME/.config/nio"
ENV_FILE="$CONFIG/nio.env"
UNITS="$HOME/.config/systemd/user"
VAULT="${NIO_OBSIDIAN_VAULT:-$ROOT/workspace/obsidian}"

secret() { python3 -c "import secrets; print(secrets.token_urlsafe(32))"; }
pin() { python3 -c "import secrets; print(''.join(secrets.choice('0123456789') for _ in range(8)))"; }

mkdir -p "$CONFIG" "$UNITS"
chmod 700 "$CONFIG"

echo "[1/6] Python-Umgebung"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -q "fastapi>=0.110" "uvicorn>=0.29" "pydantic>=2"

echo "[2/6] Apollo bauen"
npm --prefix "$ROOT/frontend" ci --silent
npm --prefix "$ROOT/frontend" run build --silent

echo "[3/6] Worker-Image und Agentennetz"
docker build -q -t nio-worker:1 "$ROOT/docker/kanban-worker"
bash "$ROOT/scripts/agents_network.sh"

echo "[4/6] Konfiguration"
if [ ! -e "$ENV_FILE" ]; then
  (
    umask 077
    sed -e "s|^NIO_KANBAN_API_TOKEN=.*|NIO_KANBAN_API_TOKEN=$(secret)|" \
        -e "s|^NIO_APPROVAL_KEY=.*|NIO_APPROVAL_KEY=$(secret)|" \
        -e "s|^NIO_APOLLO_APPROVAL_PIN=.*|NIO_APOLLO_APPROVAL_PIN=$(pin)|" \
        -e "s|^NEU_ROOT=.*|NEU_ROOT=$ROOT|" \
        -e "s|^NIO_REPO_ROOT=.*|NIO_REPO_ROOT=$ROOT|" \
        -e "s|^NIO_PYTHON=.*|NIO_PYTHON=$ROOT/.venv/bin/python|" \
        -e "s|^NIO_OBSIDIAN_VAULT=.*|NIO_OBSIDIAN_VAULT=$VAULT|" \
        "$ROOT/deploy/env.example" > "$ENV_FILE"
  )
else
  sed -i -e "s|^NEU_ROOT=.*|NEU_ROOT=$ROOT|" \
         -e "s|^NIO_REPO_ROOT=.*|NIO_REPO_ROOT=$ROOT|" \
         -e "s|^NIO_PYTHON=.*|NIO_PYTHON=$ROOT/.venv/bin/python|" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

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
