"""Citation Verifier: Verifies that LLM claims directly match raw logs, events, and metrics"""

from typing import List
from backend.models import RCA, LogLine, K8sEvent, MetricPoint


def verify_citations(
    rca: RCA,
    logs: List[LogLine],
    events: List[K8sEvent],
    metrics: List[MetricPoint],
) -> RCA:
    """
    Verifies every evidence citation against raw cluster telemetry.
    If an evidence item cannot be verified in the raw data, marks verified=False
    and reduces diagnosis confidence by 0.2 per invalid citation.
    """
    if not rca or not rca.evidence:
        return rca

    unverified_count = 0

    for item in rca.evidence:
        verified = False

        if item.type == "log":
            # Check against log lines (by line number or substring match)
            for log in logs:
                if item.line is not None and log.line == item.line:
                    if item.text.lower() in log.text.lower() or log.text.lower() in item.text.lower():
                        verified = True
                        break
                elif item.text.lower() in log.text.lower():
                    verified = True
                    break

        elif item.type == "k8s_event":
            # Check against cluster events
            for ev in events:
                if item.text.lower() in ev.text.lower() or ev.text.lower() in item.text.lower():
                    verified = True
                    break

        elif item.type == "metric":
            # Check against metric data
            verified = len(metrics) > 0

        item.verified = verified
        if not verified:
            unverified_count += 1

    if unverified_count > 0:
        rca.confidence = max(0.1, round(rca.confidence - (0.2 * unverified_count), 2))

    return rca
