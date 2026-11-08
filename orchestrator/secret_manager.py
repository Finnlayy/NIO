"""Server-only environment / owner-only JSON mount adapter. Never an encrypted vault.

Shared contract with frontend/src/server/secretManager.ts. No secret values in
exceptions, reprs, logs or argv. Credentials cross the sandbox boundary only
through the explicit Kanban allowlist and only for the selected LLM provider.
"""
from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.parse import urlsplit


def secret_environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ if env is None else env)
    mounted: dict[str, str] = {}
    if source.get("NIO_SECRET_FILE"):
        try:
            fd = os.open(source["NIO_SECRET_FILE"], os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "r", encoding="utf-8") as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 65_536 or info.st_mode & 0o077 or info.st_uid != os.getuid():
                    raise ValueError
                data = json.load(file)
                if not isinstance(data, dict) or any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", k) or not isinstance(v, str) for k, v in data.items()):
                    raise ValueError
                mounted = data
        except (OSError, ValueError, TypeError):
            raise ValueError("secret_store_unavailable_or_invalid") from None
    return {**mounted, **source}


def llm_worker_environment(allowlist: Sequence[str], *, provider_id: str = "", env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = secret_environment(env)
    catalog = json.loads(Path(__file__).with_name("provider_catalog.json").read_text())
    selected = provider_id or source.get("NIO_LLM_PROVIDER", "")
    provider = next((p for p in catalog if p["id"] == selected), None) if selected else next(
        (p for p in catalog if any(source.get(n, "").strip() for n in [p["secret"], *p.get("aliases", [])])), None)
    if not provider:
        return {"NIO_LLM_ERROR": "no_provider_configured"}
    names = [provider["secret"], *provider.get("aliases", [])]
    present = next((n for n in names if source.get(n, "").strip()), None)
    if not present:
        return {"NIO_LLM_ERROR": "missing_secret"}
    if present not in allowlist:
        return {"NIO_LLM_ERROR": "provider_secret_not_allowlisted"}
    endpoint = provider["endpoint"]
    if provider["id"] == "freellm" and source.get("FREELLMAPI_HOST"):
        host = source["FREELLMAPI_HOST"].strip()
        parsed = urlsplit("http://" + host)
        if parsed.netloc != host or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            return {"NIO_LLM_ERROR": "invalid_gateway_host"}
        scheme = "http" if parsed.hostname in ("localhost", "127.0.0.1", "::1") else "https"
        endpoint = f"{scheme}://{host}/v1/chat/completions"
    model = source.get(provider["modelEnv"], "").strip() or (source.get("APOLLO_MODEL", "").strip() if selected == source.get("NIO_LLM_PROVIDER") else "") or provider["model"]
    if not model:
        return {"NIO_LLM_ERROR": "model_missing"}
    return {"NIO_LLM_PROVIDER": provider["id"], "NIO_LLM_ENDPOINT": endpoint, "NIO_LLM_MODEL": model,
            "NIO_LLM_PROTOCOL": provider["protocol"], "NIO_LLM_API_KEY": source[present].strip()}
