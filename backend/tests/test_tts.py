"""Tests for backend/agents/tts.py's POST /api/tts endpoint (task 3.10, voice briefing).

The real Gemini TTS call is mocked out -- these test routing/validation/error handling,
not the actual Google TTS integration (that's verified manually, same as the other
LLM-backed endpoints).
"""

from httpx import ASGITransport, AsyncClient

import backend.agents.tts as tts
import backend.main as main_module


async def test_post_tts_returns_wav_audio(monkeypatch):
    async def fake_synthesize(text, *, voice=tts.DEFAULT_VOICE):
        assert text == "hello from the test"
        return b"RIFF....WAVEfake"

    monkeypatch.setattr(tts, "synthesize_speech", fake_synthesize)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/tts", json={"text": "hello from the test"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert resp.content == b"RIFF....WAVEfake"


async def test_post_tts_rejects_empty_text():
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/tts", json={"text": "   "})

    assert resp.status_code == 422


async def test_post_tts_returns_502_on_synthesis_failure(monkeypatch):
    async def failing_synthesize(text, *, voice=tts.DEFAULT_VOICE):
        raise tts.TTSError("upstream unreachable")

    monkeypatch.setattr(tts, "synthesize_speech", failing_synthesize)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/tts", json={"text": "hello"})

    assert resp.status_code == 502
