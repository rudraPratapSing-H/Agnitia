"""Text-to-speech for the voice briefing (task 3.10), via Google's TTS stack.

Two paths, tried in order:
1. Cloud Text-to-Speech API (texttospeech.googleapis.com), if GOOGLE_TTS_API_KEY is set.
   This is a separate GCP product/credential from the Gemini API key, billed and quota'd
   independently -- doesn't hit the Generative Language API's free-tier request cap.
2. Gemini's native TTS via the google-genai SDK, reusing LLM_API_KEY. No separate
   credential needed, but on the free tier this is capped at 10 requests/day
   (see demo/manual-setup-guide.md).

Either way, failures raise TTSError; the frontend falls back to the browser's own
speechSynthesis so the briefing is never silently lost on stage.
"""

import asyncio
import base64
import logging
import os

import httpx
from dotenv import load_dotenv
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

logger = logging.getLogger("agnitia.tts")

DEFAULT_VOICE = "Kore"  # short prebuilt-voice name, used by the Gemini-native path
CLOUD_TTS_VOICE = "en-US-Chirp3-HD-Kore"  # full Cloud TTS voice name, same "Kore" voice
TTS_TIMEOUT_S = 15.0  # TTS generation is slower and more variable than text generation


class TTSError(Exception):
    """Raised when speech synthesis fails."""


async def _synthesize_cloud_tts(text: str, api_key: str, voice: str) -> bytes:
    """Cloud Text-to-Speech API (texttospeech.googleapis.com). Returns MP3 bytes."""
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": "en-US", "name": voice},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    try:
        async with httpx.AsyncClient(timeout=TTS_TIMEOUT_S) as client:
            resp = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        raise TTSError(f"Cloud TTS call timed out after {TTS_TIMEOUT_S}s") from exc
    except httpx.HTTPError as exc:
        raise TTSError(f"Cloud TTS call failed: {exc}") from exc

    if resp.status_code != 200:
        raise TTSError(f"Cloud TTS returned {resp.status_code}: {resp.text[:300]}")

    try:
        audio_b64 = resp.json()["audioContent"]
        return base64.b64decode(audio_b64)
    except (KeyError, ValueError) as exc:
        raise TTSError(f"Cloud TTS response had no audio: {exc}") from exc


async def _synthesize_gemini_native(text: str, voice: str) -> bytes:
    """Gemini's own TTS models via google-genai, reusing LLM_API_KEY. Returns WAV bytes."""
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


async def synthesize_speech(text: str, *, voice: str = DEFAULT_VOICE) -> tuple[bytes, str]:
    """Returns (audio_bytes, mime_type) for `text`.

    Prefers the dedicated Cloud Text-to-Speech API (GOOGLE_TTS_API_KEY) when configured --
    separate quota from the Gemini API's free-tier request cap. Falls back to Gemini's
    native TTS (LLM_API_KEY) otherwise.
    """
    cloud_key = os.getenv("GOOGLE_TTS_API_KEY", "").strip()
    if cloud_key:
        audio = await _synthesize_cloud_tts(text, cloud_key, CLOUD_TTS_VOICE)
        return audio, "audio/mpeg"

    audio = await _synthesize_gemini_native(text, voice)
    return audio, "audio/wav"


# ── REST endpoint: POST /api/tts ─────────────────────────────────────────────

router = APIRouter()


class TTSRequest(BaseModel):
    text: str


@router.post("/api/tts")
async def post_tts(body: TTSRequest) -> Response:
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    try:
        audio, mime_type = await synthesize_speech(body.text)
    except TTSError as exc:
        logger.warning("TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    return Response(content=audio, media_type=mime_type)
