#!/usr/bin/env bash
# Meldet jeden Dienst einzeln. Exit 1, sobald einer fehlt.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failed=0

report() {  # name ok|fehlt detail
  printf '%-16s %-6s %s\n' "$1" "$2" "${3:-}"
  [ "$2" = "ok" ] || failed=1
}

http() {  # name url  -- jede HTTP-Antwort zaehlt als erreichbar
  local code
  code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$2")"
  if [ "$code" != "000" ]; then report "$1" ok "HTTP $code"; else report "$1" fehlt "$2"; fi
}

unit() {
  if systemctl --user is-active -q "$1"; then report "$1" ok; else report "$1" fehlt "systemctl --user status $1"; fi
}

container() {
  local state
  state="$(docker inspect "$1" --format '{{.State.Status}}' 2>/dev/null)"
  if [ "$state" = "running" ]; then report "$1" ok; else report "$1" fehlt "${state:-nicht vorhanden}"; fi
}

unit nio-kanban
unit nio-apollo
http kanban-api http://127.0.0.1:8740/api/v1/kanban/boards
http apollo http://127.0.0.1:4001/apollo
http speaches http://127.0.0.1:8011/health
http freellmapi http://127.0.0.1:3001/
container sigma-redis

if [ -e "$ROOT/runtime/STOP" ]; then report not-aus fehlt "runtime/STOP ist gesetzt"; else report not-aus ok "nicht gesetzt"; fi

open="$(ss -ltnH | awk '{print $4}' | grep -E ':(4001|8740)$' | grep -v -E '^(127\.0\.0\.1|\[::1\]):' || true)"
if [ -z "$open" ]; then report bindung ok "nur Loopback"; else report bindung fehlt "$open"; fi

exit "$failed"
