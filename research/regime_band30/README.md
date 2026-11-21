# Bitget Regime Band-30 PAPER (separate from H054 production)

This is a **read-only, 90-day prospective PAPER** companion to the current H054-MOM2 bot. It never imports or calls bot.main, bot.live, the production state files or the funding-arbitrage module. It cannot place real orders, even if LIVE_TRADING=true.

The signal ports quant_superlab H116 top2_btc_regime and H117 regime_band30 exactly in sequence: BTC SMA200 and positive 90-day regime; four-asset momentum majority vote, 200-day SMA, top two by 90-day score, 40% annual volatility targeting, H116 10-percentage-point band followed by H117 30-percentage-point band. All decisions use fully closed 4h candles.

After merge, Actions → Regime Band-30 — Bitget independent PAPER → Run workflow → main, mode **start** once. Later ticks run at UTC 00:25, 04:25, 08:25, 12:25, 16:25, 20:25. State persists to **paper/regime-band30-bitget** (orphan branch), never main. Each run publishes summary.json. If no market data are available, record an outage and skip fills; no backfilling.

Virtual initial capital 10,000 USDT, Bitget spot fresh bid/ask snapshots, 15bp assumed extra cost per traded side, no leverage, shorts, funding, or real fills. The H054 production bot remains unchanged. Do not treat this PAPER account as equivalent to H054's full funding-arbitrage portfolio or as proof of actual exchange execution.

## Prospective signal decision diagnostics (research only)

Every *new* confirmed 4h PAPER observation now carries an optional
`decision_trace` alongside the unchanged `weights`, `quotes` and `nav`.
The trace reports BTC regime conditions, 90-day score, annualized volatility,
200-day SMA test, 30/90/180-day momentum votes, top-two eligibility, raw
targets, H116 10-percentage-point band and H117 30-percentage-point band.
`reason` identifies why the existing signal stays in cash, e.g.
`BTC_REGIME_OFF`, `NO_ELIGIBLE_ASSETS` or `H117_BAND_30_BLOCKED`.
The independent diagnostic calculation checks exact parity with the *existing*
`weights()` result; a mismatch is visible, never used to change a trade.

The report/summary.json includes the most recent decision trace. Telegram adds
one concise reason on a **new** no-trade observation, without changing the
existing duplicate-message protection. Older observations are not backfilled
or relabelled. If diagnostic computation fails, the original PAPER observation
continues, with a visible `TRACE_UNAVAILABLE` marker.

The same closed candles produce **signal-only**, **not executed** 20pp and 25pp
shadow alternative band results under
`shadow_alternative_signals_not_pnl`. These are not portfolio accounts, fills,
NAV, profitability evidence or a recommendation to loosen filters. An actual
candidate promotion requires separate cost-aware, no-lookahead historical
testing AND prospective out-of-sample PAPER evaluation. H054-MOM2, funding
arbitrage, original Band-30 trading weights, ledger start date, and current
90-day PAPER window are unchanged.

Existing GitHub cron: 05/25/45 each hour; GitHub external repository dispatch
(and H054 workflow completion) can also trigger checks. Closed candles are
deduplicated by `tick()`. The independent external scheduler is configured
outside this repository; no secret is included here.
