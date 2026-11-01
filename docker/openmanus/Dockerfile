# OpenManus fuer NIO: fester Upstream-Stand, gesperrte Abhaengigkeiten, kein Root.
# Der Container selbst ist die Sandbox, siehe docs/OPENMANUS.md.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

ARG OPENMANUS_COMMIT=3309bf4e416fb1c74b008f3e86494439a31bad53

WORKDIR /app/OpenManus

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && git init -q . \
    && git fetch -q --depth 1 https://github.com/FoundationAgents/OpenManus.git "$OPENMANUS_COMMIT" \
    && git checkout -q FETCH_HEAD \
    && rm -rf .git \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --root-user-action=ignore --require-hashes -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

# Im Lauf gibt es kein Internet, der Tokenizer muss schon im Image liegen.
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

COPY runner.py /opt/nio/runner.py

# Snap-Docker vertraegt no-new-privileges nicht, deshalb gibt es gar kein Setuid.
RUN find / -xdev -type f -perm /6000 -exec chmod a-s {} +

ENV OPENMANUS_DISABLE_BROWSER_USE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

USER 10001:10001
ENTRYPOINT ["python", "/opt/nio/runner.py"]
