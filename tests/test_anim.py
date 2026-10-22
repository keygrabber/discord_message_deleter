"""Offline tests for the pure animation helpers (no Tk). Run: python -m unittest"""

import unittest

from deleter_app.anim import count_step, ease_out, lerp_color


class LerpColorTests(unittest.TestCase):
    """Colour blending between two hex values."""

    def test_endpoints_return_the_inputs(self):
        """t=0 gives the start colour and t=1 the end colour."""
        self.assertEqual(lerp_color("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(lerp_color("#000000", "#ffffff", 1), "#ffffff")

    def test_midpoint_is_the_average(self):
        """t=0.5 lands halfway on every channel."""
        self.assertEqual(lerp_color("#000000", "#ffffff", 0.5), "#808080")

    def test_t_is_clamped(self):
        """Values outside 0..1 never overshoot the endpoints."""
        self.assertEqual(lerp_color("#102030", "#405060", -3), "#102030")
        self.assertEqual(lerp_color("#102030", "#405060", 9), "#405060")


class EaseOutTests(unittest.TestCase):
    """Deceleration curve used by every animation."""

    def test_fixed_points(self):
        """0 stays 0 and 1 stays 1."""
        self.assertEqual(ease_out(0), 0)
        self.assertEqual(ease_out(1), 1)

    def test_starts_fast(self):
        """An ease-out curve is above the diagonal early on."""
        self.assertGreater(ease_out(0.25), 0.25)

    def test_is_clamped(self):
        """Out-of-range input is clamped to 0..1."""
        self.assertEqual(ease_out(-1), 0)
        self.assertEqual(ease_out(2), 1)


class CountStepTests(unittest.TestCase):
    """Count-up of the stat counters."""

    def test_reaches_target_at_the_end(self):
        """The last frame always shows the exact target."""
        self.assertEqual(count_step(0, 137, 1), 137)

    def test_starts_at_origin(self):
        """The first frame shows the starting value."""
        self.assertEqual(count_step(10, 50, 0), 10)

    def test_counts_down_too(self):
        """A reset to a smaller value animates downwards."""
        self.assertLess(count_step(100, 0, 0.5), 100)

    def test_progress_is_monotonic(self):
        """Values never move away from the target."""
        frames = [count_step(0, 80, i / 10) for i in range(11)]
        self.assertEqual(frames, sorted(frames))


if __name__ == "__main__":
    unittest.main()
