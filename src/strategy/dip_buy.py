"""Buy-the-dip exposure rule. Spec frozen in docs/preregistration_v2.md §2.

If this file and the preregistration ever disagree, the preregistration is correct and
this file is the bug.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

W_BASE = 0.50    # the level the static sweep showed respects the 20% abandon point
W_MIN = 0.50     # the rule adds on weakness and never reduces below base
W_MAX = 0.90     # mandate cap
BAND = 0.05      # fixed convention, not a searched parameter


@dataclass(frozen=True)
class DipBuy:
    """Two free parameters, exactly as frozen.

    k  how hard to lean into a decline
    l  trailing window, in sessions, for the peak
    """

    k: float
    l: int

    def __post_init__(self):
        if self.k <= 0:
            raise ValueError("k must be positive")
        if self.l < 2:
            raise ValueError("l must be at least 2 sessions")

    @property
    def warmup(self) -> int:
        return self.l

    @property
    def lookback(self) -> int:
        return self.l

    def target_weight(self, closes: np.ndarray) -> float:
        c = np.asarray(closes, dtype=float)
        if len(c) < 2:
            return W_BASE
        w = c[-self.l:] if len(c) >= self.l else c
        peak = float(np.max(w))
        if peak <= 0:
            return W_BASE
        dd = float(c[-1]) / peak - 1.0           # <= 0
        raw = W_BASE + self.k * abs(dd)
        return float(min(max(raw, W_MIN), W_MAX))

    def __call__(self, history: dict, state) -> float:
        """Returns the CURRENT weight when inside the band, so the engine sees no change
        and places no order. Keeping the band here means it lives in one place."""
        closes = history["close"]
        if len(closes) < 2:
            return 0.0

        want = self.target_weight(closes)
        nav = state.nav()
        held = (state.shares * state.last_price / nav) if nav > 0 else 0.0
        if abs(want - held) <= BAND:
            return float(held)
        return float(want)
