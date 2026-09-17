"""At what target size does this sample contain enough evidence to validate an edge?

Two forces pull in opposite directions as the target tightens:
  - trades resolve faster, so the sample holds more INDEPENDENT observations, and the
    statistical power rises
  - trades happen more often, so the fixed per-order fee takes a larger share, and the
    economic room for an edge falls

This finds where the two curves cross, if they cross at all. Purely mechanical - no
signal, no model, no fitted parameter.

Usage: python tools/find_testable_level.py
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
HORIZON = BARS * 30
STRIDE = 6
SESSIONS = 2012
YEARS = SESSIONS / 252.0
ROUND_TRIP_USD = 2.4636          # on a 10,000 portfolio, measured
TP_CAPITAL = 10_000.0
FEE_PCT = ROUND_TRIP_USD / TP_CAPITAL          # 0.0246 % per round trip

# The lift we would be trying to detect, as a fraction of the win rate. Held fixed at
# the value measured for 3%/3% so the comparison across levels is like for like.
LIFT = 0.05
Z50, Z80 = 1.96, 1.96 + 0.8416

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
h, l, o = (d[k].to_numpy(float) for k in ("high", "low", "open"))
n = len(o)

print("=" * 116)
print("WHERE STATISTICAL POWER AND ECONOMIC ROOM CROSS - QQQ 5-minute, symmetric targets")
print(f"lift to detect {LIFT:+.0%} on the win rate; round trip costs "
      f"{FEE_PCT:.4%} of a {TP_CAPITAL:,.0f} portfolio")
print("=" * 116)
print(f"{'level':>7} | {'win%':>6} {'med sess':>9} {'indep/8y':>9} {'cond n':>8} | "
      f"{'need 80%':>9} {'power':>7} | {'trades/yr':>10} {'fees/yr':>8} "
      f"{'edge $/yr':>10} {'net':>7}")
print("-" * 116)

rows = []
for lvl in (0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05):
    outcomes, held = [], []
    for i in range(0, n - 1, STRIDE):
        e = i + 1
        j_end = min(e + HORIZON, n)
        if j_end - e < 2:
            break
        p = float(o[e])
        if p <= 0:
            continue
        up, dn = p * (1 + lvl), p * (1 - lvl)
        hs, ls = h[e:j_end], l[e:j_end]
        u = np.flatnonzero(hs >= up)
        dd = np.flatnonzero(ls <= dn)
        ju = int(u[0]) if u.size else None
        jd = int(dd[0]) if dd.size else None
        if ju is None and jd is None:
            outcomes.append(0)
            held.append(j_end - e)
        elif jd is None or (ju is not None and ju < jd):
            outcomes.append(1)
            held.append(ju + 1)
        else:
            outcomes.append(-1)
            held.append(jd + 1)

    out = np.array(outcomes)
    hb = np.array(held)
    resolved = out != 0
    win = float((out == 1).sum() / max(resolved.sum(), 1))
    med_bars = float(np.median(hb))
    med_sess = med_bars / BARS
    indep = SESSIONS / med_sess                       # non-overlapping trades over 8y
    cond = indep * win                                # those following a WIN
    need80 = Z80 ** 2 * win * (1 - win) / LIFT ** 2
    need50 = Z50 ** 2 * win * (1 - win) / LIFT ** 2
    power_ok = cond >= need80

    trades_yr = indep / YEARS
    fees_yr_pct = trades_yr * FEE_PCT * 100
    # economic room: an edge of LIFT on the win rate is worth LIFT * 2 * level per trade
    edge_per_trade = LIFT * 2 * lvl
    edge_yr_pct = edge_per_trade * trades_yr * 100

    rows.append({"level": lvl, "win_rate": win, "median_sessions": med_sess,
                 "indep_trades_8y": indep, "conditional_n": cond,
                 "need_80pct": need80, "need_50pct": need50,
                 "power_ok": bool(power_ok), "trades_per_year": trades_yr,
                 "fees_pct_per_year": fees_yr_pct, "edge_pct_per_year": edge_yr_pct,
                 "net_pct_per_year": edge_yr_pct - fees_yr_pct})
    print(f"{lvl:>7.2%} | {win:>6.1%} {med_sess:>9.2f} {indep:>9.0f} {cond:>8.0f} | "
          f"{need80:>9.0f} {'PASS' if power_ok else 'fail':>7} | "
          f"{trades_yr:>10.0f} {fees_yr_pct:>7.2f}% {edge_yr_pct:>9.2f}% "
          f"{edge_yr_pct - fees_yr_pct:>+6.2f}%")

print()
print("  'cond n' is the independent trades that FOLLOW a winning exit - the only ones")
print("  that test the hypothesis. 'need 80%' is what resolving a 5pp lift requires.")
print("  'edge $/yr' assumes the lift is real and fully harvested; it is an upper bound.")
print()
ok = [r for r in rows if r["power_ok"]]
if ok:
    best = max(ok, key=lambda r: r["net_pct_per_year"])
    print(f"  Levels with enough evidence AND positive net: ", end="")
    good = [r for r in ok if r["net_pct_per_year"] > 0]
    print(", ".join(f"{r['level']:.2%}" for r in good) if good else "NONE")
    if good:
        print(f"  best net: {best['level']:.2%} -> {best['net_pct_per_year']:+.2f}%/yr "
              f"with {best['conditional_n']:.0f} conditional observations")
else:
    print("  NO level in this range has enough independent conditional observations")
    print("  to resolve a 5pp lift at 80% power on this 8-year sample.")

with open(os.path.join(ROOT, "reports", "testable_level.json"), "w",
          encoding="utf-8") as fh:
    json.dump({"lift": LIFT, "fee_pct_round_trip": FEE_PCT,
               "sessions": SESSIONS, "rows": rows}, fh, indent=2, default=str)
print("\nwritten: reports/testable_level.json")
