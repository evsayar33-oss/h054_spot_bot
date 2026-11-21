"""Read-only freshness gate for the H054-MOM2 fallback clock.

Invoked ONLY by the independent Band-30 external repository_dispatch tick.
Never modifies the bot state, ledger, orders, or position approvals.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BAR_HOURS = 4
PUBLICATION_GRACE_MINUTES = 5


def parse_bar(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("H054_LAST_BAR_MISSING")
    bar = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if bar.tzinfo is None:
        bar = bar.replace(tzinfo=timezone.utc)
    bar = bar.astimezone(timezone.utc)
    if bar.minute or bar.second or bar.microsecond or bar.hour % BAR_HOURS:
        raise ValueError("H054_INVALID_LAST_BAR_ALIGNMENT")
    return bar


def latest_completed_bar(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("H054_NAIVE_CLOCK")
    effective = now.astimezone(timezone.utc) - timedelta(minutes=PUBLICATION_GRACE_MINUTES)
    start = effective.replace(hour=(effective.hour // BAR_HOURS) * BAR_HOURS,
                              minute=0, second=0, microsecond=0)
    return start - timedelta(hours=BAR_HOURS)


def should_dispatch(state: dict, now: datetime) -> bool:
    if not isinstance(state, dict):
        raise ValueError("H054_INVALID_SOURCE_STATE")
    last = parse_bar(state.get("last_bar"))
    expected = latest_completed_bar(now)
    if last > expected:
        raise ValueError("H054_SOURCE_LAST_BAR_IN_FUTURE")
    return last < expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    # Fail visibly if state is absent, malformed or rolled forward unexpectedly.
    state = json.loads(args.state.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    pending = should_dispatch(state, now)
    expected = latest_completed_bar(now)
    print(f"H054_CLOCK_CHECK last={state['last_bar']} expected={expected.isoformat()} dispatch={pending}")
    with args.github_output.open("a", encoding="utf-8") as output:
        output.write(f"should_dispatch={'true' if pending else 'false'}\n")


if __name__ == "__main__":
    main()
