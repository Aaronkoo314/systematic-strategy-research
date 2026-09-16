"""Static weight sweep on the FULL 20-year daily sample, which contains 2008.

The 8-year sweep said a fixed 50 % of QQQ kept the worst drawdown at -18.36 %, inside
the operator's 20 % abandon point. That sample began in 2018. This one begins in 2006
and contains a -53 % decline, so the answer is expected to change - and by how much is
the number that actually decides the allocation.

Usage: python tools/static_sweep_daily.py
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
from src.data.bars import load_daily  # noqa: E402
from src.risk.controls import RiskLimits, RiskManager  # noqa: E402
from src.strategy.vol_target import static_blend  # noqa: E402

bars = load_daily(os.path.join(ROOT, "data", "raw", "US_QQQ_daily.csv"))
divs = pd.read_csv(os.path.join(ROOT, "data", "US_QQQ_dividends_daily.csv"))
dates = np.array([str(d) for d in bars.date])

PERIODS = {
    "full 2006-09 .. 2026-09 (20y, contains 2008)": ("2006-09-01", "2026-09-11"),
    "post-GFC 2010-01 .. 2026-09 (16.7y, no 2008)": ("2010-01-01", "2026-09-11"),
}
WEIGHTS = (0.20, 0.25, 0.30, 0.35, 0.375, 0.40, 0.50, 0.60, 0.80, 1.00)

out = {}
for label, (lo, hi) in PERIODS.items():
    idx = np.where((dates >= lo) & (dates <= hi))[0]
    start, end = int(idx[0]), int(idx[-1]) + 1
    print("\n" + "=" * 100)
    print(label)
    print("net of all modelled costs; dividends net of 30% withholding; idle cash at 0%")
    print("=" * 100)
    print(f"{'weight':>7} {'total':>10} {'CAGR':>8} {'maxDD':>9} {'ret/DD':>7} "
          f"{'fills':>6} {'fees/yr':>8} {'end NAV':>11}  {'20% abandon':>12}")
    print("-" * 100)
    rows = []
    for w in WEIGHTS:
        bt = Backtester(bars, initial_cash=10_000.0, execution=ExecutionModel(),
                        dividends=divs, lookback=2,
                        risk=RiskManager(RiskLimits(max_weight=1.0)))
        res = bt.run(static_blend(w), start=start, end=end, warmup=1)
        s = res.summary
        dd = float(s["max_drawdown"])
        yrs = s["years"]
        rows.append({"weight": w, "total_return": s["total_return"], "cagr": s["cagr"],
                     "max_drawdown": dd, "n_fills": s["n_fills"],
                     "fees_pct_yr": s["total_fees"] / 10_000 / yrs * 100,
                     "final_nav": s["final_nav"], "breached_20pct": bool(dd <= -0.20)})
        print(f"{w:>7.1%} {s['total_return']:>10.1%} {s['cagr']:>8.2%} {dd:>9.2%} "
              f"{(s['total_return'] / abs(dd)):>7.2f} {s['n_fills']:>6d} "
              f"{rows[-1]['fees_pct_yr']:>7.3f}% {s['final_nav']:>11,.0f}"
              f"  {'YES - stopped' if dd <= -0.20 else 'no':>12}")
    safe = [r for r in rows if not r["breached_20pct"]]
    if safe:
        top = max(safe, key=lambda r: r["cagr"])
        print(f"\n  highest CAGR inside the 20% abandon point: weight {top['weight']:.1%}"
              f"  ->  {top['cagr']:.2%}/yr, worst drawdown {top['max_drawdown']:.2%}")
    else:
        print("\n  NO tested weight stayed inside the 20% abandon point.")
    out[label] = rows

with open(os.path.join(ROOT, "reports", "static_sweep_daily.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, default=str)
print("\nwritten: reports/static_sweep_daily.json")
