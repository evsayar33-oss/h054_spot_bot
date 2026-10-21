import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np, pandas as pd, yaml
from bot import paper, plan, signal

cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text())
coins = cfg["strategy"]["assets"]

def test_signal():
    idx = pd.date_range("2020-01-01", periods=2600, freq="4h")
    up = {c: pd.Series(np.linspace(100, 300, len(idx)), idx) for c in coins}
    dn = {c: pd.Series(np.linspace(300, 100, len(idx)), idx) for c in coins}
    t_up = signal.targets(up, cfg["strategy"], "4h"); t_dn = signal.targets(dn, cfg["strategy"], "4h")
    assert all(0 < v <= 1 / len(coins) + 1e-9 for v in t_up.values()), t_up
    assert all(v == 0 for v in t_dn.values()), t_dn

def test_parity_with_quant_lab():
    """bot/signal.py must give the same exposure as quant_lab lab/core.py (fixture made by quant_lab
    tests/make_parity_fixture.py). If this fails, signal.py and quant_lab have drifted apart: do not trade live."""
    import json
    fx = json.loads((Path(__file__).resolve().parent / "fixtures" / "h054_parity.json").read_text())
    close = pd.Series(fx["close"], pd.date_range(fx["index_start"], periods=len(fx["close"]), freq="4h"))
    prm = fx["params"]
    c = {"sma_days": prm["sma_days"], "horizons_days": prm["horizons_days"], "vol_target": prm["target"],
         "vol_lookback_days": prm["lookback_days"]}
    e = signal.exposure(close, c, fx["ppy"])
    b = signal.apply_band(e, fx["band"])
    assert np.allclose(e.values, fx["exposure_raw"], atol=1e-9), "raw exposure differs from quant_lab"
    assert np.allclose(b.values, fx["exposure_band"], atol=1e-9), "banded exposure differs from quant_lab"
    # the bot's own config must be the same rule as the fixture (so a config edit cannot drift silently)
    s = cfg["strategy"]
    assert (s["sma_days"], s["horizons_days"], s["vol_target"], s["vol_lookback_days"], s["band"]) == \
        (prm["sma_days"], prm["horizons_days"], prm["target"], prm["lookback_days"], fx["band"]), "config.yaml differs from H054 rule"

def test_plan():
    h = {c: 0.25 for c in coins}
    tb = plan.target_book(1000, h, cfg["idle_arb"])
    tot = sum(tb["spot"].values()) + tb["perp_margin"]
    assert abs(tot - 1000) < 1e-6 or tot <= 1000 + 1e-6, tb
    od = plan.orders({}, tb, {c: 100.0 for c in coins}, 6, 0.6, 1000)
    assert od and sum(o["usdt"] for o in od) <= 0.6 * 1000 * 2 + 1e-6

def test_paper():
    pf = paper.new(1000, coins); px = {c: 100.0 for c in coins}
    tb = plan.target_book(1000, {c: 0.25 for c in coins}, cfg["idle_arb"])
    od = plan.orders(paper.holdings(pf, px), tb, px, 6, 1.0, 1000)
    paper.execute(pf, od, px, cfg["costs"], tb["perp_margin"])
    eq = paper.equity(pf, px)
    assert 990 < eq <= 1000, eq          # only costs lost
    paper.accrue_funding(pf, px, {c: 0.0001 for c in coins}, 8)
    assert paper.equity(pf, px) > eq     # short earns positive funding

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
