import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from app import config
from app.live import pool, run_bridge

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Gemini Malayalam Talkback (WebSocket API)")


@app.get("/api/health")
async def health():
    return {"ok": pool.status()["disabled"] < len(pool.keys), "model": config.LIVE_MODEL, "keys": pool.status()}


@app.get("/api/voices")
async def voices():
    return {"voices": config.VOICES, "default": config.DEFAULT_VOICE}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, voice: str = config.DEFAULT_VOICE):
    """Protocol: client sends 16 kHz PCM binary frames and JSON {type: "text"|"audio_end"};
    server sends 24 kHz PCM binary frames and JSON {type: ready|user|gemini|interrupted|turn_complete|error}."""
    await ws.accept()
    if voice not in config.VOICES:
        voice = config.DEFAULT_VOICE
    try:
        await run_bridge(ws, voice)
    except WebSocketDisconnect:
        log.info("Client disconnected")
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


# Serve the built React client (web/dist) when present.
_dist = Path(__file__).parent.parent / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8003, reload=True)
