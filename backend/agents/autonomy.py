"""Autonomy Engine: Evaluates policy levels (1 to 3) to determine human approval gates"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models import PlaybookStep

CURRENT_AUTONOMY_LEVEL = 2


def set_autonomy_level(level: int):
    global CURRENT_AUTONOMY_LEVEL
    if level in (1, 2, 3):
        CURRENT_AUTONOMY_LEVEL = level


def get_autonomy_level() -> int:
    return CURRENT_AUTONOMY_LEVEL


def needs_approval(step: PlaybookStep, level: int = 2) -> bool:
    """
    Determines whether a remediation step requires human authorization.
    Level 1: Strict - Every step requires human approval.
    Level 2: Balanced - High-risk steps require approval; low/medium do not.
    Level 3: Autonomous - Routine restarts & rollouts execute autonomously;
             only stateful/resource limit mutations require human sign-off.
    """
    if level == 1:
        return True

    if level == 2:
        return step.risk == "high" or step.requires_approval

    if level == 3:
        # At level 3, restarts, rollbacks, and probes execute automatically.
        # Only infrastructure/resource limit changes (like patch_memory_limit) require approval.
        if step.action in ("patch_memory_limit", "patch_cpu_limit"):
            return True
        return False

    return True


# ── REST endpoint: POST /api/autonomy (CONTRACT.md) ─────────────────────────

router = APIRouter()


class AutonomyUpdate(BaseModel):
    level: int


@router.post("/api/autonomy")
async def update_autonomy(body: AutonomyUpdate) -> dict:
    if body.level not in (1, 2, 3):
        raise HTTPException(status_code=422, detail="level must be 1, 2 or 3")
    set_autonomy_level(body.level)
    return {"level": get_autonomy_level()}
