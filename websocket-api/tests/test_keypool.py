"""Offline tests for the key rotator (no network)."""

import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.keypool import AllKeysBusy, KeyPool


def rate_limited(delay: int = 30) -> errors.ClientError:
    return errors.ClientError(
        429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": f"Quota exceeded. Please retry in {delay}s."}}
    )


def invalid_key() -> errors.ClientError:
    return errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "API key not valid."}})


class FakeModels:
    def __init__(self, name: str, behaviour: list):
        self.name, self.behaviour, self.calls = name, behaviour, 0

    async def generate_content(self, *, model, **kwargs):
        self.calls += 1
        outcome = self.behaviour.pop(0) if self.behaviour else "ok"
        if isinstance(outcome, Exception):
            raise outcome
        return f"{self.name}:{model}"


def make_pool(*behaviours: list) -> tuple[KeyPool, list[FakeModels]]:
    pool = KeyPool([f"key-number-{i}-xxxx" for i in range(len(behaviours))])
    fakes = []
    for i, (key, b) in enumerate(zip(pool.keys, behaviours)):
        fake = FakeModels(f"k{i}", list(b))
        key.client = SimpleNamespace(aio=SimpleNamespace(models=fake))
        fakes.append(fake)
    return pool, fakes


def run(coro):
    return asyncio.run(coro)


def test_round_robin_spreads_requests():
    pool, _ = make_pool([], [], [])
    results = [run(pool.generate_content(model="m", contents="x")) for _ in range(6)]
    assert results == ["k0:m", "k1:m", "k2:m", "k0:m", "k1:m", "k2:m"]


def test_rate_limited_key_fails_over_and_cools_down():
    pool, fakes = make_pool([rate_limited(30)], [], [])
    assert run(pool.generate_content(model="m", contents="x")) == "k1:m"
    assert 25 < pool.keys[0].ready_in("m") <= 31
    # Cooling key is skipped for that model, but still used for other models.
    for _ in range(4):
        assert run(pool.generate_content(model="m", contents="x")) != "k0:m"
    assert pool.keys[0].ready_in("other") == 0
    assert "key-nu" in next(iter(pool.status()["cooling_down"]))


def test_invalid_key_is_disabled():
    pool, fakes = make_pool([invalid_key()], [])
    assert run(pool.generate_content(model="m", contents="x")) == "k1:m"
    assert pool.keys[0].disabled_reason
    for _ in range(3):
        run(pool.generate_content(model="m", contents="x"))
    assert fakes[0].calls == 1
    assert pool.status()["disabled"] == 1


def test_all_keys_busy_raises_with_retry_after():
    pool, _ = make_pool([rate_limited(20)], [rate_limited(40)])
    with pytest.raises(AllKeysBusy) as exc:
        run(pool.generate_content(model="m", contents="x"))
    assert 15 <= exc.value.retry_after <= 22


def test_non_key_errors_are_not_retried():
    bad_request = errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "bad schema"}})
    pool, fakes = make_pool([bad_request], [])
    with pytest.raises(errors.ClientError):
        run(pool.generate_content(model="m", contents="x"))
    assert fakes[1].calls == 0


def test_keys_are_deduplicated_and_parsed_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "aaaaaa1111, bbbbbb2222\ncccccc3333,aaaaaa1111")
    monkeypatch.setenv("GEMINI_API_KEY", "bbbbbb2222")
    pool = KeyPool.from_env()
    assert [k.label for k in pool.keys] == ["aaaaaa…1111", "bbbbbb…2222", "cccccc…3333"]


def test_empty_pool_raises_on_use():
    pool = KeyPool([])
    with pytest.raises(ValueError):
        run(pool.generate_content(model="m", contents="x"))
