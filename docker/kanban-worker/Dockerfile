# Worker-Image fuer die Kanban-Sandbox: Python ohne Setuid-Dateien.
# Snap-Docker vertraegt no-new-privileges nicht, deshalb gibt es gar kein Setuid.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

RUN find / -xdev -type f -perm /6000 -exec chmod a-s {} +

ENV PYTHONDONTWRITEBYTECODE=1
