"""Policy gate for autonomous healing (Member 3, TASK P5)."""

from collections import defaultdict, deque
from typing import Any, Dict, List, Set
from backend.ml.config import PERSISTENCE, THRESHOLD

STATELESS: Set[str] = {"auth-service", "payment-service", "api-gateway", "web-ui"}
AUTONOMOUS_ACTIONS: Set[str] = {
    "patch_memory_limit",
    "patch_cpu_limit",
    "rollout_restart",
    "scale_replicas",
}


class Action:
    def __init__(self, name: str, service: str, params: dict) -> None:
        self.name = name
        self.service = service
        self.params = params

    def __repr__(self) -> str:
        return f"Action(name={self.name!r}, service={self.service!r}, params={self.params!r})"


class Decision:
    def __init__(self, allowed: bool, reasons: List[str]) -> None:
        self.allowed = allowed
        self.reasons = reasons

    def __repr__(self) -> str:
        return f"Decision(allowed={self.allowed}, reasons={self.reasons!r})"


class PolicyState:
    """Stateful policy tracking observations, action cooldowns, and autonomy level."""

    def __init__(self, level: int = 2) -> None:
        self.level: int = level
        self.kill_switch: bool = False
        self.probs: Dict[str, List[float]] = defaultdict(list)
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self.last_action: Dict[str, float] = {}
        self.hold_until: Dict[str, float] = {}
        self.action_history: List[float] = []

    def reset(self) -> None:
        self.probs.clear()
        self.history.clear()
        self.last_action.clear()
        self.hold_until.clear()
        self.action_history.clear()


def observe(state: PolicyState, service: str, prob: float) -> None:
    """Record a failure probability prediction for a service."""
    state.probs[service].append(prob)
    state.history[service].append(prob)


def streak_of(state: PolicyState, service: str) -> int:
    """Number of consecutive recent predictions for service that meet or exceed THRESHOLD."""
    hist = list(state.history.get(service, []))
    streak = 0
    for p in reversed(hist):
        if p >= THRESHOLD:
            streak += 1
        else:
            break
    return streak


def record_action(state: PolicyState, service: str, now: float, hold_after_action_s: float) -> None:
    """Record that an autonomous action occurred, setting cooldowns."""
    state.last_action[service] = now
    state.hold_until[service] = now + hold_after_action_s
    state.action_history.append(now)


def decide(state: PolicyState, action: Action, now: float) -> Decision:
    """Evaluates the 7 safety guardrails before allowing an autonomous action."""
    reasons: List[str] = []

    # Rule 7: Kill switch
    if state.kill_switch:
        return Decision(False, ["R7 kill switch is on"])

    # Rule 5 / Level check: Autonomous execution requires level 3
    if state.level < 3:
        reasons.append("R5 unapproved action requires level 3")

    # Rule 1 / Rule 2: Probability above threshold and held for consecutive windows
    if streak_of(state, action.service) < PERSISTENCE:
        reasons.append(f"R1/R2 streak below persistence ({PERSISTENCE})")

    # Rule 6: Cooldown & Rate limits (1 action per service per 10 min, max 5 per hour total)
    if now < state.hold_until.get(action.service, 0.0) or (
        action.service in state.last_action and (now - state.last_action[action.service]) < 600.0
    ):
        reasons.append("R6 cooldown active")

    # Filter action history for last hour (3600s)
    recent_actions = [t for t in state.action_history if now - t <= 3600.0]
    if len(recent_actions) >= 5:
        reasons.append("R6 rate limit exceeded (5/hour)")

    # Rule 3: Allow-list check
    if action.name not in AUTONOMOUS_ACTIONS:
        reasons.append(f"R3 action '{action.name}' not in autonomous allow-list")

    # Rule 4: Size cap
    if action.name == "patch_memory_limit":
        to_mb = action.params.get("to_mb", 0)
        from_mb = action.params.get("from_mb", 64)
        if to_mb > 512 or to_mb > 4 * from_mb:
            reasons.append("R4 memory limit exceeds cap (512Mi or 4x)")

    return Decision(len(reasons) == 0, reasons)
