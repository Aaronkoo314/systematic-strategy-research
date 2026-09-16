"""Generate figures F1-F6 from the experiment outputs. Spec: docs/report_sop.md."""

from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.data.bars import load_5min  # noqa: E402
from src.reporting import charts  # noqa: E402
from src.risk.controls import RiskLimits, RiskManager  # noqa: E402
from src.strategy.vol_target import buy_and_hold  # noqa: E402

FIG = os.path.join(ROOT, "reports", "figures")
os.makedirs(FIG, exist_ok=True)

bars = load_5min(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"),
                 allow_overnight=True)
divs = pd.read_csv(os.path.join(ROOT, "data", "US_QQQ_dividends.csv"))
dates = [str(d) for d in bars.date]

SPLITS = {"validation": ("2023-01-01", "2024-12-31"),
          "test": ("2025-01-01", "2026-09-11")}


def bench(split):
    lo, hi = SPLITS[split]
    idx = [i for i, d in enumerate(dates) if lo <= d <= hi]
    bt = Backtester(bars, initial_cash=10_000.0, execution=ExecutionModel(),
                    dividends=divs, lookback=2,
                    risk=RiskManager(RiskLimits(max_weight=1.0)))
    return bt.run(buy_and_hold, start=idx[0], end=idx[-1] + 1, warmup=1).equity


made = []
for split in ("validation", "test"):
    eq = pd.read_csv(os.path.join(ROOT, "reports", f"equity_{split}.csv"))
    fills = pd.read_csv(os.path.join(ROOT, "reports", f"fills_{split}.csv"))
    trades = pd.read_csv(os.path.join(ROOT, "reports", f"trades_{split}.csv"))
    bq = bench(split)
    extra = f"   [{split.upper()} {SPLITS[split][0]} .. {SPLITS[split][1]}]"

    made.append(charts.f1_equity(eq, bq, os.path.join(FIG, f"F1_equity_{split}.png"), extra))
    made.append(charts.f2_price_with_fills(eq, fills,
                                           os.path.join(FIG, f"F2_fills_{split}.png"), extra))
    tbl = charts.annual_table(eq, bq, fills)
    tbl.to_csv(os.path.join(ROOT, "reports", f"annual_{split}.csv"), index=False)
    made.append(charts.f3_annual(tbl, os.path.join(FIG, f"F3_annual_{split}.png"), extra))
    made.append(charts.f4_concentration(trades,
                                        os.path.join(FIG, f"F4_concentration_{split}.png"), extra))
    made.append(charts.f5_drawdown(eq, os.path.join(FIG, f"F5_drawdown_{split}.png"), extra))
    made.append(charts.f6_costs(fills, eq, os.path.join(FIG, f"F6_costs_{split}.png"), extra))
    print(f"{split}: {len(eq)} bars, {len(fills)} fills, {len(trades)} trades")
    print(tbl.to_string(index=False))
    print()

for m in made:
    print("wrote", os.path.relpath(m, ROOT).replace("\\", "/"))
