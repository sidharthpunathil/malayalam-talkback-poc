# Malayalam Talkback: Jinja2 template + WebSocket

Server-rendered page (FastAPI + Jinja2) with vanilla JS. The browser streams the mic over a
WebSocket to FastAPI, which bridges it to a Gemini Live session (`gemini-3.8-live`).

```
browser mic ──16 kHz PCM──▶ /ws (FastAPI) ──▶ Gemini Live
browser speaker ◀─24 kHz PCM── /ws ◀── audio + transcripts
```

## Run

```bash
cp .env.example .env    # set GEMINI_API_KEYS
uv sync
uv run python -m app    # http://127.0.0.1:8001
```

Press **Start**, allow the microphone, speak Malayalam. Talk over Gemini to interrupt it.
The text box sends typed questions into the same live session.

## Files

| Path | What it does |
|---|---|
| `app/main.py` | `GET /` renders `templates/index.html`; `WS /ws?voice=Kore` runs the bridge |
| `app/live.py` | Opens the Live session (through the key pool) and pumps audio both ways |
| `app/keypool.py` | Gemini key rotator (`uv run python -m app.keypool` checks keys) |
| `app/config.py` | Env settings, voice list, Malayalam system instruction |
| `app/templates/index.html` | Jinja2 page: model name, voice picker |
| `app/static/app.js` | WebSocket client, gapless 24 kHz playback, live transcript |
| `app/static/mic-processor.js` | AudioWorklet: mic to 16 kHz 16-bit PCM |

## WebSocket protocol

- Client to server: binary frames of 16 kHz PCM; JSON `{"type": "text", "text": "..."}` or `{"type": "audio_end"}`.
- Server to client: binary frames of 24 kHz PCM; JSON `ready`, `user` / `gemini` (transcript chunks),
  `interrupted`, `turn_complete`, `error`.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEYS` | (required) | One or more comma-separated keys, rotated |
| `GEMINI_LIVE_MODEL` | `gemini-3.8-live` | Live model |
| `GEMINI_VOICE` | `Kore` | Default voice |

## Tests

```bash
uv run pytest     # 13 tests: page render, key pool, live Malayalam speech/text, real Chrome with fake mic
```
