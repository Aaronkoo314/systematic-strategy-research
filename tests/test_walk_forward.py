"""Walk-forward: the selector must not be able to see the test window, folds must tile
the sample as declared, and the stitched curve must be hand-checkable."""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.costs.fees import FeeSchedule  # noqa: E402
from src.data.bars import BarSeries, FREQ_DAILY  # noqa: E402
from src.validation.walk_forward import (  # noqa: E402
    Fold, build_folds, slice_bars, spearman, stitch, walk_forward,
)

FLAT = ExecutionModel(half_spread=0.0, slippage_bps_intraday=0.0,
                      slippage_bps_overnight=0.0)
FREE = FeeSchedule(platform_fee=0.0, settlement_per_share=0.0, sec_rate=0.0, sec_min=0.0,
                   taf_per_share=0.0, taf_min=0.0, cat_per_share=0.0)


def daily(n: int, closes=None) -> BarSeries:
    dates = pd.bdate_range("2020-01-01", periods=n)
    px = np.full(n, 100.0) if closes is None else np.asarray(closes, dtype=float)
    df = pd.DataFrame({"time_key": [f"{d:%Y-%m-%d} 16:00:00" for d in dates],
                       "open": px, "high": px + 1, "low": px - 1, "close": px,
                       "volume": np.full(n, 1e6)})
    return BarSeries(df, frequency=FREQ_DAILY)


def make_bt(bars):
    return lambda: Backtester(bars, initial_cash=10_000.0, execution=FLAT, fees=FREE,
                              bypass_risk_controls=True)


# ---------------- folds ----------------

def test_rolling_folds_tile_the_sample_without_overlap():
    bars = daily(30)
    folds = build_folds(bars, train_sessions=10, test_sessions=5)
    assert [f.test_start for f in folds] == [10, 15, 20, 25]
    for f in folds:
        assert f.train_end == f.test_start
        assert f.train_end - f.train_start == 10
        assert f.test_end - f.test_start == 5
    for a, b in zip(folds, folds[1:]):
        assert a.test_end == b.test_start


def test_expanding_folds_keep_the_training_start_fixed():
    folds = build_folds(daily(30), train_sessions=10, test_sessions=5, window="expanding")
    assert all(f.train_start == 0 for f in folds)
    assert [f.train_end - f.train_start for f in folds] == [10, 15, 20, 25]


def test_partial_final_window_is_dropped_not_run_short():
    folds = build_folds(daily(27), train_sessions=10, test_sessions=5)
    assert folds[-1].test_end == 25            # 25..27 is two sessions: dropped


def test_fold_rejects_a_test_window_that_precedes_training():
    with pytest.raises(ValueError):
        Fold(0, train_start=10, train_end=20, test_start=5, test_end=10)


def test_folds_count_sessions_not_bars_on_intraday_series():
    """Three sessions of 78 bars: one session of training, one of test."""
    from tests.test_engine import make
    bars = make(n_days=3)
    folds = build_folds(bars, train_sessions=1, test_sessions=1)
    assert len(folds) == 2
    assert folds[0].train_end == 78 and folds[0].test_start == 78
    assert folds[0].test_end == 156


# ---------------- the selector cannot see the test window ----------------

def test_selector_receives_only_training_bars():
    bars = daily(30, closes=np.arange(100, 130, dtype=float))
    folds = build_folds(bars, train_sessions=10, test_sessions=5)
    seen = []

    def select(train, fold):
        seen.append((len(train), float(train.close[-1]), fold.number))
        return (lambda h, st: 0.0), "flat", {}

    walk_forward(bars, select, folds, make_backtester=make_bt(bars))
    for (n, last, k), f in zip(seen, folds):
        assert n == f.train_end - f.train_start
        assert last == float(bars.close[f.train_end - 1])      # nothing past train_end


def test_slice_is_an_owned_copy_not_a_view():
    bars = daily(20)
    s = slice_bars(bars, 3, 9)
    assert len(s) == 6
    for a in (s.close, s.open, s.volume, s.time_key):
        assert a.base is None and a.flags.owndata


def test_slice_bounds_are_checked():
    bars = daily(10)
    with pytest.raises(ValueError):
        slice_bars(bars, 5, 5)
    with pytest.raises(ValueError):
        slice_bars(bars, 0, 11)


# ---------------- results ----------------

def test_oos_equity_contains_only_test_window_bars():
    bars = daily(30)
    folds = build_folds(bars, train_sessions=10, test_sessions=5)
    res = walk_forward(bars, lambda t, f: ((lambda h, st: 1.0), "hold", {}), folds,
                       make_backtester=make_bt(bars), warmup=3)
    for fr in res.folds:
        assert fr.oos_equity["bar"].min() == fr.fold.test_start
        assert fr.oos_equity["bar"].max() == fr.fold.test_end - 1
        assert len(fr.oos_equity) == 5


def test_holding_strategy_matches_hold_comparator_in_every_fold():
    """A strategy that returns 1.0 IS buy-and-hold; the comparator must agree exactly."""
    closes = 100.0 * np.cumprod(1.0 + np.random.default_rng(1).normal(0, 0.01, 40))
    bars = daily(40, closes=closes)
    folds = build_folds(bars, train_sessions=10, test_sessions=10)
    res = walk_forward(bars, lambda t, f: ((lambda h, st: 1.0), "hold", {}), folds,
                       make_backtester=make_bt(bars))
    for fr in res.folds:
        assert fr.metrics["excess_vs_hold"] == pytest.approx(0.0, abs=1e-12)
    assert res.summary["folds_beating_hold"] == 0


def test_flat_strategy_has_zero_return_and_no_fills():
    bars = daily(30, closes=np.linspace(100, 200, 30))
    folds = build_folds(bars, train_sessions=10, test_sessions=5)
    res = walk_forward(bars, lambda t, f: ((lambda h, st: 0.0), "flat", {}), folds,
                       make_backtester=make_bt(bars))
    assert res.summary["oos_total_return"] == pytest.approx(0.0)
    assert res.summary["total_fills"] == 0
    assert res.summary["hold_total_return"] > 0


# ---------------- stitching, by hand ----------------

def test_stitch_chains_fold_returns_geometrically():
    a = pd.DataFrame({"bar": [0, 1], "date": ["d0", "d1"], "time_key": ["t0", "t1"],
                      "nav": [100.0, 110.0]})                   # +10 %
    b = pd.DataFrame({"bar": [2, 3], "date": ["d2", "d3"], "time_key": ["t2", "t3"],
                      "nav": [100.0, 90.0]})                    # -10 %, fresh base
    s = stitch([a, b])
    assert s["wealth"].tolist() == pytest.approx([1.0, 1.1, 1.1, 0.99])
    assert s["fold"].tolist() == [0, 0, 1, 1]


def test_stitch_with_no_rows_is_empty_not_an_error():
    assert len(stitch([])) == 0


# ---------------- spearman ----------------

def test_spearman_hand_values():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    # ranks (1,2,3,4) vs (2,1,4,3): d = (-1, 1, -1, 1), sum d^2 = 4 -> 1 - 6*4/(4*15) = 0.6
    assert spearman([1, 2, 3, 4], [2, 1, 4, 3]) == pytest.approx(0.6)


def test_spearman_too_short_is_nan():
    assert np.isnan(spearman([1, 2], [2, 1]))
