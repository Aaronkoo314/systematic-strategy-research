"""Bootstrap: deterministic under a seed, hand-checkable in the degenerate cases, and
measuring returns on NAV rather than on deployed capital."""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.validation.monte_carlo import (  # noqa: E402
    bootstrap, returns_on_nav, run, summarise,
)


def test_same_seed_same_paths():
    r = np.array([0.01, -0.02, 0.03, 0.005, -0.01])
    a = bootstrap(r, n_paths=50, seed=7)
    b = bootstrap(r, n_paths=50, seed=7)
    pd.testing.assert_frame_equal(a, b)
    c = bootstrap(r, n_paths=50, seed=8)
    assert not a["terminal_return"].equals(c["terminal_return"])


def test_constant_returns_give_a_constant_terminal():
    r = np.full(10, 0.01)
    paths = bootstrap(r, n_paths=20, seed=0)
    assert paths["terminal_return"].to_numpy() == pytest.approx(np.full(20, 1.01 ** 10 - 1))
    assert (paths["max_drawdown"] == 0.0).all()


def test_full_length_block_is_a_rotation_so_terminal_is_historical():
    """With block == n every path is a cyclic rotation: the same multiset of returns in
    the same cyclic order, so the terminal wealth is exactly the historical one."""
    r = np.array([0.05, -0.03, 0.02, -0.04, 0.06, 0.01])
    hist = float(np.prod(1 + r) - 1)
    paths = bootstrap(r, n_paths=30, seed=3, block=len(r))
    assert paths["terminal_return"].to_numpy() == pytest.approx(np.full(30, hist))


def test_block_bootstrap_keeps_consecutive_pairs_together():
    """Returns 0..9 with block 5: every drawn block is 5 consecutive values (mod 10)."""
    r = np.arange(10, dtype=float) / 100.0
    paths = bootstrap(r, n_paths=1, seed=11, block=5)
    assert len(paths) == 1
    # reconstruct the draw with the same generator to inspect the sequence
    rng = np.random.default_rng(11)
    starts = rng.integers(0, 10, size=2)
    idx = (starts[:, None] + np.arange(5)[None, :]).ravel() % 10
    s = r[idx]
    for k in range(len(s) - 1):
        if k % 5 != 4:
            assert round((s[k + 1] - s[k]) * 100) % 10 == 1


def test_block_bounds():
    r = np.array([0.1, 0.2, 0.3])
    with pytest.raises(ValueError):
        bootstrap(r, block=0)
    with pytest.raises(ValueError):
        bootstrap(r, block=4)


def test_returns_on_nav_divides_by_nav_at_entry_not_notional():
    """One trade: 10 shares bought at 100 with NAV 10,000, sold at 110, fees 2.
    On deployed capital that is +9.8 %; on NAV it is 98 / 10,000 = +0.98 %."""
    trades = pd.DataFrame({"entry_bar": [5], "net_pnl": [98.0],
                           "entry_price": [100.0], "shares": [10]})
    equity = pd.DataFrame({"bar": range(10), "nav": [10_000.0] * 10})
    r = returns_on_nav(trades, equity)
    assert r == pytest.approx([0.0098])


def test_returns_on_nav_rejects_an_entry_bar_without_equity():
    trades = pd.DataFrame({"entry_bar": [99], "net_pnl": [1.0]})
    equity = pd.DataFrame({"bar": range(10), "nav": [1.0] * 10})
    with pytest.raises(ValueError, match="no equity row"):
        returns_on_nav(trades, equity)


def test_summary_quantiles_are_ordered_and_historical_percentile_is_a_probability():
    rng = np.random.default_rng(0)
    r = rng.normal(0.002, 0.02, 60)
    paths = bootstrap(r, n_paths=500, seed=1)
    s = summarise(r, paths)
    assert s.terminal_return_p05 <= s.terminal_return_p50 <= s.terminal_return_p95
    assert s.max_drawdown_p05 <= s.max_drawdown_p50 <= 0.0
    assert 0.0 <= s.probability_of_loss <= 1.0
    assert 0.0 <= s.historical_percentile <= 1.0
    assert s.n_trades == 60 and s.n_paths == 500


def test_run_end_to_end_and_refuses_an_empty_record():
    trades = pd.DataFrame({"entry_bar": [1, 3, 5], "net_pnl": [50.0, -30.0, 20.0]})
    equity = pd.DataFrame({"bar": range(8), "nav": [10_000.0] * 8})
    paths, s = run(trades, equity, n_paths=100, seed=2)
    assert len(paths) == 100
    assert s.historical_terminal_return == pytest.approx(1.005 * 0.997 * 1.002 - 1)
    with pytest.raises(ValueError):
        run(trades.iloc[:0], equity)
