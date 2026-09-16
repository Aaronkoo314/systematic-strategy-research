"""Independent pre-trade risk controls.

These sit OUTSIDE signal generation and run BEFORE any order. A strategy bug must not be
able to bypass them, so the engine does not offer a way to run without a RiskManager -
passing None gets the mandate defaults, not an unguarded run.

Two distinctions the module is built around:

  A THRESHOLD SAYS WHEN TO ACT. It does not cap the loss. Gaps, halts, thin liquidity,
  broker outages and network failure can all produce a loss larger than any number here.
  Nothing in this file guarantees a maximum loss, and no report may say otherwise.

  HALTING MEANS STOPPING NEW RISK, NOT LIQUIDATING. Reacting to every breach with an
  indiscriminate market sale is its own failure mode: it converts paper losses into
  realised ones at the worst prices, and it fires on data errors as readily as on real
  ones. Risk-reducing orders stay allowed throughout; only risk-increasing orders are
  refused.

Limits carry the mandate's values (investment_mandate.md §4, operator decisions of
2026-09-15 and 2026-09-16). They are intervention triggers, not guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TRADING_SESSIONS_PER_YEAR = 252


@dataclass(frozen=True)
class RiskLimits:
    """All rates are fractions of trading-portfolio NAV."""

    max_weight: float = 0.90
    """Mandate §4: aggregate risk-asset exposure <= 90 % of TP NAV.

    This binds AT ORDER TIME, on NAV net of the order's estimated fees. It is not a
    continuous guarantee on realised weight, and the difference is not pedantic:
      - fees leave cash, so NAV falls while market value does not; realised weight
        ticks up after every buy
      - a rising price raises weight with no order at all
    Holding weight continuously at the cap would mean selling on every small drift,
    which at USD 1.08 a round trip is churn that costs more than the drift.
    Realised weight is reported, and drift above the cap is expected and benign.

    Note the tension, which is real and should not be hidden: the passive benchmark is
    buy-and-hold at 100 %, so a capped strategy is handicapped against it by design.
    Benchmarks are run uncapped because they are benchmarks, not strategies.
    """

    annual_fee_budget_rate: float = 0.10
    """Operator decision 2026-09-16. At QQQ 706.38 and TP 10,000 this is 405 round
    trips a year. Enforced here as a rolling counter - previously it was only a
    function that computed a number nobody consumed."""

    daily_loss_rate: float = 0.01          # USD 100 on a 10,000 portfolio
    drawdown_review: float = 0.05          # USD 500  - flag, keep trading
    drawdown_halt: float = 0.08            # USD 800  - stop new risk
    drawdown_abandon: float = 0.20         # USD 2,000 - terminal, preregistered

    max_bar_move: float = 0.20
    """A single 5-minute bar moving more than this is treated as suspect data rather
    than a real price. QQQ's worst real 5-minute move in 2018-2026 is far below it."""

    max_stale_bars: int = 2
    """Refuse to trade on information older than this many bars."""

    def __post_init__(self):
        if not 0 < self.max_weight <= 1.0:
            raise ValueError("max_weight must be in (0, 1]")
        for name in ("annual_fee_budget_rate", "daily_loss_rate", "drawdown_review",
                     "drawdown_halt", "drawdown_abandon"):
            v = getattr(self, name)
            if not 0 < v <= 1.0:
                raise ValueError(f"{name} must be a fraction in (0, 1], got {v}")
        if not (self.drawdown_review <= self.drawdown_halt <= self.drawdown_abandon):
            raise ValueError(
                "thresholds must be ordered review <= halt <= abandon, got "
                f"{self.drawdown_review}, {self.drawdown_halt}, {self.drawdown_abandon}")


@dataclass
class RiskDecision:
    """`max_shares` is the SHARE COUNT the gate permits, not a weight.

    It returns shares rather than a weight deliberately. An earlier version returned a
    weight, the engine re-derived a share count from it, and the two derivations
    disagreed - the gate sized net of fees while the engine sized gross - so the cap
    leaked by the fee fraction. One computation, one place.
    """

    allowed: bool
    reason: str = "ok"
    max_shares: int | None = None      # set only when the gate reduced the order
    breach: str | None = None


