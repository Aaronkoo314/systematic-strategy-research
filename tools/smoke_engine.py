"""Engine self-check on the real series. NOT a strategy result.

Runs buy-and-hold, whose answer is already known independently: QQQ compounded at
18.63 %/yr on price alone over 2018-09-10 to 2026-09-11. If the engine reproduces that,
less two orders of fees and plus net dividends, its accounting is sound. If it does not,
the engine is wrong and every later number would be wrong with it.

Usage: python tools/smoke_engine.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.data.bars import load_5min  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BARS = os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv")
DIVS = os.path.join(ROOT, "data", "US_QQQ_dividends.csv")

bars = load_5min(BARS, allow_overnight=True)
divs = pd.read_csv(DIVS)
print(f"bars={len(bars)}  sessions={len(bars.sessions)}  "
      f"{bars.time_key[0]} .. {bars.time_key[-1]}")
print(f"dividends={len(divs)}  net per share total={divs['per_share_net'].sum():.4f}\n")


def buy_and_hold(history, state):
    return 1.0


bt = Backtester(bars, initial_cash=10_000.0, execution=ExecutionModel(), dividends=divs)
res = bt.run(buy_and_hold, warmup=1)
s = res.summary

print("=" * 74)
print("BUY AND HOLD - engine self-check, not a strategy result")
print("=" * 74)
for k in ("initial_nav", "final_nav", "total_return", "cagr", "sessions", "years",
          "max_drawdown", "n_fills", "n_overnight_fills", "n_rejected",
          "total_fees", "total_slippage", "dividends_received", "n_dividend_events"):
    v = s[k]
    if isinstance(v, float):
        print(f"  {k:24s} {v:,.4f}")
    else:
        print(f"  {k:24s} {v}")

px0, px1 = float(bars.close[0]), float(bars.close[-1])
years = s["years"]
price_cagr = (px1 / px0) ** (1 / years) - 1
print(f"\n  price-only CAGR (independent) {price_cagr * 100:6.2f} %")
print(f"  engine CAGR                   {s['cagr'] * 100:6.2f} %")
print(f"  difference                    {(s['cagr'] - price_cagr) * 100:+6.2f} pp"
      f"   <- dividends net of 30 %, less fees and slippage and idle cash")

eq = res.equity
idle = (eq["cash"] / eq["nav"]).mean()
print(f"\n  mean idle cash share          {idle * 100:6.2f} %   "
      f"<- stays in the denominator, never excluded")
print(f"  NAV identity max error        "
      f"{(eq['nav'] - (eq['cash'] + eq['shares'] * eq['price'])).abs().max():.2e}")

out = os.path.join(ROOT, "reports")
os.makedirs(out, exist_ok=True)
eq[["time_key", "date", "price", "cash", "shares", "nav", "drawdown"]].iloc[::78].to_csv(
    os.path.join(out, "smoke_equity_daily.csv"), index=False)
res.fills.to_csv(os.path.join(out, "smoke_fills.csv"), index=False)
print(f"\n  wrote reports/smoke_equity_daily.csv and reports/smoke_fills.csv")
