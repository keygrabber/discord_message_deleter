"""Pure helpers for GUI animations (no Tk, so they can be unit-tested)."""


def _clamp(t: float) -> float:
    """Limit t to the 0..1 range."""
    return max(0.0, min(1.0, t))


def ease_out(t: float) -> float:
    """Cubic ease-out: fast start, soft landing."""
    t = _clamp(t)
    return 1 - (1 - t) ** 3


def lerp_color(start: str, end: str, t: float) -> str:
    """Blend two '#rrggbb' colours; t is clamped to 0..1."""
    t = _clamp(t)
    a = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def count_step(start: int, target: int, t: float) -> int:
    """Integer shown by a counter animating from start to target at progress t."""
    return round(start + (target - start) * ease_out(t))
