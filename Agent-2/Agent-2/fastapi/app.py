import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import core
from routes import router as api_router


app = FastAPI(title="Travel Agent API", version="0.3.0")
app.mount("/static", StaticFiles(directory=str(core.STATIC_DIR)), name="static")
app.include_router(api_router)


@app.get("/")
def root():
    return FileResponse(str(core.STATIC_DIR / "index.html"))


@app.on_event("startup")
def on_startup() -> None:
    core.init_db()


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": str(exc),
            "model": core.TEXT_MODEL,
        },
    )


@app.websocket("/api/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    """
    Compatibility websocket for frontends that expect a log stream.

    The travel app does not currently produce websocket logs, but some
    browser sessions still connect to this endpoint. Accept the connection
    and keep it alive with simple ping/pong messages so those clients do not
    fail with a 403 handshake error.
    """

    await websocket.accept()
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        return
