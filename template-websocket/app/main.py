import logging
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.live import pool, run_bridge

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE = Path(__file__).parent
app = FastAPI(title="Gemini Malayalam Talkback")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "model": config.LIVE_MODEL,
            "voices": config.VOICES,
            "default_voice": config.DEFAULT_VOICE,
            "has_key": bool(pool.keys),
        },
    )


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, voice: str = config.DEFAULT_VOICE):
    await ws.accept()
    if voice not in config.VOICES:
        voice = config.DEFAULT_VOICE
    try:
        await run_bridge(ws, voice)
    except WebSocketDisconnect:
        log.info("Browser disconnected")
    except Exception as e:
        log.exception("Live session failed")
        try:
            await ws.send_json({"type": "error", "error": f"{type(e).__name__}: {e}"})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
