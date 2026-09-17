"""Is a 3% stop inside the noise, and what happens after it fires?

Two measurements that decide whether a stop level is workable, both purely mechanical:

  MAXIMUM ADVERSE EXCURSION. Of the entries that eventually reach +TP within the horizon
  IF NO STOP EXISTED, how far down did they first travel? Every one of those that dipped
  past -SL is a winner the stop converts into a loser. That number is the true cost of
  the stop, and it is invisible in a win-rate table.

  WHIPSAW. After a stop fires, how often does price return above the entry, and how fast?
  A high rate means the stop sits inside the noise band rather than outside it.

Neither depends on any signal. Both are properties of the instrument and the levels.

Usage: python tools/analyse_stops.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BARS_PER_SESSION = 78
HORIZON = BARS_PER_SESSION * 30
STRIDE = 6
RECHECK = BARS_PER_SESSION * 5        # look 5 sessions past a stop for recovery

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
h = d["high"].to_numpy(float)
l = d["low"].to_numpy(float)
o = d["open"].to_numpy(float)
c = d["close"].to_numpy(float)
n = len(c)

print("=" * 104)
print("WHAT A STOP COSTS - QQQ 5-minute, random entry, no signal")
print(f"horizon {HORIZON // BARS_PER_SESSION} sessions, entries every {STRIDE * 5} min")
print("=" * 104)

rows = []
for tp, sl in ((0.03, 0.03), (0.03, 0.05), (0.05, 0.03), (0.05, 0.05),
               (0.03, 0.02), (0.10, 0.05)):
    winners_no_stop = 0
    killed_by_stop = 0
    mae_of_winners = []
    stops = 0
    recovered = 0
    bars_to_recover = []
    adverse_after_stop = []

    for i in range(0, n - 1, STRIDE):
        e = i + 1
        j_end = min(e + HORIZON, n)
        if j_end - e < 2:
            break
        p = float(o[e])
        if p <= 0:
            continue
        up, dn = p * (1 + tp), p * (1 - sl)
        hs, ls = h[e:j_end], l[e:j_end]

        up_hit = np.flatnonzero(hs >= up)
        dn_hit = np.flatnonzero(ls <= dn)
        j_up = int(up_hit[0]) if up_hit.size else None
        j_dn = int(dn_hit[0]) if dn_hit.size else None

        # --- MAE: would this entry have reached +TP with no stop at all? ---
        if j_up is not None:
            winners_no_stop += 1
            worst = float(np.min(ls[:j_up + 1]))
            mae = worst / p - 1.0
            mae_of_winners.append(mae)
            if j_dn is not None and j_dn <= j_up:
                killed_by_stop += 1      # the stop fires before the target is reached

        # --- whipsaw: what happens after the stop fires? ---
        if j_dn is not None and (j_up is None or j_dn < j_up):
            stops += 1
            s_bar = e + j_dn
            k_end = min(s_bar + RECHECK, n)
            if k_end - s_bar > 1:
                fwd_h = h[s_bar + 1:k_end]
                back = np.flatnonzero(fwd_h >= p)     # back above the ENTRY price
                if back.size:
                    recovered += 1
                    bars_to_recover.append(int(back[0]) + 1)
                adverse_after_stop.append(float(np.min(l[s_bar + 1:k_end])) / p - 1.0)

    mae_arr = np.array(mae_of_winners)
    kill_rate = killed_by_stop / winners_no_stop if winners_no_stop else float("nan")
    rec_rate = recovered / stops if stops else float("nan")
    med_rec = float(np.median(bars_to_recover)) if bars_to_recover else float("nan")

    rows.append({
        "tp": tp, "sl": sl,
        "winners_if_no_stop": winners_no_stop,
        "killed_by_stop": killed_by_stop, "kill_rate": kill_rate,
        "mae_median": float(np.median(mae_arr)) if len(mae_arr) else None,
        "mae_p90": float(np.percentile(mae_arr, 10)) if len(mae_arr) else None,
        "stops": stops, "recovery_rate": rec_rate,
        "median_bars_to_recover": med_rec,
        "median_sessions_to_recover": med_rec / BARS_PER_SESSION if med_rec == med_rec else None,
        "median_further_drop_after_stop": float(np.median(adverse_after_stop))
        if adverse_after_stop else None,
    })

print(f"\n{'TP':>5} {'SL':>5} | {'reach +TP':>10} {'stop kills':>11} {'kill rate':>10} | "
      f"{'winner MAE med':>15} {'MAE p10':>9}")
print("-" * 104)
for r in rows:
    print(f"{r['tp']:>5.0%} {r['sl']:>5.0%} | {r['winners_if_no_stop']:>10,} "
          f"{r['killed_by_stop']:>11,} {r['kill_rate']:>10.1%} | "
          f"{r['mae_median']:>15.2%} {r['mae_p90']:>9.2%}")
print("\n  'reach +TP' counts entries that would have hit the target with NO stop.")
print("  'kill rate' is the share of those the stop turns into losses.")
print("  'winner MAE' is how far a winner typically dips before it works -")
print("  if that is deeper than the stop, the stop is inside the noise.")

print(f"\n{'TP':>5} {'SL':>5} | {'stops':>8} {'back above entry':>17} "
      f"{'median wait':>13} {'further drop':>13}")
print("-" * 104)
for r in rows:
    print(f"{r['tp']:>5.0%} {r['sl']:>5.0%} | {r['stops']:>8,} "
          f"{r['recovery_rate']:>17.1%} "
          f"{r['median_sessions_to_recover']:>10.1f} sess "
          f"{r['median_further_drop_after_stop']:>13.2%}")
print(f"\n  'back above entry' = within {RECHECK // BARS_PER_SESSION} sessions of the stop,")
print("  price traded above the original entry again. That is the whipsaw rate: you took")
print("  the loss and the move happened without you.")

with open(os.path.join(ROOT, "reports", "stop_analysis.json"), "w", encoding="utf-8") as fh:
    json.dump({"horizon_sessions": HORIZON // BARS_PER_SESSION, "stride": STRIDE,
               "recheck_sessions": RECHECK // BARS_PER_SESSION, "rows": rows},
              fh, indent=2, default=str)
print("\nwritten: reports/stop_analysis.json")
