"""Signal-only explainability for Regime Band-30; no state, orders, or fills.

This deliberately reconstructs the *existing* decision path independently, so
an audit can detect formula drift by comparing it to paper.weights().
Shadow bands are illustrative signals, not PAPER fills or P&L.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

SYMBOLS = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT")


def _band(data: pd.DataFrame, threshold: float) -> pd.DataFrame:
    current = np.zeros(len(SYMBOLS))
    out = []
    for row in data.to_numpy(dtype=float):
        change = (np.abs(row - current) > threshold) | ((row == 0) & (current != 0))
        current = np.where(change, row, current)
        out.append(current.copy())
    return pd.DataFrame(out, index=data.index, columns=data.columns)


def _number(value):
    value = float(value)
    return value if math.isfinite(value) else None


def explain(closes: pd.DataFrame, actual_weights: dict) -> dict:
    """Explain latest fully closed candle without modifying its trade signal.

    No additional exchange requests. All history-dependent bands are replayed
    from the same full OHLC close window as the existing strategy.
    """
    if tuple(closes.columns) != SYMBOLS or len(closes) < 1201:
        raise ValueError("TRACE_INVALID_HISTORY")
    if closes.isna().any().any() or (closes <= 0).any().any():
        raise ValueError("TRACE_BAD_CLOSES")

    returns = closes.pct_change(fill_method=None)
    vol = returns.rolling(180, min_periods=90).std() * math.sqrt(365.25 * 6)
    score = closes.pct_change(540, fill_method=None)
    above = closes > closes.rolling(1200, min_periods=1200).mean()
    votes = sum((closes > closes.shift(h * 6)).astype(int) for h in (30, 90, 180))
    valid = (vol > 1e-8) & above & (votes >= 2) & score.notna()
    rank = score.where(valid).rank(axis=1, ascending=False, method="first")
    chosen = rank <= 2
    regime = above["BTC/USDT"] & (score["BTC/USDT"] > 0)
    raw = (0.40 / vol).clip(upper=1).where(chosen, 0).fillna(0) / 2
    raw = raw.where(regime, 0.0).clip(lower=0, upper=1)
    h116 = _band(raw, 0.10)
    current = _band(h116, 0.30)
    alternatives = {"20pp": _band(h116, 0.20), "25pp": _band(h116, 0.25)}

    expected = current.iloc[-1]
    match = set(actual_weights) == set(SYMBOLS) and all(
        math.isfinite(float(actual_weights[s])) and
        abs(float(actual_weights[s]) - float(expected[s])) < 1e-10 for s in SYMBOLS
    )
    latest = {}
    for sym in SYMBOLS:
        latest[sym] = {
            "close": _number(closes[sym].iloc[-1]),
            "ret_90d": _number(score[sym].iloc[-1]),
            "annualized_vol": _number(vol[sym].iloc[-1]),
            "above_sma200": bool(above[sym].iloc[-1]),
            "momentum_votes": int(votes[sym].iloc[-1]),
            "eligible": bool(valid[sym].iloc[-1]),
            "top_two": bool(chosen[sym].iloc[-1]),
            "preband_weight": float(raw[sym].iloc[-1]),
            "after_10pp_weight": float(h116[sym].iloc[-1]),
            "final_30pp_weight": float(expected[sym]),
        }
    if not match:
        reason = "TRACE_MISMATCH"
    elif any(float(actual_weights[s]) > 0 for s in SYMBOLS):
        reason = "POSITION_TARGETS_ACTIVE"
    elif not bool(regime.iloc[-1]):
        reason = "BTC_REGIME_OFF"
    elif not any(bool(chosen[s].iloc[-1]) for s in SYMBOLS):
        reason = "NO_ELIGIBLE_ASSETS"
    elif not (raw.iloc[-1] > 0).any():
        reason = "NO_POSITIVE_RAW_TARGET"
    elif not (h116.iloc[-1] > 0).any():
        reason = "H116_BAND_10_BLOCKED"
    elif not (current.iloc[-1] > 0).any():
        reason = "H117_BAND_30_BLOCKED"
    else:
        reason = "UNCLASSIFIED_CASH"

    return {
        "version": 1,
        "signal_only": True,
        "candle_ms": int(closes.index[-1].timestamp() * 1000),
        "reason": reason,
        "actual_signal_parity": bool(match),
        "btc_regime_on": bool(regime.iloc[-1]),
        "btc_positive_90d": bool(score["BTC/USDT"].iloc[-1] > 0),
        "btc_above_sma200": bool(above["BTC/USDT"].iloc[-1]),
        "historical_btc_regime_on_last_30_bars": int(regime.tail(30).sum()),
        "assets": latest,
        "shadow_alternative_signals_not_pnl": {
            name: {sym: float(df[sym].iloc[-1]) for sym in SYMBOLS}
            for name, df in alternatives.items()
        },
    }
