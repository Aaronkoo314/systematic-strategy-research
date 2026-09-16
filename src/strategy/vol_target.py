"""Volatility-targeting exposure rule. Spec frozen in docs/preregistration_v1.md §2.

The rule is deliberately small. Every quantity below appears in the preregistration; if
the two ever disagree, the preregistration is correct and this file is the bug.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BARS_PER_YEAR = 78 * 252     # 5-minute bars in a regular-session trading year
BAND = 0.10                  # fixed convention, not a searched parameter
MIN_SIGMA = 0.01             # floor, so a flat window cannot demand infinite exposure


@dataclass(frozen=True)
class VolTarget:
    """Two free parameters, exactly as frozen.

    n_bars       trailing 5-minute bars used to estimate realised volatility
    sigma_target annualised volatility the position is sized toward
    max_weight   the mandate cap; NOT a free parameter, carried so the rule never
                 proposes an exposure the risk layer would only have to refuse
    """

    n_bars: int
    sigma_target: float
    max_weight: float = 0.90

    def __post_init__(self):
        if self.n_bars < 2:
            raise ValueError("n_bars must be at least 2")
        if not 0 < self.sigma_target <= 2.0:
            raise ValueError("sigma_target must be a positive annualised fraction")
        if not 0 < self.max_weight <= 1.0:
            raise ValueError("max_weight must be in (0, 1]")

    @property
    def warmup(self) -> int:
        return self.n_bars + 1

    @property
    def lookback(self) -> int:
        """Bars the engine must hand over: n_bars returns needs n_bars + 1 closes."""
        return self.n_bars + 1

    def realised_vol(self, closes: np.ndarray) -> float:
        c = np.asarray(closes, dtype=float)
        if len(c) < self.n_bars + 1:
            return float("nan")
        w = c[-(self.n_bars + 1):]
        r = np.diff(np.log(w))
        return float(np.std(r, ddof=1) * np.sqrt(BARS_PER_YEAR))

    def target_weight(self, closes: np.ndarray) -> float:
        sigma = self.realised_vol(closes)
        if not np.isfinite(sigma):
            return float("nan")
        raw = self.sigma_target / max(sigma, MIN_SIGMA)
        return float(min(max(raw, 0.0), self.max_weight))

    def __call__(self, history: dict, state) -> float:
        """Engine entry point. Returns the CURRENT weight when inside the band, so the
        engine sees no change and places no order - the band is what keeps turnover
        down, and expressing it as 'ask for what you already hold' means the band logic
        lives in one place instead of two."""
        closes = history["close"]
        if len(closes) < self.n_bars + 1:
            return 0.0

        want = self.target_weight(closes)
        if not np.isfinite(want):
            return 0.0

        nav = state.nav()
        held = (state.shares * state.last_price / nav) if nav > 0 else 0.0
        if abs(want - held) <= BAND:
            return float(held)
        return float(want)


def static_blend(weight: float):
    """Constant-dollar comparator at a fixed weight. Comparator 3 and 4 of the
    preregistration: it isolates what the volatility timing added over simply holding
    the same average exposure all the time."""
    w = float(weight)
    if not 0.0 <= w <= 1.0:
        raise ValueError("weight must be in [0, 1]")

    def _f(history: dict, state) -> float:
        return w

    _f.__name__ = f"static_{w:.2f}"
    return _f


def buy_and_hold(history: dict, state) -> float:
    return 1.0
