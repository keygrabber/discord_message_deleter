"""Accent palettes, gradients and the non-secret settings file (no Tk)."""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from .anim import lerp_color

# name -> (accent, hover, dim); "dim" is a dark tint of the accent for icon tiles
PALETTES: Dict[str, Tuple[str, str, str]] = {
    "Blurple": ("#5865f2", "#4752c4", "#2f3470"),
    "Mint": ("#2dd4a7", "#1fb08a", "#1d4a41"),
    "Rose": ("#f2589b", "#c93f7c", "#4d2437"),
    "Amber": ("#f0a032", "#c98122", "#4d3a1c"),
    "Sky": ("#3aa7f2", "#2a85c4", "#1c3a50"),
}
DEFAULT_PALETTE = "Blurple"


def gradient(start: str, end: str, count: int) -> List[str]:
    """`count` colours blending from start to end (inclusive)."""
    if count <= 1:
        return [start]
    return [lerp_color(start, end, i / (count - 1)) for i in range(count)]


def load_settings(path: Path) -> dict:
    """Read the settings file; any problem gives {} so the app always starts."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(path: Path, data: dict) -> None:
    """Write the settings file (only preferences, never tokens); failures are ignored."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
