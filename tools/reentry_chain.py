"""Does a winning exit predict the next trade? Measured on non-overlapping chains.

Every earlier measurement of this used OVERLAPPING samples - an entry every 30 minutes,
each trade's horizon covering dozens of others. That inflates the apparent sample by an
order of magnitude and makes any lift look far better supported than it is.

This walks the sample the way the system would actually trade it: enter, hold to a
barrier, re-enter on the next bar, repeat to the end of the data. Every trade is disjoint
from every other, so the trade count IS the independent sample size, and the sequence of
outcomes is the sequence the strategy would have lived through.

Three things come out, none of them fitted:

  THE CHAIN'S OWN P&L. What "always in the market with these barriers" is worth after
  fees. This is the thing any signal has to beat, and it costs nothing to know.

  THE CONDITIONAL LIFT, with the standard error the chain length actually supports. If
  the lift is smaller than its own standard error it is not evidence of anything.

  WHAT IT WOULD TAKE. Required trades at 80% power for the lift as observed, against the
  trades the sample contains - and the years of data that gap implies.

Usage: python tools/reentry_chain.py
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
SESSIONS = 2012
YEARS = SESSIONS / 252.0
HORIZON = BARS * 15                       # a swing; beyond this the trade is abandoned
FEE = 2.4636 / 10_000.0                   # measured round trip on a 10,000 portfolio
Z80 = 1.96 + 0.8416

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
h, l, o, c = (d[k].to_numpy(float) for k in ("high", "low", "open", "close"))
n = len(c)


def chain(level: float):
    """Walk the whole sample as one back-to-back sequence of disjoint trades."""
    e, outs, rets, held = 1, [], [], []
    while e < n - 1:
        j_end = min(e + HORIZON, n)
        if j_end - e < 2:
            break
        p = float(o[e])
        if p <= 0:
            e += 1
            continue
        hs, ls = h[e:j_end], l[e:j_end]
        u = np.flatnonzero(hs >= p * (1 + level))
        dd = np.flatnonzero(ls <= p * (1 - level))
        ju = int(u[0]) if u.size else None
        jd = int(dd[0]) if dd.size else None
        if ju is None and jd is None:
            k = j_end - e - 1
            out, r = 0, float(c[e + k]) / p - 1.0
        elif jd is None or (ju is not None and ju < jd):
            k, out, r = ju, 1, level            # ties go to the stop, deliberately
        else:
            k, out, r = jd, -1, -level
        outs.append(out)
        rets.append(r - FEE)
        held.append(k + 1)
        e = e + k + 1
    return np.array(outs), np.array(rets), np.array(held)


print("=" * 112)
print("NON-OVERLAPPING CHAINS - QQQ 5-minute, always in the market, symmetric barriers")
print(f"{d['time_key'].iloc[0][:10]} .. {d['time_key'].iloc[-1][:10]}   "
      f"horizon {HORIZON // BARS} sessions   round trip costs {FEE:.4%}")
print("=" * 112)
print(f"{'level':>7} | {'trades':>7} {'/yr':>6} | {'net/yr':>8} {'fees/yr':>8} | "
      f"{'base':>6} {'after win':>10} {'lift':>7} {'SE':>6} {'z':>6} | {'verdict':>9}")
print("-" * 112)

rows = []
for lvl in (0.005, 0.0075, 0.01, 0.015, 0.02, 0.03):
    outs, rets, held = chain(lvl)
    nt = len(outs)
    base = float((outs == 1).mean())

    prev, nxt = outs[:-1], outs[1:]
    after_win = nxt[prev == 1]
    n_c = len(after_win)
    cond = float((after_win == 1).mean()) if n_c else float("nan")
    lift = cond - base

    se = float(np.sqrt(cond * (1 - cond) / n_c + base * (1 - base) / nt)) if n_c else float("nan")
    z = lift / se if se else float("nan")
    need80 = Z80 ** 2 * base * (1 - base) / lift ** 2 if lift else float("inf")

    curve = np.cumprod(1.0 + rets)
    equity = float(curve[-1])
    net_yr = equity ** (1 / YEARS) - 1.0
    fees_yr = nt / YEARS * FEE
    maxdd = float((curve / np.maximum.accumulate(curve) - 1.0).min())
    in_mkt = float(held.sum()) / (n - 1)

    verdict = "REAL" if abs(z) >= 1.96 else "noise"
    rows.append({"level": lvl, "trades": nt, "trades_per_year": nt / YEARS,
                 "net_per_year": net_yr, "fees_per_year": fees_yr,
                 "base_win_rate": base, "cond_win_rate": cond, "n_conditional": n_c,
                 "lift": lift, "se_of_lift": se, "z": z,
                 "need_80pct": need80, "significant": bool(abs(z) >= 1.96),
                 "max_drawdown": maxdd, "time_in_market": in_mkt})
    print(f"{lvl:>7.2%} | {nt:>7,} {nt / YEARS:>6.0f} | {net_yr:>+7.2%} {fees_yr:>7.2%} | "
          f"{base:>6.1%} {cond:>10.1%} {lift:>+7.2%} {se:>6.2%} {z:>6.2f} | {verdict:>9}")

print()
print("  'lift' is P(win | previous trade won) minus the unconditional rate, both measured")
print("  on the SAME disjoint chain. 'SE' is its standard error at that chain length.")
print("  |z| below 1.96 means the lift is not distinguishable from zero on this sample.")
print()
print("=" * 112)
print("WHAT WOULD IT TAKE TO RESOLVE THE LIFT AS OBSERVED?")
print("=" * 112)
print(f"{'level':>7} | {'observed lift':>14} {'have':>8} {'need @80%':>11} "
      f"{'shortfall':>10} {'years of QQQ needed':>21}")
print("-" * 112)
for r in rows:
    if not np.isfinite(r["need_80pct"]):
        continue
    short = r["need_80pct"] / r["n_conditional"]
    print(f"{r['level']:>7.2%} | {r['lift']:>+13.2%} {r['n_conditional']:>8,} "
          f"{r['need_80pct']:>11,.0f} {short:>9.1f}x {short * 8:>20.0f}")

# ---------------------------------------------------------------- the only benchmark
# The chain re-enters on the bar after every exit, so it is long essentially all of the
# time. Whatever it earns, it earns from QQQ's drift - not from the barriers. Holding is
# therefore the floor it has to clear, and the barriers can only subtract from it.
bh_eq = float(c[-1]) / float(o[1])
bh_yr = bh_eq ** (1 / YEARS) - 1.0
bh_curve = c[1:] / float(o[1])
bh_dd = float((bh_curve / np.maximum.accumulate(bh_curve) - 1.0).min())

print()
print("=" * 112)
print("AGAINST SIMPLY HOLDING THE SAME SHARES OVER THE SAME WINDOW")
print("=" * 112)
print(f"{'level':>7} | {'in market':>10} {'net/yr':>8} {'vs hold':>9} "
      f"{'max DD':>8} {'hold DD':>8} | {'what the barriers did':>24}")
print("-" * 112)
for r in rows:
    diff = r["net_per_year"] - bh_yr
    tag = "beat holding" if diff > 0 else "cost you money"
    print(f"{r['level']:>7.2%} | {r['time_in_market']:>10.1%} {r['net_per_year']:>+7.2%} "
          f"{diff:>+8.2%} {r['max_drawdown']:>7.1%} {bh_dd:>7.1%} | {tag:>24}")
print()
print(f"  buy and hold, same window, no fees after the first purchase: {bh_yr:+.2%}/yr, "
      f"max drawdown {bh_dd:.1%}")
print("  The chain holds QQQ almost continuously. Its return is QQQ's drift minus fees")
print("  minus whatever the barriers cut short. There is no signal in it to be right or")
print("  wrong - so beating buy and hold is the ONLY result that would mean anything.")

print()
best = max(rows, key=lambda r: r["net_per_year"])
print(f"  Best chain P&L: {best['level']:.2%} at {best['net_per_year']:+.2%}/yr "
      f"({best['trades_per_year']:.0f} trades/yr, {best['fees_per_year']:.2%}/yr in fees)")
sig = [r for r in rows if r["significant"]]
print(f"  Levels where the re-entry lift is statistically real: "
      f"{', '.join(f'{r['level']:.2%}' for r in sig) if sig else 'NONE'}")

with open(os.path.join(ROOT, "reports", "reentry_chain.json"), "w", encoding="utf-8") as fh:
    json.dump({"horizon_sessions": HORIZON // BARS, "fee_round_trip": FEE,
               "sessions": SESSIONS, "rows": rows}, fh, indent=2, default=str)
print("\nwritten: reports/reentry_chain.json")
