"""Event-driven backtest engine for the 5-minute QQQ series.

Design decisions that exist to prevent specific, named failures:

1. A strategy returns a TARGET WEIGHT in [0, 1], never a share count. Share sizing,
   whole-share rounding and idle cash all live here, in one tested place. If a strategy
   could compute its own share count it could also compute returns on deployed capital
   instead of full NAV, which inflates every figure by the idle fraction - at QQQ 706
   one share is 7.6 % of a USD 10,000 portfolio.

2. NAV is always cash + market value. There is no other denominator anywhere in this
   file, and `deployed_value` is recorded only so a report can show it as a clearly
   labelled secondary line.

3. A decision at bar i fills at `next_executable_index(i)` at that bar's OPEN. The bar
   layer checks the relation on every call; the engine never touches prices directly.

4. Execution friction is charged EXPLICITLY. open[i+1] is the price at the instant
   close[i] prints - 20.05 % of pairs are exactly equal and 62.93 % within one cent -
   so "fill on the next bar" is a bookkeeping delay, not a time delay. Without an
   explicit spread and slippage charge this engine would model frictionless trading.

5. Overnight fills are a different animal and are charged and reported separately: the
   information is 17 hours stale and the gap is not a five-minute move.

6. Dividends are cash events on ex-dates, net of withholding. The price series is raw
   on purpose; substituting an adjusted series would encode future distributions into
   historical prices, which is look-ahead.

Known and deliberately unmodelled, listed so they are visible in review:
  - limit-order non-fill. This engine sends the equivalent of a market order at the
    next open, which always fills but pays the spread. Modelling resting limit orders
    requires modelling non-fill, which is a separate piece of work.
  - queue position and market impact beyond the participation cap.
  - the account-level fixed fees and platform-fee basis listed in costs.fees.UNMODELLED.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np
import pandas as pd

from src.costs.fees import FeeSchedule, order_cost
from src.data.bars import BarSeries, NotFillableError


class Strategy(Protocol):
    """Receives only what was knowable at bar i, returns a target weight in [0, 1]."""

    def __call__(self, history: dict, state: "PortfolioState") -> float: ...


@dataclass(frozen=True)
class ExecutionModel:
    """Friction assumptions. These are ASSUMPTIONS, not measurements.

    QQQ's quoted spread is about one cent, which at 706 is 0.14 bp. The defaults below
    are deliberately not the most favourable reading; §6 of the report SOP requires the
    stress variants to be run at higher values as well.
    """

    half_spread: float = 0.005            # half of a one-cent quoted spread
    slippage_bps_intraday: float = 1.0
    slippage_bps_overnight: float = 5.0   # a gap is not a five-minute move
    max_participation: float = 0.01       # never take more than 1 % of a bar's volume

    def slip(self, price: float, overnight: bool) -> float:
        bps = self.slippage_bps_overnight if overnight else self.slippage_bps_intraday
        return self.half_spread + price * bps / 10_000.0


@dataclass
class PortfolioState:
    cash: float
    shares: int = 0
    last_price: float = 0.0

    @property
    def deployed_value(self) -> float:
        return self.shares * self.last_price

    def nav(self, price: float | None = None) -> float:
        """The only denominator used anywhere. Cash plus market value, always."""
        p = self.last_price if price is None else price
        return self.cash + self.shares * p


@dataclass
class Fill:
    signal_i: int
    exec_i: int
    time_key: str
    side: str
    shares: int
    ref_price: float        # the bar's open, before friction
    fill_price: float       # after spread and slippage
    slippage_cost: float
    fees: float
    fee_breakdown: dict
    overnight: bool
    nav_after: float


@dataclass
class BacktestResult:
    equity: pd.DataFrame
    fills: pd.DataFrame
    trades: pd.DataFrame
    dividends: pd.DataFrame
    rejected: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class Backtester:
    def __init__(self, bars: BarSeries, *, initial_cash: float = 10_000.0,
                 execution: ExecutionModel = ExecutionModel(),
                 fees: FeeSchedule = FeeSchedule(),
                 dividends: pd.DataFrame | None = None,
                 max_orders: int | None = None,
                 lookback: int = 500):
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.bars = bars
        self.initial_cash = float(initial_cash)
        self.execution = execution
        self.fees = fees
        self.max_orders = max_orders
        # Bounded lookback is required, not optional: an unbounded window makes a full
        # pass O(n^2) in copying. A strategy needing more must keep its own incremental
        # state rather than ask for the whole past on every bar.
        if not isinstance(lookback, int) or lookback < 1:
            raise ValueError(f"lookback must be a positive int, got {lookback!r}")
        self.lookback = lookback

        # ex_date -> net cash per share already after withholding
        self.div = {}
        if dividends is not None and len(dividends):
            for _, r in dividends.iterrows():
                self.div[str(r["ex_date"])] = float(r["per_share_net"])

    # ------------------------------------------------------------------

    def _target_shares(self, weight: float, nav: float, price: float) -> int:
        """Whole shares only. Long-only, never more than NAV - no leverage by rounding."""
        if not (0.0 <= weight <= 1.0):
            raise ValueError(f"target weight must be in [0, 1], got {weight}")
        if price <= 0:
            raise ValueError("price must be positive")
        return int(math.floor(weight * nav / price))

    def run(self, strategy: Strategy, *, start: int = 0, end: int | None = None,
            warmup: int = 0) -> BacktestResult:
        bars = self.bars
        n = len(bars)
        end = n if end is None else min(end, n)
        state = PortfolioState(cash=self.initial_cash, shares=0,
                               last_price=float(bars.close[start]))

        fills: list[Fill] = []
        rejected: list[dict] = []
        div_events: list[dict] = []
        eq_i, eq_nav, eq_cash, eq_shares, eq_px = [], [], [], [], []
        paid_dividend_on: set[str] = set()
        orders_placed = 0

        for i in range(start, end):
            price = float(bars.close[i])
            state.last_price = price

            # --- dividends: credited once, on the first bar of the ex-date, to shares
            #     held at that moment. Raw prices, so this is the only place a
            #     distribution can enter the account.
            d = str(bars.date[i])
            if d in self.div and d not in paid_dividend_on:
                paid_dividend_on.add(d)
                if state.shares > 0:
                    gross_net = state.shares * self.div[d]
                    state.cash += gross_net
                    div_events.append({
                        "ex_date": d, "time_key": str(bars.time_key[i]),
                        "shares": state.shares, "per_share_net": self.div[d],
                        "cash_credited": gross_net,
                    })

            if i - start >= warmup:
                exec_i = bars.next_executable_index(i)
                if exec_i is not None and exec_i < end:
                    weight = float(strategy(bars.history_upto(i, self.lookback), state))
                    nav = state.nav(price)
                    want = self._target_shares(weight, nav, price)
                    delta = want - state.shares
                    if delta != 0:
                        if self.max_orders is not None and orders_placed >= self.max_orders:
                            rejected.append({"signal_i": i, "reason": "order budget exhausted",
                                             "wanted_delta": delta})
                        else:
                            ok = self._execute(state, i, exec_i, delta, fills, rejected)
                            if ok:
                                orders_placed += 1

            eq_i.append(i)
            eq_nav.append(state.nav(price))
            eq_cash.append(state.cash)
            eq_shares.append(state.shares)
            eq_px.append(price)

        equity = pd.DataFrame({
            "bar": eq_i,
            "time_key": [str(bars.time_key[k]) for k in eq_i],
            "date": [str(bars.date[k]) for k in eq_i],
            "price": eq_px, "cash": eq_cash, "shares": eq_shares, "nav": eq_nav,
        })
        equity["deployed_value"] = equity["shares"] * equity["price"]
        equity["hwm"] = equity["nav"].cummax()
        equity["drawdown"] = equity["nav"] / equity["hwm"] - 1.0

        fills_df = pd.DataFrame([f.__dict__ for f in fills]) if fills else pd.DataFrame(
            columns=[k for k in Fill.__annotations__])
        return BacktestResult(
            equity=equity, fills=fills_df, trades=self._pair_trades(fills),
            dividends=pd.DataFrame(div_events), rejected=rejected,
            summary=self._summarise(equity, fills, div_events, rejected))

    # ------------------------------------------------------------------

    def _execute(self, state: PortfolioState, signal_i: int, exec_i: int,
                 delta: int, fills: list, rejected: list) -> bool:
        bars, ex = self.bars, self.execution
        side = "buy" if delta > 0 else "sell"
        qty = abs(delta)

        try:
            ref = bars.fill_price(signal_i, exec_i)       # checks the execution rule
        except NotFillableError as exc:
            rejected.append({"signal_i": signal_i, "exec_i": exec_i,
                             "reason": f"not fillable: {exc}", "wanted_delta": delta})
            return False

        # participation cap: a 5-minute bar cannot absorb an arbitrary size
        cap = int(bars.volume[exec_i] * ex.max_participation)
        if cap < 1:
            rejected.append({"signal_i": signal_i, "exec_i": exec_i,
                             "reason": "bar volume cannot absorb one share",
                             "wanted_delta": delta})
            return False
        if qty > cap:
            rejected.append({"signal_i": signal_i, "exec_i": exec_i,
                             "reason": f"participation cap: wanted {qty}, filled {cap}",
                             "wanted_delta": delta})
            qty = cap

        overnight = bars.is_overnight_fill(signal_i, exec_i)
        slip = ex.slip(ref, overnight)
        px = ref + slip if side == "buy" else ref - slip
        if px <= 0:
            rejected.append({"signal_i": signal_i, "exec_i": exec_i,
                             "reason": "slippage drove the fill price non-positive",
                             "wanted_delta": delta})
            return False

        cost = order_cost(int(qty), float(px), side, self.fees)

        if side == "buy":
            need = qty * px + cost.total
            if need > state.cash + 1e-9:
                affordable = qty
                while affordable > 0:
                    c = order_cost(int(affordable), float(px), side, self.fees)
                    if affordable * px + c.total <= state.cash + 1e-9:
                        break
                    affordable -= 1
                if affordable == 0:
                    rejected.append({"signal_i": signal_i, "exec_i": exec_i,
                                     "reason": "insufficient cash for one share",
                                     "wanted_delta": delta})
                    return False
                rejected.append({"signal_i": signal_i, "exec_i": exec_i,
                                 "reason": f"cash capped: wanted {qty}, filled {affordable}",
                                 "wanted_delta": delta})
                qty = affordable
                cost = order_cost(int(qty), float(px), side, self.fees)
            state.cash -= qty * px + cost.total
            state.shares += qty
        else:
            if qty > state.shares:
                qty = state.shares
                if qty == 0:
                    return False
                cost = order_cost(int(qty), float(px), side, self.fees)
            state.cash += qty * px - cost.total
            state.shares -= qty

        state.last_price = float(bars.close[exec_i])
        fills.append(Fill(
            signal_i=signal_i, exec_i=exec_i, time_key=str(bars.time_key[exec_i]),
            side=side, shares=int(qty), ref_price=float(ref), fill_price=float(px),
            slippage_cost=float(slip * qty), fees=float(cost.total),
            fee_breakdown=cost.as_dict(), overnight=bool(overnight),
            nav_after=state.nav(),
        ))
        return True

    # ------------------------------------------------------------------

    @staticmethod
    def _pair_trades(fills: list) -> pd.DataFrame:
        """Pair buys and sells into round trips, FIFO."""
        open_lots: list[dict] = []
        rows = []
        for f in fills:
            if f.side == "buy":
                open_lots.append({"shares": f.shares, "price": f.fill_price,
                                  "fees": f.fees, "fill": f})
                continue
            remaining = f.shares
            while remaining > 0 and open_lots:
                lot = open_lots[0]
                take = min(remaining, lot["shares"])
                entry_fee = lot["fees"] * take / lot["fill"].shares
                exit_fee = f.fees * take / f.shares
                gross = (f.fill_price - lot["price"]) * take
                rows.append({
                    "entry_time": lot["fill"].time_key, "exit_time": f.time_key,
                    "entry_bar": lot["fill"].exec_i, "exit_bar": f.exec_i,
                    "shares": take,
                    "entry_price": lot["price"], "exit_price": f.fill_price,
                    "gross_pnl": gross, "fees": entry_fee + exit_fee,
                    "net_pnl": gross - entry_fee - exit_fee,
                    "bars_held": f.exec_i - lot["fill"].exec_i,
                    "crossed_session": lot["fill"].time_key[:10] != f.time_key[:10],
                    "entry_overnight": lot["fill"].overnight, "exit_overnight": f.overnight,
                })
                lot["shares"] -= take
                remaining -= take
                if lot["shares"] == 0:
                    open_lots.pop(0)
        return pd.DataFrame(rows)

    def _summarise(self, equity, fills, div_events, rejected) -> dict:
        nav0 = float(equity["nav"].iloc[0]) if len(equity) else self.initial_cash
        nav1 = float(equity["nav"].iloc[-1]) if len(equity) else self.initial_cash
        sessions = equity["date"].nunique() if len(equity) else 0
        years = sessions / 252.0 if sessions else 0.0
        total_fees = float(sum(f.fees for f in fills))
        total_slip = float(sum(f.slippage_cost for f in fills))
        return {
            "initial_nav": nav0, "final_nav": nav1,
            "total_return": nav1 / nav0 - 1.0 if nav0 else 0.0,
            "cagr": (nav1 / nav0) ** (1 / years) - 1.0 if years > 0 and nav0 > 0 else None,
            "sessions": int(sessions), "years": round(years, 3),
            "max_drawdown": float(equity["drawdown"].min()) if len(equity) else 0.0,
            "n_fills": len(fills),
            "n_overnight_fills": int(sum(1 for f in fills if f.overnight)),
            "n_rejected": len(rejected),
            "total_fees": round(total_fees, 4),
            "total_slippage": round(total_slip, 4),
            "fees_pct_of_initial_nav": round(total_fees / nav0 * 100, 4) if nav0 else None,
            "dividends_received": round(sum(d["cash_credited"] for d in div_events), 4),
            "n_dividend_events": len(div_events),
            "denominator": "full NAV (cash + market value), never deployed capital",
        }
