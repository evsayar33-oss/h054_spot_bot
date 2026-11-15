import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from paper import BAR, INITIAL, SYMBOLS, run, seed, tick, weights, SIGNAL_VERSION, _repair_missing_candles, _fresh_orderbook_quotes
import numpy as np
import pandas as pd


def snap(now):
    weights={s:0. for s in SYMBOLS}
    weights[SYMBOLS[0]]=0.4
    return {"candle_ms":now-BAR,
            "weights":weights,
            "quotes":{s:{"bid":100.,"ask":100.2,"ts":now-1000} for s in SYMBOLS}}


class PaperTests(unittest.TestCase):
    def test_buy_spread_fee_and_no_duplicate(self):
        t=200*BAR;s=seed(t)
        self.assertTrue(tick(s,t,snap(t)))
        self.assertLess(s["ticks"][-1]["nav"],INITIAL)
        self.assertGreaterEqual(s["cash"],0)
        self.assertFalse(tick(s,t+1000,snap(t)))
        self.assertEqual(len(s["ticks"]),1)

    def test_full_exit_and_no_leverage(self):
        t=200*BAR;s=seed(t);tick(s,t,snap(t))
        x=snap(t+BAR);x["weights"][SYMBOLS[0]]=0.
        tick(s,t+BAR,x)
        self.assertAlmostEqual(s["qty"][SYMBOLS[0]],0.)
        x=snap(t+2*BAR);x["weights"][SYMBOLS[0]]=1.1
        with self.assertRaisesRegex(ValueError,"INVALID_EXPOSURE"):
            tick(s,t+2*BAR,x)

    def test_network_failure_preserves_state_and_idempotent_restart(self):
        t=200*BAR
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.json";out=Path(d)/"out"
            def bad(_):raise TimeoutError("offline")
            state=run("start",path,out,now=t,snapshot_fn=bad)
            self.assertEqual(len(state["outages"]),1)
            restarted=run("start",path,out,now=t+BAR,snapshot_fn=snap)
            self.assertEqual(restarted["start_ms"],t)
            self.assertEqual(len(restarted["ticks"]),1)
            state=run("tick",path,out,now=t+BAR,snapshot_fn=snap)
            self.assertEqual(len(state["ticks"]),1)

    def test_exact_gap_recovery_only(self):
        ts=[i*BAR for i in (1,2,4,5)]
        rows=[[x,100,101,99,100,1] for x in ts]
        df=pd.DataFrame(rows,columns=["ts","o","h","l","c","v"])
        class Fake:
            def fetch_ohlcv(self,sym,tf,since,limit,params):
                return [[3*BAR,100,101,99,100,1]]
        repaired=_repair_missing_candles(Fake(),"BTC/USDT",df)
        self.assertEqual(repaired.ts.tolist(),[i*BAR for i in (1,2,3,4,5)])

    def test_missing_gap_never_interpolated(self):
        ts=[i*BAR for i in (1,2,4)]
        df=pd.DataFrame([[x,100,101,99,100,1] for x in ts],
                        columns=["ts","o","h","l","c","v"])
        class Fake:
            def fetch_ohlcv(self,*args,**kwargs): return []
        with self.assertRaisesRegex(ValueError,"UNRECOVERABLE_BITGET_GAPS"):
            _repair_missing_candles(Fake(),"BTC/USDT",df)

    def test_fresh_books_without_ticker_timestamp(self):
        class Exchange:
            def fetch_order_book(self,sym,limit):
                return {"bids":[[100.,2.]],"asks":[[100.1,2.]],"timestamp":1000000}
        q=_fresh_orderbook_quotes(Exchange(),SYMBOLS,clock_ms=lambda:1001000)
        self.assertEqual(set(q),set(SYMBOLS))
        self.assertTrue(all(x["source"]=="bitget_spot_orderbook" for x in q.values()))

    def test_missing_stale_and_crossed_book_fail_closed(self):
        class Exchange:
            book={}
            def fetch_order_book(self,sym,limit):return self.book
        e=Exchange()
        for book in (
            {"bids":[[100,1]],"asks":[[101,1]],"timestamp":None},
            {"bids":[[100,1]],"asks":[[101,1]],"timestamp":100000},
            {"bids":[[101,1]],"asks":[[100,1]],"timestamp":1000000},
        ):
            e.book=book
            with self.assertRaisesRegex(ValueError,"ORDERBOOK_QUOTE"):
                _fresh_orderbook_quotes(e,SYMBOLS,clock_ms=lambda:1001000)

    def test_corrected_band_can_enter_positions(self):
        # BTC alone has positive regime, 90d momentum and SMA200.
        # SOL, ETH, BNB stay below SMA200; BTC target must not be
        # annihilated by the impossible old 30pp outer band.
        idx=pd.date_range("2025-01-01",periods=1350,freq="4h")
        btc=100*np.exp(np.linspace(0,0.9,len(idx)) +
                       0.008*np.sin(np.arange(len(idx))*0.29))
        closes=pd.DataFrame({SYMBOLS[0]:btc,
             SYMBOLS[1]:np.linspace(300,100,len(idx)),
             SYMBOLS[2]:np.linspace(300,100,len(idx)),
             SYMBOLS[3]:np.linspace(300,100,len(idx))},index=idx)
        target=weights(closes)
        self.assertGreater(target[SYMBOLS[0]],0.0)
        self.assertLessEqual(sum(target.values()),1.)

    def test_old_unversioned_flat_state_migrates_on_new_bar(self):
        t=200*BAR;s=seed(t)
        tick(s,t,snap(t))
        s.pop("signal_version")
        s["qty"]={sym:0. for sym in SYMBOLS}
        s["cash"]=INITIAL
        s["trades"]=[]
        tick(s,t+BAR,snap(t+BAR))
        self.assertEqual(s["signal_version"],SIGNAL_VERSION)

    def test_legacy_traded_ledger_is_not_silently_migrated(self):
        t=200*BAR
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.json"
            s=seed(t)
            s["trades"]=[{"asset":SYMBOLS[0]}]
            import json
            path.write_text(json.dumps(s))
            with self.assertRaisesRegex(ValueError,"LEGACY_LEDGER_HAS_TRADES"):
                run("tick",path,Path(d)/"out",now=t+BAR,snapshot_fn=snap)


if __name__=="__main__":unittest.main()
