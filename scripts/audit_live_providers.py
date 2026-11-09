#!/usr/bin/env python3
"""Secret-free audit of the running Apollo API.

GET reads measured metadata only. --probe explicitly requests one max-16-token
completion per configured provider. --transport performs credential-free HEAD
requests to registry defaults; reachability never counts as completion success.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def transport(url: str) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=3) as response:
            return {"reachable": True, "httpStatus": response.status, "authenticated": False}
    except urllib.error.HTTPError as error:
        return {"reachable": True, "httpStatus": error.code, "authenticated": False}
    except (OSError, urllib.error.URLError):
        return {"reachable": False, "error": "network_or_tls_unreachable", "authenticated": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4001")
    parser.add_argument("--probe", action="store_true", help="May incur minimal provider charges")
    parser.add_argument("--transport", action="store_true", help="Unauthenticated HEAD to fixed registry endpoints")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    request = urllib.request.Request(args.base_url.rstrip("/") + "/api/apollo/providers", method="POST" if args.probe else "GET")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        data = json.load(error)
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "error": "apollo_api_unreachable_or_invalid"}))
        return 1
    # Allowlist fields even if a future server inadvertently returns extra data.
    fields = ("id", "name", "configured", "model", "status", "checkedAt", "latencyMs", "httpStatus")
    providers = [{key: p[key] for key in fields if key in p} for p in data.get("providers", [])]
    report: dict[str, Any] = {"at": datetime.now(UTC).isoformat(), "liveProbeRequested": args.probe,
                              "configuredProviders": sum(bool(p.get("configured")) for p in providers),
                              "readyProviders": sum(p.get("status") == "ready" for p in providers), "providers": providers}
    if data.get("error"):
        report["error"] = "server_secret_store_error"
    if args.transport:
        catalog = json.loads((Path(__file__).resolve().parents[1] / "orchestrator/provider_catalog.json").read_text())
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: transport(p["endpoint"]), catalog))
        report["unauthenticatedTransportToRegistryDefaults"] = {p["id"]: result for p, result in zip(catalog, results, strict=True)}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["readyProviders"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
