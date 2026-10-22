"""Offline tests for palettes, gradients and the settings file (no Tk). Run: python -m unittest"""

import json
import tempfile
import unittest
from pathlib import Path

from deleter_app.theme import DEFAULT_PALETTE, PALETTES, gradient, load_settings, save_settings


class PaletteTests(unittest.TestCase):
    """The accent palettes offered in the sidebar."""

    def test_default_exists(self):
        """The default palette name must be one of the offered palettes."""
        self.assertIn(DEFAULT_PALETTE, PALETTES)

    def test_every_palette_is_three_hex_colours(self):
        """Each palette is (accent, hover, dim) as '#rrggbb'."""
        for name, colours in PALETTES.items():
            self.assertEqual(len(colours), 3, name)
            for colour in colours:
                self.assertRegex(colour, r"^#[0-9a-f]{6}$", name)


class GradientTests(unittest.TestCase):
    """Colour ramp used by the hero banner."""

    def test_length_and_endpoints(self):
        """n stops, first = start colour, last = end colour."""
        stops = gradient("#000000", "#ffffff", 5)
        self.assertEqual(len(stops), 5)
        self.assertEqual(stops[0], "#000000")
        self.assertEqual(stops[-1], "#ffffff")

    def test_single_stop_is_the_start(self):
        """n=1 must not divide by zero."""
        self.assertEqual(gradient("#102030", "#ffffff", 1), ["#102030"])


class SettingsTests(unittest.TestCase):
    """Non-secret preferences stored as JSON."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "settings.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_gives_empty_dict(self):
        """First start: no file, no crash."""
        self.assertEqual(load_settings(self.path), {})

    def test_round_trip_creates_the_folder(self):
        """save then load returns the same data, creating parent folders."""
        save_settings(self.path, {"accent": "Mint"})
        self.assertEqual(load_settings(self.path), {"accent": "Mint"})

    def test_corrupt_file_is_ignored(self):
        """A broken file must never stop the app from starting."""
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_settings(self.path), {})

    def test_non_object_json_is_ignored(self):
        """Valid JSON that is not an object is treated as empty."""
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps([1, 2]), encoding="utf-8")
        self.assertEqual(load_settings(self.path), {})


if __name__ == "__main__":
    unittest.main()
