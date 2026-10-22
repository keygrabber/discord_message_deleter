"""Offline tests for run speed / ETA maths (no Tk). Run: python -m unittest"""

import unittest

from deleter_app.metrics import eta_seconds, format_eta, rate_per_min


class RateTests(unittest.TestCase):
    """Items per minute."""

    def test_rate(self):
        """30 items in 60 s is 30 per minute."""
        self.assertEqual(rate_per_min(30, 60), 30)

    def test_zero_elapsed_is_zero(self):
        """No time passed yet: avoid division by zero."""
        self.assertEqual(rate_per_min(5, 0), 0)


class EtaTests(unittest.TestCase):
    """Seconds left."""

    def test_eta(self):
        """25 of 100 done after 50 s leaves 150 s."""
        self.assertEqual(eta_seconds(25, 100, 50), 150)

    def test_unknown_when_nothing_done(self):
        """No progress yet means no estimate."""
        self.assertIsNone(eta_seconds(0, 100, 10))

    def test_unknown_when_total_unknown(self):
        """A total of 0 means no estimate."""
        self.assertIsNone(eta_seconds(5, 0, 10))

    def test_finished_is_zero(self):
        """Everything done leaves nothing."""
        self.assertEqual(eta_seconds(100, 100, 40), 0)


class FormatTests(unittest.TestCase):
    """Human-readable durations."""

    def test_none_is_dash(self):
        """Unknown shows an em-dash-free placeholder."""
        self.assertEqual(format_eta(None), "--")

    def test_seconds(self):
        """Under a minute shows seconds only."""
        self.assertEqual(format_eta(42), "42s")

    def test_minutes(self):
        """Under an hour shows minutes and zero-padded seconds."""
        self.assertEqual(format_eta(125), "2m 05s")

    def test_hours(self):
        """An hour or more shows hours and zero-padded minutes."""
        self.assertEqual(format_eta(3725), "1h 02m")


if __name__ == "__main__":
    unittest.main()
