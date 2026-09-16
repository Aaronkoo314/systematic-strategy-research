"""Moomoo Singapore US-equity fee schedule, as verified in docs/feasibility.md section 7.

Every component is itemised rather than returned as a single number, because Goal 6
requires costs to be reported by type, and because a single figure makes it impossible
to notice later that one component was silently dropped.

Rates verified 2026-09-15 against moomoo Singapore's published schedule:
  https://www.moomoo.com/sg/support/topic5_76?lang=en-us

Anything not verified is NOT modelled here and is listed in UNMODELLED below, so that
a missing cost is visible in code review rather than hidden in an optimistic total.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# Costs known to exist or suspected, but NOT yet verified, and therefore NOT charged
# by this module. Each one makes backtested results look BETTER than reality.
UNMODELLED = (
    "account-level fixed fees (custody / monthly / inactivity / FX) - unverified; "
    "at TP=10,000 even USD 5/month would be 0.60 %/yr, larger than every modelled item",
    "the NON-PROMOTIONAL rate card - this schedule assumes the zero-commission tier the "
    "operator currently qualifies for. Eligibility is not permanent and is not checked "
    "anywhere; on standard rates a round trip is materially more expensive",
    "GST treatment of the US settlement fee - charged by default here as the "
    "conservative choice, but moomoo does not state whether it counts as a clearing fee",
    "whether the platform fee is charged per SUBMITTED or per FILLED order - unverified; "
    "if per submitted, an unfilled limit order re-posted the next session is charged twice",
    "bid-ask spread and market impact - modelled separately by the execution model, not here",
    "borrow, margin interest - long-only and unlevered, but NO LONGER flat overnight "
    "(operator decision 2026-09-16). A negative cash balance across a night would accrue "
    "interest; the engine must refuse to place an order that would create one rather "
    "than rely on this being unmodelled",
)


@dataclass(frozen=True)
class FeeSchedule:
    """All rates in USD unless stated. Verified 2026-09-15."""

    platform_fee: float = 0.99          # per order
    gst_rate: float = 0.09              # on commission / platform / clearing fees
    settlement_per_share: float = 0.003
    settlement_cap_rate: float = 0.01   # capped at 1 % of order value
    commission: float = 0.0             # zero for ELIGIBLE SG clients only - see below

    # moomoo SG states GST applies to "commission, trading fees, clearing fees and
    # platform fees". Whether the US settlement fee counts as a clearing fee is not
    # stated. Defaulting to True charges it - the conservative direction, since an
    # overstated cost cannot manufacture an edge. Magnitude is small: on 14 QQQ shares
    # it is 0.042 * 0.09 = USD 0.004 per order. Flagged as unverified rather than
    # silently decided, because the previous version's own comment claimed clearing
    # fees were taxed while the code did not tax them.
    gst_on_settlement: bool = True

    # Sell side only
    sec_rate: float = 0.0000206         # x notional
    sec_min: float = 0.01
    taf_per_share: float = 0.000195
    taf_min: float = 0.01
    taf_max: float = 9.79

    # Both sides
    cat_per_share: float = 0.000003


@dataclass(frozen=True)
class CostBreakdown:
    commission: float
    platform: float          # platform fee including GST
    settlement: float
    sec: float               # sell only, else 0
    taf: float               # sell only, else 0
    cat: float
    total: float

    def as_dict(self) -> dict:
        return asdict(self)


def order_cost(shares: int, price: float, side: str,
               schedule: FeeSchedule = FeeSchedule()) -> CostBreakdown:
    """Cost of a single filled order.

    shares : whole shares, must be a positive integer (fractional support unverified)
    price  : fill price per share
    side   : 'buy' or 'sell'
    """
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if not isinstance(shares, int) or isinstance(shares, bool):
        raise TypeError("shares must be an int - fractional-share support is unverified")
    if shares <= 0:
        raise ValueError(f"shares must be positive, got {shares}")
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")

    notional = shares * price

    gst = 1.0 + schedule.gst_rate
    # commission and platform are reported SEPARATELY. The previous version folded a
    # non-zero commission into the platform field and hard-coded commission to 0.0 in
    # the breakdown, so the promise to report costs by type was false for any client
    # not on the zero-commission tier.
    commission = schedule.commission * gst
    platform = schedule.platform_fee * gst
    settlement = min(shares * schedule.settlement_per_share,
                     notional * schedule.settlement_cap_rate)
    if schedule.gst_on_settlement:
        settlement *= gst
    cat = shares * schedule.cat_per_share

    if side == "sell":
        sec = max(schedule.sec_min, notional * schedule.sec_rate)
        taf = min(schedule.taf_max, max(schedule.taf_min, shares * schedule.taf_per_share))
    else:
        sec = 0.0
        taf = 0.0

    total = commission + platform + settlement + sec + taf + cat
    return CostBreakdown(commission=commission, platform=platform, settlement=settlement,
                         sec=sec, taf=taf, cat=cat, total=total)


def round_trip_cost(shares: int, buy_price: float, sell_price: float,
                    schedule: FeeSchedule = FeeSchedule()) -> float:
    """Total fees for entering and exiting one position of `shares`."""
    return (order_cost(shares, buy_price, "buy", schedule).total
            + order_cost(shares, sell_price, "sell", schedule).total)


def max_round_trips_per_year(capital: float, price: float, cost_ceiling_rate: float,
                             schedule: FeeSchedule = FeeSchedule()) -> int:
    """How many round trips a fee budget allows.

    The operator set an annual fee ceiling of 10 % of the trading portfolio on
    2026-09-15.

    NOT ENFORCED ANYWHERE. This function computes a number; nothing consumes it.
    There is no counter, no throttle and no rejection path - the execution layer
    does not exist yet. An earlier version of this docstring said the ceiling was
    "enforced as a pre-trade risk control", which was false and was flagged by
    adversarial review: a reader would have taken the turnover constraint as solved
    and never implemented it. Mentioning a control is not having one.

    To enforce it, the execution layer must keep a rolling 12-month total of fees
    actually paid, estimate this order's cost before sending, and refuse when
    running_total + this_order > capital * ceiling - with a test that submits the
    408th round trip and asserts it is rejected.
    """
    if not 0.0 < cost_ceiling_rate <= 1.0:
        raise ValueError(
            f"cost_ceiling_rate must be a fraction in (0, 1], got {cost_ceiling_rate} - "
            f"passing 10 instead of 0.10 would silently allow 100x the turnover")
    if capital <= 0 or price <= 0:
        raise ValueError(f"capital and price must be positive, got {capital}, {price}")
    shares = int(capital // price)
    if shares < 1:
        raise ValueError(f"capital {capital} cannot buy one share at {price}")
    rt = round_trip_cost(shares, price, price, schedule)
    return int((capital * cost_ceiling_rate) // rt)
