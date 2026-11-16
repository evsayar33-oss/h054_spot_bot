import unittest
from scripts.telegram_paper_report import message

class TelegramPaperTests(unittest.TestCase):
    def test_no_new_event(self):
        self.assertIsNone(message({"ticks": [], "outages": [{"observed_ms": 100, "error": "old"}]}, {}, now_ms=2000000))
    def test_new_tick(self):
        state = {"ticks": [{"observed_ms": 100000, "candle_ms": 0}], "outages": [],
                 "trades": [{"observed_ms": 100000, "side": "buy", "asset": "BTC/USDT", "usdt": 50, "px": 100}]}
        result = message(state, {"observations": 1, "trades": 1, "nav": 9999, "return_pct": -.01}, now_ms=100001)
        self.assertIn("BUY BTC/USDT", result)
    def test_old_outages_ignored(self):
        state = {"ticks": [{"observed_ms": 100000, "candle_ms": 0}], "outages": [{"observed_ms": 1, "error": "old"}], "trades": []}
        self.assertIn("4h mum", message(state, {"nav": 10000}, now_ms=100001))

if __name__ == "__main__":
    unittest.main()
