"""World-Bridge Core (T6): FastAPI loopback :8750, WS /ws/world Multiplex live+shadow,
Snapshot-Resume (seq), Batch <=15Hz, Auth Bearer NIO_WORLD_TOKEN (fail-closed),
Static-Serve, POST /api/world/command -> Router (D3)."""
from __future__ import annotations
import asyncio
import time
from typing import Any, AsyncIterator
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from .adapters import WorldAdapter
from .state import StateStore
from .batch import WorldBatcher
from .router import CommandRouter, CommandError
from .mcp_tools import MCPToolServer
from .events import CityEvent


class Bridge:
    def __init__(self, adapters: dict[str, WorldAdapter], token: str = "",
                 static_dir: str | None = None, poll_s: float = 1.0 / 15.0,
                 store: StateStore | None = None) -> None:
        self.adapters = adapters
        self.store = store or StateStore()
        self.batchers = {w: WorldBatcher() for w in adapters}
        self.router = CommandRouter(adapters, {w: {a.repo_path} for w, a in adapters.items()}, self.store)
        self.token = token
        self.static_dir = static_dir
        self.poll_s = poll_s
        self.mcp = MCPToolServer(self.store, on_event=self._on_mcp_event)

    def _on_mcp_event(self, ev: CityEvent) -> None:
        self.batchers[ev.world_id].add(ev)

    async def _snapshot_event(self, world_id: str) -> CityEvent:
        snap = await self.adapters[world_id].snapshot()
        st = self.store.get(world_id)
        ev = CityEvent("world_snapshot", world_id, snap, st.seq.next())
        st.apply(ev)
        return ev

    async def stream(self, worlds: list[str], last_event_id: int = 0,
                     iterations: int | None = None) -> AsyncIterator[dict]:
        for w in worlds:
            ev = await self._snapshot_event(w)
            if ev.seq > last_event_id:
                yield ev.to_dict()
        n = 0
        while iterations is None or n < iterations:
            n += 1
            now = time.time() * 1000
            for w in worlds:
                for ev in await self.adapters[w].poll_events():
                    self.store.get(w).apply(ev)
                    self.batchers[w].add(ev)
                for ev in self.batchers[w].drain(now):
                    if ev.seq > last_event_id:
                        yield ev.to_dict()
            if iterations is None:
                await asyncio.sleep(self.poll_s)

    def create_app(self) -> FastAPI:
        app = FastAPI(title="NIO World-Bridge", version="1.0")
        bearer = HTTPBearer(auto_error=False)

        def auth(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
            if not self.token:
                raise HTTPException(503, "NIO_WORLD_TOKEN nicht gesetzt — fail-closed")
            if cred is None or cred.credentials != self.token:
                raise HTTPException(401, "ungueltiges Token")
            return cred.credentials

        @app.get("/health")
        async def health() -> dict:
            return {"ok": True, "worlds": list(self.adapters), "token_set": bool(self.token)}

        @app.post("/api/world/command")
        async def command(body: dict, actor: str = Depends(auth)) -> dict:
            try:
                return await self.router.handle(body)
            except CommandError as e:
                raise HTTPException(e.status, str(e))

        @app.post("/mcp")
        async def mcp(req: dict, actor: str = Depends(auth)) -> dict:
            return self.mcp.handle(req)

        @app.websocket("/ws/world")
        async def ws_world(ws: WebSocket) -> None:
            token = ws.query_params.get("token") or (ws.headers.get("authorization", "").removeprefix("Bearer ").strip())
            if not self.token or token != self.token:
                await ws.close(code=4401)
                return
            await ws.accept()
            wparam = ws.query_params.get("world_id", "both")
            worlds = list(self.adapters) if wparam == "both" else [wparam]
            worlds = [w for w in worlds if w in self.adapters]
            try:
                last = int(ws.query_params.get("last_event_id", "0"))
            except ValueError:
                last = 0
            try:
                async for msg in self.stream(worlds, last_event_id=last):
                    await ws.send_json(msg)
            except WebSocketDisconnect:
                return

        if self.static_dir and os.path.isdir(self.static_dir):
            from fastapi.staticfiles import StaticFiles
            app.mount("/", StaticFiles(directory=self.static_dir, html=True), name="static")
        else:
            @app.get("/")
            async def index() -> dict:
                return {"service": "nio-world-bridge", "static": "kein Build vorhanden (P3)", "ws": "/ws/world"}
        return app


import os  # noqa: E402  (fuer static_dir check)


def build_bridge_from_env(adapters: dict[str, WorldAdapter]) -> Bridge:
    return Bridge(adapters, token=os.environ.get("NIO_WORLD_TOKEN", ""),
                  static_dir=os.environ.get("NIO_WORLD_STATIC_DIR"))
