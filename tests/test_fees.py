"""Fee model tested against hand-computed values from the official schedule.

These are not regression tests against the code's own output - every expected value is
computed here from the published rates, so if the module drifts from the schedule the
test fails rather than blessing the drift.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.costs.fees import (  # noqa: E402
    FeeSchedule, order_cost, round_trip_cost, max_round_trips_per_year, UNMODELLED,
)

GST = 1.09
PLATFORM_WITH_GST = 0.99 * GST  # 1.0791
# moomoo SG applies GST to commission, trading fees, clearing fees and platform fees.
# Whether the US settlement fee is a clearing fee is unstated; the model charges it
# as the conservative choice, so these expectations charge it too.
SETTLE_GST = GST


def test_platform_fee_includes_gst():
    c = order_cost(1, 100.0, "buy")
    assert c.platform == pytest.approx(PLATFORM_WITH_GST, abs=1e-12)


def test_buy_has_no_sec_or_taf():
    """SEC and FINRA TAF are sell-side only. Charging them on buys would overstate cost."""
    c = order_cost(100, 500.0, "buy")
    assert c.sec == 0.0
    assert c.taf == 0.0


def test_sell_charges_sec_and_taf():
    c = order_cost(100, 500.0, "sell")
    assert c.sec > 0
    assert c.taf > 0


def test_qqq_round_trip_matches_hand_computation():
    """The live case from docs/intraday_data.md section 5: QQQ 706.38, 14 whole shares."""
    price, shares = 706.38, 14
    notional = shares * price  # 9889.32

    settle = shares * 0.003 * SETTLE_GST
    buy = PLATFORM_WITH_GST + settle + shares * 0.000003
    sell = (PLATFORM_WITH_GST + settle
            + max(0.01, notional * 0.0000206)
            + max(0.01, shares * 0.000195)
            + shares * 0.000003)

    assert order_cost(shares, price, "buy").total == pytest.approx(buy, abs=1e-9)
    assert order_cost(shares, price, "sell").total == pytest.approx(sell, abs=1e-9)
    # buy  : 1.0791 + 0.04578 + 0.000042                      = 1.124922
    # sell : 1.0791 + 0.04578 + 0.203719992 + 0.01 + 0.000042 = 1.338641992
    assert round_trip_cost(shares, price, price) == pytest.approx(2.463563992, abs=1e-9)


def test_sec_minimum_binds_on_small_orders():
    """SEC fee has a USD 0.01 floor; a tiny notional must pay the floor, not the rate."""
    c = order_cost(1, 10.0, "sell")          # 10 * 0.0000206 = 0.000206 << 0.01
    assert c.sec == pytest.approx(0.01)


def test_taf_minimum_and_maximum_bind():
    small = order_cost(1, 10.0, "sell")
    assert small.taf == pytest.approx(0.01)   # 1 * 0.000195 << 0.01

    huge = order_cost(1_000_000, 10.0, "sell")
    assert huge.taf == pytest.approx(9.79)    # 1e6 * 0.000195 = 195 -> capped


def test_settlement_cap_binds_on_low_priced_shares():
    """Settlement is 0.003/share capped at 1 % of value. At USD 0.10/share the cap binds."""
    shares, price = 10_000, 0.10
    uncapped = shares * 0.003          # 30.00
    cap = shares * price * 0.01        # 10.00
    assert order_cost(shares, price, "buy").settlement == pytest.approx(min(uncapped, cap) * SETTLE_GST)
    assert order_cost(shares, price, "buy").settlement == pytest.approx(cap * SETTLE_GST)


def test_settlement_cap_does_not_bind_at_normal_prices():
    shares, price = 14, 706.38
    assert order_cost(shares, price, "buy").settlement == pytest.approx(shares * 0.003 * SETTLE_GST)


def test_total_equals_sum_of_components():
    """A component must never be dropped from the total."""
    for side in ("buy", "sell"):
        c = order_cost(37, 412.5, side)
        assert c.total == pytest.approx(
            c.platform + c.settlement + c.sec + c.taf + c.cat, abs=1e-12)


def test_commission_is_zero_but_present():
    assert order_cost(10, 100.0, "buy").commission == 0.0


def test_fractional_shares_rejected():
    """Fractional-share support via API is unverified, so the model must refuse it
    rather than silently price a trade that may not be placeable."""
    with pytest.raises(TypeError):
        order_cost(1.5, 100.0, "buy")


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        order_cost(0, 100.0, "buy")
    with pytest.raises(ValueError):
        order_cost(-5, 100.0, "buy")
    with pytest.raises(ValueError):
        order_cost(10, 0.0, "buy")
    with pytest.raises(ValueError):
        order_cost(10, 100.0, "hold")


def test_turnover_budget_matches_operator_ceiling():
    """Operator set a 10 %/yr fee ceiling on 2026-09-15 at TP = 10,000.

    At QQQ 706.38 that is 14 shares and USD 2.463564 per round trip, so the budget
    allows floor(1000 / 2.463564) = 405. It was 407 before GST was charged on the
    settlement fee - the conservative direction.
    """
    n = max_round_trips_per_year(capital=10_000.0, price=706.38, cost_ceiling_rate=0.10)
    assert n == 405


def test_turnover_budget_scales_with_ceiling():
    at_10 = max_round_trips_per_year(10_000.0, 706.38, 0.10)
    at_1 = max_round_trips_per_year(10_000.0, 706.38, 0.01)
    assert at_1 == pytest.approx(at_10 / 10, rel=0.02)


def test_schedule_is_immutable():
    """A frozen cost model must not be mutable at runtime - silently loosening costs
    mid-backtest is exactly the failure this project is meant to prevent."""
    s = FeeSchedule()
    with pytest.raises(Exception):
        s.platform_fee = 0.0


# ---------------- regressions from adversarial review, 2026-09-16 ----------------

def test_commission_is_reported_separately_not_folded_into_platform():
    """A non-zero commission was folded into platform while the commission field was
    hard-coded to 0.0, so reporting costs by type was false off the promo tier."""
    sched = FeeSchedule(commission=1.50)
    c = order_cost(10, 100.0, "buy", sched)
    assert c.commission == pytest.approx(1.50 * 1.09)
    assert c.platform == pytest.approx(0.99 * 1.09)
    assert c.total == pytest.approx(
        c.commission + c.platform + c.settlement + c.sec + c.taf + c.cat, abs=1e-12)


def test_cost_ceiling_rate_must_be_a_fraction():
    """Passing 10 for 10 per cent would have silently allowed 100x the turnover."""
    for bad in (10, 0.0, -0.1):
        with pytest.raises(ValueError, match="fraction"):
            max_round_trips_per_year(10_000.0, 706.38, bad)


def test_gst_on_settlement_is_explicit_and_switchable():
    """The choice is unverified, so it must be visible and reversible, not buried."""
    with_gst = order_cost(14, 706.38, "buy", FeeSchedule(gst_on_settlement=True))
    without = order_cost(14, 706.38, "buy", FeeSchedule(gst_on_settlement=False))
    assert with_gst.settlement == pytest.approx(without.settlement * 1.09)


def test_unmodelled_list_reflects_the_overnight_decision():
    """The module claimed margin interest was not applicable because the strategy was
    flat overnight. Overnight holding was enabled on 2026-09-16."""
    joined = " ".join(UNMODELLED).lower()
    assert "overnight" in joined
    assert "non-promotional" in joined
