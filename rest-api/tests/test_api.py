"""REST API tests. Validation tests run offline; the rest call the real Gemini API."""

import base64
import json


from conftest import is_malayalam, requires_key



def test_health_and_voices(client):
    assert client.get("/api/health").json()["ok"] is True
    body = client.get("/api/voices").json()
    assert body["default"] in body["voices"]


def test_rejects_unsupported_audio_type(client):
    res = client.post("/api/talk", files={"audio": ("x.txt", b"x" * 2000, "text/plain")})
    assert res.status_code == 415


def test_rejects_empty_audio(client):
    res = client.post("/api/talk", files={"audio": ("x.wav", b"RIFF", "audio/wav")})
    assert res.status_code == 400


def test_rejects_bad_history(client, question_wav):
    res = client.post(
        "/api/talk",
        files={"audio": ("q.wav", question_wav, "audio/wav")},
        data={"history": "not json"},
    )
    assert res.status_code == 422


def test_chat_requires_text(client):
    assert client.post("/api/chat", json={"text": ""}).status_code == 422


def assert_wav(b64: str) -> None:
    wav = base64.b64decode(b64)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert len(wav) > 48000, "expected at least 1 s of reply audio"


@requires_key
def test_talk_malayalam_speech(client, question_wav):
    res = client.post(
        "/api/talk",
        files={"audio": ("q.wav", question_wav, "audio/wav")},
        data={"voice": "Puck"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "നദി" in body["transcript"], body
    assert is_malayalam(body["reply"]), body
    assert_wav(body["audio_wav_base64"])
    assert set(body["timings_ms"]) == {"understand", "tts"}


@requires_key
def test_chat_english_text_gets_malayalam_reply(client):
    res = client.post("/api/chat", json={"text": "What is the capital of Kerala?"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert is_malayalam(body["reply"]), body
    assert "തിരുവനന്തപുര" in body["reply"], body
    assert_wav(body["audio_wav_base64"])


@requires_key
def test_chat_uses_history(client):
    history = [
        {"role": "user", "text": "എന്റെ പേര് അനു എന്നാണ്."},
        {"role": "model", "text": "നമസ്കാരം അനു! നിങ്ങളെ പരിചയപ്പെട്ടതിൽ സന്തോഷം."},
    ]
    res = client.post("/api/chat", json={"text": "എന്റെ പേര് എന്താണ്?", "history": history})
    assert res.status_code == 200, res.text
    assert "അനു" in res.json()["reply"]
