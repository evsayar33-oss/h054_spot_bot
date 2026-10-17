"""Kill switch: trade only while quant_lab still says ACCEPT for H054 (and the decision is fresh)."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone


def approved(cfg: dict) -> tuple[bool, str]:
    s = cfg["safety"]
    try:
        with urllib.request.urlopen(s["quant_lab_registry"], timeout=20) as r:
            reg = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001 - no registry -> do NOT trade (fail-safe)
        return False, f"quant_lab kaydı okunamadı: {e}"
    h = reg.get("hypotheses", {}).get(s["hypothesis"])
    if not h:
        return False, f"{s['hypothesis']} kayıtta yok"
    if h.get("verdict") != "ACCEPT":
        return False, f"{s['hypothesis']} kararı {h.get('verdict')}"
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(h["validated_at"])
    except Exception:  # noqa: BLE001
        return False, "doğrulama tarihi okunamadı"
    if age > timedelta(days=s.get("max_registry_age_days", 10)):
        return False, f"karar {age.days} günlük (eski)"
    return True, f"{s['hypothesis']} ACCEPT ({age.days} gün önce doğrulandı)"
