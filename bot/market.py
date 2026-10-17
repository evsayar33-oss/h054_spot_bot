"""Public Bitget data through ccxt (no key needed): closed 4h candles with enough history for the rule."""
from __future__ import annotations

import time

import pandas as pd

TF_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def closes(ex, symbols: list[str], timeframe: str = "4h", days: int = 420) -> dict[str, pd.Series]:
    out = {}
    now = int(time.time() * 1000)
    step = TF_MS[timeframe]
    for sym in symbols:
        since, rows = now - days * 86_400_000, []
        for _ in range(100):
            batch = ex.fetch_ohlcv(sym, timeframe, since=since, limit=200)
            if not batch:
                break
            rows += batch
            nxt = batch[-1][0] + step
            if nxt >= now or len(batch) < 2:
                break
            since = nxt
        df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "v"]).drop_duplicates("ts").sort_values("ts")
        df = df[df["ts"] + step <= now]                         # drop the bar that is still forming
        out[sym] = pd.Series(df["c"].astype(float).values, index=pd.to_datetime(df["ts"], unit="ms"))
    return out
