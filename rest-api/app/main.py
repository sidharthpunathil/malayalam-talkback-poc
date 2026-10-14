import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app import config
from app.gemini import HistoryTurn, Timer, b64, pool, reply_to_text, speak, understand_audio
from app.keypool import AllKeysBusy

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Gemini Malayalam Talkback (REST)")

_history_adapter = TypeAdapter(list[HistoryTurn])


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = []
    voice: str = config.DEFAULT_VOICE


class TalkResponse(BaseModel):
    transcript: str
    reply: str
    audio_wav_base64: str
    timings_ms: dict[str, int]


def _gemini_error(e: Exception) -> HTTPException:
    if isinstance(e, AllKeysBusy):
        return HTTPException(
            429,
            f"All Gemini keys are rate limited right now. Try again in {e.retry_after}s.",
            headers={"Retry-After": str(e.retry_after)},
        )
    log.exception("Gemini call failed")
    return HTTPException(502, f"Gemini error: {e}")


def _voice(voice: str) -> str:
    return voice if voice in config.VOICES else config.DEFAULT_VOICE


@app.get("/api/health")
async def health():
    return {
        "ok": pool.status()["disabled"] < len(pool.keys),
        "keys": pool.status(),
        "text_model": config.TEXT_MODEL,
        "tts_model": config.TTS_MODEL,
    }


@app.get("/api/voices")
async def voices():
    return {"voices": config.VOICES, "default": config.DEFAULT_VOICE}


@app.post("/api/talk", response_model=TalkResponse)
async def talk(
    audio: UploadFile = File(...),
    history: str = Form("[]"),
    voice: str = Form(config.DEFAULT_VOICE),
):
    """Malayalam speech in, Malayalam transcript + reply + spoken reply (WAV) out."""
    mime = (audio.content_type or "").split(";")[0]
    if mime not in config.AUDIO_TYPES:
        raise HTTPException(415, f"Unsupported audio type {mime!r}")
    data = await audio.read(config.MAX_AUDIO_BYTES + 1)
    if len(data) > config.MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too large (max 10 MB)")
    if len(data) < 1000:
        raise HTTPException(400, "Audio is empty or too short")
    try:
        turns = _history_adapter.validate_python(json.loads(history))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(422, f"Invalid history: {e}") from e

    timer = Timer()
    try:
        understood = await understand_audio(data, "audio/mp3" if mime == "audio/mpeg" else mime, turns)
        timer.mark("understand")
        wav = await speak(understood.reply, _voice(voice))
        timer.mark("tts")
    except Exception as e:
        raise _gemini_error(e) from e
    return TalkResponse(
        transcript=understood.transcript,
        reply=understood.reply,
        audio_wav_base64=b64(wav),
        timings_ms=timer.marks,
    )


@app.post("/api/chat", response_model=TalkResponse)
async def chat(req: ChatRequest):
    """Typed text in (any language), Malayalam reply + spoken reply out."""
    timer = Timer()
    try:
        reply = await reply_to_text(req.text, req.history)
        timer.mark("reply")
        wav = await speak(reply, _voice(req.voice))
        timer.mark("tts")
    except Exception as e:
        raise _gemini_error(e) from e
    return TalkResponse(transcript=req.text, reply=reply, audio_wav_base64=b64(wav), timings_ms=timer.marks)


# Serve the built React client (web/dist) when present.
_dist = Path(__file__).parent.parent / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
