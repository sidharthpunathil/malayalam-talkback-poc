"""Round-robin pool of Gemini API keys.

Free-tier quotas are per project and per model, so a key that hits 429 on one model
is put on cooldown for that model only (for as long as Google's retryDelay says) and
the request moves on to the next key. Keys rejected as invalid are disabled.

Configure with GEMINI_API_KEYS (comma or newline separated) and/or GEMINI_API_KEY.
Check every key with:  uv run python -m app.keypool
"""

import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from google import genai
from google.genai import errors, types

log = logging.getLogger(__name__)

DEFAULT_COOLDOWN_S = 60.0
TRANSIENT_COOLDOWN_S = 5.0


class AllKeysBusy(Exception):
    """Every usable key is rate limited (or failing) for this model right now."""

    def __init__(self, model: str, retry_after: float, last_error: Exception | None = None):
        self.model = model
        self.retry_after = max(1, round(retry_after))
        self.last_error = last_error
        super().__init__(f"All Gemini keys are busy for {model}; retry in ~{self.retry_after}s ({last_error})")


@dataclass
class PoolKey:
    label: str
    client: genai.Client
    cooldown_until: dict[str, float] = field(default_factory=dict)
    disabled_reason: str = ""

    def ready_in(self, model: str) -> float:
        return max(0.0, self.cooldown_until.get(model, 0.0) - time.monotonic())


def mask(key: str) -> str:
    return f"{key[:6]}…{key[-4:]}"


def _retry_delay(err: Exception) -> float:
    m = re.search(r"retry in ([\d.]+)s|retryDelay'?\"?: ?'?\"?(\d+)s", str(err))
    return float(m.group(1) or m.group(2)) + 1 if m else DEFAULT_COOLDOWN_S


def classify(err: Exception) -> str:
    """'rate_limited', 'invalid_key', 'transient' or 'fatal' (not the key's fault)."""
    text = str(err)
    code = getattr(err, "code", None)
    if code == 429 or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return "rate_limited"
    if code in (401, 403) or "API key not valid" in text or "API_KEY_INVALID" in text:
        return "invalid_key"
    if code in (500, 502, 503, 504) or "UNAVAILABLE" in text:
        return "transient"
    return "fatal"


class KeyPool:
    def __init__(self, keys: list[str]):
        unique = list(dict.fromkeys(k.strip() for k in keys if k.strip()))
        # The pool does the retrying, so turn off the SDK's own retry-on-429 per client.
        opts = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
        self.keys = [PoolKey(mask(k), genai.Client(api_key=k, http_options=opts)) for k in unique]
        self._next = 0

    @classmethod
    def from_env(cls) -> "KeyPool":
        raw = os.environ.get("GEMINI_API_KEYS", "") + "," + os.environ.get("GEMINI_API_KEY", "")
        return cls(re.split(r"[,\s]+", raw))

    def _order(self, model: str) -> list[PoolKey]:
        """Usable keys starting from the round-robin cursor, ready ones first."""
        if not self.keys:
            raise ValueError("No Gemini API keys configured (set GEMINI_API_KEYS or GEMINI_API_KEY)")
        n = len(self.keys)
        start = self._next
        self._next = (self._next + 1) % n
        rotated = [self.keys[(start + i) % n] for i in range(n)]
        usable = [k for k in rotated if not k.disabled_reason]
        return sorted(usable, key=lambda k: k.ready_in(model) > 0)

    def _record_failure(self, key: PoolKey, model: str, err: Exception) -> bool:
        """Update key state; return True if the next key should be tried."""
        kind = classify(err)
        if kind == "rate_limited":
            delay = _retry_delay(err)
            key.cooldown_until[model] = time.monotonic() + delay
            log.warning("Key %s rate limited on %s, cooling down %.0fs", key.label, model, delay)
            return True
        if kind == "invalid_key":
            key.disabled_reason = str(err)[:120]
            log.error("Key %s disabled: %s", key.label, key.disabled_reason)
            return True
        if kind == "transient":
            key.cooldown_until[model] = time.monotonic() + TRANSIENT_COOLDOWN_S
            log.warning("Key %s got a transient error on %s: %s", key.label, model, str(err)[:120])
            return True
        return False

    def _busy(self, model: str, last: Exception | None) -> AllKeysBusy:
        waits = [k.ready_in(model) for k in self.keys if not k.disabled_reason]
        return AllKeysBusy(model, min(waits) if waits else DEFAULT_COOLDOWN_S, last)

    async def generate_content(self, *, model: str, **kwargs: Any) -> types.GenerateContentResponse:
        last: Exception | None = None
        for key in self._order(model):
            if key.ready_in(model) > 0:
                break  # sorted: everything after this is cooling down too
            try:
                return await key.client.aio.models.generate_content(model=model, **kwargs)
            except errors.APIError as e:
                last = e
                if not self._record_failure(key, model, e):
                    raise
        raise self._busy(model, last)

    @asynccontextmanager
    async def live_connect(self, *, model: str, config: types.LiveConnectConfig) -> AsyncIterator[Any]:
        """Like client.aio.live.connect, but the connect step fails over to the next key."""
        last: Exception | None = None
        for key in self._order(model):
            if key.ready_in(model) > 0:
                break
            cm = key.client.aio.live.connect(model=model, config=config)
            try:
                session = await cm.__aenter__()
            except Exception as e:
                last = e
                if self._record_failure(key, model, e):
                    continue
                raise
            log.info("Live session on key %s", key.label)
            try:
                yield session
            except BaseException as exc:
                if not await cm.__aexit__(type(exc), exc, exc.__traceback__):
                    raise
            else:
                await cm.__aexit__(None, None, None)
            return
        raise self._busy(model, last)

    def status(self) -> dict[str, Any]:
        return {
            "total": len(self.keys),
            "disabled": sum(bool(k.disabled_reason) for k in self.keys),
            "cooling_down": {
                k.label: {m: round(k.ready_in(m)) for m in k.cooldown_until if k.ready_in(m) > 0}
                for k in self.keys
                if any(k.ready_in(m) > 0 for m in k.cooldown_until)
            },
        }


async def _check(key: PoolKey, model: str) -> str:
    try:
        await key.client.aio.models.generate_content(
            model=model, contents="Say hi", config=types.GenerateContentConfig(max_output_tokens=5)
        )
        return "OK"
    except errors.APIError as e:
        return f"{classify(e)} ({e.code} {e.status})"


async def _main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    pool = KeyPool.from_env()
    model = os.environ.get("GEMINI_CHECK_MODEL", "gemini-3.5-flash-lite")
    results = await asyncio.gather(*(_check(k, model) for k in pool.keys))
    print(f"Checked {len(pool.keys)} keys against {model}:")
    for key, result in zip(pool.keys, results):
        print(f"  {key.label}  {result}")
    print(f"{sum(r == 'OK' for r in results)}/{len(results)} working")


if __name__ == "__main__":
    asyncio.run(_main())
