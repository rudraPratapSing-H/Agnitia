#!/usr/bin/env python3
"""
Tiny checker for frontend/src/mock/events_db_oom.json
Asserts:
- Exactly 56 alerts
- Strictly increasing timestamps
- Valid event envelope structure {type, ts, payload}
Prints count of events per type, then PASS.
"""

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MOCK_FILE = REPO_ROOT / "frontend" / "src" / "mock" / "events_db_oom.json"


def check_mock():
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if not MOCK_FILE.exists():

        print(f"Error: {MOCK_FILE} does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(MOCK_FILE, "r", encoding="utf-8") as f:
        events = json.load(f)

    if not isinstance(events, list) or len(events) == 0:
        print("Error: events must be a non-empty list.", file=sys.stderr)
        sys.exit(1)

    counts = Counter()
    for idx, event in enumerate(events):
        # Validate envelope
        assert "type" in event, f"Event at index {idx} missing 'type'"
        assert "ts" in event, f"Event at index {idx} missing 'ts'"
        assert "payload" in event, f"Event at index {idx} missing 'payload'"
        counts[event["type"]] += 1

    # Print count of events per type
    print("Event counts per type:")
    for ev_type, count in counts.items():
        print(f"  {ev_type:<18}: {count}")
    print(f"Total events: {len(events)}")

    # Assert exactly 56 alerts
    alert_count = counts.get("alert", 0)
    assert alert_count == 56, f"Expected exactly 56 alerts, found {alert_count}"

    # Assert strictly increasing timestamps
    for i in range(len(events) - 1):
        t_curr = events[i]["ts"]
        t_next = events[i + 1]["ts"]
        assert t_curr < t_next, (
            f"Timestamp not strictly increasing at index {i}: "
            f"event[{i}] ({events[i]['type']}) ts={t_curr} >= "
            f"event[{i+1}] ({events[i+1]['type']}) ts={t_next}"
        )

    print("PASS")


if __name__ == "__main__":
    check_mock()
