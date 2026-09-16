"""Multi-asset portfolio backtester.

The properties that must hold regardless of allocation, checked against hand-computable
outcomes on synthetic daily bars.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.engine import ExecutionModel  # noqa: E402
from src.backtest.portfolio import PortfolioBacktester  # noqa: E402
from src.data.bars import BarSeries, FREQ_DAILY  # noqa: E402
from src.risk.controls import RiskLimits, RiskManager  # noqa: E402

FLAT = ExecutionModel(half_spread=0.0, slippage_bps_intraday=0.0,
                      slippage_bps_overnight=0.0)


def daily(prices, start="2020-01-02"):
    dates = pd.bdate_range(start, periods=len(prices)).strftime("%Y-%m-%d")
    p = np.asarray(prices, dtype=float)
    return BarSeries(pd.DataFrame({
        "time_key": [f"{d} 00:00:00" for d in dates],
        "open": p, "close": p, "high": p * 1.01, "low": p * 0.99,
        "volume": np.full(len(p), 1e7),
    }), frequency=FREQ_DAILY)


def two(n=600, a_start=100.0, b_start=50.0, a_drift=0.0, b_drift=0.0):
    a = a_start * (1 + a_drift) ** np.arange(n)
    b = b_start * (1 + b_drift) ** np.arange(n)
    return {"A": daily(a), "B": daily(b)}


def mk(series, **kw):
    kw.setdefault("execution", FLAT)
    kw.setdefault("risk", RiskManager(RiskLimits(max_weight=1.0)))
    return PortfolioBacktester(series, initial_cash=10_000.0, **kw)


# ---------------- alignment and input validation ----------------

def test_misaligned_series_are_rejected():
    s = two()
    s["B"] = daily([50.0] * 599, start="2020-01-02")
    with pytest.raises(ValueError, match="different lengths"):
        mk(s)


def test_dates_must_match_not_merely_lengths():
    s = two(n=300)
    s["B"] = daily([50.0] * 300, start="2021-01-04")     # same length, wrong dates
    with pytest.raises(ValueError, match="do not align"):
        mk(s)


def test_leverage_and_shorting_are_refused():
    bt = mk(two())
    with pytest.raises(ValueError, match="no leverage"):
        bt.run({"A": 0.7, "B": 0.5})
    with pytest.raises(ValueError, match="long only"):
        bt.run({"A": 1.2, "B": -0.2})


def test_unknown_symbol_is_refused():
    bt = mk(two())
    with pytest.raises(ValueError, match="no price series"):
        bt.run({"A": 0.5, "C": 0.5})


# ---------------- the denominator ----------------

def test_nav_is_cash_plus_market_value_every_bar():
    bt = mk(two())
    r = bt.run({"A": 0.6, "B": 0.4})
    eq = r.equity
    recomputed = eq["cash"] + eq["value_A"] + eq["value_B"]
    assert (eq["nav"] - recomputed).abs().max() < 1e-9


def test_idle_cash_from_rounding_stays_in_the_denominator():
    """At 100 a share on a 10,000 portfolio the residual is small but must be counted."""
    bt = mk(two(a_start=707.0, b_start=91.0))
    r = bt.run({"A": 0.5, "B": 0.5})
    assert (r.equity["cash"] > 0).all()
    assert (r.equity["weight_A"] + r.equity["weight_B"] < 1.0).all()


def test_cash_never_goes_negative():
    bt = mk(two())
    r = bt.run({"A": 0.9, "B": 0.1})
    assert (r.equity["cash"] >= -1e-9).all()


# ---------------- rebalancing ----------------

def test_rebalances_once_per_year_only():
    """Three calendar years of business days, one rebalance each plus the opening one."""
    n = 760                                    # about three years of weekdays
    bt = mk(two(n=n))
    r = bt.run({"A": 0.5, "B": 0.5})
    years = {rb["date"][:4] for rb in r.rebalances}
    assert len(r.rebalances) == len(years), "more than one rebalance in some year"
    assert len(years) >= 3


def test_rebalance_month_is_honoured():
    bt = mk(two(n=760), rebalance_month=7)
    r = bt.run({"A": 0.5, "B": 0.5})
    months = {rb["date"][5:7] for rb in r.rebalances[1:]}   # skip the opening one
    assert months <= {"07"}


def test_position_is_established_on_the_first_bar_not_next_january():
    """A window opening mid-year must not sit in cash until the next rebalance date."""
    bt = mk(two(n=300, a_start=100.0), )
    r = bt.run({"A": 0.5, "B": 0.5})
    assert r.equity["value_A"].iloc[5] > 0


def test_no_orders_between_rebalances():
    bt = mk(two(n=760))
    r = bt.run({"A": 0.5, "B": 0.5})
    fill_bars = set(r.fills["exec_bar"]) if len(r.fills) else set()
    reb_exec = {rb["exec_bar"] for rb in r.rebalances}
    assert fill_bars <= reb_exec


def test_weights_drift_between_rebalances():
    """No bands, no mid-year action: a rising leg is allowed to grow."""
    s = two(n=400, a_drift=0.004, b_drift=0.0)
    r = mk(s).run({"A": 0.5, "B": 0.5})
    w = r.equity["weight_A"]
    assert w.max() > w.iloc[1] + 0.05


# ---------------- costs and dividends ----------------

def test_fees_match_the_schedule_for_every_fill():
    from src.costs.fees import FeeSchedule, order_cost
    r = mk(two()).run({"A": 0.5, "B": 0.5})
    for _, f in r.fills.iterrows():
        exp = order_cost(int(f["shares"]), float(f["fill_price"]), f["side"],
                         FeeSchedule()).total
        assert f["fees"] == pytest.approx(exp, abs=1e-9)


def test_dividends_credited_per_symbol_and_once_each():
    s = two(n=300)
    d0 = s["A"].date[10]
    divs = {"A": pd.DataFrame([{"ex_date": str(d0), "per_share_net": 1.0}])}
    r = mk(s, dividends=divs).run({"A": 0.5, "B": 0.5})
    assert len(r.dividends) == 1
    row = r.dividends.iloc[0]
    assert row["symbol"] == "A"
    assert row["cash_credited"] == pytest.approx(row["shares"] * 1.0)


def test_dividends_not_credited_when_not_holding():
    s = two(n=300)
    d0 = s["A"].date[10]
    divs = {"A": pd.DataFrame([{"ex_date": str(d0), "per_share_net": 1.0}])}
    r = mk(s, dividends=divs).run({"A": 0.0, "B": 1.0})
    assert len(r.dividends) == 0


# ---------------- accounting integrity ----------------

def test_all_cash_allocation_leaves_nav_exactly_flat():
    r = mk(two()).run({"A": 0.0, "B": 0.0})
    assert r.equity["nav"].nunique() == 1
    assert r.summary["total_return"] == pytest.approx(0.0)
    assert r.summary["n_fills"] == 0


def test_a_flat_market_loses_exactly_the_fees():
    """Reconciled against the unrounded fills, not the summary - the summary rounds to
    four decimals, which is coarser than the identity being checked."""
    r = mk(two(n=300)).run({"A": 0.5, "B": 0.5})
    exact_fees = float(r.fills["fees"].sum())
    assert r.equity["nav"].iloc[-1] == pytest.approx(10_000.0 - exact_fees, abs=1e-9)
    assert r.summary["total_fees"] == pytest.approx(exact_fees, abs=5e-5)


def test_drawdown_and_breach_flag_agree():
    s = two(n=400)
    s["A"] = daily(np.concatenate([np.full(200, 100.0), np.full(200, 40.0)]))
    r = mk(s).run({"A": 1.0, "B": 0.0})
    assert r.summary["max_drawdown"] < -0.20
    assert r.summary["breached_20pct"] is True


def test_summary_states_the_denominator():
    r = mk(two()).run({"A": 0.5, "B": 0.5})
    assert "full NAV" in r.summary["denominator"]
