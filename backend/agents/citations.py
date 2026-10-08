"""Citation Verifier: Verifies that LLM claims directly match raw logs, events, and metrics"""

import re
from backend.models import RCA, LogLine, K8sEvent, MetricPoint


def _normalise(text: str) -> str:
    """Removes all whitespace characters from text (case-sensitive)."""
    return re.sub(r"\s+", "", text)


def _extract_first_number(text: str) -> float | None:
    """Finds and parses the first float/integer in the text."""
    match = re.search(r"[-+]?(?:\d+\.?\d*|\.\d+)", text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def verify_citations(
    rca: RCA,
    logs: list[LogLine],
    events: list[K8sEvent],
    metrics: list[MetricPoint],
) -> RCA:
    """
    Verifies cited evidence items against raw cluster telemetry.
    Returns a deep copy of the RCA, never mutating the input.
    """
    rca_copy = rca.model_copy(deep=True)

    if not rca_copy.evidence:
        rca_copy.warning = "No evidence cited"
        return rca_copy

    failing_texts: list[str] = []

    for ev in rca_copy.evidence:
        norm_text = _normalise(ev.text)

        # Evidence text shorter than 5 characters after normalising counts as NOT verified
        if len(norm_text) < 5:
            ev.verified = False
            failing_texts.append(ev.text)
            continue

        verified = False

        if ev.type == "log":
            # type "log": verified only if normalised text appears in a log line's text
            # and if evidence has a line number, it must match that exact line
            if ev.line is not None:
                matching_logs = [l for l in logs if l.line == ev.line]
                verified = any(norm_text in _normalise(l.text) for l in matching_logs)
            else:
                verified = any(norm_text in _normalise(l.text) for l in logs)

        elif ev.type == "k8s_event":
            # type "k8s_event": verified only if text appears inside some event's text
            verified = any(norm_text in _normalise(e.text) for e in events)

        elif ev.type == "metric":
            # type "metric": take first number in text; must match mem_mb or cpu_pct within +-0.1
            first_num = _extract_first_number(ev.text)
            if first_num is not None:
                verified = any(
                    abs(pt.mem_mb - first_num) <= 0.1 + 1e-7
                    or abs(pt.cpu_pct - first_num) <= 0.1 + 1e-7
                    for pt in metrics
                )
            else:
                verified = False

        ev.verified = verified
        if not verified:
            failing_texts.append(ev.text)

    if failing_texts:
        # Apply penalty ONCE, not per item
        rca_copy.confidence = round(max(0.0, rca_copy.confidence - 0.2), 2)
        rca_copy.warning = (
            f"{len(failing_texts)} citation(s) could not be verified against the raw data: "
            + ", ".join(failing_texts)
        )
    else:
        rca_copy.warning = None

    return rca_copy
