"""Offline tests for the canvas icon shape specs (no Tk). Run: python -m unittest"""

import unittest

from deleter_app.icons import ICON_NAMES, icon_shapes


class IconShapeTests(unittest.TestCase):
    """Every icon is a list of primitives scaled to the requested size."""

    def test_all_names_have_shapes(self):
        """Each advertised icon draws at least one primitive."""
        for name in ICON_NAMES:
            self.assertTrue(icon_shapes(name, 20), name)

    def test_coordinates_stay_inside_the_box(self):
        """No primitive may leave the size x size canvas."""
        for name in ICON_NAMES:
            for shape in icon_shapes(name, 40):
                for value in shape["coords"]:
                    self.assertGreaterEqual(value, 0, name)
                    self.assertLessEqual(value, 40, name)

    def test_scales_with_size(self):
        """Doubling the size doubles the coordinates."""
        small = icon_shapes("user", 10)[0]["coords"]
        big = icon_shapes("user", 20)[0]["coords"]
        self.assertEqual([v * 2 for v in small], big)

    def test_unknown_name_raises(self):
        """A typo must fail loudly, not draw nothing."""
        with self.assertRaises(KeyError):
            icon_shapes("nope", 20)


if __name__ == "__main__":
    unittest.main()
