#!/usr/bin/env bash
# Baut Apollo in einen eigenen Release-Ordner und schaltet erst danach um.
#
#   release_apollo.sh <repo-root> <config-dir>            neues Release bauen und aktivieren
#   release_apollo.sh <repo-root> <config-dir> --rollback auf das vorige Release zurueck
#
# Der laufende Dienst liest seinen Build aus frontend/.releases/<id>. Ein neuer
# Build schreibt nie in diesen Ordner. Aktiviert wird, indem
# <config-dir>/apollo.release atomar ersetzt wird (mv); nio-apollo.service liest
# die Datei beim naechsten (Neu-)Start. Das vorige Release bleibt fuer den
# Rollback stehen, aeltere werden bis auf KEEP Stueck geloescht.
set -euo pipefail

ROOT="$1"
CONFIG="$2"
MODE="${3:-}"
NPM="${NPM:-npm}"
KEEP="${NIO_RELEASES_KEEP:-3}"

FRONTEND="$ROOT/frontend"
RELEASES="$FRONTEND/.releases"
POINTER="$CONFIG/apollo.release"
PREVIOUS="$CONFIG/apollo.release.previous"

mkdir -p "$RELEASES" "$CONFIG"

release_of() {  # Datei -> Release-ID oder leer
  [ -f "$1" ] && sed -n 's|^NIO_NEXT_DIST_DIR=\.releases/||p' "$1" | tail -n 1 || true
}

valid() {  # ID -> fertiger Build vorhanden?
  [ -n "$1" ] && [ -s "$RELEASES/$1/BUILD_ID" ]
}

activate() {  # ID -> Zeiger atomar setzen, alten Zeiger als "previous" behalten
  local id="$1" current
  current="$(release_of "$POINTER")"
  if [ -n "$current" ] && [ "$current" != "$id" ]; then
    printf 'NIO_NEXT_DIST_DIR=.releases/%s\n' "$current" > "$PREVIOUS.tmp"
    mv -f "$PREVIOUS.tmp" "$PREVIOUS"
  fi
  printf 'NIO_NEXT_DIST_DIR=.releases/%s\n' "$id" > "$POINTER.tmp"
  mv -f "$POINTER.tmp" "$POINTER"
}

if [ "$MODE" = "--rollback" ]; then
  target="$(release_of "$PREVIOUS")"
  if ! valid "$target"; then
    echo "rollback: kein vorhergehendes Release mit fertigem Build" >&2
    exit 1
  fi
  activate "$target"
  echo "$target"
  exit 0
fi

sha="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)"
id="$(date -u +%Y%m%dT%H%M%S%N | cut -c1-18)-$sha"
staging="$RELEASES/$id"

cleanup() { [ -n "${staging:-}" ] && rm -rf "$staging"; }
trap cleanup ERR INT TERM

# Abhaengigkeiten nur neu installieren, wenn sich das Lockfile geaendert hat.
lock_hash="$(sha256sum "$FRONTEND/package-lock.json" | cut -d' ' -f1)"
if [ ! -d "$FRONTEND/node_modules" ] || [ "$(cat "$RELEASES/.lock.sha256" 2>/dev/null)" != "$lock_hash" ]; then
  "$NPM" --prefix "$FRONTEND" ci --silent
  echo "$lock_hash" > "$RELEASES/.lock.sha256"
fi

NIO_NEXT_DIST_DIR=".releases/$id" "$NPM" --prefix "$FRONTEND" run build --silent

# Rauchtest: ohne BUILD_ID ist der Build unvollstaendig und wird nie aktiv.
if ! valid "$id"; then
  echo "release: Build $id unvollstaendig (BUILD_ID fehlt)" >&2
  cleanup
  exit 1
fi
trap - ERR INT TERM

activate "$id"

# Aufraeumen: aktive und vorige Version bleiben immer, sonst die neuesten KEEP.
active="$(release_of "$POINTER")"
previous="$(release_of "$PREVIOUS")"
mapfile -t all < <(find "$RELEASES" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
kept=0
for dir in "${all[@]}"; do
  if [ "$dir" = "$active" ] || [ "$dir" = "$previous" ]; then continue; fi
  kept=$((kept + 1))
  if [ "$kept" -gt $((KEEP - 2)) ]; then rm -rf "${RELEASES:?}/$dir"; fi
done

echo "$id"
