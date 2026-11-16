"""Read-only Bitget 4h Regime Band-30 forward PAPER. Never calls bot.main or live."""
from __future__ import annotations
import argparse
import json
import math
import time
import random
from pathlib import Path
import numpy as np
import pandas as pd

SYMBOLS=("BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT")
BAR=4*3600000
SCHEMA="h054.regime_band30.bitget.paper.v1"
COST=0.0015
INITIAL=10000.0


def weights(closes: pd.DataFrame) -> dict:
    """Port of quant_superlab H116 top2_btc_regime + H117 wide_band(0.30).

    Warm up with complete history so the band state is path dependent.
    """
    if len(closes)<1201 or closes.isna().any().any() or (closes<=0).any().any():
        raise ValueError("INSUFFICIENT_OR_GAPPED_WARMUP")
    returns=closes.pct_change(fill_method=None)
    vol=returns.rolling(180,min_periods=90).std()*math.sqrt(365.25*6)
    score=closes.pct_change(540,fill_method=None)
    above=closes>closes.rolling(1200,min_periods=1200).mean()
    votes=sum((closes>closes.shift(h*6)).astype(int) for h in (30,90,180))
    valid=(vol>1e-8)&above&(votes>=2)&score.notna()
    rank=score.where(valid).rank(axis=1,ascending=False,method="first")
    chosen=rank<=2
    regime=above["BTC/USDT"]&(score["BTC/USDT"]>0)
    raw=(0.40/vol).clip(upper=1).where(chosen,0).fillna(0)/2
    raw=raw.where(regime,0.)
    raw=raw.clip(lower=0,upper=1)
    # H116 banded first applies its original 10% band; H117 then applies 30%.
    def band(data,threshold):
        current=np.zeros(len(SYMBOLS))
        out=[]
        for row in data.to_numpy(dtype=float):
            change=(np.abs(row-current)>threshold)|((row==0)&(current!=0))
            current=np.where(change,row,current)
            out.append(current.copy())
        return pd.DataFrame(out,index=data.index,columns=data.columns)
    target=band(band(raw,0.10),0.30).iloc[-1].to_dict()
    if any(not math.isfinite(v) or v<0 for v in target.values()) or sum(target.values())>1.000001:
        raise ValueError("INVALID_TARGET")
    return {k:float(v) for k,v in target.items()}


def _fetch_retry(fn, *args, **kwargs):
    import ccxt
    for attempt in range(6):
        try:
            return fn(*args, **kwargs)
        except (ccxt.RateLimitExceeded, ccxt.DDoSProtection, ccxt.RequestTimeout, ccxt.NetworkError):
            if attempt == 5:
                raise
            time.sleep(min(45, 3 * 2**attempt) + random.uniform(0, 1))


def _repair_missing_candles(ex, sym, df):
    """Refetch only missing 4h timestamps from Bitget; never interpolate or substitute."""
    if df.empty or df.ts.duplicated().any():
        raise ValueError("DUPLICATE_OR_EMPTY_CANDLES:" + sym)
    missing = []
    timestamps = df.ts.to_numpy(dtype="int64")
    for left, right in zip(timestamps[:-1], timestamps[1:]):
        if right <= left or (right-left) % BAR:
            raise ValueError("UNALIGNED_CANDLE_GRID:" + sym)
        missing.extend(range(int(left)+BAR,int(right),BAR))
        if len(missing)>40:
            raise ValueError("TOO_MANY_MISSING_CANDLES:" + sym)
    if not missing:
        return df
    recovered={}
    for ts in missing:
        # Look around each missing candle. Bitget may exclude since boundary.
        for params in ({"useHistoryEndpoint":True}, {}):
            batch=_fetch_retry(ex.fetch_ohlcv,sym,"4h",
                               since=ts-3*BAR,limit=12,params=params)
            for row in batch:
                if int(row[0])==ts:
                    recovered[ts]=row
            if ts in recovered:
                break
            time.sleep(0.5)
    if set(recovered)!=set(missing):
        missing_left=sorted(set(missing)-set(recovered))
        raise ValueError(f"UNRECOVERABLE_BITGET_GAPS:{sym}:count={len(missing_left)}:first={missing_left[:4]}")
    repaired=pd.concat([df,pd.DataFrame(list(recovered.values()),columns=df.columns)],ignore_index=True)
    repaired=repaired.sort_values("ts").reset_index(drop=True)
    if repaired.ts.duplicated().any() or np.any(np.diff(repaired.ts.to_numpy(dtype="int64"))!=BAR):
        raise ValueError("REPAIR_FAILED_VALIDATION:"+sym)
    return repaired


