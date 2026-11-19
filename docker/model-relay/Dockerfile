# Relay zu den Modell-Endpunkten fuer den OpenCode-Worker (ADR-001 Phase 3).
# Haengt im internen Netz ``nio-opencode-model`` und im Standard-Bridge-Netz; siehe relay.py.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

WORKDIR /app
COPY relay.py /app/relay.py
RUN chmod 0555 /app/relay.py

USER 1000:1000

ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python3", "-I", "/app/relay.py"]
