"""LLM Helper for Agnitia using google-genai SDK"""

import asyncio
import json
import logging
import os
import time
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

logger = logging.getLogger("agnitia.llm")
logging.basicConfig(level=logging.INFO)


class LLMError(Exception):
    """Base exception for LLM call failures."""
    pass


class LLMTimeout(LLMError):
    """Raised when an LLM call exceeds the allowed timeout."""
    pass


def _strip_code_fences(text: str) -> str:
    """Strips markdown ```json / ``` code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


async def call_json(
    system_prompt: str,
    payload: dict | str,
    model_cls: type[BaseModel],
    *,
    timeout_s: float = 4.0,
) -> BaseModel:
    """
    Invokes the Gemini model with JSON output mode, strips code fences,
    validates the result using model_cls.model_validate_json, and performs
    one repair retry on validation error.
    """
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key or api_key == "your_llm_api_key_here":
        raise LLMError("LLM_API_KEY is not configured or invalid in environment.")

    model_name = os.getenv("LLM_MODEL", "gemini-2.0-flash").strip()

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise LLMError(f"google-genai SDK not installed: {e}") from e

    client = genai.Client(api_key=api_key)

    payload_str = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    schema_desc = json.dumps(model_cls.model_json_schema(), indent=2)
    full_prompt = (
        f"{payload_str}\n\n"
        f"Respond ONLY with valid JSON matching this schema:\n{schema_desc}"
    )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.0,
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    async def _execute_generate(prompt_text: str) -> str:
        t0 = time.perf_counter()
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt_text,
            config=config,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        prompt_tokens = 0
        completion_tokens = 0
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count or 0
            completion_tokens = response.usage_metadata.candidates_token_count or 0

        logger.info(
            f"model={model_name} latency_ms={latency_ms:.1f} "
            f"prompt_tokens={prompt_tokens} completion_tokens={completion_tokens}"
        )
        return response.text or ""

    try:
        async with asyncio.timeout(timeout_s):
            raw_text = await _execute_generate(full_prompt)
            clean_text = _strip_code_fences(raw_text)

            try:
                return model_cls.model_validate_json(clean_text)
            except (ValidationError, ValueError) as first_err:
                # ONE repair retry sending error back to model
                repair_prompt = (
                    f"The previous output failed validation:\n{first_err}\n\n"
                    f"Original input:\n{payload_str}\n\n"
                    f"Fix the output and return ONLY valid JSON matching this schema:\n{schema_desc}"
                )
                raw_text_retry = await _execute_generate(repair_prompt)
                clean_text_retry = _strip_code_fences(raw_text_retry)
                try:
                    return model_cls.model_validate_json(clean_text_retry)
                except (ValidationError, ValueError) as retry_err:
                    raise LLMError(
                        f"Validation failed after repair retry: {retry_err}"
                    ) from retry_err

    except TimeoutError as e:
        raise LLMTimeout(f"LLM call timed out after {timeout_s}s") from e
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"LLM call failed: {e}") from e


if __name__ == "__main__":
    from backend.models import RCA

    test_logs = [
        {"line": 38, "t_s": 0.0, "text": "2026-10-09 03:14:00 [LOG] checkpoint starting: time"},
        {"line": 39, "t_s": 1.0, "text": "2026-10-09 03:14:01 [LOG] checkpoint complete: wrote 892 buffers"},
        {"line": 40, "t_s": 2.0, "text": "2026-10-09 03:14:02 [LOG] autovacuum launcher started"},
        {"line": 41, "t_s": 3.0, "text": "2026-10-09 03:14:03 [LOG] worker thread 1 allocating memory buffer"},
        {"line": 42, "t_s": 4.0, "text": "2026-10-09 03:14:04 [FATAL] FATAL: out of memory (allocated 67108864 bytes, limit 67108864 bytes)"},
        {"line": 43, "t_s": 5.0, "text": "2026-10-09 03:14:05 [LOG] server process terminated by signal 9"},
        {"line": 44, "t_s": 5.5, "text": "2026-10-09 03:14:05 [LOG] terminating any other active server processes"},
        {"line": 45, "t_s": 6.0, "text": "2026-10-09 03:14:06 [LOG] database system was interrupted; last known up at 2026-10-09 03:14:00"},
    ]
    test_events = [
        {"t_s": 4.0, "service": "postgres", "text": "Reason: OOMKilled, Exit Code: 137"}
    ]
    system_prompt = (
        "You are Agnitia's diagnosis agent, an expert Kubernetes SRE. "
        "Find the root cause from the logs and events. Respond ONLY with JSON matching the rca schema."
    )
    payload = {
        "root_service": "postgres",
        "logs": test_logs,
        "events": test_events,
        "instruction": "Identify the root cause of the postgres service failure."
    }

    async def main():
        t0 = time.perf_counter()
        try:
            rca = await call_json(system_prompt, payload, RCA, timeout_s=30.0)
            latency = (time.perf_counter() - t0) * 1000.0
            print("\n=== Validated RCA Result ===")
            print(json.dumps(rca.model_dump(), indent=2))
            print(f"\nLatency: {latency:.1f} ms")
        except LLMError as err:
            print(f"Self-test failed with LLMError: {err}")

    asyncio.run(main())