def _fresh_orderbook_quotes(ex, symbols, clock_ms=None):
    """Fresh spot order-book top levels, gathered together AFTER the historical scan.

    Reject missing, crossed, stale, or delayed books. Never substitute candle close
    for executable bid/ask. A book lacking an exchange timestamp is conservatively
    rejected rather than mislabelled as fresh.
    """
    clock_ms=clock_ms or (lambda: int(time.time()*1000))
    result={}
    for sym in symbols:
        # A transient stale / missing book is not a valid fill price. Refresh
        # the *same* exchange order book up to three times; never replace it
        # with last candle close, another venue's price, or a synthetic quote.
        for attempt in range(3):
            started=clock_ms()
            book=_fetch_retry(ex.fetch_order_book,sym,limit=5)
            received=clock_ms()
            bids,asks=book.get("bids") or [],book.get("asks") or []
            stamp=book.get("timestamp")
            reason="MISSING_ORDERBOOK_QUOTE" if not bids or not asks or stamp is None else None
            if reason is None:
                bid,ask=float(bids[0][0]),float(asks[0][0])
                stamp=int(stamp)
                if (not math.isfinite(bid) or not math.isfinite(ask)
                    or bid<=0 or ask<bid or ask/bid>1.05
                    or received<started or received-started>60000
                    or received-stamp>120000 or stamp>received+30000):
                    reason="STALE_ORDERBOOK_QUOTE"
            if reason is None:
                result[sym]={"bid":bid,"ask":ask,"ts":stamp,"received_ms":received,
                             "source":"bitget_spot_orderbook"}
                break
            if attempt==2:
                raise ValueError(reason+":"+sym)
            time.sleep(1.5)
    # No artificial synchronous valuation from quotes taken minutes apart.
    if max(v["received_ms"] for v in result.values())-min(v["received_ms"] for v in result.values())>120000:
        raise ValueError("DESYNCHRONIZED_ORDERBOOKS")
    return result


def snapshot(now_ms):
    import ccxt
    ex=ccxt.bitget({"enableRateLimit":True,"timeout":20000})
    frames={}
    anchor=int(pd.Timestamp("2025-01-01",tz="UTC").timestamp()*1000)
    for sym in SYMBOLS:
        cursor=anchor
        rows=[]
        for _ in range(300):
            batch=_fetch_retry(ex.fetch_ohlcv,sym,"4h",since=cursor,limit=200)
            # Avoid bursts across four full-history Bitget spot requests.
            time.sleep(1.5)
            if not batch:break
            next_rows=[r for r in batch if int(r[0])>=cursor]
            if not next_rows:raise ValueError("NON_PROGRESSING_SOURCE:"+sym)
            rows.extend(next_rows)
            cursor=int(next_rows[-1][0])+BAR
            if cursor>now_ms-BAR:break
        else:raise ValueError("SOURCE_PAGE_LIMIT:"+sym)
        df=pd.DataFrame(rows,columns=["ts","o","h","l","c","v"])
        df=df.loc[df.ts+BAR<=now_ms].copy()
        if len(df)<1201:
            raise ValueError(f"INSUFFICIENT_WARMUP:{sym}:{len(df)}")
        df=_repair_missing_candles(ex,sym,df)
        if not np.isfinite(df[["o","h","l","c","v"]].to_numpy(float)).all() or (df.c<=0).any():
            raise ValueError("BAD_PRICES:"+sym)
        df.index=pd.to_datetime(df.pop("ts"),unit="ms",utc=True)
        frames[sym]=df
    if any(not frames[s].index.equals(frames[SYMBOLS[0]].index) for s in SYMBOLS):
        raise ValueError("MISALIGNED_CANDLES")
    last=int(frames[SYMBOLS[0]].index[-1].timestamp()*1000)
    if now_ms-(last+BAR)>BAR*2:raise ValueError("STALE_LAST_CANDLE")
    closes=pd.DataFrame({s:frames[s].c for s in SYMBOLS})
    target=weights(closes)
    quotes=_fresh_orderbook_quotes(ex,SYMBOLS)
    return {"candle_ms":last,"quotes":quotes,"weights":target}


def seed(now):
    return {"schema":SCHEMA,"start_ms":now,"end_ms":now+90*86400000,
            "last_candle_ms":None,"cash":INITIAL,"qty":{s:0. for s in SYMBOLS},
            "trades":[],"ticks":[],"outages":[],"finalized":False}


