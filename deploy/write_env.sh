#!/usr/bin/env bash
# Schreibt die Dienst-Umgebungen getrennt nach Dienst:
#   kanban.env  -- Backend: Operator-Token, Freigabeschluessel, Sandbox, Pfade
#   apollo.env  -- UI: nur das eingeschraenkte Apollo-Token, die PIN und Pfade
# Mehrfach ausfuehrbar: vorhandene Geheimnisse bleiben stehen. Eine alte
# gemeinsame nio.env wird einmal uebernommen und danach beiseitegelegt.
#
# Aufruf: write_env.sh <repo-root> <config-dir> <vault-dir>
set -euo pipefail

ROOT="$1"
CONFIG="$2"
VAULT="$3"
KANBAN_ENV="$CONFIG/kanban.env"
APOLLO_ENV="$CONFIG/apollo.env"
LEGACY_ENV="$CONFIG/nio.env"

umask 077
mkdir -p "$CONFIG"
chmod 700 "$CONFIG"

secret() { python3 -c "import secrets; print(secrets.token_urlsafe(32))"; }
pin() { python3 -c "import secrets; print(''.join(secrets.choice('0123456789') for _ in range(8)))"; }

# get KEY FILE -> letzter Wert oder leer
get() { [ -f "$2" ] && sed -n "s/^$1=//p" "$2" | tail -n 1 || true; }

# put KEY VALUE FILE -> ersetzt die Zeile oder haengt sie an (Wert ohne sed-Quoting)
put() {
  python3 - "$1" "$2" "$3" <<'PY'
import sys
from pathlib import Path

key, value, path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out, done = [], False
for line in lines:
    if line.startswith(key + "="):
        if not done:
            out.append(f"{key}={value}")
            done = True
        continue
    out.append(line)
if not done:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

# drop KEY FILE -> entfernt die Zeile
drop() { [ -f "$2" ] && sed -i "/^$1=/d" "$2" || true; }

# --- kanban.env --------------------------------------------------------
if [ ! -e "$KANBAN_ENV" ]; then
  if [ -e "$LEGACY_ENV" ]; then
    cp "$LEGACY_ENV" "$KANBAN_ENV"
  else
    cp "$ROOT/deploy/kanban.env.example" "$KANBAN_ENV"
  fi
fi
chmod 600 "$KANBAN_ENV"

for key in NIO_KANBAN_API_TOKEN NIO_APPROVAL_KEY NIO_KANBAN_APOLLO_TOKEN; do
  [ -n "$(get "$key" "$KANBAN_ENV")" ] || put "$key" "$(secret)" "$KANBAN_ENV"
done
put NEU_ROOT "$ROOT" "$KANBAN_ENV"
put NIO_REPO_ROOT "$ROOT" "$KANBAN_ENV"
put NIO_PYTHON "$ROOT/.venv/bin/python" "$KANBAN_ENV"
[ -n "$(get NIO_OBSIDIAN_VAULT "$KANBAN_ENV")" ] || put NIO_OBSIDIAN_VAULT "$VAULT" "$KANBAN_ENV"

# Die PIN gehoert Apollo. Aus einer alten nio.env wird sie mitgenommen.
LEGACY_PIN="$(get NIO_APOLLO_APPROVAL_PIN "$KANBAN_ENV")"
drop NIO_APOLLO_APPROVAL_PIN "$KANBAN_ENV"

# --- apollo.env --------------------------------------------------------
[ -e "$APOLLO_ENV" ] || cp "$ROOT/deploy/apollo.env.example" "$APOLLO_ENV"
chmod 600 "$APOLLO_ENV"

put NIO_KANBAN_APOLLO_TOKEN "$(get NIO_KANBAN_APOLLO_TOKEN "$KANBAN_ENV")" "$APOLLO_ENV"
if [ -z "$(get NIO_APOLLO_APPROVAL_PIN "$APOLLO_ENV")" ]; then
  put NIO_APOLLO_APPROVAL_PIN "${LEGACY_PIN:-$(pin)}" "$APOLLO_ENV"
fi
put NIO_REPO_ROOT "$ROOT" "$APOLLO_ENV"
put NIO_PYTHON "$ROOT/.venv/bin/python" "$APOLLO_ENV"
put NIO_OBSIDIAN_VAULT "$(get NIO_OBSIDIAN_VAULT "$KANBAN_ENV")" "$APOLLO_ENV"
if [ -z "$(get FREELLMAPI_KEY "$APOLLO_ENV")" ] && [ -n "$(get FREELLMAPI_KEY "$KANBAN_ENV")" ]; then
  put FREELLMAPI_KEY "$(get FREELLMAPI_KEY "$KANBAN_ENV")" "$APOLLO_ENV"
fi

# Was Apollo nie haben darf, fliegt hart raus -- auch wenn es von Hand eingetragen wurde.
for key in NIO_KANBAN_API_TOKEN NIO_APPROVAL_KEY; do
  drop "$key" "$APOLLO_ENV"
done

# --- alte gemeinsame Datei ----------------------------------------------
if [ -e "$LEGACY_ENV" ]; then
  mv "$LEGACY_ENV" "$LEGACY_ENV.migriert"
  chmod 600 "$LEGACY_ENV.migriert"
  echo "Hinweis: $LEGACY_ENV wurde nach kanban.env/apollo.env aufgeteilt und liegt jetzt als nio.env.migriert daneben. Nach Pruefung loeschen."
fi
