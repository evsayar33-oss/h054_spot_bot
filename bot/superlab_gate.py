"""Fail-closed Quant Superlab approval lookup for H054 live execution.

PAPER remains governed by the local prospective decision. This module is only
an additional LIVE boundary: unavailable, stale, mismatched or non-ACCEPT
central evidence can never authorize an order.
"""
from __future__ import annotations
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_URL = ("https://raw.githubusercontent.com/evsayar33-oss/quant_superlab/"
               "main/decisions/registry.json")

def fetch_registry(url: str | None = None, timeout: int = 15) -> dict:
    request = urllib.request.Request(
        url or os.getenv("QUANT_LAB_URL", DEFAULT_URL),
        headers={"User-Agent": "h054-superlab-live-gate"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def live_accepted(*, hypothesis: str = "H054", max_age_days: int = 10,
                  registry: dict | None = None,
                  now: datetime | None = None) -> tuple[bool, str]:
    """Require a fresh central ACCEPT explicitly assigned to this bot."""
    try:
        data = registry if registry is not None else fetch_registry()
        decision = data["hypotheses"][hypothesis]
        if decision.get("for_system") != "h054_spot_bot":
            return False, "SUPERLAB_SYSTEM_MISMATCH"
        if decision.get("verdict") != "ACCEPT":
            return False, "SUPERLAB_ACCEPT_MISSING"
        stamp = datetime.fromisoformat(str(decision["validated_at"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False, "SUPERLAB_DATE_INVALID"
        current = now or datetime.now(timezone.utc)
        age = current.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)
        if not timedelta(0) <= age <= timedelta(days=max_age_days):
            return False, "SUPERLAB_ACCEPT_EXPIRED_OR_FUTURE"
        return True, f"Quant Superlab {hypothesis} ACCEPT"
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return False, "SUPERLAB_REGISTRY_UNAVAILABLE_OR_INVALID:" + type(exc).__name__
