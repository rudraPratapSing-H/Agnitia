#!/usr/bin/env python3
"""Warm-up call before going on stage (task 4.8, Member 3).

Makes one real LLM call so the first real diagnose/plan call during the live demo
isn't also paying for cold-start latency (DNS, TLS, provider cold start). Run as
part of `make demo`, right before the servers start.

Exit code 0 and a printed "warm-up call succeeded" line on success; exits 1 (but
never raises) if the LLM is unreachable -- DEMO_MODE=cache keeps the actual demo
safe either way, this is purely a latency head start.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents import llm  # noqa: E402
from backend.models import RCA  # noqa: E402


async def main() -> int:
    t0 = time.perf_counter()
    try:
        await llm.call_json(
            "Reply with a minimal valid RCA JSON object for a warm-up ping.",
            {"root_cause": "warm-up", "category": "warm-up", "confidence": 1.0, "evidence": []},
            RCA,
            timeout_s=10.0,
        )
    except Exception as exc:
        print(f"[warmup] LLM call failed ({exc}); demo will rely on DEMO_MODE=cache.")
        return 1

    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"[warmup] AI warm-up call succeeded in {elapsed_ms:.0f}ms. Ready to go on stage.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
