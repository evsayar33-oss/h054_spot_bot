"""One bot run (every closed 4h bar): signal -> kill switch -> target book -> orders -> log -> Telegram.

  python -m bot.main            uses config.yaml (mode paper by default)
  python -m bot.main --offline  no network: synthetic prices (for tests)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from bot import paper, plan, signal
from bot.notify import telegram

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "state.json"
PAPER = ROOT / "state" / "paper.json"
LOGS = ROOT / "logs"


def _read(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return default


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, default=str))


def _append(name: str, row: dict) -> None:
    LOGS.mkdir(exist_ok=True)
    path = LOGS / name
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def run(offline: bool = False) -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    sc = cfg["strategy"]
    coins = sc["assets"]
    live = cfg["mode"] == "live" and os.environ.get("LIVE_TRADING", "").lower() == "true"
    now = datetime.now(timezone.utc)

    # 1) closed candles + prices
    if offline:
        import numpy as np
        import pandas as pd
        idx = pd.date_range(end=now.replace(tzinfo=None, minute=0, second=0, microsecond=0), periods=2600, freq="4h")
        rng = np.random.default_rng(1)
        closes = {c: pd.Series(100 * (i + 1) * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(idx)))), idx) for i, c in enumerate(coins)}
        rates = {c: 0.0001 for c in coins}
        ex = None
    else:
        import ccxt
        from bot import market
        pub = ccxt.bitget({"enableRateLimit": True})
        closes = market.closes(pub, coins, sc["timeframe"])
        rates = {}
        for c in coins:
            try:
                rates[c] = float(pub.fetch_funding_rate(c + ":USDT").get("fundingRate") or 0.0)
            except Exception:  # noqa: BLE001
                rates[c] = 0.0
        ex = None
    px = {c: float(s.iloc[-1]) for c, s in closes.items()}
    bar = str(max(s.index[-1] for s in closes.values()))
    st = _read(STATE, {})
    if st.get("last_bar") == bar and not offline:
        print(f"[bot] bar {bar} already handled")
        return {"skipped": True}

    # 2) kill switch
    if offline:
        ok, why = True, "offline test"
    else:
        from bot.safety import approved
        ok, why = approved(cfg)

    # 3) targets (share of capital per coin for the H054 sleeve)
    h054 = signal.targets(closes, sc, sc["timeframe"]) if ok else {c: 0.0 for c in coins}
    idle_cfg = cfg["idle_arb"] if ok else {**cfg["idle_arb"], "enabled": False}

    # 4) current book
    if live:
        from bot import live as L
        ex = L.client()
        snap = L.snapshot(ex, coins, px)
        eq, cur = snap["equity"], snap["holdings"]
        if eq < cfg["safety"]["min_equity_usdt"]:
            telegram(f"⛔ h054 bot: bakiye {eq:.0f} USDT < {cfg['safety']['min_equity_usdt']} — işlem yok")
            return {"stopped": "low equity"}
    else:
        pf = _read(PAPER, None) or paper.new(cfg["paper_capital"], coins)
        hours = 4.0 if st.get("last_bar") else 0.0
        paper.accrue_funding(pf, px, rates, hours)
        eq, cur = paper.equity(pf, px), paper.holdings(pf, px)

    # 5) plan
    tb = plan.target_book(eq, h054, idle_cfg)
    od = plan.orders(cur, tb, px, cfg["safety"]["min_trade_usdt"], cfg["safety"]["max_turnover_per_run"], eq)

    # 6) execute
    if live:
        L.prepare_perp(ex, coins, int(cfg["idle_arb"].get("leverage", 1)))
        done = L.execute(ex, od, tb["perp_margin"], snap["swap_usdt"])
    else:
        done = paper.execute(pf, od, px, cfg["costs"], tb["perp_margin"])
        eq = paper.equity(pf, px)
        _write(PAPER, pf)

    # 7) log + notify
    mode = "LIVE" if live else "PAPER"
    for d in done:
        _append("trades.csv", {"time": now.isoformat(timespec="seconds"), "bar": bar, "mode": mode, "leg": d["leg"],
                               "symbol": d["symbol"], "side": d["side"], "usdt": d["usdt"],
                               "ok": d.get("ok", True), "error": d.get("error", "")})
    _append("equity.csv", {"time": now.isoformat(timespec="seconds"), "bar": bar, "mode": mode, "equity": round(eq, 2),
                           **{f"h054_{c.split('/')[0]}": round(v, 4) for c, v in h054.items()},
                           "idle": round(tb["idle"], 4), "hedge": round(tb["hedge_total"], 2), "approved": ok})
    prev_ok = st.get("approved", True)
    msg = []
    if not ok and prev_ok:
        msg.append(f"⛔ h054 bot DURDU: {why}. Tüm pozisyonlar kapatılıyor.")
    if ok and not prev_ok:
        msg.append(f"✅ h054 bot yeniden aktif: {why}")
    if done:
        msg.append(f"🤖 h054 bot [{mode}] bar {bar[:16]} · kasa {eq:,.2f} USDT")
        msg.append("Hedef: " + ", ".join(f"{c.split('/')[0]} %{v * 100:.0f}" for c, v in h054.items())
                   + f" · boşta %{tb['idle'] * 100:.0f} (arbitraj {tb['hedge_total']:,.0f} USDT)")
        msg += [f"• {d['leg']} {d['side']} {d['symbol']} {d['usdt']:,.2f} USDT" + ("" if d.get("ok", True) else f" ❌ {d.get('error')}")
                for d in done]
    day = now.date().isoformat()
    if now.hour >= 20 and st.get("summary_day") != day:
        msg.append(f"📊 h054 bot günlük [{mode}]: kasa {eq:,.2f} USDT · {why}")
        st["summary_day"] = day
    if msg:
        telegram("\n".join(msg))
    st.update(last_bar=bar, approved=ok, why=why, equity=round(eq, 2), updated_at=now.isoformat(timespec="seconds"),
              targets=h054)
    _write(STATE, st)
    return {"equity": eq, "orders": done, "targets": h054, "book": tb, "approved": ok}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    out = run(a.offline)
    print(json.dumps({k: v for k, v in out.items() if k != "orders"}, default=str, indent=1))
