"""Deterministic, offline signal audit tests. No trades or exchange calls."""
import json
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from diagnostics import explain
from paper import weights, SYMBOLS, BAR, seed, tick


def prices(direction=1):
    # 1450 complete 4h candles, shared grid, realistic nonzero volatility.
    i = np.arange(1450)
    data = {}
    for n, sym in enumerate(SYMBOLS):
        arr = np.exp(direction * (0.00055 - n * 0.00006) * i +
                     0.024 * np.sin(i / (7 + n)) + 0.012 * np.cos(i / 13 + n))
        data[sym] = 100 * arr
    return pd.DataFrame(data, index=pd.date_range('2025-01-01', periods=len(i), freq='4h', tz='UTC'))


class DiagnosticTests(unittest.TestCase):
    def test_parity_with_original_strategy_uptrend(self):
        close = prices(1)
        report = explain(close, weights(close))
        self.assertTrue(report['actual_signal_parity'])
        self.assertTrue(report['signal_only'])
        self.assertEqual(set(report['assets']), set(SYMBOLS))
        self.assertEqual(set(report['shadow_alternative_signals_not_pnl']), {'20pp', '25pp'})
        json.dumps(report, allow_nan=False)

    def test_bear_regime_explained_as_cash(self):
        close = prices(-1)
        signal = weights(close)
        report = explain(close, signal)
        self.assertTrue(report['actual_signal_parity'])
        self.assertEqual(report['reason'], 'BTC_REGIME_OFF')
        self.assertTrue(all(value == 0 for value in signal.values()))

    def test_parity_drift_is_visible_not_silently_accepted(self):
        close = prices(1)
        original = weights(close)
        corrupted = {sym: 0.0 for sym in SYMBOLS}
        if all(v == 0 for v in original.values()):
            corrupted['BTC/USDT'] = 0.9
        report = explain(close, corrupted)
        self.assertFalse(report['actual_signal_parity'])
        self.assertEqual(report['reason'], 'TRACE_MISMATCH')

    def test_diagnostic_carried_into_new_tick_only(self):
        now = 200 * BAR
        state = seed(now)
        trace = {'reason': 'BTC_REGIME_OFF', 'signal_only': True}
        ob = {
            'candle_ms': now - BAR,
            'weights': {s: 0.0 for s in SYMBOLS},
            'quotes': {s: {'bid': 100.0, 'ask': 100.1} for s in SYMBOLS},
            'decision_trace': trace,
        }
        self.assertTrue(tick(state, now, ob))
        self.assertEqual(state['ticks'][0]['decision_trace'], trace)
        self.assertEqual(state['cash'], 10000.0)
        self.assertFalse(tick(state, now + 1000, ob))
        self.assertEqual(len(state['ticks']), 1)
        self.assertEqual(state['trades'], [])

    def test_invalid_history_fails_closed_for_diagnostic_only(self):
        with self.assertRaisesRegex(ValueError, 'TRACE_INVALID_HISTORY'):
            explain(prices().tail(100), {s: 0.0 for s in SYMBOLS})


if __name__ == '__main__':
    unittest.main()
