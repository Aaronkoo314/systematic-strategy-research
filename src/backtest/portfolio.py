"""Two-or-more asset portfolio with calendar rebalancing. Spec: docs/preregistration_v3.md.

Deliberately narrower than backtest.engine. That engine drives a signal; this one holds a
fixed mix and rebalances on a date. Keeping them separate means the signal machinery -
history windows, look-ahead checks, band logic - cannot silently affect an allocation
result, and the allocation path cannot grow a signal by accident.

What it shares with the engine, because these are the parts that must never diverge:
  - the same fee model, order_cost, itemised
  - the same NAV definition: cash plus market value, idle cash always in the denominator
  - the same dividend treatment: cash credit on the ex-date, net of withholding
  - the same risk manager, consulted before every order
  - the same execution rule: a decision on bar i fills at bar i+1's OPEN

Rebalancing is by calendar date only. No bands, no drift triggers, no mid-year action -
Stage B established that at TP = 10,000 the fixed per-order fee makes frequent calendar
rebalancing cost more than the rebalancing premium is worth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.backtest.engine import ExecutionModel
from src.costs.fees import FeeSchedule, order_cost
from src.data.bars import BarSeries
from src.risk.controls import RiskLimits, RiskManager


@dataclass
class PortfolioResult:
    equity: pd.DataFrame
    fills: pd.DataFrame
    dividends: pd.DataFrame
    rebalances: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class PortfolioBacktester:
    def __init__(self, series: dict[str, BarSeries], *, initial_cash: float = 10_000.0,
                 execution: ExecutionModel = ExecutionModel(),
                 fees: FeeSchedule = FeeSchedule(),
                 dividends: dict[str, pd.DataFrame] | None = None,
                 risk: RiskManager | None = None,
                 rebalance_month: int = 1):
        if not series:
            raise ValueError("at least one instrument is required")
        lengths = {k: len(v) for k, v in series.items()}
        if len(set(lengths.values())) != 1:
            raise ValueError(f"instruments have different lengths: {lengths}")
        ref = next(iter(series.values()))
        for name, s in series.items():
            if not np.array_equal(np.asarray(s.date), np.asarray(ref.date)):
                raise ValueError(f"{name} dates do not align with the reference series")
        if not 1 <= rebalance_month <= 12:
            raise ValueError("rebalance_month must be 1..12")

        self.series = series
        self.dates = np.array([str(d) for d in ref.date])
        self.initial_cash = float(initial_cash)
        self.execution = execution
        self.fees = fees
        self.risk = risk or RiskManager(RiskLimits(max_weight=1.0))
        self.rebalance_month = rebalance_month

        self.div = {}
        for name in series:
            table = (dividends or {}).get(name)
            m = {}
            if table is not None and len(table):
                for _, r in table.iterrows():
                    m[str(r["ex_date"])] = float(r["per_share_net"])
            self.div[name] = m

    # ------------------------------------------------------------------

    def _rebalance_bars(self, start: int, end: int) -> list[int]:
        """First session of the target month in each calendar year, within the window."""
        out, seen = [], set()
        for i in range(start, end):
            d = self.dates[i]
            year, month = int(d[:4]), int(d[5:7])
            if month == self.rebalance_month and year not in seen:
                seen.add(year)
                out.append(i)
        return out

    def _nav(self, shares: dict, cash: float, i: int) -> float:
        return cash + sum(sh * float(self.series[n].close[i]) for n, sh in shares.items())

    def run(self, weights: dict[str, float], *, start: int = 0,
            end: int | None = None) -> PortfolioResult:
        w_sum = sum(weights.values())
        if w_sum > 1.0 + 1e-9:
            raise ValueError(f"weights sum to {w_sum}, above 1.0 - no leverage")
        if any(v < 0 for v in weights.values()):
            raise ValueError("weights must be non-negative - long only")
        missing = set(weights) - set(self.series)
        if missing:
            raise ValueError(f"no price series for {sorted(missing)}")

        n = len(self.dates)
        end = n if end is None else min(end, n)
        cash = self.initial_cash
        shares = {name: 0 for name in self.series}
        fills, div_events, rebals = [], [], []
        rows = []
        paid: set[tuple] = set()
        seen_dates: set[str] = set()

        reb = set(self._rebalance_bars(start, end))
        # The window may open mid-year; establish the position on the first bar so the
        # portfolio is not accidentally all-cash until the next January.
        first_exec = start + 1
        if first_exec < end:
            reb.add(start)

        for i in range(start, end):
            d = self.dates[i]
            if d not in seen_dates:
                seen_dates.add(d)
                self.risk.start_session(d)

            # dividends first: credited to shares held at the open of the ex-date
            for name in self.series:
                if d in self.div[name] and (name, d) not in paid:
                    paid.add((name, d))
                    if shares[name] > 0:
                        amt = shares[name] * self.div[name][d]
                        cash += amt
                        div_events.append({"ex_date": d, "symbol": name,
                                           "shares": shares[name],
                                           "per_share_net": self.div[name][d],
                                           "cash_credited": amt})

            nav = self._nav(shares, cash, i)
            self.risk.observe(nav, d)

            if i in reb and i + 1 < end:
                done = self._rebalance(shares, cash, weights, i, i + 1, fills, d)
                cash = done["cash"]
                rebals.append({"signal_bar": i, "exec_bar": i + 1, "date": d,
                               "nav_before": nav, "orders": done["orders"]})

            nav = self._nav(shares, cash, i)
            row = {"bar": i, "date": d, "cash": cash, "nav": nav}
            for name in self.series:
                row[f"shares_{name}"] = shares[name]
                row[f"price_{name}"] = float(self.series[name].close[i])
                row[f"value_{name}"] = shares[name] * float(self.series[name].close[i])
            rows.append(row)

        eq = pd.DataFrame(rows)
        eq["hwm"] = eq["nav"].cummax()
        eq["drawdown"] = eq["nav"] / eq["hwm"] - 1.0
        for name in self.series:
            eq[f"weight_{name}"] = eq[f"value_{name}"] / eq["nav"]

        return PortfolioResult(
            equity=eq,
            fills=pd.DataFrame(fills) if fills else pd.DataFrame(),
            dividends=pd.DataFrame(div_events) if div_events else pd.DataFrame(),
            rebalances=rebals,
            summary=self._summarise(eq, fills, div_events, weights))

    # ------------------------------------------------------------------

    def _rebalance(self, shares: dict, cash: float, weights: dict,
                   signal_i: int, exec_i: int, fills: list, date: str) -> dict:
        """Sell first, then buy, so proceeds are available to fund purchases."""
        nav = self._nav(shares, cash, signal_i)
        targets = {}
        for name in self.series:
            w = float(weights.get(name, 0.0))
            px = float(self.series[name].open[exec_i])
            targets[name] = int(math.floor(w * nav / px)) if px > 0 else 0

        orders = 0
        for phase in ("sell", "buy"):
            for name, tgt in targets.items():
                delta = tgt - shares[name]
                if delta == 0 or (phase == "sell" and delta > 0) or \
                        (phase == "buy" and delta < 0):
                    continue
                side = "buy" if delta > 0 else "sell"
                qty = abs(delta)
                ref = float(self.series[name].open[exec_i])
                if self.series[name].volume[exec_i] <= 0:
                    continue                       # no trade could have happened
                slip = self.execution.slip(ref, overnight=True)
                px = ref + slip if side == "buy" else ref - slip

                est = order_cost(int(qty), float(px), side, self.fees).total
                d = self.risk.check_order(
                    date=date, nav=nav, price=px,
                    prev_price=float(self.series[name].close[signal_i]),
                    current_shares=shares[name], target_shares=tgt, est_fees=est,
                    fingerprint=f"{exec_i}:{name}:{side}:{qty}")
                if not d.allowed:
                    continue
                if d.max_shares is not None:
                    qty = max(0, min(qty, abs(d.max_shares - shares[name])))
                    if qty == 0:
                        continue

                if side == "buy":
                    while qty > 0 and qty * px + order_cost(int(qty), float(px), side,
                                                            self.fees).total > cash + 1e-9:
                        qty -= 1
                    if qty == 0:
                        continue
                cost = order_cost(int(qty), float(px), side, self.fees)
                if side == "buy":
                    cash -= qty * px + cost.total
                    shares[name] += qty
                else:
                    qty = min(qty, shares[name])
                    if qty == 0:
                        continue
                    cost = order_cost(int(qty), float(px), side, self.fees)
                    cash += qty * px - cost.total
                    shares[name] -= qty
                self.risk.record_fees(date, float(cost.total))
                orders += 1
                fills.append({"exec_bar": exec_i, "date": self.dates[exec_i],
                              "symbol": name, "side": side, "shares": int(qty),
                              "ref_price": ref, "fill_price": px,
                              "slippage_cost": slip * qty, "fees": cost.total})
        return {"cash": cash, "orders": orders}

    def _summarise(self, eq, fills, divs, weights) -> dict:
        nav0, nav1 = float(eq["nav"].iloc[0]), float(eq["nav"].iloc[-1])
        sessions = int(eq["date"].nunique())
        years = sessions / 252.0
        total_fees = float(sum(f["fees"] for f in fills))
        dd = float(eq["drawdown"].min())
        return {
            "weights": dict(weights),
            "initial_nav": nav0, "final_nav": nav1,
            "total_return": nav1 / nav0 - 1.0,
            "cagr": (nav1 / nav0) ** (1 / years) - 1.0 if years > 0 and nav0 > 0 else None,
            "max_drawdown": dd,
            "return_over_maxdd": (nav1 / nav0 - 1.0) / abs(dd) if dd < 0 else float("inf"),
            "sessions": sessions, "years": round(years, 3),
            "n_fills": len(fills), "total_fees": round(total_fees, 4),
            "fees_pct_per_year": round(total_fees / nav0 / max(years, 1e-9) * 100, 4),
            "dividends_received": round(sum(d["cash_credited"] for d in divs), 4),
            "n_dividend_events": len(divs),
            "halted": self.risk.state.halted, "abandoned": self.risk.state.abandoned,
            "breached_20pct": bool(dd <= -0.20),
            "denominator": "full NAV (cash + market value), never deployed capital",
        }
