"""Unconditional base rates for take-profit / stop-loss pairs on QQQ 5-minute bars.

No model, no signal, no parameters fitted. This measures what a RANDOM entry produces,
which is the bar any signal has to beat. If a pair already has positive expectancy
unconditionally, the "strategy" is just being in the market; if it does not, a signal
has to lift it, and by a measurable amount.

Usage: python tools/sweep_barriers.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.validation.barriers import label_barriers, summarise  # noqa: E402

BARS_PER_SESSION = 78
BARS_PER_YEAR = BARS_PER_SESSION * 252
HORIZON_SESSIONS = 30                  # a swing, not a position trade
HORIZON = BARS_PER_SESSION * HORIZON_SESSIONS
STRIDE = 6                             # sample every 30 minutes
# entry + exit on a 10,000 portfolio: 2.4636 USD round trip = 0.0246 %
COST_PCT = 0.000246

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float)
o = d["open"].to_numpy(float)
c = d["close"].to_numpy(float)
dates = d["time_key"].str[:10].to_numpy()

print("=" * 116)
print("UNCONDITIONAL BASE RATES - QQQ 5-minute, random entry, no signal")
print(f"{dates[0]} .. {dates[-1]}   {len(c):,} bars   horizon {HORIZON_SESSIONS} sessions"
      f"   entries sampled every {STRIDE} bars ({STRIDE * 5} min)")
print("round-trip cost 0.0246% of a 10,000 portfolio; a stop is assumed to fill AT the")
print("barrier, which is optimistic - gaps go through it")
print("=" * 116)
print(f"{'TP':>5} {'SL':>5} {'R:R':>5} | {'win%':>6} {'loss%':>6} {'t/out%':>7} | "
      f"{'breakeven':>10} {'edge':>7} | {'E[ret]%':>8} {'net%':>7} | "
      f"{'med bars':>9} {'trades/yr':>10} {'indep n':>8}")
print("-" * 116)

rows = []
for tp in (0.03, 0.05, 0.08, 0.10, 0.15):
    for sl in (0.02, 0.03, 0.05, 0.08):
        lab = label_barriers(h, l, o, c, tp=tp, sl=sl,
                             horizon_bars=HORIZON, stride=STRIDE)
        r = summarise(lab, tp=tp, sl=sl, horizon_bars=HORIZON,
                      bars_per_year=BARS_PER_YEAR, cost_pct=COST_PCT)
        edge = r.win_rate - r.breakeven_win_rate
        print(f"{tp:>5.0%} {sl:>5.0%} {tp / sl:>5.1f} | "
              f"{r.win_rate:>6.1%} {r.loss_rate:>6.1%} {r.timeout_rate:>7.1%} | "
              f"{r.breakeven_win_rate:>10.1%} {edge:>+7.1%} | "
              f"{r.expectancy_pct:>+8.3f} {r.expectancy_net_pct:>+7.3f} | "
              f"{r.median_bars_to_resolve:>9.0f} {r.trades_per_year:>10.1f} "
              f"{r.n_non_overlapping:>8d}")
        rows.append({**r.as_dict(), "edge_over_breakeven": edge})

print()
best_e = max(rows, key=lambda x: x["expectancy_net_pct"])
best_w = max(rows, key=lambda x: x["win_rate"])
print(f"  highest NET EXPECTANCY : TP {best_e['tp']:.0%} / SL {best_e['sl']:.0%}"
      f"  ->  {best_e['expectancy_net_pct']:+.3f}% per trade,"
      f" win rate {best_e['win_rate']:.1%},"
      f" {best_e['trades_per_year']:.0f} trades/yr")
print(f"  highest WIN RATE       : TP {best_w['tp']:.0%} / SL {best_w['sl']:.0%}"
      f"  ->  win rate {best_w['win_rate']:.1%},"
      f" net expectancy {best_w['expectancy_net_pct']:+.3f}% per trade")
print()
print("  Those two are usually different pairs, and the win-rate winner is usually the")
print("  worse trade. Expectancy is what compounds.")

# annualised expectancy, to compare against holding
print()
print("=" * 116)
print("Annualised, if every trade were taken back to back at the same base rate")
print("=" * 116)
print(f"{'TP':>5} {'SL':>5} | {'net per trade':>14} {'trades/yr':>10} "
      f"{'crude ann.':>11}   (buy & hold over the same period: see note)")
print("-" * 116)
for r in sorted(rows, key=lambda x: -x["expectancy_net_pct"])[:8]:
    ann = (1 + r["expectancy_net_pct"] / 100) ** r["trades_per_year"] - 1
    print(f"{r['tp']:>5.0%} {r['sl']:>5.0%} | {r['expectancy_net_pct']:>+13.3f}% "
          f"{r['trades_per_year']:>10.1f} {ann:>+10.1%}")

px_ann = (c[-1] / c[0]) ** (252 / (len(set(dates)))) - 1
print(f"\n  QQQ price-only over the same window: {px_ann:+.2%}/yr")
print("  The crude annualisation above assumes trades can be chained with no gap and")
print("  that the base rate is stationary. Neither is true; it is an upper bound.")

with open(os.path.join(ROOT, "reports", "barrier_sweep.json"), "w", encoding="utf-8") as fh:
    json.dump({"window": [str(dates[0]), str(dates[-1])],
               "horizon_sessions": HORIZON_SESSIONS, "stride": STRIDE,
               "cost_pct": COST_PCT, "rows": rows}, fh, indent=2, default=str)
pd.DataFrame(rows).to_csv(os.path.join(ROOT, "reports", "barrier_sweep.csv"), index=False)
print("\nwritten: reports/barrier_sweep.csv and .json")
