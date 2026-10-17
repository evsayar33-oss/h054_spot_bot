"""Virtual portfolio for paper mode: same plan, fills at the last close with fees and slippage,
perp short marked to market, funding accrued from the public Bitget funding rate."""
from __future__ import annotations


def new(capital: float, coins: list[str]) -> dict:
    return {"usdt": capital, "spot": {c: 0.0 for c in coins}, "perp": {c: {"qty": 0.0, "entry": 0.0} for c in coins},
            "perp_cash": 0.0, "funding_paid": 0.0, "fees_paid": 0.0}


def equity(pf: dict, px: dict) -> float:
    spot = sum(q * px[c] for c, q in pf["spot"].items())
    unreal = sum(p["qty"] * (p["entry"] - px[c]) for c, p in pf["perp"].items())
    return pf["usdt"] + spot + pf["perp_cash"] + unreal


def holdings(pf: dict, px: dict) -> dict:
    return {"spot": {c: q * px[c] for c, q in pf["spot"].items()},
            "perp_short": {c: p["qty"] * px[c] for c, p in pf["perp"].items()}}


def accrue_funding(pf: dict, px: dict, rates: dict, hours: float) -> float:
    """Short perp RECEIVES positive funding (8h settlement)."""
    got = sum(p["qty"] * px[c] * rates.get(c, 0.0) * hours / 8.0 for c, p in pf["perp"].items())
    pf["perp_cash"] += got
    pf["funding_paid"] -= got
    return got


def execute(pf: dict, orders: list[dict], px: dict, costs: dict, target_margin: float) -> list[dict]:
    done = []
    for o in orders:
        c, usdt = o["symbol"], o["usdt"]
        if o["leg"] == "spot":
            fee = usdt * (costs["spot_fee"] + costs["slippage"])
            q = usdt / px[c]
            if o["side"] == "buy":
                usdt = min(usdt, max(0.0, pf["usdt"] - fee))
                q = usdt / px[c]
                pf["usdt"] -= usdt + fee
                pf["spot"][c] += q
            else:
                q = min(q, pf["spot"][c])
                pf["spot"][c] -= q
                pf["usdt"] += q * px[c] - fee
        else:
            fee = usdt * (costs["perp_fee"] + costs["slippage"])
            p = pf["perp"][c]
            q = usdt / px[c]
            if o["side"] == "sell":                      # add to the short
                p["entry"] = (p["entry"] * p["qty"] + px[c] * q) / (p["qty"] + q) if p["qty"] + q > 0 else 0.0
                p["qty"] += q
            else:                                         # buy back: realize PnL on the closed part
                q = min(q, p["qty"])
                pf["perp_cash"] += q * (p["entry"] - px[c])
                p["qty"] -= q
                if p["qty"] <= 1e-12:
                    p["qty"], p["entry"] = 0.0, 0.0
            pf["perp_cash"] -= fee
        pf["fees_paid"] += fee
        done.append({**o, "fill_px": px[c], "fee": round(fee, 4)})
    # keep the perp account at its target margin (paper transfer, free)
    move = target_margin - pf["perp_cash"]
    move = max(-pf["perp_cash"], min(move, pf["usdt"]))
    pf["perp_cash"] += move
    pf["usdt"] -= move
    return done
