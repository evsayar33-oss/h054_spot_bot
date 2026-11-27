"""Repo-local strategy gate: independent PAPER approval; LIVE remains fail-closed."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.superlab_gate import live_accepted

REGISTRY = Path(__file__).resolve().parent.parent / "decisions" / "registry.json"
STRATEGY_KEYS = (
    "assets", "timeframe", "sma_days", "horizons_days",
    "vol_target", "vol_lookback_days", "band", "min_positive_horizons",
)

def approved(cfg: dict, *, live: bool = False) -> tuple[bool, str]:
    """Reject unreviewed rule edits and never turn PAPER permission into LIVE approval."""
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        if data.get("schema") != "h054.local.decisions.v1":
            return False, "LOCAL_REGISTRY_SCHEMA"
        name = cfg["safety"]["hypothesis"]
        decision = data["hypotheses"][name]
        approved_rules = decision["strategy"]
        actual_rules = cfg["strategy"]
        if set(approved_rules) != set(STRATEGY_KEYS):
            return False, "LOCAL_REGISTRY_RULES_INVALID"
        if any(actual_rules.get(k) != approved_rules[k] for k in STRATEGY_KEYS):
            return False, "STRATEGY_CONFIG_NOT_APPROVED"
        if decision.get("verdict") != "PAPER_ACCEPT":
            return False, "PAPER_DECISION_NOT_ACCEPTED"
        if not live:
            return True, "H054-MOM2 local PAPER_ACCEPT (simulation only)"
        if decision.get("live_verdict") != "ACCEPT":
            return False, "LIVE_APPROVAL_MISSING"
        stamp = datetime.fromisoformat(decision["live_validated_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False, "LIVE_APPROVAL_DATE_INVALID"
        age = datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)
        if not timedelta(0) <= age <= timedelta(days=cfg["safety"].get("max_registry_age_days", 10)):
            return False, "LIVE_APPROVAL_EXPIRED_OR_FUTURE"
        central_ok, central_reason = live_accepted(
            max_age_days=cfg["safety"].get("max_registry_age_days", 10))
        if not central_ok:
            return False, central_reason
        return True, "H054-MOM2 local LIVE_ACCEPT + " + central_reason
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return False, "LOCAL_REGISTRY_UNAVAILABLE_OR_INVALID:" + type(exc).__name__