@dataclass
class RiskState:
    """Persistent risk state. The high-water mark is monotone by construction.

    It is never reset by a restart, a configuration change or capital being added.
    Resetting it is how a drawdown breach gets hidden, so `hwm` has no setter and
    `note_nav` only ever raises it.
    """

    hwm: float = 0.0
    day: str | None = None
    day_start_nav: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    halt_kind: str = ""          # "DAILY" clears next session; "DRAWDOWN" needs review
    abandoned: bool = False
    abandon_reason: str = ""
    review_flagged: bool = False
    fees_by_session: list = field(default_factory=list)   # [(date, fees)]
    order_fingerprints: set = field(default_factory=set)
    events: list = field(default_factory=list)

    def note_nav(self, nav: float, date: str) -> None:
        if self.day != date:
            self.day = date
            self.day_start_nav = nav
        if nav > self.hwm:
            self.hwm = nav

    def drawdown(self, nav: float) -> float:
        return 0.0 if self.hwm <= 0 else nav / self.hwm - 1.0

    def day_return(self, nav: float) -> float:
        return 0.0 if self.day_start_nav <= 0 else nav / self.day_start_nav - 1.0

    def trailing_fees(self, sessions: int = TRADING_SESSIONS_PER_YEAR) -> float:
        recent = self.fees_by_session[-sessions:]
        return float(sum(f for _, f in recent))


