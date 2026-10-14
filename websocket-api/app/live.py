"""Bridge between a browser WebSocket and a Gemini Live session."""

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app import config
from app.keypool import KeyPool

log = logging.getLogger(__name__)

pool = KeyPool.from_env()


def live_config(voice: str) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=config.SYSTEM_INSTRUCTION,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


async def browser_to_gemini(ws: WebSocket, session) -> None:
    """Binary frames are 16 kHz PCM mic audio; text frames are JSON control/text messages."""
    while True:
        msg = await ws.receive()
        if msg["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(msg.get("code", 1000))
        if msg.get("bytes"):
            await session.send_realtime_input(
                audio=types.Blob(data=msg["bytes"], mime_type="audio/pcm;rate=16000")
            )
        elif msg.get("text"):
            payload = json.loads(msg["text"])
            if payload.get("type") == "text" and payload.get("text", "").strip():
                await session.send_realtime_input(text=payload["text"])
            elif payload.get("type") == "audio_end":
                await session.send_realtime_input(audio_stream_end=True)


async def gemini_to_browser(ws: WebSocket, session) -> None:
    """Forward 24 kHz PCM audio as binary frames and transcripts/events as JSON."""
    while True:
        # receive() yields one model turn, then ends; loop to keep listening.
        async for response in session.receive():
            sc = response.server_content
            if not sc:
                continue
            if sc.model_turn:
                for part in sc.model_turn.parts or []:
                    if part.inline_data and part.inline_data.data:
                        await ws.send_bytes(part.inline_data.data)
            if sc.input_transcription and sc.input_transcription.text:
                await ws.send_json({"type": "user", "text": sc.input_transcription.text})
            if sc.output_transcription and sc.output_transcription.text:
                await ws.send_json({"type": "gemini", "text": sc.output_transcription.text})
            if sc.interrupted:
                await ws.send_json({"type": "interrupted"})
            if sc.turn_complete:
                await ws.send_json({"type": "turn_complete"})


async def run_bridge(ws: WebSocket, voice: str) -> None:
    async with pool.live_connect(model=config.LIVE_MODEL, config=live_config(voice)) as session:
        log.info("Live session open: model=%s voice=%s", config.LIVE_MODEL, voice)
        await ws.send_json({"type": "ready", "model": config.LIVE_MODEL, "voice": voice})
        tasks = [
            asyncio.create_task(browser_to_gemini(ws, session)),
            asyncio.create_task(gemini_to_browser(ws, session)),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Also runs if this handler is cancelled, so no task is left orphaned.
            for t in tasks:
                t.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception) and not isinstance(r, WebSocketDisconnect):
                raise r
