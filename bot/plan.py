"""Turn target shares into concrete holdings and orders (pure arithmetic, no network: fully testable)."""
from __future__ import annotations


def target_book(equity: float, h054: dict[str, float], idle_cfg: dict) -> dict:
    """USDT targets: spot value per coin (H054 sleeve + arb hedge leg), perp short notional per coin,
    and the margin the perp account should hold."""
    coins = list(h054)
    used = sum(h054.values())
    idle = max(0.0, 1.0 - used)
    hedge_total = equity * idle * idle_cfg.get("hedge_share", 0.5) if idle_cfg.get("enabled") else 0.0
    per = hedge_total / len(coins) if coins else 0.0
    spot = {c: equity * h054[c] + per for c in coins}
    perp_short = {c: per for c in coins}
    margin = hedge_total / max(1.0, float(idle_cfg.get("leverage", 1)))
    return {"spot": spot, "perp_short": perp_short, "perp_margin": margin, "idle": idle, "hedge_total": hedge_total}


def orders(current: dict, target: dict, prices: dict[str, float], min_usdt: float, max_turnover: float,
           equity: float) -> list[dict]:
    """current/target: {"spot": {sym: usdt}, "perp_short": {sym: usdt}}. Sells and short-reductions first."""
    out = []
    for leg in ("spot", "perp_short"):
        for sym, tgt in target[leg].items():
            cur = current.get(leg, {}).get(sym, 0.0)
            d = tgt - cur
            if abs(d) < min_usdt:
                continue
            if leg == "spot":
                side = "buy" if d > 0 else "sell"
            else:                      # more short = sell the perp, less short = buy it back
                side = "sell" if d > 0 else "buy"
            out.append({"leg": leg, "symbol": sym, "side": side, "usdt": round(abs(d), 2),
                        "amount": abs(d) / prices[sym], "reduce": (leg == "spot" and d < 0) or (leg == "perp_short" and d < 0)})
    total = sum(o["usdt"] for o in out)
    if equity > 0 and total > max_turnover * equity:          # fat-finger guard: scale everything down
        f = max_turnover * equity / total
        for o in out:
            o["usdt"] = round(o["usdt"] * f, 2)
            o["amount"] *= f
            o["scaled"] = True
    out.sort(key=lambda o: (not o["reduce"], o["leg"]))      # reduce first (frees cash), then add
    return out
