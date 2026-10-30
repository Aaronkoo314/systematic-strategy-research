"""Walk-forward validation on the project's own engine.

Ported from the first-phase framework (quant-research-framework, optimization/
walk_forward.py) and rewritten against `src.backtest.engine.Backtester` so that it
inherits every guarantee that engine carries: owned history copies, next-bar-open
fills, itemised fees, full-NAV accounting and the risk gate. The original ran on a
separate engine with its own cost model; two engines that must agree is one more
thing to test, so the old one was not carried over.

The procedure, per fold:

  1. `select(train)` is handed a BarSeries that CONTAINS ONLY THE TRAINING BARS. It may
     grid-search, run Optuna, or return a fixed rule - the function decides. It cannot
     see a test bar because the object it is given does not have one.
  2. The strategy it returns is frozen and run ONCE on the test window. The bars before
     the window are visible to the strategy as history (that is the past, which is
     legitimate); the engine's `warmup` keeps it from trading until the window opens.
  3. Buy-and-hold is run on the same window with the same fees, because every result in
     this project is a comparison against holding, never a number on its own.

Folds are counted in SESSIONS, not months, so the same code serves daily and 5-minute
bars. Rolling keeps the training length fixed; expanding keeps the training start fixed.

What this module does NOT do, stated so nobody assumes it:
  - it does not correct for the number of folds or candidates searched. A rule selected
    on 24 configurations and run on 8 folds has been looked at 24 times; the power gate
    (`power.py`) is where that is accounted for, before any of this runs.
  - a stitched out-of-sample curve is a chain of fold returns, each fold starting from
    the previous fold's terminal wealth. It is NOT one continuous account: positions are
    not carried across the fold boundary, so a position open at a fold's end is marked
    at that bar's close and the next fold starts flat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from src.backtest.engine import Backtester, BacktestResult
from src.data.bars import BarSeries


@dataclass(frozen=True)
class Fold:
    """Bar indices. `*_end` is EXCLUSIVE, like a Python slice."""

    number: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int

    def __post_init__(self):
        if not (0 <= self.train_start < self.train_end <= self.test_start < self.test_end):
            raise ValueError(
                f"fold {self.number}: need train_start < train_end <= test_start < "
                f"test_end, got {self.train_start}, {self.train_end}, "
                f"{self.test_start}, {self.test_end}")


@dataclass
class FoldResult:
    fold: Fold
    strategy_name: str
    selection: dict
    test: BacktestResult
    hold: BacktestResult
    oos_equity: pd.DataFrame          # test-window rows only, warmup rows removed
    metrics: dict


@dataclass
class WalkForwardResult:
    folds: list[FoldResult] = field(default_factory=list)
    stitched: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: dict = field(default_factory=dict)

    def table(self) -> pd.DataFrame:
        rows = []
        for fr in self.folds:
            rows.append({"fold": fr.fold.number,
                         "train_start": fr.fold.train_start, "train_end": fr.fold.train_end,
                         "test_start": fr.fold.test_start, "test_end": fr.fold.test_end,
                         "strategy": fr.strategy_name, **fr.metrics})
        return pd.DataFrame(rows)


# ---------------- folds ----------------

def build_folds(bars: BarSeries, *, train_sessions: int, test_sessions: int,
                step_sessions: int | None = None, window: str = "rolling") -> list[Fold]:
    """Folds by SESSION count, converted to bar indices through the series' own sessions.

    The first test window opens after `train_sessions` sessions. Each subsequent fold
    moves `step_sessions` sessions forward (default: the test length, so test windows
    tile without overlap). A final partial test window is dropped rather than run short.
    """
    if window not in ("rolling", "expanding"):
        raise ValueError("window must be 'rolling' or 'expanding'")
    if train_sessions < 1 or test_sessions < 1:
        raise ValueError("train_sessions and test_sessions must be positive")
    step = test_sessions if step_sessions is None else step_sessions
    if step < 1:
        raise ValueError("step_sessions must be positive")

    sessions = bars.sessions
    n = len(sessions)
    folds = []
    k = 0
    test_s = train_sessions
    while test_s + test_sessions <= n:
        train_s = 0 if window == "expanding" else test_s - train_sessions
        folds.append(Fold(
            number=k,
            train_start=sessions[train_s].start,
            train_end=sessions[test_s - 1].end + 1,
            test_start=sessions[test_s].start,
            test_end=sessions[test_s + test_sessions - 1].end + 1))
        k += 1
        test_s += step
    return folds


def slice_bars(bars: BarSeries, start: int, end: int) -> BarSeries:
    """A NEW BarSeries holding only bars[start:end]. Owned copies, re-validated.

    This is how the selector is prevented from seeing the test window: it is handed an
    object that does not contain it, rather than an object plus an instruction not to
    look. Validation is skipped when the slice would start or end mid-session on a
    5-minute series, since the session-shape checks would correctly reject it.
    """
    if not (0 <= start < end <= len(bars)):
        raise ValueError(f"slice [{start}, {end}) outside 0..{len(bars)}")
    df = pd.DataFrame({
        "time_key": bars.time_key[start:end].copy(),
        "open": bars.open[start:end].copy(), "high": bars.high[start:end].copy(),
        "low": bars.low[start:end].copy(), "close": bars.close[start:end].copy(),
        "volume": bars.volume[start:end].copy(),
    })
    whole = (bars.session_of(start).start == start
             and bars.session_of(end - 1).end == end - 1)
    return BarSeries(df, validate=whole, allow_overnight=bars.allow_overnight,
                     frequency=bars.frequency)


# ---------------- the run ----------------

def _hold(history: dict, state) -> float:
    return 1.0


def walk_forward(bars: BarSeries, select: Callable[[BarSeries, Fold], tuple],
                 folds: list[Fold], *, make_backtester: Callable[[], Backtester],
                 warmup: int = 0) -> WalkForwardResult:
    """Run every fold. `select(train_bars, fold)` returns `(strategy, name, selection)`
    where `selection` is a JSON-able record of what was chosen and why (the grid, the
    best score, the Optuna trial count) so the choice is auditable afterwards.

    `make_backtester()` must return a Backtester over the FULL series; the engine's
    `start`/`end`/`warmup` arguments confine each run to its window. A fresh instance
    per run is required because the risk manager carries state across a run.
    """
    if not folds:
        raise ValueError("no folds")
    results: list[FoldResult] = []
    for fold in folds:
        train = slice_bars(bars, fold.train_start, fold.train_end)
        strategy, name, selection = select(train, fold)

        start = max(0, fold.test_start - warmup)
        wu = fold.test_start - start
        test = make_backtester().run(strategy, start=start, end=fold.test_end, warmup=wu)
        hold = make_backtester().run(_hold, start=start, end=fold.test_end, warmup=wu)

        oos = test.equity[test.equity["bar"] >= fold.test_start].reset_index(drop=True)
        hold_eq = hold.equity[hold.equity["bar"] >= fold.test_start].reset_index(drop=True)
        metrics = _fold_metrics(oos, hold_eq, test, hold)
        results.append(FoldResult(fold=fold, strategy_name=name, selection=selection,
                                  test=test, hold=hold, oos_equity=oos, metrics=metrics))

    hold_curves = [fr.hold.equity[fr.hold.equity["bar"] >= fr.fold.test_start]
                   .reset_index(drop=True) for fr in results]
    stitched = stitch([fr.oos_equity for fr in results], hold_curves)
    return WalkForwardResult(folds=results, stitched=stitched,
                             summary=_overall(results, stitched))


def _fold_metrics(oos: pd.DataFrame, hold_eq: pd.DataFrame,
                  test: BacktestResult, hold: BacktestResult) -> dict:
    r_strat = _window_return(oos)
    r_hold = _window_return(hold_eq)
    sessions = int(oos["date"].nunique()) if len(oos) else 0
    years = sessions / 252.0
    return {
        "sessions": sessions,
        "oos_return": r_strat,
        "hold_return": r_hold,
        "excess_vs_hold": r_strat - r_hold,
        "oos_cagr": _cagr(r_strat, years),
        "hold_cagr": _cagr(r_hold, years),
        "oos_max_drawdown": _max_dd(oos["nav"].to_numpy()) if len(oos) else 0.0,
        "hold_max_drawdown": _max_dd(hold_eq["nav"].to_numpy()) if len(hold_eq) else 0.0,
        "n_fills": int(test.summary["n_fills"]),
        "fees": float(test.summary["total_fees"]),
        # The risk manager observes NAV even when bypassed, so its halted flag is
        # only meaningful when the controls were actually enforced.
        "halted": bool(test.summary.get("halted", False)
                       and test.summary.get("risk_controls") == "enforced"),
    }


def _window_return(eq: pd.DataFrame) -> float:
    if len(eq) < 1:
        return 0.0
    nav0 = float(eq["nav"].iloc[0])
    return float(eq["nav"].iloc[-1]) / nav0 - 1.0 if nav0 else 0.0


def _cagr(total_return: float, years: float) -> float | None:
    if years <= 0 or total_return <= -1.0:
        return None
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def _max_dd(nav: np.ndarray) -> float:
    if len(nav) == 0:
        return 0.0
    hwm = np.maximum.accumulate(nav)
    return float(np.min(nav / hwm - 1.0))


def stitch(fold_curves: list[pd.DataFrame],
           hold_curves: list[pd.DataFrame] | None = None) -> pd.DataFrame:
    """Chain per-fold NAV paths into one out-of-sample wealth index starting at 1.0.

    Each fold is rebased to its own first NAV and multiplied onto the running product.
    A position open at the end of a fold is marked, not carried - see the module note.
    """
    rows = []
    w = 1.0
    w_hold = 1.0
    for k, eq in enumerate(fold_curves):
        if not len(eq):
            continue
        base = float(eq["nav"].iloc[0])
        rel = eq["nav"].to_numpy() / base
        out = pd.DataFrame({"bar": eq["bar"].to_numpy(), "date": eq["date"].to_numpy(),
                            "time_key": eq["time_key"].to_numpy(), "fold": k,
                            "wealth": w * rel})
        if hold_curves is not None:
            h = hold_curves[k]
            hb = float(h["nav"].iloc[0])
            out["hold_wealth"] = w_hold * (h["nav"].to_numpy() / hb)
            w_hold = float(out["hold_wealth"].iloc[-1])
        w = float(out["wealth"].iloc[-1])
        rows.append(out)
    if not rows:
        return pd.DataFrame(columns=["bar", "date", "time_key", "fold", "wealth"])
    return pd.concat(rows, ignore_index=True)


def _overall(results: list[FoldResult], stitched: pd.DataFrame) -> dict:
    t = pd.DataFrame([fr.metrics for fr in results])
    sessions = int(t["sessions"].sum())
    years = sessions / 252.0
    total = float(stitched["wealth"].iloc[-1]) - 1.0 if len(stitched) else 0.0
    hold = (float(stitched["hold_wealth"].iloc[-1]) - 1.0
            if "hold_wealth" in stitched and len(stitched) else None)
    return {
        "n_folds": len(results),
        "sessions": sessions, "years": round(years, 3),
        "oos_total_return": total,
        "oos_cagr": _cagr(total, years),
        "hold_total_return": hold,
        "hold_cagr": _cagr(hold, years) if hold is not None else None,
        "oos_max_drawdown": _max_dd(stitched["wealth"].to_numpy()) if len(stitched) else 0.0,
        "folds_beating_hold": int((t["excess_vs_hold"] > 0).sum()),
        "folds_positive": int((t["oos_return"] > 0).sum()),
        "total_fills": int(t["n_fills"].sum()),
        "total_fees": float(t["fees"].sum()),
        "any_halted": bool(t["halted"].any()),
    }


# ---------------- does the ranking mean anything? ----------------

def spearman(a, b) -> float:
    """Spearman rank correlation, ties by average rank. No scipy dependency.

    Used to ask the question walk-forward exists for: does the training rank of a
    parameter set predict its out-of-sample result? Rank 1 is the best, so a USEFUL
    ranking shows a NEGATIVE correlation between train rank and OOS return; near zero
    is the signature of a search that fitted noise.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError("length mismatch")
    if len(a) < 3:
        return float("nan")
    ra = pd.Series(a).rank(method="average").to_numpy()
    rb = pd.Series(b).rank(method="average").to_numpy()
    ra -= ra.mean()
    rb -= rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return float((ra * rb).sum() / den) if den > 0 else float("nan")
