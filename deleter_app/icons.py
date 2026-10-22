"""Vector icon specs drawn on a tk.Canvas (no Tk here, so the shapes can be unit-tested).

Each icon is a list of primitives in a 0..1 box; `icon_shapes` scales them to pixels.
Primitive keys: kind (oval|line|poly|arc), coords, fill (bool), width (in 1/20ths of the
icon size), and start/extent for arcs.
"""

from typing import Dict, List

ICONS: Dict[str, List[dict]] = {
    "user": [
        {"kind": "oval", "coords": [0.34, 0.12, 0.66, 0.44], "fill": False, "width": 1.8},
        {"kind": "arc", "coords": [0.14, 0.56, 0.86, 1.0], "fill": False, "width": 1.8,
         "start": 0, "extent": 180},
    ],
    "target": [
        {"kind": "oval", "coords": [0.1, 0.1, 0.9, 0.9], "fill": False, "width": 1.8},
        {"kind": "oval", "coords": [0.28, 0.28, 0.72, 0.72], "fill": False, "width": 1.8},
        {"kind": "oval", "coords": [0.43, 0.43, 0.57, 0.57], "fill": True, "width": 1},
    ],
    "filter": [
        {"kind": "poly", "coords": [0.1, 0.16, 0.9, 0.16, 0.58, 0.54, 0.58, 0.88, 0.42, 0.78,
                                    0.42, 0.54], "fill": False, "width": 1.8},
    ],
    "clock": [
        {"kind": "oval", "coords": [0.1, 0.1, 0.9, 0.9], "fill": False, "width": 1.8},
        {"kind": "line", "coords": [0.5, 0.26, 0.5, 0.5, 0.7, 0.62], "fill": False, "width": 1.8},
    ],
    "play": [
        {"kind": "poly", "coords": [0.3, 0.18, 0.82, 0.5, 0.3, 0.82], "fill": True, "width": 1},
    ],
    "stop": [
        {"kind": "poly", "coords": [0.24, 0.24, 0.76, 0.24, 0.76, 0.76, 0.24, 0.76],
         "fill": True, "width": 1},
    ],
    "eye": [
        {"kind": "oval", "coords": [0.06, 0.28, 0.94, 0.72], "fill": False, "width": 1.8},
        {"kind": "oval", "coords": [0.38, 0.38, 0.62, 0.62], "fill": True, "width": 1},
    ],
    "trash": [
        {"kind": "line", "coords": [0.14, 0.26, 0.86, 0.26], "fill": False, "width": 1.8},
        {"kind": "line", "coords": [0.4, 0.26, 0.4, 0.12, 0.6, 0.12, 0.6, 0.26], "fill": False,
         "width": 1.8},
        {"kind": "poly", "coords": [0.24, 0.26, 0.3, 0.88, 0.7, 0.88, 0.76, 0.26], "fill": False,
         "width": 1.8},
    ],
    "shield": [
        {"kind": "poly", "coords": [0.5, 0.1, 0.86, 0.24, 0.8, 0.62, 0.5, 0.9, 0.2, 0.62, 0.14, 0.24],
         "fill": False, "width": 1.8},
    ],
    "check": [
        {"kind": "line", "coords": [0.2, 0.55, 0.42, 0.76, 0.8, 0.28], "fill": False, "width": 2.2},
    ],
}
ICON_NAMES = tuple(ICONS)


def icon_shapes(name: str, size: int) -> List[dict]:
    """Primitives of icon `name` scaled to a `size` x `size` pixel box (KeyError if unknown)."""
    scaled = []
    for shape in ICONS[name]:
        item = dict(shape)
        item["coords"] = [round(v * size, 4) for v in shape["coords"]]
        item["width"] = max(1, round(shape["width"] * size / 20))
        scaled.append(item)
    return scaled
