# Malayalam Talkback: REST API + React

Stateless request/response version. Record a Malayalam question, POST it, get back the transcript,
a Malayalam reply and the reply as spoken audio (WAV).

```
POST /api/talk (WAV) ─▶ gemini-3.5-flash-lite: transcript + reply (JSON schema)
                     ─▶ gemini-3.8-flash-tts: reply as speech (falls back to flash-lite-tts)
                     ◀─ {transcript, reply, audio_wav_base64, timings_ms}
```

## Run

```bash
cp .env.example .env    # set GEMINI_API_KEYS
uv sync
(cd web && npm install && npm run build)
uv run python -m app    # http://127.0.0.1:8002 serves API + built React app
```

Frontend development with hot reload (proxies `/api` to :8002):

```bash
uv run python -m app            # terminal 1
cd web && npm run dev           # terminal 2, http://localhost:5172
```

## API

| Endpoint | Body | Returns |
|---|---|---|
| `GET /api/health` | | `{ok, text_model, tts_model, keys}` |
| `GET /api/voices` | | `{voices, default}` |
| `POST /api/talk` | multipart: `audio` (wav/mp3/ogg/flac/aac/webm, max 10 MB), `history` (JSON list of `{role, text}`), `voice` | `TalkResponse` |
| `POST /api/chat` | JSON `{text, history, voice}` | `TalkResponse` (reply in Malayalam even for English text) |

`TalkResponse` = `{transcript, reply, audio_wav_base64, timings_ms}`.
Errors: 400 empty audio, 413 too large, 415 unsupported type, 422 bad input,
429 every key rate limited (with `Retry-After`), 502 other Gemini errors.

```bash
curl -F audio=@tests/fixtures/question_ml.wav http://127.0.0.1:8002/api/talk | jq '{transcript, reply, timings_ms}'
```

Conversation state lives in the client: send previous turns as `history`.

## Files

| Path | What it does |
|---|---|
| `app/main.py` | Routes, validation, error mapping, serves `web/dist` |
| `app/gemini.py` | Understand (audio or text) and speak (TTS with model fallback) |
| `app/keypool.py` | Gemini key rotator (`uv run python -m app.keypool`) |
| `web/src/recorder.ts` | Records the mic as 16 kHz WAV in the browser |
| `web/src/api.ts` | Typed fetch client |
| `web/src/App.tsx` | UI: record/send, typed chat, transcript, per-turn timings |

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEYS` | (required) | One or more comma-separated keys, rotated |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash-lite` | Transcribe + reply |
| `GEMINI_TTS_MODEL` | `gemini-3.8-flash-tts` | Speech |
| `GEMINI_TTS_FALLBACK_MODELS` | `gemini-3.8-flash-lite-tts` | Tried when every key is rate limited on the main TTS model |
| `GEMINI_VOICE` | `Kore` | Default voice |

## Tests

```bash
(cd web && npm run build)
uv run pytest     # 17 tests: validation, key pool, real Malayalam audio/text/history, real Chrome with fake mic
```
