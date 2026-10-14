"""Integration tests against the real Gemini Live API (needs GEMINI_API_KEY in .env)."""

import io
import json
import time
import wave

import pytest

from conftest import is_malayalam, requires_key


def pcm_frames(wav_bytes: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        return w.readframes(w.getnframes())


def converse(ws, pcm: bytes) -> dict:
    """Stream speech in real time (100 ms chunks), then silence, and collect one model turn."""
    ready = ws.receive_json()
    assert ready["type"] == "ready"
    for i in range(0, len(pcm), 3200):
        ws.send_bytes(pcm[i : i + 3200])
        time.sleep(0.1)
    for _ in range(15):
        ws.send_bytes(bytes(3200))
        time.sleep(0.1)
    return collect_turn(ws)


def collect_turn(ws) -> dict:
    out = {"user": "", "gemini": "", "audio_bytes": 0}
    for _ in range(2000):
        msg = ws.receive()
        if msg.get("bytes"):
            out["audio_bytes"] += len(msg["bytes"])
            continue
        event = json.loads(msg["text"])
        if event["type"] in ("user", "gemini"):
            out[event["type"]] += event["text"]
        elif event["type"] == "error":
            pytest.fail(event["error"])
        elif event["type"] == "turn_complete":
            break
    return out


@requires_key
def test_malayalam_speech_gets_spoken_malayalam_reply(client, question_wav):
    with client.websocket_connect("/ws?voice=Puck") as ws:
        turn = converse(ws, pcm_frames(question_wav))
    assert "നദി" in turn["user"], turn
    assert is_malayalam(turn["gemini"]), turn
    assert turn["audio_bytes"] > 48000, "expected at least 1 s of 24 kHz reply audio"


@requires_key
def test_english_text_gets_malayalam_reply(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_text(json.dumps({"type": "text", "text": "What is the capital of Kerala?"}))
        turn = collect_turn(ws)
    assert is_malayalam(turn["gemini"]), turn
    assert "തിരുവനന്തപുരം" in turn["gemini"] or "തിരുവനന്തപുര" in turn["gemini"], turn
    assert turn["audio_bytes"] > 0


@requires_key
def test_unknown_voice_falls_back_to_default(client):
    with client.websocket_connect("/ws?voice=NotAVoice") as ws:
        ready = ws.receive_json()
    assert ready["voice"] == "Kore"
