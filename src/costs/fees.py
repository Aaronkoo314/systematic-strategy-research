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
    "whether the platform fee is charged per SUBMITTED or per FILLED order - unverified; "
    "if per submitted, an unfilled limit order re-posted the next session is charged twice",
    "bid-ask spread and market impact - modelled separately by the execution model, not here",
    "borrow, margin interest - not applicable: long-only, unlevered, flat overnight",
)


@dataclass(frozen=True)
class FeeSchedule:
    """All rates in USD unless stated. Verified 2026-09-15."""

    platform_fee: float = 0.99          # per order
    gst_rate: float = 0.09              # on commission / platform / clearing fees
    settlement_per_share: float = 0.003
    settlement_cap_rate: float = 0.01   # capped at 1 % of order value
    commission: float = 0.0             # zero for eligible SG clients

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

    commission = schedule.commission
    # GST applies to commission and platform fee, not to the regulatory pass-throughs.
    platform = (schedule.platform_fee + commission) * (1.0 + schedule.gst_rate)
    settlement = min(shares * schedule.settlement_per_share,
                     notional * schedule.settlement_cap_rate)
    cat = shares * schedule.cat_per_share

    if side == "sell":
        sec = max(schedule.sec_min, notional * schedule.sec_rate)
        taf = min(schedule.taf_max, max(schedule.taf_min, shares * schedule.taf_per_share))
    else:
        sec = 0.0
        taf = 0.0

    total = platform + settlement + sec + taf + cat
    return CostBreakdown(commission=0.0, platform=platform, settlement=settlement,
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
    shares = int(capital // price)
    if shares < 1:
        raise ValueError(f"capital {capital} cannot buy one share at {price}")
    rt = round_trip_cost(shares, price, price, schedule)
    return int((capital * cost_ceiling_rate) // rt)
