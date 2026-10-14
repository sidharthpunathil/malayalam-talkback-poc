"""Request/response pipeline: understand (audio or text) with a Flash model, then speak with TTS."""

import base64
import logging
import io
import time
import wave

from google.genai import types
from pydantic import BaseModel

from app import config
from app.keypool import AllKeysBusy, KeyPool

log = logging.getLogger(__name__)

pool = KeyPool.from_env()


class HistoryTurn(BaseModel):
    role: str  # "user" or "model"
    text: str


class Understood(BaseModel):
    transcript: str
    reply: str


def _history_contents(history: list[HistoryTurn]) -> list[types.Content]:
    return [
        types.Content(role="model" if t.role == "model" else "user", parts=[types.Part(text=t.text)])
        for t in history[-20:]
        if t.text.strip()
    ]


async def understand_audio(audio: bytes, mime_type: str, history: list[HistoryTurn]) -> Understood:
    contents = _history_contents(history) + [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=audio, mime_type=mime_type),
                types.Part(text="Transcribe exactly what I said in this audio, then reply to it."),
            ],
        )
    ]
    resp = await pool.generate_content(
        model=config.TEXT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=config.SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=Understood,
        ),
    )
    if not isinstance(resp.parsed, Understood):
        raise RuntimeError(f"Unexpected model output: {resp.text!r}")
    return resp.parsed


async def reply_to_text(text: str, history: list[HistoryTurn]) -> str:
    contents = _history_contents(history) + [types.Content(role="user", parts=[types.Part(text=text)])]
    resp = await pool.generate_content(
        model=config.TEXT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=config.SYSTEM_INSTRUCTION),
    )
    return (resp.text or "").strip()


async def speak(text: str, voice: str) -> bytes:
    """Return a WAV file of `text` spoken in Malayalam, rotating keys, then falling back to other TTS models."""
    models = [config.TTS_MODEL, *config.TTS_FALLBACK_MODELS]
    for i, model in enumerate(models):
        try:
            return await _speak(model, text, voice)
        except AllKeysBusy:
            if i == len(models) - 1:
                raise
            log.warning("TTS model %s busy on every key, trying %s", model, models[i + 1])
    raise AssertionError("unreachable")


async def _speak(model: str, text: str, voice: str) -> bytes:
    resp = await pool.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    data = resp.candidates[0].content.parts[0].inline_data.data
    if data[:4] == b"RIFF":
        return data
    # Raw 24 kHz PCM: wrap it in a WAV header.
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(data)
    return buf.getvalue()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class Timer:
    def __init__(self) -> None:
        self.marks: dict[str, int] = {}
        self._t = time.perf_counter()

    def mark(self, name: str) -> None:
        now = time.perf_counter()
        self.marks[name] = round((now - self._t) * 1000)
        self._t = now
