
from app import config



def test_index_renders_template(client):
    res = client.get("/")
    assert res.status_code == 200
    assert config.LIVE_MODEL in res.text
    for voice in config.VOICES:
        assert f'value="{voice}"' in res.text
    assert "മലയാളം Talkback" in res.text


def test_static_assets_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/mic-processor.js").status_code == 200
