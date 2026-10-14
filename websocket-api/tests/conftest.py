import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
MALAYALAM = re.compile(r"[ഀ-ൿ]")

load_dotenv(ROOT / ".env")

requires_key = pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY")), reason="no Gemini API key set"
)


def is_malayalam(text: str) -> bool:
    """True when most letters in `text` are Malayalam script."""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(bool(MALAYALAM.match(c)) for c in letters) / len(letters) > 0.6


@pytest.fixture(scope="session")
def question_wav() -> bytes:
    """~3 s of Malayalam speech: "കേരളത്തിലെ ഏറ്റവും വലിയ നദി ഏതാണ്?" (16 kHz mono WAV)."""
    return (FIXTURES / "question_ml.wav").read_bytes()


@pytest.fixture(scope="session")
def live_server():
    """Run the real app with uvicorn on a free port (used by the browser tests)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(url + "/api/health" if (ROOT / "web").exists() else url, timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    yield url
    proc.terminate()
    proc.wait(5)


@pytest.fixture(scope="session")
def client():
    """One TestClient (one event loop) for the whole run, like a real uvicorn worker."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
