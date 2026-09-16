"""Engine tests. Synthetic bars, hand-computable outcomes.

Every assertion here is a property the engine must hold regardless of strategy. The
arithmetic is derived from the fee schedule and the execution model, never captured
from the engine's own output.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.engine import (  # noqa: E402
    Backtester, ExecutionModel, PortfolioState,
)
from src.costs.fees import FeeSchedule, order_cost  # noqa: E402
from src.data.bars import BarSeries, REGULAR_BARS  # noqa: E402

HM = [f"{9 + (35 + 5 * k) // 60:02d}:{(35 + 5 * k) % 60:02d}" for k in range(REGULAR_BARS)]


def make(n_days=2, allow_overnight=False, base=100.0, drift=0.0, volume=1e6):
    frames = []
    for d in range(n_days):
        date = f"2024-01-{2 + d:02d}"
        px = base + d * drift + np.arange(REGULAR_BARS, dtype=float) * 0.0
        frames.append(pd.DataFrame({
            "time_key": [f"{date} {h}:00" for h in HM],
            "open": px, "close": px, "high": px + 0.5, "low": px - 0.5,
            "volume": np.full(REGULAR_BARS, volume),
        }))
    return BarSeries(pd.concat(frames, ignore_index=True), allow_overnight=allow_overnight)


FLAT = ExecutionModel(half_spread=0.0, slippage_bps_intraday=0.0,
                      slippage_bps_overnight=0.0)


# ---------------- the denominator ----------------

def test_nav_is_cash_plus_market_value_not_deployed_capital():
    s = PortfolioState(cash=111.0, shares=14, last_price=700.0)
    assert s.nav() == pytest.approx(111.0 + 14 * 700.0)
    assert s.deployed_value == pytest.approx(9800.0)
    assert s.nav() > s.deployed_value          # idle cash is inside the denominator


def test_idle_cash_stays_in_nav_across_the_whole_run():
    """At QQQ-like prices one share is a large fraction of the portfolio, so idle cash
    is always present. Returns computed on deployed capital would be inflated by it."""
    bars = make(base=700.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0, warmup=1)
    eq = res.equity
    assert (eq["nav"] - (eq["cash"] + eq["shares"] * eq["price"])).abs().max() < 1e-9
    held = eq[eq["shares"] > 0]
    assert len(held) > 0
    assert (held["cash"] > 0).all()            # idle cash exists and is counted


def test_strategy_cannot_request_leverage():
    bars = make()
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        bt.run(lambda h, st: 1.5, warmup=1)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        bt.run(lambda h, st: -0.2, warmup=1)


def test_position_never_exceeds_nav():
    bars = make(base=100.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0, warmup=1)
    assert (res.equity["deployed_value"] <= res.equity["nav"] + 1e-6).all()
    assert (res.equity["cash"] >= -1e-9).all()      # never borrows


# ---------------- look-ahead ----------------

def test_strategy_only_ever_sees_history_up_to_the_decision_bar():
    bars = make()
    seen = []

    def spy(h, st):
        seen.append((h["n"], h["time_key"][-1]))
        assert h["close"].base is None          # owned copy, not a view
        return 0.0

    Backtester(bars, execution=FLAT).run(spy, warmup=0)
    for n, last in seen:
        assert str(bars.time_key[n - 1]) == str(last)


def test_fill_happens_on_the_next_bar_open_not_the_signal_bar():
    bars = make(base=100.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0 if h["n"] == 5 else (1.0 if st.shares else 0.0), warmup=0)
    assert len(res.fills) >= 1
    f = res.fills.iloc[0]
    assert f["exec_i"] == f["signal_i"] + 1
    assert f["ref_price"] == pytest.approx(bars.open[int(f["exec_i"])])


# ---------------- costs ----------------

def test_buy_cost_matches_the_fee_schedule_exactly():
    bars = make(base=100.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0 if h["n"] >= 3 else 0.0, warmup=2)
    f = res.fills.iloc[0]
    expected = order_cost(int(f["shares"]), float(f["fill_price"]), "buy", FeeSchedule())
    assert f["fees"] == pytest.approx(expected.total, abs=1e-9)


def test_slippage_moves_the_fill_against_the_trader():
    bars = make(base=100.0)
    ex = ExecutionModel(half_spread=0.01, slippage_bps_intraday=2.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=ex)
    res = bt.run(lambda h, st: 1.0 if h["n"] >= 3 else 0.0, warmup=2)
    f = res.fills.iloc[0]
    assert f["fill_price"] > f["ref_price"]     # a buy pays more than the reference
    assert f["fill_price"] == pytest.approx(f["ref_price"] + ex.slip(f["ref_price"], False))


def test_zero_friction_is_not_the_default():
    """Without an explicit charge the engine would model frictionless trading, because
    open[i+1] is the price at the instant close[i] prints."""
    d = ExecutionModel()
    assert d.half_spread > 0
    assert d.slippage_bps_intraday > 0
    assert d.slippage_bps_overnight > d.slippage_bps_intraday


# ---------------- overnight ----------------

def test_overnight_fill_is_flagged_and_charged_more():
    bars = make(n_days=2, allow_overnight=True, base=100.0)
    ex = ExecutionModel(half_spread=0.0, slippage_bps_intraday=1.0,
                        slippage_bps_overnight=20.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=ex)
    last = bars.sessions[0].end
    # hold once bought - otherwise the very next bar sells again and there are 2 fills
    res = bt.run(lambda h, st: 1.0 if h["n"] - 1 >= last else 0.0, warmup=0)
    assert len(res.fills) == 1
    f = res.fills.iloc[0]
    assert bool(f["overnight"]) is True
    assert f["fill_price"] - f["ref_price"] == pytest.approx(ex.slip(f["ref_price"], True))


def test_no_fill_across_the_close_in_flat_mode():
    bars = make(n_days=2, allow_overnight=False)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    last = bars.sessions[0].end
    res = bt.run(lambda h, st: 1.0 if h["n"] - 1 == last else 0.0, warmup=0)
    assert len(res.fills) == 0


# ---------------- unfillable bars ----------------

def test_order_on_a_zero_volume_bar_is_rejected_not_filled():
    """Seven such bars exist in the real series, all March 2020 halts."""
    df = pd.DataFrame({
        "time_key": [f"2024-01-02 {h}:00" for h in HM],
        "open": np.full(REGULAR_BARS, 100.0), "close": np.full(REGULAR_BARS, 100.0),
        "high": np.full(REGULAR_BARS, 100.5), "low": np.full(REGULAR_BARS, 99.5),
        "volume": np.full(REGULAR_BARS, 1e6),
    })
    df.loc[10, "volume"] = 0.0
    bars = BarSeries(df)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0 if h["n"] - 1 == 9 else (1.0 if st.shares else 0.0),
                 warmup=0)
    assert len(res.fills) == 0
    assert any("not fillable" in r["reason"] for r in res.rejected)


def test_participation_cap_limits_size():
    df = pd.DataFrame({
        "time_key": [f"2024-01-02 {h}:00" for h in HM],
        "open": np.full(REGULAR_BARS, 1.0), "close": np.full(REGULAR_BARS, 1.0),
        "high": np.full(REGULAR_BARS, 1.5), "low": np.full(REGULAR_BARS, 0.5),
        "volume": np.full(REGULAR_BARS, 100.0),      # cap = 1 share at 1 %
    })
    bars = BarSeries(df)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0 if h["n"] >= 3 else 0.0, warmup=2)
    assert int(res.fills.iloc[0]["shares"]) == 1
    assert any("participation cap" in r["reason"] for r in res.rejected)


# ---------------- dividends ----------------

def test_dividend_credited_only_when_holding():
    bars = make(n_days=2, allow_overnight=True, base=100.0)
    div = pd.DataFrame([{"ex_date": "2024-01-03", "per_share_net": 0.50}])

    held = Backtester(bars, initial_cash=10_000.0, execution=FLAT,
                      dividends=div).run(lambda h, st: 1.0, warmup=1)
    flat = Backtester(bars, initial_cash=10_000.0, execution=FLAT,
                      dividends=div).run(lambda h, st: 0.0, warmup=1)

    assert len(held.dividends) == 1
    assert held.dividends.iloc[0]["cash_credited"] == pytest.approx(
        held.dividends.iloc[0]["shares"] * 0.50)
    assert len(flat.dividends) == 0


def test_dividend_is_credited_once_per_ex_date():
    bars = make(n_days=2, allow_overnight=True, base=100.0)
    div = pd.DataFrame([{"ex_date": "2024-01-03", "per_share_net": 0.50}])
    res = Backtester(bars, initial_cash=10_000.0, execution=FLAT,
                     dividends=div).run(lambda h, st: 1.0, warmup=1)
    assert len(res.dividends) == 1          # not once per bar of that day


# ---------------- accounting integrity ----------------

def test_cash_and_shares_reconcile_with_every_fill():
    bars = make(n_days=2, allow_overnight=True, base=100.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0 if (h["n"] // 7) % 2 == 0 else 0.0, warmup=1)

    cash, shares = 10_000.0, 0
    for _, f in res.fills.iterrows():
        q, px = int(f["shares"]), float(f["fill_price"])
        if f["side"] == "buy":
            cash -= q * px + f["fees"]
            shares += q
        else:
            cash += q * px - f["fees"]
            shares -= q
    credited = float(res.dividends["cash_credited"].sum()) if len(res.dividends) else 0.0
    assert shares == int(res.equity["shares"].iloc[-1])
    assert cash + credited == pytest.approx(float(res.equity["cash"].iloc[-1]), abs=1e-6)


def test_doing_nothing_leaves_nav_exactly_flat():
    bars = make(base=100.0)
    res = Backtester(bars, initial_cash=10_000.0, execution=FLAT).run(lambda h, st: 0.0)
    assert res.equity["nav"].nunique() == 1
    assert res.summary["total_return"] == pytest.approx(0.0)
    assert res.summary["n_fills"] == 0


def test_round_trip_at_a_constant_price_loses_exactly_the_costs():
    """The clearest statement of the cost drag: no price move, so the loss IS the fees."""
    bars = make(base=100.0)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0 if h["n"] - 1 in (5,) else 0.0, warmup=1)
    assert len(res.fills) == 2
    total_fees = float(res.fills["fees"].sum())
    assert res.equity["nav"].iloc[-1] == pytest.approx(10_000.0 - total_fees, abs=1e-6)
    assert float(res.trades.iloc[0]["gross_pnl"]) == pytest.approx(0.0, abs=1e-9)
    assert float(res.trades.iloc[0]["net_pnl"]) == pytest.approx(-total_fees, abs=1e-6)


def test_summary_states_the_denominator():
    bars = make(base=100.0)
    res = Backtester(bars, execution=FLAT).run(lambda h, st: 0.0)
    assert "full NAV" in res.summary["denominator"]
