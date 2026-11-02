#!/usr/bin/env bash

# Skript zum Einrichten des isolierten nio-agents Docker-Netzwerks.
# Es wird von agents und dem Orchestrator genutzt und verbindet FreeLLMAPI.

set -euo pipefail

NETWORK_NAME="nio-agents"
FREELLMAPI_CONTAINER="freellmapi-freellmapi-1"

# Pruefe, ob das Netzwerk bereits existiert
if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "Erstelle Docker-Netzwerk $NETWORK_NAME..."
    # Netzwerk erstellen (interne Kommunikation ohne direkten externen Zugang, ausser via Proxy,
    # aber wir belassen es standardmaessig als normales Bridge-Netz oder internal?
    # Vorgabe aus J6: "The container reaches only FreeLLMAPI" "durch einen kontrollierten Pfad".
    # Ein `internal` bridge network wuerde outbound traffic blockieren.
    # Openmanus_limb prueft `{{.Internal}} {{index .Options "com.docker.network.bridge.inhibit_ipv4"}}` -> `true true`
    # (Siehe openmanus_limb.py `_network_problem` check).
    docker network create \
        --internal \
        --opt com.docker.network.bridge.inhibit_ipv4=true \
        "$NETWORK_NAME"
else
    echo "Docker-Netzwerk $NETWORK_NAME existiert bereits."
fi

# FreeLLMAPI verbinden, falls der Container existiert und noch nicht verbunden ist.
if docker ps -a --format '{{.Names}}' | grep -Eq "^${FREELLMAPI_CONTAINER}\$"; then
    if ! docker network inspect "$NETWORK_NAME" | grep -q "\"Name\": \"${FREELLMAPI_CONTAINER}\""; then
        echo "Verbinde $FREELLMAPI_CONTAINER mit $NETWORK_NAME..."
        docker network connect "$NETWORK_NAME" "$FREELLMAPI_CONTAINER"
    else
        echo "$FREELLMAPI_CONTAINER ist bereits mit $NETWORK_NAME verbunden."
    fi
else
    echo "Warnung: Container $FREELLMAPI_CONTAINER nicht gefunden. FreeLLMAPI muss eventuell spaeter verbunden werden."
fi
