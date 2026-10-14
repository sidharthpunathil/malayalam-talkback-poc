# Malayalam Talkback (Gemini)

Speak Malayalam, get a spoken Malayalam answer. Three standalone implementations of the same idea,
each its own uv project with its own `.env`, `.env.example`, `.gitignore`, `.python-version`,
`pyproject.toml`, `uv.lock`, README and tests.

| Folder | Transport | Client | Gemini models | Port |
|---|---|---|---|---|
| [`template-websocket/`](template-websocket/) | WebSocket, real time | Jinja2 template + vanilla JS | `gemini-3.8-live` (native audio) | 8001 |
| [`rest-api/`](rest-api/) | REST, request/response | React (Vite + TS) | `gemini-3.5-flash-lite` (understand) + `gemini-3.8-flash-tts` (speak) | 8002 (dev UI 5172) |
| [`websocket-api/`](websocket-api/) | WebSocket, real time | React (Vite + TS) | `gemini-3.8-live` (native audio) | 8003 (dev UI 5173) |

```bash
cd template-websocket   # or rest-api / websocket-api
cp .env.example .env    # add your key(s)
uv sync
uv run python -m app    # see that folder's README for the React client
```

## Which one to use

- **Real-time conversation** (talk over it, interrupt it, ~1 s latency): `template-websocket` or `websocket-api`.
  Gemini Live streams 16 kHz PCM in and 24 kHz PCM out over one session.
- **Simple, stateless HTTP** (press record, then send; easy to call from anything): `rest-api`.
  Two calls per turn: audio to text, then text to speech. About 4 to 5 s per turn.

## What is in every project

- `app/keypool.py`: Gemini **key rotator**. Put several keys in `GEMINI_API_KEYS` (comma separated).
  Requests round-robin across keys. A key that gets a 429 cools down for that model for Google's
  `retryDelay` and the request moves to the next key. Invalid keys are disabled. Live sessions fail
  over at connect time. `uv run python -m app.keypool` checks every key.
- `tests/`: pytest suite. Offline unit tests, integration tests against the real Gemini API, and a
  browser test that drives real Chrome (Playwright) with a fake microphone that plays a recorded
  Malayalam question (`tests/fixtures/mic_ml.wav`).

Run tests: `uv run pytest` inside a project (needs Google Chrome installed for the browser test;
React projects need `npm run build` in `web/` first).

## Gemini and Malayalam: research notes (Oct 2026)

- Malayalam (`ml`) is on the Live API supported-language list. Native audio models auto-detect the
  spoken language and **do not accept `language_code`**. Replies are kept in Malayalam through the
  system instruction.
- `gemini-3.8-live` is the stable Live model. `gemini-3.1-flash-live-preview` and
  `gemini-2.5-flash-native-audio-*` shut down on Nov 17, 2026.
- Live audio: input raw 16-bit PCM at 16 kHz, output 16-bit PCM at 24 kHz.
- `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts` both speak Malayalam. The free tier allows
  only about 3 TTS requests per minute per project, which is why the key rotator and the TTS model
  fallback exist.
- `gemini-3.8-flash` took about 90 s for one audio turn (default thinking) and was often overloaded;
  `gemini-3.5-flash-lite` does transcript + reply in about 2 s.
- New "AQ." style keys work with `google-genai` exactly like "AIza" keys.
- Free-tier quota is per Google Cloud project, so rotating keys only adds capacity when the keys
  belong to different projects. Check Google's Gemini API terms before relying on multiple projects
  to raise limits.

References: [Live API docs](https://ai.google.dev/gemini-api/docs/live-api),
[official Live examples](https://github.com/google-gemini/gemini-live-api-examples).
