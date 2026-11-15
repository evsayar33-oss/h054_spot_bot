# Bitget Regime Band-30 PAPER (separate from H054 production)

This is a **read-only, 90-day prospective PAPER** companion to the current H054-MOM2 bot. It never imports or calls bot.main, bot.live, the production state files or the funding-arbitrage module. It cannot place real orders, even if LIVE_TRADING=true.

The signal ports quant_superlab H116 top2_btc_regime and H117 regime_band30 exactly in sequence: BTC SMA200 and positive 90-day regime; four-asset momentum majority vote, 200-day SMA, top two by 90-day score, 40% annual volatility targeting, H116 10-percentage-point band followed by H117 30-percentage-point band. All decisions use fully closed 4h candles.

After merge, Actions → Regime Band-30 — Bitget independent PAPER → Run workflow → main, mode **start** once. Later ticks run at UTC 00:25, 04:25, 08:25, 12:25, 16:25, 20:25. State persists to **paper/regime-band30-bitget** (orphan branch), never main. Each run publishes summary.json. If no market data are available, record an outage and skip fills; no backfilling.

Virtual initial capital 10,000 USDT, Bitget spot fresh bid/ask snapshots, 15bp assumed extra cost per traded side, no leverage, shorts, funding, or real fills. The H054 production bot remains unchanged. Do not treat this PAPER account as equivalent to H054's full funding-arbitrage portfolio or as proof of actual exchange execution.

## Critical H117 validity correction (2026-11-15)

Original H117 `regime_band30` adds a 0.30 **absolute allocation-point** band to a 2-of-4 rotation with maximum 0.20 per-asset target. Starting from cash, its 30pp outer band cannot enter positions. As a result, the historical claim of +266.878% for that exact label is inconsistent with the code and must **not** be used to advertise this system. The present `regime_relative30_v2` uses a **relative** 30% change threshold, with zero-exposure exits permitted. It is **a new experimental strategy**, not a verified historical winner; run independent archived-data backtests before any LIVE consideration.

Only empty/no-trade legacy paper state is eligible for v2 continuation. State contains signal_version and summary reports historical_returns_not_transferable. The prior single zero-trade observation is retained for provenance, not counted as v2 performance evidence. No live orders or promotion.
