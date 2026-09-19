"""What does simply holding a fixed fraction of QQQ actually produce?

No timing, no signal, no parameters to search. One purchase, then hold. Run on the same
validated engine, the same cost model, the same dividend treatment and the same full-NAV
denominator as every other result in this project.

This is not a strategy proposal. It is the arithmetic of the question "I want profit"
once the operator's 20 % abandon point is taken seriously.

WHY THE RISK MANAGER IS BYPASSED HERE, EXPLICITLY. This is a BENCHMARK - "hold a
fixed fraction, rebalance both ways" - not a strategy under the mandate's controls.
An earlier version ran it with the live RiskManager. The DRAWDOWN halt fired at the
first -8% drawdown (2008-02-06 on the 20-year window, 2010-07-01 post-GFC), never
auto-resumes, and lets risk-REDUCING orders through while blocking buys. Every
"static weight" therefore became "sell-only after the first drawdown": it sold on
the way up but never bought back at the 2009, 2020 or 2022 lows. Realised weight
sagged to 21% at the 2009 bottom against a 35% target. Those runs are kept as
reports/*_VOID_halt_sellonly.* and must not be quoted. The bypass is a named engine
flag and is recorded in summary["risk_controls"].

Usage: python tools/static_sweep.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.data.bars import load_5min  # noqa: E402
from src.strategy.vol_target import static_blend  # noqa: E402

bars = load_5min(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"),
                 allow_overnight=True)
divs = pd.read_csv(os.path.join(ROOT, "data", "US_QQQ_dividends.csv"))

WEIGHTS = (0.30, 0.40, 0.50, 0.56, 0.60, 0.70, 0.80, 0.90, 1.00)

print("=" * 96)
print("HOLD A FIXED FRACTION OF QQQ - full sample 2018-09-10 .. 2026-09-11 (7.98 years)")
print("net of all modelled costs; dividends net of 30% withholding; idle cash at 0%")
print("=" * 96)
print(f"{'weight':>7} {'total':>9} {'CAGR':>8} {'maxDD':>9} {'ret/DD':>7} "
      f"{'fills':>6} {'fees/yr':>8} {'end NAV':>11}  {'20% abandon':>12}")
print("-" * 96)

rows = []
for w in WEIGHTS:
    # Benchmark, not a strategy: the risk manager is bypassed on purpose (see header).
    bt = Backtester(bars, initial_cash=10_000.0, execution=ExecutionModel(),
                    dividends=divs, lookback=2,
                    bypass_risk_controls=True)
    res = bt.run(static_blend(w), warmup=1)
    s = res.summary
    eq = res.equity
    dd = float(s["max_drawdown"])
    years = s["years"]
    rows.append({
        "weight": w, "total_return": s["total_return"], "cagr": s["cagr"],
        "max_drawdown": dd, "ret_over_dd": s["total_return"] / abs(dd) if dd else None,
        "n_fills": s["n_fills"], "fees_per_year_pct": s["total_fees"] / 10_000 / years * 100,
        "final_nav": s["final_nav"], "breached_20pct": bool(dd <= -0.20),
        "avg_weight": float((eq["deployed_value"] / eq["nav"]).mean()),
    })
    print(f"{w:>7.0%} {s['total_return']:>9.1%} {s['cagr']:>8.2%} {dd:>9.2%} "
          f"{(s['total_return'] / abs(dd)):>7.2f} {s['n_fills']:>6d} "
          f"{rows[-1]['fees_per_year_pct']:>7.3f}% {s['final_nav']:>11,.0f}"
          f"  {'YES - stopped' if dd <= -0.20 else 'no':>12}")

print()
print("The operator's preregistered abandon point is a 20 % drawdown on the trading")
print("portfolio. Every row marked YES would have been terminated by it.")
best = [r for r in rows if not r["breached_20pct"]]
if best:
    top = max(best, key=lambda r: r["cagr"])
    print(f"\nHighest CAGR that never breached 20 %: weight {top['weight']:.0%}"
          f"  ->  {top['cagr']:.2%}/yr, worst drawdown {top['max_drawdown']:.2%},"
          f"  {top['n_fills']} orders in 8 years")
else:
    print("\nNo tested weight stayed inside the 20 % abandon point.")

with open(os.path.join(ROOT, "reports", "static_sweep.json"), "w", encoding="utf-8") as fh:
    json.dump({"note": "hold a fixed fraction of QQQ, no timing, same engine and costs",
               "sample": "2018-09-10 .. 2026-09-11", "rows": rows}, fh, indent=2, default=str)
pd.DataFrame(rows).to_csv(os.path.join(ROOT, "reports", "static_sweep.csv"), index=False)
print("\nwritten: reports/static_sweep.csv and .json")
