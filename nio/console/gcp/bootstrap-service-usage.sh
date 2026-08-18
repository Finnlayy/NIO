#!/usr/bin/env bash
# Grants or revokes the temporary API-bootstrap role for a deployment principal.
# This script must be run by a project IAM administrator, not by the application.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-}"
BOOTSTRAP_PRINCIPAL="${BOOTSTRAP_PRINCIPAL:-}"
ACTION="${1:-grant}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPIRY_FILE="$SCRIPT_DIR/.bootstrap-role-expiry"
if date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:%SZ' >/dev/null 2>&1; then
  DEFAULT_EXPIRY="$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:%SZ')"
else
  DEFAULT_EXPIRY="$(date -u -v+2H '+%Y-%m-%dT%H:%M:%SZ')"
fi
EXPIRY="${BOOTSTRAP_ROLE_EXPIRY:-$DEFAULT_EXPIRY}"
ROLE="roles/serviceusage.serviceUsageAdmin"
CONDITION_TITLE="nexus-api-bootstrap"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

[[ -n "$PROJECT_ID" ]] || fail "PROJECT_ID is required."
[[ -n "$BOOTSTRAP_PRINCIPAL" ]] || fail "BOOTSTRAP_PRINCIPAL is required, for example user:admin@example.com or serviceAccount:terraform-bootstrap@PROJECT_ID.iam.gserviceaccount.com."

case "$BOOTSTRAP_PRINCIPAL" in
  *nexus-console-run-sa*|*nexus-console-build-sa*|*nexus-console-vertex-sa*|*atlas-orchestrator*|*aegis-security*)
    fail "Refusing to grant Service Usage Admin to an application, build, or agent runtime identity. Use a dedicated bootstrap principal."
    ;;
esac

case "$ACTION" in
  grant)
    printf '%s' "$EXPIRY" > "$EXPIRY_FILE"
    echo "Granting $ROLE to $BOOTSTRAP_PRINCIPAL until $EXPIRY ..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="$BOOTSTRAP_PRINCIPAL" \
      --role="$ROLE" \
      --condition="expression=request.time < timestamp('$EXPIRY'),title=$CONDITION_TITLE,description=Temporary API enablement for Nexus infrastructure bootstrap" \
      --quiet
    echo "Temporary bootstrap grant created. Run the infrastructure deployment before $EXPIRY."
    ;;
  revoke)
    if [[ -z "${BOOTSTRAP_ROLE_EXPIRY:-}" && -f "$EXPIRY_FILE" ]]; then
      EXPIRY="$(cat "$EXPIRY_FILE")"
    fi
    echo "Removing temporary $ROLE binding from $BOOTSTRAP_PRINCIPAL ..."
    gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
      --member="$BOOTSTRAP_PRINCIPAL" \
      --role="$ROLE" \
      --condition="expression=request.time < timestamp('$EXPIRY'),title=$CONDITION_TITLE,description=Temporary API enablement for Nexus infrastructure bootstrap" \
      --quiet
    rm -f "$EXPIRY_FILE"
    echo "Bootstrap grant removed."
    ;;
  *)
    fail "Unknown action '$ACTION'. Use 'grant' or 'revoke'."
    ;;
esac
