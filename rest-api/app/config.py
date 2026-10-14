import os

from dotenv import load_dotenv

load_dotenv()

TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.5-flash-lite")
TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
# Tried in order when the primary TTS model is rate limited (free tier: a few requests/minute).
TTS_FALLBACK_MODELS = [m for m in os.environ.get("GEMINI_TTS_FALLBACK_MODELS", "gemini-3.8-flash-lite-tts").split(",") if m]
DEFAULT_VOICE = os.environ.get("GEMINI_VOICE", "Kore")

VOICES = ["Kore", "Puck", "Charon", "Aoede", "Leda", "Fenrir", "Orus", "Zephyr"]
MAX_AUDIO_BYTES = 10 * 1024 * 1024
AUDIO_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp3", "audio/ogg", "audio/flac", "audio/aac", "audio/webm"}

SYSTEM_INSTRUCTION = """You are a warm, friendly voice assistant for Malayalam speakers.
Always reply only in Malayalam (മലയാളം), even if the user writes or speaks English or mixes languages.
Use natural, conversational Kerala Malayalam and answer in one to three complete sentences,
since the reply is read aloud. If the audio is unclear, politely ask the user in Malayalam to repeat."""
