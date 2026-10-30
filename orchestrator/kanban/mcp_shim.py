import json
import os
import sys
import urllib.error
import urllib.request


def main() -> None:
    api_url = os.environ.get("NIO_KANBAN_API_URL")
    task_token = os.environ.get("NIO_KANBAN_TASK_TOKEN")

    if not api_url or not task_token:
        print("Missing NIO_KANBAN_API_URL or NIO_KANBAN_TASK_TOKEN", file=sys.stderr)
        sys.exit(1)

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        if "method" not in req:
            continue

        method = req["method"]
        msg_id = req.get("id")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "nio-kanban", "version": "1"}
                }
            }
            print(json.dumps(res), flush=True)

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            try:
                req_obj = urllib.request.Request(f"{api_url}/api/v1/kanban/tools")
                with urllib.request.urlopen(req_obj, timeout=30) as response:
                    tools_data = json.loads(response.read().decode("utf-8"))
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"tools": tools_data}
                    }
            except Exception as e:
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(e)}
                }
            print(json.dumps(res), flush=True)

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})

            body = json.dumps({"tool": name, "arguments": arguments}).encode("utf-8")
            req_obj = urllib.request.Request(
                f"{api_url}/api/v1/kanban/tools/{name}",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {task_token}"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req_obj, timeout=30) as response:
                    result_data = json.loads(response.read().decode("utf-8"))
                    content = [{"type": "text", "text": json.dumps(result_data)}]
                    is_error = False
            except urllib.error.HTTPError as e:
                try:
                    error_data = json.loads(e.read().decode("utf-8"))
                    text = json.dumps(error_data)
                except Exception:
                    text = str(e)
                content = [{"type": "text", "text": text}]
                is_error = True
            except Exception as e:
                content = [{"type": "text", "text": str(e)}]
                is_error = True

            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": content,
                    "isError": is_error
                }
            }
            print(json.dumps(res), flush=True)

if __name__ == "__main__":
    main()
