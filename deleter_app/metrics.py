"""Run speed and ETA maths for the dashboard (no Tk, so it can be unit-tested)."""

from typing import Optional


def rate_per_min(done: int, elapsed: float) -> float:
    """Items processed per minute; 0 until some time has passed."""
    return done / elapsed * 60 if elapsed > 0 else 0


def eta_seconds(done: int, total: int, elapsed: float) -> Optional[float]:
    """Seconds left at the current pace, or None while it cannot be estimated."""
    if total <= 0 or done <= 0 or elapsed <= 0:
        return None
    return max(0.0, elapsed / done * (total - done))


def format_eta(seconds: Optional[float]) -> str:
    """'42s', '2m 05s', '1h 02m', or '--' when unknown."""
    if seconds is None:
        return "--"
    total = round(seconds)
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m {total % 60:02d}s"
    return f"{total // 3600}h {total % 3600 // 60:02d}m"
