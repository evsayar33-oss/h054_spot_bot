import io
import socket
import unittest
import urllib.error
from unittest.mock import patch
from scripts.telegram_paper_report import message, send_telegram

class TelegramPaperTests(unittest.TestCase):
    def test_no_new_event(self):
        self.assertIsNone(message({"ticks": [], "outages": [{"observed_ms": 100, "error": "old"}]}, {}, now_ms=2000000))
    def test_new_tick(self):
        state = {"ticks": [{"observed_ms": 100000, "candle_ms": 0}], "outages": [],
                 "trades": [{"observed_ms": 100000, "side": "buy", "asset": "BTC/USDT", "usdt": 50, "px": 100}]}
        result = message(state, {"observations": 1, "trades": 1, "nav": 9999, "return_pct": -.01}, now_ms=100001)
        self.assertIn("BUY BTC/USDT", result)
    def test_new_continuity_gap_alert(self):
        state = {"ticks": [{"observed_ms": 100000, "candle_ms": 0}], "outages": [],
                 "continuity_gaps": [{"detected_ms": 200000, "count": 2,
                                      "first_missed_candle_ms": 14400000}]}
        msg = message(state, {}, now_ms=200001)
        self.assertIn("Eksik mum: 2", msg)

    def test_fallback_does_not_repeat_fresh_tick(self):
        state = {"ticks": [{"observed_ms": 100000, "candle_ms": 0}], "outages": []}
        self.assertIsNone(message(state, {"run_ms": 200000}, now_ms=200001))
        self.assertIn("4h mum", message(state, {"run_ms": 100000}, now_ms=100001))

    def test_fallback_does_not_repeat_gap(self):
        state = {"ticks": [], "outages": [], "continuity_gaps": [
            {"detected_ms": 100000, "count": 1, "first_missed_candle_ms": 0}]}
        self.assertIsNone(message(state, {"run_ms": 200000}, now_ms=200001))

    def test_old_outages_ignored(self):
        state = {"ticks": [{"observed_ms": 100000, "candle_ms": 0}], "outages": [{"observed_ms": 1, "error": "old"}], "trades": []}
        self.assertIn("4h mum", message(state, {"nav": 10000}, now_ms=100001))

class TelegramDeliveryTests(unittest.TestCase):
    def test_transient_dns_retry_then_success(self):
        calls = []
        def opener(url, data, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise urllib.error.URLError(socket.gaierror(-3, "temporary"))
            return io.BytesIO(b'{"ok": true}')
        with patch("builtins.print") as log:
            self.assertTrue(send_telegram("secret", "123", "test", opener=opener, sleeper=lambda _: None))
        self.assertEqual(len(calls), 2)
        self.assertNotIn("secret", str(log.call_args_list))

    def test_permanent_unauthorized_no_retry(self):
        calls = []
        def opener(url, data, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(url, 401, "unauthorized", {}, None)
        with patch("builtins.print") as log:
            self.assertFalse(send_telegram("secret", "123", "test", opener=opener, sleeper=lambda _: None))
        self.assertEqual(len(calls), 1)
        self.assertIn("http_401", str(log.call_args_list))
        self.assertNotIn("secret", str(log.call_args_list))

    def test_timeout_exhausted(self):
        calls = []
        def opener(url, data, timeout):
            calls.append(1)
            raise urllib.error.URLError(socket.timeout())
        with patch("builtins.print") as log:
            self.assertFalse(send_telegram("secret", "123", "test", opener=opener, sleeper=lambda _: None))
        self.assertEqual(len(calls), 3)
        self.assertIn("timeout", str(log.call_args_list))


if __name__ == "__main__":
    unittest.main()
