"""Deterministic visual smoothing for determinate task progress.

The renderer remains the source of truth.  This helper never invents progress
past the latest authoritative target; it only animates the UI through every
integer percentage instead of jumping between sparse renderer updates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class SmoothProgressValue:
    """Animate a float value toward a monotonic target without skipping integers."""

    current: float = 0.0
    target: float = 0.0

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def reset(self, value: float = 0.0) -> float:
        clean = self._clamp(value)
        self.current = clean
        self.target = clean
        return self.current

    def set_target(self, value: float, allow_decrease: bool = False) -> float:
        clean = self._clamp(value)
        if allow_decrease:
            self.target = clean
            if self.current > clean:
                self.current = clean
        else:
            self.target = max(self.target, clean)
        return self.target

    def tick(self, step: float = 0.5) -> float:
        amount = max(0.01, min(0.99, float(step)))
        if self.current < self.target:
            self.current = min(self.target, self.current + amount)
        elif self.current > self.target:
            self.current = self.target
        return self.current

    @property
    def display_percent(self) -> int:
        # The displayed counter advances through every whole number.  The only
        # special case is exact completion, where it must show 100 immediately
        # after the animation reaches its target.
        if self.current >= 100.0:
            return 100
        return max(0, min(99, int(math.floor(self.current))))

    @property
    def bar_value(self) -> int:
        """Return a 0..1000 value for a visually smoother QProgressBar."""
        return max(0, min(1000, int(round(self.current * 10.0))))

    @property
    def settled(self) -> bool:
        return abs(self.current - self.target) < 1e-6
