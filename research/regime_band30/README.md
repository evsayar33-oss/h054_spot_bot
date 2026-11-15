# Bitget Regime Band-30 PAPER (separate from H054 production)

This is a **read-only, 90-day prospective PAPER** companion to the current H054-MOM2 bot. It never imports or calls bot.main, bot.live, the production state files or the funding-arbitrage module. It cannot place real orders, even if LIVE_TRADING=true.

The signal ports quant_superlab H116 top2_btc_regime and H117 regime_band30 exactly in sequence: BTC SMA200 and positive 90-day regime; four-asset momentum majority vote, 200-day SMA, top two by 90-day score, 40% annual volatility targeting, H116 10-percentage-point band followed by H117 30-percentage-point band. All decisions use fully closed 4h candles.

After merge, Actions → Regime Band-30 — Bitget independent PAPER → Run workflow → main, mode **start** once. Later ticks run at UTC 00:25, 04:25, 08:25, 12:25, 16:25, 20:25. State persists to **paper/regime-band30-bitget** (orphan branch), never main. Each run publishes summary.json. If no market data are available, record an outage and skip fills; no backfilling.

Virtual initial capital 10,000 USDT, Bitget spot fresh bid/ask snapshots, 15bp assumed extra cost per traded side, no leverage, shorts, funding, or real fills. The H054 production bot remains unchanged. Do not treat this PAPER account as equivalent to H054's full funding-arbitrage portfolio or as proof of actual exchange execution.
