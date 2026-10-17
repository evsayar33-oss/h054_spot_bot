"""H054 signal: exact copy of quant_lab lab/core.py (exposure "dual_trend_vt" + apply_band).
Exposure per coin in [0, 1], decided on CLOSED bars. Do not change without changing quant_lab too."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def bars(days: float, ppy: float) -> int:
    return max(2, int(round(days * ppy / 365.0)))


def ppy_of(index: pd.DatetimeIndex, timeframe: str) -> float:
    return {"1h": 24 * 365.25, "4h": 6 * 365.25, "1d": 365.25}.get(timeframe, 6 * 365.25)


def _vt(r, target, lookback_days, ppy):
    look = bars(lookback_days, ppy)
    vol = r.rolling(look, min_periods=look // 2).std() * math.sqrt(ppy)
    return (target / vol).clip(upper=1.0).fillna(0.0)


def _tsmom(close, horizons, ppy):
    sig = [(close / close.shift(bars(h, ppy)) - 1 > 0).astype(float) for h in horizons]
    return sum(sig) / len(sig)


def exposure(close: pd.Series, cfg: dict, ppy: float) -> pd.Series:
    r = close.pct_change(fill_method=None)
    n = bars(cfg["sma_days"], ppy)
    up = (close > close.rolling(n, min_periods=n).mean()).astype(float)
    e = up * (_tsmom(close, cfg["horizons_days"], ppy) > 0).astype(float) * _vt(r, cfg["vol_target"], cfg["vol_lookback_days"], ppy)
    return e.where(close.notna()).fillna(0.0).clip(0, 1)


def apply_band(e: pd.Series, band: float) -> pd.Series:
    if not band:
        return e
    v = e.to_numpy()
    out = np.empty_like(v)
    cur = 0.0
    for i, t in enumerate(v):
        if abs(t - cur) > band or (t == 0.0 and cur != 0.0):
            cur = t
        out[i] = cur
    return pd.Series(out, e.index)


def targets(closes: dict[str, pd.Series], cfg: dict, timeframe: str) -> dict[str, float]:
    """Share of TOTAL capital per coin for the H054 sleeve (equal capital per coin)."""
    out = {}
    for sym, c in closes.items():
        e = apply_band(exposure(c, cfg, ppy_of(c.index, timeframe)), cfg.get("band", 0.0))
        out[sym] = float(e.iloc[-1]) / len(closes)
    return out
