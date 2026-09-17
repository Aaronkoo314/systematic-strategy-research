"""After an exit, should the system re-enter immediately?

Two questions, both mechanical, neither needing a signal.

  WHAT THE TAKE-PROFIT LEAVES BEHIND. Of the entries that reach +TP, how far did price
  travel afterwards? A tight target that regularly exits into a much larger move is
  paying a real opportunity cost, and that cost is invisible in a win-rate table.

  IS RE-ENTRY BETTER OR WORSE THAN RANDOM? Immediately after an exit, place the same
  bet again and label it the same way. Compare its win rate to the unconditional base
  rate. Above it means the exit event carries continuation information and re-entry is
  trading WITH something; below it means re-entry is trading against something.

Both exit types are measured, because the answers can differ in sign.

Usage: python tools/analyse_reentry.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BARS = 78
HORIZON = BARS * 15
STRIDE = 6
AFTER = BARS * 5           # how far to look past a take-profit for further upside

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
h, l, o, c = (d[k].to_numpy(float) for k in ("high", "low", "open", "close"))
n = len(c)


def first_touch(e, j_end, up, dn):
    hs, ls = h[e:j_end], l[e:j_end]
    u = np.flatnonzero(hs >= up)
    dd = np.flatnonzero(ls <= dn)
    ju = int(u[0]) if u.size else None
    jd = int(dd[0]) if dd.size else None
    if ju is None and jd is None:
        return 0, j_end - e
    if jd is None or (ju is not None and ju < jd):
        return 1, ju + 1
    return -1, jd + 1


def barrier_from(e, tp, sl):
    """Outcome of a fresh entry filled at open[e]."""
    if e >= n - 1:
        return None, None
    p = float(o[e])
    if p <= 0:
        return None, None
    j_end = min(e + HORIZON, n)
    if j_end - e < 2:
        return None, None
    return first_touch(e, j_end, p * (1 + tp), p * (1 - sl))


rows = []
for tp, sl in ((0.0075, 0.0075), (0.01, 0.01), (0.015, 0.015), (0.02, 0.02),
               (0.03, 0.03)):
    base_w = base_n = 0
    tp_hits = 0
    further = []                     # max upside after the target, as % of exit price
    reached = {0.02: 0, 0.05: 0, 0.10: 0}
    re_tp = {"win": 0, "loss": 0, "timeout": 0}
    re_sl = {"win": 0, "loss": 0, "timeout": 0}

    for i in range(0, n - 1, STRIDE):
        e = i + 1
        out, held = barrier_from(e, tp, sl)
        if out is None:
            continue
        base_n += 1
        if out == 1:
            base_w += 1

        exit_bar = e + held - 1

        if out == 1:
            tp_hits += 1
            px_exit = float(o[e]) * (1 + tp)
            k_end = min(exit_bar + AFTER, n)
            if k_end - exit_bar > 1:
                mfe = float(np.max(h[exit_bar + 1:k_end])) / px_exit - 1.0
                further.append(mfe)
                for thr in reached:
                    if mfe >= thr:
                        reached[thr] += 1
            r_out, _ = barrier_from(exit_bar + 1, tp, sl)
            if r_out is not None:
                re_tp["win" if r_out == 1 else "loss" if r_out == -1 else "timeout"] += 1
        elif out == -1:
            r_out, _ = barrier_from(exit_bar + 1, tp, sl)
            if r_out is not None:
                re_sl["win" if r_out == 1 else "loss" if r_out == -1 else "timeout"] += 1

    f = np.array(further)
    n_tp_re = sum(re_tp.values())
    n_sl_re = sum(re_sl.values())
    rows.append({
        "tp": tp, "sl": sl,
        "base_win_rate": base_w / base_n if base_n else None,
        "base_n": base_n, "tp_hits": tp_hits,
        "further_median": float(np.median(f)) if len(f) else None,
        "further_p75": float(np.percentile(f, 75)) if len(f) else None,
        "share_further_2pct": reached[0.02] / tp_hits if tp_hits else None,
        "share_further_5pct": reached[0.05] / tp_hits if tp_hits else None,
        "share_further_10pct": reached[0.10] / tp_hits if tp_hits else None,
        "reentry_after_tp_win_rate": re_tp["win"] / n_tp_re if n_tp_re else None,
        "reentry_after_tp_n": n_tp_re,
        "reentry_after_sl_win_rate": re_sl["win"] / n_sl_re if n_sl_re else None,
        "reentry_after_sl_n": n_sl_re,
    })

print("=" * 108)
print("WHAT THE TAKE-PROFIT LEAVES ON THE TABLE - QQQ 5-minute, random entry")
print(f"upside measured for {AFTER // BARS} sessions after the target is hit")
print("=" * 108)
print(f"{'TP':>5} {'SL':>5} | {'TP hits':>9} | {'further med':>12} {'p75':>8} | "
      f"{'+2% more':>9} {'+5% more':>9} {'+10% more':>10}")
print("-" * 108)
for r in rows:
    print(f"{r['tp']:>5.0%} {r['sl']:>5.0%} | {r['tp_hits']:>9,} | "
          f"{r['further_median']:>12.2%} {r['further_p75']:>8.2%} | "
          f"{r['share_further_2pct']:>9.1%} {r['share_further_5pct']:>9.1%} "
          f"{r['share_further_10pct']:>10.1%}")
print("\n  'further' is the additional upside from the EXIT price. The share columns are")
print("  the fraction of winning trades where the move continued that much further -")
print("  those are the moves a tight target cuts short.")

print("\n" + "=" * 108)
print("SHOULD IT RE-ENTER? Same bet placed on the bar after the exit")
print("=" * 108)
print(f"{'TP':>5} {'SL':>5} | {'base win%':>10} | {'after TP':>9} {'diff':>8} "
      f"{'n':>8} | {'after SL':>9} {'diff':>8} {'n':>8}")
print("-" * 108)
for r in rows:
    d_tp = r["reentry_after_tp_win_rate"] - r["base_win_rate"]
    d_sl = r["reentry_after_sl_win_rate"] - r["base_win_rate"]
    print(f"{r['tp']:>5.0%} {r['sl']:>5.0%} | {r['base_win_rate']:>10.1%} | "
          f"{r['reentry_after_tp_win_rate']:>9.1%} {d_tp:>+8.1%} {r['reentry_after_tp_n']:>8,} | "
          f"{r['reentry_after_sl_win_rate']:>9.1%} {d_sl:>+8.1%} {r['reentry_after_sl_n']:>8,}")
print("\n  A positive diff means the exit carries continuation information and re-entering")
print("  beats a random entry. A negative diff means re-entry is worse than random.")

with open(os.path.join(ROOT, "reports", "reentry_tight.json"), "w",
          encoding="utf-8") as fh:
    json.dump({"horizon_sessions": HORIZON // BARS, "after_sessions": AFTER // BARS,
               "stride": STRIDE, "rows": rows}, fh, indent=2, default=str)
print("\nwritten: reports/reentry_analysis.json")
