FROM python:3.12-slim

WORKDIR /app
COPY proxy.py /app/proxy.py
RUN chmod +x /app/proxy.py

USER 1000:1000

ENTRYPOINT ["python3", "/app/proxy.py"]