class RiskManager:
    """Checked before every order. Returns a decision; never places or cancels anything."""

    def __init__(self, limits: RiskLimits | None = None,
                 state: RiskState | None = None):
        self.limits = limits or RiskLimits()
        self.state = state or RiskState()

    # ---------------- bookkeeping the engine must call every bar ----------------

    def observe(self, nav: float, date: str, bar_return: float | None = None) -> None:
        """Update NAV-derived state and fire threshold breaches.

        Called on every bar regardless of whether an order is contemplated, because a
        drawdown breach must be detected while sitting still, not only when trading.
        """
        st, lim = self.state, self.limits
        st.note_nav(nav, date)
        dd = st.drawdown(nav)

        if not st.abandoned and dd <= -lim.drawdown_abandon:
            st.abandoned = True
            st.abandon_reason = (
                f"drawdown {dd:.2%} breached the preregistered abandon point "
                f"{-lim.drawdown_abandon:.0%} on {date}")
            self._event(date, "ABANDON", st.abandon_reason, nav, dd)
            return

        if not st.halted and dd <= -lim.drawdown_halt:
            st.halted = True
            st.halt_kind = "DRAWDOWN"
            st.halt_reason = f"drawdown {dd:.2%} breached halt {-lim.drawdown_halt:.0%}"
            self._event(date, "HALT_DRAWDOWN", st.halt_reason, nav, dd)

        if not st.review_flagged and dd <= -lim.drawdown_review:
            st.review_flagged = True
            self._event(date, "REVIEW", f"drawdown {dd:.2%}", nav, dd)

        day_r = st.day_return(nav)
        if not st.halted and day_r <= -lim.daily_loss_rate:
            st.halted = True
            st.halt_kind = "DAILY"
            st.halt_reason = f"daily loss {day_r:.2%} breached {-lim.daily_loss_rate:.0%}"
            self._event(date, "HALT_DAILY_LOSS", st.halt_reason, nav, dd)

    def start_session(self, date: str) -> None:
        """New session. A DAILY loss halt expires here; a DRAWDOWN halt does not.

        This distinction was missing and it mattered enormously. Without it nothing ever
        cleared a halt, so after the first 1% down day - within days on QQQ - the system
        could only ever reduce exposure. A first full experiment run measured that
        artefact rather than the strategy: average weight collapsed to 8-31% against an
        intended 58-90%, and every configuration reported halted=True with roughly
        82,000 blocked orders. Those results are void and are recorded as such.

        A "daily" loss limit means the rest of that day. A drawdown halt is a different
        thing: it says something may be wrong with the strategy, and only a human
        looking at it should lift that.
        """
        st = self.state
        if st.halted and st.halt_kind == "DAILY":
            st.halted = False
            st.halt_kind = ""
            prev, st.halt_reason = st.halt_reason, ""
            self._event(date, "HALT_EXPIRED", f"daily halt expired at session open ({prev})",
                        None, None)
        st.fees_by_session.append((date, 0.0))

    def record_fees(self, date: str, fees: float) -> None:
        st = self.state
        if st.fees_by_session and st.fees_by_session[-1][0] == date:
            d, f = st.fees_by_session[-1]
            st.fees_by_session[-1] = (d, f + fees)
        else:
            st.fees_by_session.append((date, fees))

    def clear_halt(self, reason: str, date: str) -> None:
        """Lifting a halt is an explicit, logged act - never automatic.

        Abandonment cannot be cleared. That is the point of a preregistered abandon
        point: if it could be waved away when inconvenient it was never a limit.
        """
        if self.state.abandoned:
            raise RuntimeError(
                "abandonment is terminal and cannot be cleared: "
                f"{self.state.abandon_reason}")
        self.state.halted = False
        self.state.halt_kind = ""
        self.state.halt_reason = ""
        self._event(date, "HALT_CLEARED", reason, None, None)

    # ---------------- the gate ----------------

    def check_order(self, *, date: str, nav: float, price: float, prev_price: float,
                    current_shares: int, target_shares: int, est_fees: float,
                    bars_stale: int = 0, fingerprint: str | None = None) -> RiskDecision:
        st, lim = self.state, self.limits
        increasing = abs(target_shares) > abs(current_shares)

        # Risk-reducing orders are always allowed. Blocking them would trap a position
        # precisely when the controls say the position should not grow.
        if not increasing:
            if fingerprint is not None and fingerprint in st.order_fingerprints:
                return RiskDecision(False, "duplicate order fingerprint",
                                    breach="DUPLICATE")
            if fingerprint is not None:
                st.order_fingerprints.add(fingerprint)
            return RiskDecision(True, "risk-reducing order")

        if st.abandoned:
            return RiskDecision(False, st.abandon_reason, breach="ABANDONED")
        if st.halted:
            return RiskDecision(False, f"halted: {st.halt_reason}", breach="HALTED")

        if bars_stale > lim.max_stale_bars:
            return RiskDecision(False,
                                f"data is {bars_stale} bars stale, limit {lim.max_stale_bars}",
                                breach="STALE_DATA")

        if price <= 0 or prev_price <= 0:
            return RiskDecision(False, f"non-positive price {price}", breach="BAD_PRICE")
        move = abs(price / prev_price - 1.0)
        if move > lim.max_bar_move:
            return RiskDecision(False,
                                f"bar move {move:.1%} exceeds {lim.max_bar_move:.0%} - "
                                f"treated as suspect data, not a real price",
                                breach="ABNORMAL_PRICE")

        if fingerprint is not None:
            if fingerprint in st.order_fingerprints:
                return RiskDecision(False, "duplicate order fingerprint",
                                    breach="DUPLICATE")

        budget = nav * lim.annual_fee_budget_rate
        spent = st.trailing_fees()
        if spent + est_fees > budget:
            return RiskDecision(
                False,
                f"fee budget exhausted: {spent:.2f} + {est_fees:.2f} > {budget:.2f} "
                f"({lim.annual_fee_budget_rate:.0%} of NAV over a trailing year)",
                breach="FEE_BUDGET")

        # net of the order's own fees: they leave cash, so sizing on gross NAV would
        # place a position that is already over the cap the moment it fills
        max_shares = int(lim.max_weight * max(nav - est_fees, 0.0) / price)
        if target_shares > max_shares:
            if max_shares <= current_shares:
                return RiskDecision(False,
                                    f"exposure cap {lim.max_weight:.0%} already reached",
                                    breach="EXPOSURE_CAP")
            if fingerprint is not None:
                st.order_fingerprints.add(fingerprint)
            return RiskDecision(True, f"capped to {lim.max_weight:.0%} of NAV "
                                      f"({max_shares} shares, sized net of fees)",
                                max_shares=max_shares, breach="EXPOSURE_CAP")

        if fingerprint is not None:
            st.order_fingerprints.add(fingerprint)
        return RiskDecision(True)

    # ---------------- audit ----------------

    def _event(self, date, kind, reason, nav, dd) -> None:
        self.state.events.append({"date": date, "kind": kind, "reason": reason,
                                  "nav": nav, "drawdown": dd})

    @property
    def events(self) -> list:
        return list(self.state.events)
