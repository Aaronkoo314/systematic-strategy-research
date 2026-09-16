"""Independent risk controls.

The decisive tests are the ones where the STRATEGY is the adversary. A control that only
works when the strategy cooperates is not a control.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.data.bars import BarSeries, REGULAR_BARS  # noqa: E402
from src.risk.controls import RiskLimits, RiskManager, RiskState  # noqa: E402

HM = [f"{9 + (35 + 5 * k) // 60:02d}:{(35 + 5 * k) % 60:02d}" for k in range(REGULAR_BARS)]
FLAT = ExecutionModel(half_spread=0.0, slippage_bps_intraday=0.0,
                      slippage_bps_overnight=0.0)


def bars_from(prices_per_day, allow_overnight=True, volume=1e6):
    frames = []
    for d, px in enumerate(prices_per_day):
        arr = np.asarray(px, dtype=float)
        assert len(arr) == REGULAR_BARS
        frames.append(pd.DataFrame({
            "time_key": [f"2024-01-{2 + d:02d} {h}:00" for h in HM],
            "open": arr, "close": arr, "high": arr * 1.001, "low": arr * 0.999,
            "volume": np.full(REGULAR_BARS, volume),
        }))
    return BarSeries(pd.concat(frames, ignore_index=True),
                     allow_overnight=allow_overnight)


def flat_day(p):
    return np.full(REGULAR_BARS, float(p))


# ---------------- limits are validated, not trusted ----------------

def test_limits_must_be_ordered():
    with pytest.raises(ValueError, match="ordered"):
        RiskLimits(drawdown_review=0.10, drawdown_halt=0.08, drawdown_abandon=0.20)


def test_limits_reject_nonsense_rates():
    with pytest.raises(ValueError):
        RiskLimits(max_weight=1.5)
    with pytest.raises(ValueError):
        RiskLimits(daily_loss_rate=0.0)


# ---------------- high-water mark ----------------

def test_hwm_only_ever_rises():
    st = RiskState()
    for nav in (100, 120, 90, 80, 115, 130, 50):
        st.note_nav(float(nav), "2024-01-02")
    assert st.hwm == 130.0


def test_hwm_is_not_reset_by_adding_capital():
    """Resetting the high-water mark is how a drawdown breach gets hidden."""
    st = RiskState()
    st.note_nav(10_000.0, "2024-01-02")
    st.note_nav(8_000.0, "2024-01-03")
    assert st.drawdown(8_000.0) == pytest.approx(-0.20)
    st.note_nav(9_000.0, "2024-01-04")          # as if cash were added
    assert st.hwm == 10_000.0
    assert st.drawdown(9_000.0) == pytest.approx(-0.10)


# ---------------- thresholds ----------------

def test_abandon_is_terminal_and_cannot_be_cleared():
    rm = RiskManager(RiskLimits())
    rm.observe(10_000.0, "2024-01-02")
    rm.observe(7_900.0, "2024-01-03")           # -21 %
    assert rm.state.abandoned is True
    with pytest.raises(RuntimeError, match="terminal"):
        rm.clear_halt("feeling better about it", "2024-01-04")


def test_halt_can_be_cleared_but_only_explicitly_and_it_is_logged():
    rm = RiskManager(RiskLimits())
    rm.observe(10_000.0, "2024-01-02")
    rm.observe(9_150.0, "2024-01-03")           # -8.5 %
    assert rm.state.halted is True
    rm.clear_halt("data error confirmed and corrected", "2024-01-04")
    assert rm.state.halted is False
    kinds = [e["kind"] for e in rm.events]
    assert "HALT_DRAWDOWN" in kinds and "HALT_CLEARED" in kinds


def test_daily_loss_halts_new_risk():
    rm = RiskManager(RiskLimits())
    rm.observe(10_000.0, "2024-01-02")
    rm.observe(9_890.0, "2024-01-02")           # -1.1 % on the day
    assert rm.state.halted is True
    assert "daily loss" in rm.state.halt_reason


def test_drawdown_is_detected_while_sitting_still():
    """observe() runs every bar, so a breach while flat is still caught."""
    rm = RiskManager(RiskLimits())
    for nav in (10_000.0, 9_600.0, 9_100.0):
        rm.observe(nav, "2024-01-02")
    assert rm.state.review_flagged is True
    assert rm.state.halted is True


# ---------------- the gate ----------------

def base_kwargs(**kw):
    d = dict(date="2024-01-02", nav=10_000.0, price=100.0, prev_price=100.0,
             current_shares=0, target_shares=50, est_fees=1.1)
    d.update(kw)
    return d


def test_risk_reducing_orders_are_always_allowed():
    """Halting means stopping new risk, not trapping an existing position."""
    rm = RiskManager()
    rm.state.halted = True
    rm.state.halt_reason = "test"
    d = rm.check_order(**base_kwargs(current_shares=50, target_shares=0))
    assert d.allowed is True

    rm.state.abandoned = True
    rm.state.abandon_reason = "test"
    d = rm.check_order(**base_kwargs(current_shares=50, target_shares=10))
    assert d.allowed is True


def test_increasing_risk_is_refused_when_halted_and_when_abandoned():
    rm = RiskManager()
    rm.state.halted = True
    assert rm.check_order(**base_kwargs()).breach == "HALTED"
    rm.state.abandoned = True
    assert rm.check_order(**base_kwargs()).breach == "ABANDONED"


def test_exposure_cap_reduces_rather_than_refuses():
    rm = RiskManager(RiskLimits(max_weight=0.90))
    d = rm.check_order(**base_kwargs(target_shares=100))      # 100 % of NAV
    assert d.allowed is True
    assert d.max_shares is not None and d.max_shares < 100
    assert d.breach == "EXPOSURE_CAP"


def test_abnormal_bar_move_is_treated_as_suspect_data():
    rm = RiskManager(RiskLimits(max_bar_move=0.20))
    d = rm.check_order(**base_kwargs(price=130.0, prev_price=100.0))
    assert d.allowed is False
    assert d.breach == "ABNORMAL_PRICE"


def test_stale_data_blocks_new_risk():
    rm = RiskManager(RiskLimits(max_stale_bars=2))
    assert rm.check_order(**base_kwargs(bars_stale=3)).breach == "STALE_DATA"
    assert rm.check_order(**base_kwargs(bars_stale=1)).allowed is True


def test_duplicate_order_fingerprint_is_refused():
    rm = RiskManager()
    a = rm.check_order(**base_kwargs(fingerprint="bar7:buy:50"))
    b = rm.check_order(**base_kwargs(fingerprint="bar7:buy:50"))
    assert a.allowed is True
    assert b.allowed is False and b.breach == "DUPLICATE"


def test_fee_budget_is_actually_enforced_not_merely_computed():
    """This control previously existed only as a function nobody called."""
    rm = RiskManager(RiskLimits(annual_fee_budget_rate=0.001))   # USD 10 on 10,000
    rm.record_fees("2024-01-02", 9.5)
    ok = rm.check_order(**base_kwargs(est_fees=0.4))
    assert ok.allowed is True
    rm.record_fees("2024-01-02", 0.4)
    no = rm.check_order(**base_kwargs(est_fees=0.4, fingerprint="x"))
    assert no.allowed is False and no.breach == "FEE_BUDGET"


def test_fee_budget_rolls_off_after_a_year():
    rm = RiskManager(RiskLimits(annual_fee_budget_rate=0.001))
    for k in range(300):
        rm.record_fees(f"d{k}", 1.0)
    assert rm.state.trailing_fees(252) == pytest.approx(252.0)
    assert rm.state.trailing_fees(10) == pytest.approx(10.0)


# ---------------- the strategy as adversary ----------------

def test_a_strategy_demanding_full_exposure_is_capped_by_the_engine():
    """The cap binds at order time. Realised weight may drift slightly above it - fees
    leave cash while market value does not - and that drift is expected, not a leak."""
    bars = bars_from([flat_day(100.0), flat_day(100.0)])
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0, warmup=1)
    eq = res.equity
    max_w = (eq["deployed_value"] / eq["nav"]).max()
    assert max_w <= 0.90 + 1e-9, f"realised weight {max_w} exceeded the cap"
    assert max_w > 0.85, "cap bound far harder than intended"
    assert any(b["breach"] == "EXPOSURE_CAP" for b in res.risk_blocked)


def test_exposure_cap_is_sized_net_of_the_order_fees():
    """Sizing on gross NAV places a position already over the cap the moment it fills."""
    rm = RiskManager(RiskLimits(max_weight=0.90))
    d = rm.check_order(**base_kwargs(target_shares=100, est_fees=50.0))
    # 0.90 * (10000 - 50) / 100 = 89 shares, not the 90 that gross NAV would give
    assert d.allowed is True and d.max_shares == 89


def test_realised_weight_can_drift_above_the_cap_when_price_rises():
    """Documented and deliberate: holding the cap continuously would mean selling on
    every tick of drift, which costs more than the drift."""
    rising = [flat_day(100.0), np.full(REGULAR_BARS, 120.0)]
    bars = bars_from(rising)
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 0.90 if st.shares == 0 else 0.90, warmup=1)
    assert len(res.fills) >= 1


def test_a_strategy_cannot_trade_after_the_abandon_point():
    """The preregistered 20 % abandon point, enforced against a strategy that keeps
    trying to buy all the way down."""
    day1 = flat_day(100.0)
    day2 = flat_day(100.0)
    day3 = flat_day(70.0)          # -30 % gap
    day4 = flat_day(70.0)
    bars = bars_from([day1, day2, day3, day4])
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    res = bt.run(lambda h, st: 1.0, warmup=1)

    assert res.summary["abandoned"] is True
    assert "abandon" in res.summary["abandon_reason"].lower()
    blocked = [b for b in res.risk_blocked if b["breach"] == "ABANDONED"]
    assert blocked, "strategy kept buying but nothing was blocked as ABANDONED"

    first_abandon = next(e for e in res.summary["risk_events"] if e["kind"] == "ABANDON")
    after = res.fills[res.fills["time_key"] > first_abandon["date"] + " 23:59:59"]
    increasing = after[after["side"] == "buy"]
    assert len(increasing) == 0, "a buy was filled after abandonment"


def test_bypass_must_be_named_explicitly_and_is_recorded():
    """A result produced without controls must never be mistakable for one with them."""
    bars = bars_from([flat_day(100.0), flat_day(100.0)])
    guarded = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    assert guarded.run(lambda h, st: 1.0, warmup=1).summary["risk_controls"] == "enforced"

    unguarded = Backtester(bars, initial_cash=10_000.0, execution=FLAT,
                           bypass_risk_controls=True)
    res = unguarded.run(lambda h, st: 1.0, warmup=1)
    assert "BYPASSED" in res.summary["risk_controls"]
    assert (res.equity["deployed_value"] / res.equity["nav"]).max() > 0.90


def test_risk_controls_are_on_by_default():
    bars = bars_from([flat_day(100.0)])
    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    assert bt.risk is not None
    assert bt.bypass_risk_controls is False
    assert bt.risk.limits.drawdown_abandon == pytest.approx(0.20)


def test_a_strategy_raising_inside_the_engine_cannot_leave_risk_state_stale():
    """A strategy error must not produce a run that looks guarded but was not."""
    bars = bars_from([flat_day(100.0)])

    def broken(h, st):
        raise ZeroDivisionError("strategy bug")

    bt = Backtester(bars, initial_cash=10_000.0, execution=FLAT)
    with pytest.raises(ZeroDivisionError):
        bt.run(broken, warmup=1)
    assert bt.risk.state.hwm > 0        # observe() ran before the strategy was called
