"""Regression tests for H054 external clock gate; no trading or network."""
import unittest
from datetime import datetime, timezone

from scripts.h054_dispatch_gate import latest_completed_bar, should_dispatch


def utc(day: int, hour: int, minute: int):
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


class TestH054DispatchGate(unittest.TestCase):
    def test_new_closed_four_hour_candle_triggers_once(self):
        now = utc(21, 4, 11)
        self.assertEqual(latest_completed_bar(now), utc(21, 0, 0))
        self.assertTrue(should_dispatch({"last_bar": "2026-11-20 20:00:00"}, now))
        self.assertFalse(should_dispatch({"last_bar": "2026-11-21 00:00:00"}, now))

    def test_publication_grace_avoids_early_dispatch(self):
        now = utc(21, 4, 4)
        self.assertEqual(latest_completed_bar(now), utc(20, 20, 0))
        self.assertFalse(should_dispatch({"last_bar": "2026-11-20 20:00:00"}, now))

    def test_multi_bar_outage_remains_visible_and_dispatches(self):
        self.assertTrue(should_dispatch({"last_bar": "2026-11-19 20:00:00"}, utc(21, 10, 15)))

    def test_missing_or_unaligned_state_fails_closed(self):
        for state in ({}, {"last_bar": "garbage"}, {"last_bar": "2026-11-21 00:15:00"}):
            with self.subTest(state=state), self.assertRaises(ValueError):
                should_dispatch(state, utc(21, 4, 11))

    def test_future_source_state_fails_closed(self):
        with self.assertRaises(ValueError):
            should_dispatch({"last_bar": "2026-11-21 08:00:00"}, utc(21, 4, 11))

    def test_timezone_aware_input(self):
        self.assertFalse(should_dispatch({"last_bar": "2026-11-21T00:00:00Z"}, utc(21, 4, 11)))


if __name__ == "__main__":
    unittest.main()
