# Malayalam Talkback: WebSocket API + React

FastAPI exposes a WebSocket API (`/ws`) bridged to Gemini Live (`gemini-3.8-live`). A React
(Vite + TypeScript) client streams the mic and plays replies in real time.

## Run

```bash
cp .env.example .env    # set GEMINI_API_KEYS
uv sync
(cd web && npm install && npm run build)
uv run python -m app    # http://127.0.0.1:8003 serves API + built React app
```

Frontend development with hot reload (proxies `/api` and `/ws` to :8003):

```bash
uv run python -m app            # terminal 1
cd web && npm run dev           # terminal 2, http://localhost:5173
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/health` | `{ok, model, keys: {total, disabled, cooling_down}}` |
| `GET /api/voices` | `{voices, default}` |
| `WS /ws?voice=Kore` | Live conversation (protocol below) |

- Client to server: binary 16 kHz 16-bit mono PCM; JSON `{"type": "text", "text": "..."}`, `{"type": "audio_end"}`.
- Server to client: binary 24 kHz 16-bit mono PCM; JSON `{"type": "ready"|"user"|"gemini"|"interrupted"|"turn_complete"|"error", ...}`.

## Files

| Path | What it does |
|---|---|
| `app/main.py` | API routes, `/ws`, serves `web/dist` |
| `app/live.py` | Gemini Live bridge (through the key pool) |
| `app/keypool.py` | Gemini key rotator (`uv run python -m app.keypool`) |
| `web/src/useLiveSession.ts` | React hook: WebSocket, mic worklet, gapless playback, transcript |
| `web/src/App.tsx` | UI |
| `web/public/mic-processor.js` | AudioWorklet: mic to 16 kHz PCM |

## Tests

```bash
(cd web && npm run build)
uv run pytest     # 14 tests: HTTP, key pool, live Malayalam speech/text, real Chrome with fake mic
```
