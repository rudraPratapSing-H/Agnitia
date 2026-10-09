"""Text-to-speech for the voice briefing (task 3.10), via Gemini's native TTS.

Reuses LLM_API_KEY -- no separate credential to manage. Falls back to raising
TTSError on any failure; the frontend falls back to the browser's own
speechSynthesis so the briefing is never silently lost on stage.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

logger = logging.getLogger("agnitia.tts")

DEFAULT_VOICE = "Kore"
TTS_TIMEOUT_S = 15.0  # TTS generation is slower and more variable than text generation


class TTSError(Exception):
    """Raised when speech synthesis fails."""


async def synthesize_speech(text: str, *, voice: str = DEFAULT_VOICE) -> bytes:
    """Returns WAV audio bytes for `text`, spoken by a Gemini TTS voice."""
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key or api_key == "your_llm_api_key_here":
        raise TTSError("LLM_API_KEY is not configured or invalid in environment.")

    model_name = os.getenv("TTS_MODEL", "gemini-3.8-flash-tts").strip()

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise TTSError(f"google-genai SDK not installed: {e}") from e

    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )

    try:
        async with asyncio.timeout(TTS_TIMEOUT_S):
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=text,
                config=config,
            )
    except TimeoutError as exc:
        raise TTSError(f"TTS call timed out after {TTS_TIMEOUT_S}s") from exc
    except Exception as exc:
        raise TTSError(f"TTS call failed: {exc}") from exc

    try:
        part = response.candidates[0].content.parts[0]
        return part.inline_data.data
    except (IndexError, AttributeError) as exc:
        raise TTSError(f"TTS response had no audio: {exc}") from exc


# ── REST endpoint: POST /api/tts ─────────────────────────────────────────────

router = APIRouter()


class TTSRequest(BaseModel):
    text: str


@router.post("/api/tts")
async def post_tts(body: TTSRequest) -> Response:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    try:
        audio = await synthesize_speech(body.text)
    except TTSError as exc:
        logger.warning("TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    return Response(content=audio, media_type="audio/wav")
