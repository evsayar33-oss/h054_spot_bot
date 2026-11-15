import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from paper import BAR, INITIAL, SYMBOLS, run, seed, tick, _repair_missing_candles
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


if __name__=="__main__":unittest.main()
