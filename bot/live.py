"""Live Bitget account through ccxt (spot + USDT-M perpetual, isolated 1x short for the hedge).
Only used when config mode: live AND the repository variable LIVE_TRADING is "true"."""
from __future__ import annotations

import os


def client():
    import ccxt
    return ccxt.bitget({"apiKey": os.environ["BITGET_API_KEY"], "secret": os.environ["BITGET_API_SECRET"],
                        "password": os.environ["BITGET_PASSPHRASE"], "enableRateLimit": True,
                        "options": {"defaultType": "spot"}})


def perp_symbol(sym: str) -> str:
    return sym + ":USDT"          # BTC/USDT -> BTC/USDT:USDT (linear perpetual)


def snapshot(ex, coins: list[str], px: dict) -> dict:
    sb = ex.fetch_balance({"type": "spot"})
    fb = ex.fetch_balance({"type": "swap"})
    spot_qty = {c: float(sb.get(c.split("/")[0], {}).get("total") or 0.0) for c in coins}
    usdt = float(sb.get("USDT", {}).get("total") or 0.0)
    swap_usdt = float(fb.get("USDT", {}).get("total") or 0.0)      # includes unrealized PnL
    shorts = {c: 0.0 for c in coins}
    for p in ex.fetch_positions([perp_symbol(c) for c in coins]):
        c = p["symbol"].split(":")[0]
        if c in shorts and p.get("side") == "short":
            shorts[c] = abs(float(p.get("contracts") or 0.0)) * float(p.get("contractSize") or 1.0)
    eq = usdt + sum(spot_qty[c] * px[c] for c in coins) + swap_usdt
    return {"equity": eq, "usdt": usdt, "swap_usdt": swap_usdt,
            "holdings": {"spot": {c: spot_qty[c] * px[c] for c in coins},
                         "perp_short": {c: shorts[c] * px[c] for c in coins}}}


def prepare_perp(ex, coins: list[str], leverage: int) -> None:
    for c in coins:
        s = perp_symbol(c)
        for fn, args in (("set_margin_mode", ("isolated", s, {"marginCoin": "USDT"})),
                         ("set_leverage", (leverage, s, {"marginCoin": "USDT"}))):
            try:
                getattr(ex, fn)(*args)
            except Exception as e:  # noqa: BLE001 - already set / not needed
                print(f"[live] {fn} {s}: {e}")


def execute(ex, orders: list[dict], target_margin: float, swap_usdt: float) -> list[dict]:
    done = []
    ex.load_markets()
    for o in [x for x in orders if x["reduce"]]:          # 1) reduce first: frees cash / margin
        done.append(_one(ex, o))
    try:                                                   # 2) margin: move surplus back, top up when short grows
        swap_usdt = float(ex.fetch_balance({"type": "swap"}).get("USDT", {}).get("free") or swap_usdt)
        extra = swap_usdt - target_margin * 1.05
        if extra > 5:
            ex.transfer("USDT", round(extra, 2), "swap", "spot")
        need = target_margin - swap_usdt
        if need > 1:
            ex.transfer("USDT", round(need * 1.02, 2), "spot", "swap")
    except Exception as e:  # noqa: BLE001
        print(f"[live] transfer failed: {e}")
    for o in [x for x in orders if not x["reduce"]]:      # 3) add positions
        done.append(_one(ex, o))
    return done


def _one(ex, o: dict) -> dict:
    try:
        if o["leg"] == "spot":
            if o["side"] == "buy":
                r = ex.create_market_buy_order_with_cost(o["symbol"], round(o["usdt"], 2))
            else:
                r = ex.create_order(o["symbol"], "market", "sell", float(ex.amount_to_precision(o["symbol"], o["amount"])))
        else:
            s = perp_symbol(o["symbol"])
            amt = float(ex.amount_to_precision(s, o["amount"]))
            params = {"marginMode": "isolated"}
            if o["side"] == "buy":
                params["reduceOnly"] = True
            r = ex.create_order(s, "market", o["side"], amt, None, params)
        return {**o, "ok": True, "id": r.get("id")}
    except Exception as e:  # noqa: BLE001 - one failed order must not stop the others
        return {**o, "ok": False, "error": str(e)[:200]}
