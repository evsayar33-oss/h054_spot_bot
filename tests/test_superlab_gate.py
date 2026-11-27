from datetime import datetime, timedelta, timezone
from bot.superlab_gate import live_accepted

NOW = datetime(2026, 11, 27, tzinfo=timezone.utc)

def registry(**changes):
    decision = {"for_system": "h054_spot_bot", "verdict": "ACCEPT",
                "validated_at": (NOW - timedelta(days=1)).isoformat()}
    decision.update(changes)
    return {"hypotheses": {"H054": decision}}

def test_requires_fresh_matching_accept():
    assert live_accepted(registry=registry(), now=NOW)[0]
    assert live_accepted(registry=registry(verdict="WATCH"), now=NOW) == (False, "SUPERLAB_ACCEPT_MISSING")
    assert live_accepted(registry=registry(for_system="other"), now=NOW) == (False, "SUPERLAB_SYSTEM_MISMATCH")
    old = (NOW - timedelta(days=11)).isoformat()
    assert live_accepted(registry=registry(validated_at=old), now=NOW) == (False, "SUPERLAB_ACCEPT_EXPIRED_OR_FUTURE")

def test_malformed_registry_fails_closed():
    ok, reason = live_accepted(registry={}, now=NOW)
    assert not ok and reason.startswith("SUPERLAB_REGISTRY_UNAVAILABLE_OR_INVALID:")
