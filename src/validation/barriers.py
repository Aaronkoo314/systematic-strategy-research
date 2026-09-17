"""Triple-barrier labelling: from an entry, which barrier is touched first?

The standard supervised-learning setup for swing trading (López de Prado's term). For
each candidate entry, place an upper barrier at +TP, a lower barrier at -SL and a
vertical barrier at a maximum holding period, then record which is touched first.

Two things this module is careful about, because both are easy to get wrong and both
flatter the result:

  THE LABEL LOOKS FORWARD; THE FEATURES MUST NOT. Knowing which barrier was hit requires
  future data - that is what a label is. It is legitimate for training a model and
  illegitimate the moment it leaks into a feature. This module only produces labels.

  OVERLAPPING EVENTS ARE NOT INDEPENDENT. Entries a few bars apart share almost all of
  their forward path, so a sample of 100,000 overlapping events carries nothing like
  100,000 observations' worth of evidence. `stride` exists to make that visible, and
  every result reports the number of NON-OVERLAPPING events alongside the raw count.

Optimism that remains, and is reported rather than hidden:
  - a barrier is assumed to fill AT the barrier price. A stop can gap through it,
    especially overnight, so realised losses would be worse than -SL.
  - when both barriers fall inside the same bar, this module resolves the STOP first.
    That is the conservative choice; the opposite convention inflates win rates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BarrierResult:
    tp: float
    sl: float
    horizon_bars: int
    n_entries: int
    n_wins: int
    n_losses: int
    n_timeouts: int
    win_rate: float
    loss_rate: float
    timeout_rate: float
    breakeven_win_rate: float
    expectancy_pct: float
    expectancy_net_pct: float
    median_bars_to_resolve: float
    median_bars_win: float
    median_bars_loss: float
    trades_per_year: float
    n_non_overlapping: int

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__annotations__}


def label_barriers(high: np.ndarray, low: np.ndarray, open_: np.ndarray,
                   close: np.ndarray, *, tp: float, sl: float,
                   horizon_bars: int, stride: int = 1,
                   start: int = 0, end: int | None = None) -> dict:
    """Label every stride-th bar. Entry fills at the NEXT bar's open.

    Returns raw arrays so the caller can aggregate however it needs.
    """
    if tp <= 0 or sl <= 0:
        raise ValueError("tp and sl must be positive fractions")
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be at least 1")
    if stride < 1:
        raise ValueError("stride must be at least 1")

    n = len(close)
    end = n if end is None else min(end, n)
    idx, outcome, bars_held, entry_px, exit_px = [], [], [], [], []

    for i in range(start, end - 1, stride):
        e = i + 1                      # fill at the next bar's open
        if e >= end:
            break
        p = float(open_[e])
        if not np.isfinite(p) or p <= 0:
            continue
        up, dn = p * (1.0 + tp), p * (1.0 - sl)
        j_end = min(e + horizon_bars, end)
        if j_end <= e:
            break

        h = high[e:j_end]
        l = low[e:j_end]
        up_hit = np.flatnonzero(h >= up)
        dn_hit = np.flatnonzero(l <= dn)
        j_up = int(up_hit[0]) if up_hit.size else None
        j_dn = int(dn_hit[0]) if dn_hit.size else None

        if j_up is None and j_dn is None:
            outcome.append(0)                       # timeout
            bars_held.append(j_end - e)
            exit_px.append(float(close[j_end - 1]))
        elif j_dn is None or (j_up is not None and j_up < j_dn):
            outcome.append(1)                       # take profit
            bars_held.append(j_up + 1)
            exit_px.append(up)
        else:
            # Same-bar ties resolve to the STOP. The opposite convention inflates wins.
            outcome.append(-1)
            bars_held.append(j_dn + 1)
            exit_px.append(dn)

        idx.append(i)
        entry_px.append(p)

    return {"entry_bar": np.array(idx, dtype=int),
            "outcome": np.array(outcome, dtype=int),
            "bars_held": np.array(bars_held, dtype=int),
            "entry_price": np.array(entry_px, dtype=float),
            "exit_price": np.array(exit_px, dtype=float)}


def summarise(lab: dict, *, tp: float, sl: float, horizon_bars: int,
              bars_per_year: float, cost_pct: float = 0.0) -> BarrierResult:
    out = lab["outcome"]
    held = lab["bars_held"]
    n = len(out)
    if n == 0:
        raise ValueError("no labelled entries")

    wins = int((out == 1).sum())
    losses = int((out == -1).sum())
    timeouts = int((out == 0).sum())

    ret = np.where(out == 1, tp, np.where(out == -1, -sl,
                                          lab["exit_price"] / lab["entry_price"] - 1.0))
    exp_gross = float(ret.mean())

    # Non-overlapping count: greedily walk forward, skipping entries whose window
    # overlaps one already counted. This is the honest sample size.
    order = np.argsort(lab["entry_bar"])
    free_from, n_indep = -1, 0
    for k in order:
        b = int(lab["entry_bar"][k])
        if b > free_from:
            n_indep += 1
            free_from = b + int(held[k])

    med = float(np.median(held))
    med_w = float(np.median(held[out == 1])) if wins else float("nan")
    med_l = float(np.median(held[out == -1])) if losses else float("nan")

    return BarrierResult(
        tp=tp, sl=sl, horizon_bars=horizon_bars, n_entries=n,
        n_wins=wins, n_losses=losses, n_timeouts=timeouts,
        win_rate=wins / n, loss_rate=losses / n, timeout_rate=timeouts / n,
        breakeven_win_rate=sl / (tp + sl),
        expectancy_pct=exp_gross * 100.0,
        expectancy_net_pct=(exp_gross - cost_pct) * 100.0,
        median_bars_to_resolve=med, median_bars_win=med_w, median_bars_loss=med_l,
        trades_per_year=bars_per_year / med if med > 0 else float("nan"),
        n_non_overlapping=n_indep)
