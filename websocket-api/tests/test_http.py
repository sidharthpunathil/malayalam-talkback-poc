
from app import config



def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True and body["model"] == config.LIVE_MODEL
    assert body["keys"]["total"] >= 1


def test_voices(client):
    body = client.get("/api/voices").json()
    assert body["default"] in body["voices"]


def test_serves_react_build(client):
    res = client.get("/")
    assert res.status_code == 200
    assert '<div id="root">' in res.text
