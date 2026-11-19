# Worker-Image fuer den OpenCode-Runtime (ADR-001 Phase 3).
# Basis wie docker/kanban-worker. OpenCode kommt per npm in fester Version, nicht als Snap:
# die Snap-Version des Hosts laeuft im Container nicht.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs npm ca-certificates \
    && npm install -g opencode-ai@1.19.6 \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/* /root/.npm \
    && opencode --version

# Snap-Docker vertraegt no-new-privileges nicht, deshalb kein Setuid-Bit im Image.
RUN find / -xdev -type f -perm /6000 -exec chmod a-s {} +

ENV PYTHONDONTWRITEBYTECODE=1