def tick(state,now,ob):
    if state["schema"]!=SCHEMA:raise ValueError("STATE_SCHEMA")
    if state["finalized"]:return False
    candle=ob["candle_ms"]
    if candle+BAR>now:raise ValueError("UNCLOSED_CANDLE")
    if state["last_candle_ms"] is not None and candle<=state["last_candle_ms"]:
        return False
    previous = state["last_candle_ms"]
    if previous is not None and candle - previous > BAR:
        if (candle - previous) % BAR:
            raise ValueError("UNALIGNED_OBSERVATION_GRID")
        # This is an audit finding, not a synthetic historical trade or outage.
        state.setdefault("continuity_gaps", []).append({
            "detected_ms": now,
            "first_missed_candle_ms": previous + BAR,
            "last_missed_candle_ms": candle - BAR,
            "count": (candle - previous) // BAR - 1,
        })
    quotes=ob["quotes"];target=ob["weights"]
    if set(target)!=set(SYMBOLS) or any(v<0 or not math.isfinite(v) for v in target.values()) or sum(target.values())>1+1e-8:
        raise ValueError("INVALID_EXPOSURE")
    cash=float(state["cash"]);qty=dict(state["qty"]);trades=[]
    nav=cash+sum(qty[s]*quotes[s]["bid"] for s in SYMBOLS)
    if nav<=0:raise ValueError("NONPOSITIVE_NAV")
    for s in SYMBOLS:
        bid=quotes[s]["bid"]
        current=qty[s]*bid;desired=nav*target[s]
        if current>desired+1e-7:
            notional=current-desired
            qty[s]-=notional/bid
            cash+=notional*(1-COST)
            trades.append({"asset":s,"side":"sell","usdt":notional,"px":bid})
    for s in SYMBOLS:
        bid,ask=quotes[s]["bid"],quotes[s]["ask"]
        desired=nav*target[s];current=qty[s]*bid
        spend=min(max(0.,desired-current),cash/(1+COST))
        if spend>1e-7:
            qty[s]+=spend/ask
            cash-=spend*(1+COST)
            trades.append({"asset":s,"side":"buy","usdt":spend,"px":ask})
    if cash< -1e-6:raise ValueError("NEGATIVE_CASH")
    nav=cash+sum(qty[s]*quotes[s]["bid"] for s in SYMBOLS)
    state.update(cash=cash,qty=qty,last_candle_ms=candle)
    state["trades"].extend({"observed_ms":now,**t} for t in trades)
    state["ticks"].append({"observed_ms":now,"candle_ms":candle,
                            "nav":nav,"weights":target,"quotes":quotes,"trades":len(trades)})
    if now>=state["end_ms"]:state["finalized"]=True
    return True


def run(mode,state_path,out,now=None,snapshot_fn=snapshot):
    now=int(time.time()*1000) if now is None else now
    if mode=="start":
        if state_path.exists():
            state=json.loads(state_path.read_text())  # idempotent start; never reset the ledger
        else:
            state=seed(now)
    elif mode=="tick":
        if not state_path.exists():return None
        state=json.loads(state_path.read_text())
    else:raise ValueError("INVALID_MODE")
    if state["schema"]!=SCHEMA:raise ValueError("STATE_SCHEMA")
    if state["finalized"]:return state
    try:
        tick(state,now,snapshot_fn(now))
    except Exception as exc:
        state["outages"].append({"observed_ms":now,"error":type(exc).__name__,
                                 "message":str(exc)[:150]})
    state_path.parent.mkdir(parents=True,exist_ok=True)
    state_path.write_text(json.dumps(state,indent=2,sort_keys=True,allow_nan=False)+"\n")
    out.mkdir(parents=True,exist_ok=True)
    nav=state["ticks"][-1]["nav"] if state["ticks"] else INITIAL
    current_candle = state["last_candle_ms"]
    expected_candle = (now // BAR) * BAR - BAR
    lag_bars = max(0, (expected_candle - current_candle) // BAR) if current_candle is not None else None
    new_gaps = [g for g in state.get("continuity_gaps", []) if g["detected_ms"] == now]
    summary={"schema":SCHEMA,"venue":"Bitget spot","paper_only":True,
             "run_ms":now,
             "last_candle_ms":current_candle,"expected_candle_ms":expected_candle,
             "lag_bars":lag_bars,"new_gap_count":sum(g["count"] for g in new_gaps),
             "total_recorded_gaps":sum(g["count"] for g in state.get("continuity_gaps", [])),
             "started_ms":state["start_ms"],"ends_ms":state["end_ms"],
             "nav":nav,"return_pct":100*(nav/INITIAL-1),
             "observations":len(state["ticks"]),"trades":len(state["trades"]),
             "outages":len(state["outages"]),"finalized":state["finalized"],
             "healthy":bool(state["ticks"]) and state["ticks"][-1]["observed_ms"]==now and lag_bars==0 and not new_gaps,
             "last_error":state["outages"][-1] if state["outages"] and (not state["ticks"] or state["outages"][-1]["observed_ms"]>=state["ticks"][-1]["observed_ms"]) else None}
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary))
    return state


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["start","tick"],required=True)
    p.add_argument("--state",default="results/regime_band30/state.json")
    p.add_argument("--out",default="results/regime_band30/report")
    a=p.parse_args()
    run(a.mode,Path(a.state),Path(a.out))
