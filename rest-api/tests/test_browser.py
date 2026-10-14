"""Browser test: real Chrome with a fake microphone that plays Malayalam speech."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from conftest import is_malayalam, requires_key

MIC_WAV = Path(__file__).parent / "fixtures" / "mic_ml.wav"


@pytest.fixture()
def page(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={MIC_WAV}",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        context = browser.new_context(permissions=["microphone"])
        pg = context.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(live_server)
        yield pg
        browser.close()
        assert not errors, errors


@requires_key
def test_record_and_send_in_browser(page):
    page.click("#talk")
    expect(page.locator("#talk")).to_contain_text("Send")
    page.wait_for_timeout(6500)  # fake mic: 2.5 s silence, ~3 s question, silence
    page.click("#talk")
    reply = page.locator(".msg.gemini p").first
    expect(reply).not_to_be_empty(timeout=45_000)
    expect(page.locator(".msg.user p").first).to_contain_text("നദി")
    assert is_malayalam(reply.inner_text())


@requires_key
def test_typed_text_in_browser(page):
    page.fill("#text-input", "What is the capital of Kerala?")
    page.click("#text-form button")
    reply = page.locator(".msg.gemini p").first
    expect(reply).to_contain_text("തിരുവനന്തപുര", timeout=45_000)
