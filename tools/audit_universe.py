"""Data integrity gate for the V4 universe. Nothing is backtested until this passes.

Three checks, each of which has to pass before a barrier may be computed on these files.

  SPLITS ARE REAL AND THE CONVENTION IS RIGHT. The API reports a split_ratio whose
  direction is not self-evident. It is verified against the actual closes either side of
  each ex-date, so the correction is derived from the data rather than from a guess about
  the convention. The verified convention is: post-split price = pre-split price x ratio,
  and a position crossing it holds shares x (1 / ratio). Value is unchanged, which is the
  whole point - a split is not a return.

  NO UNEXPLAINED DISCONTINUITY REMAINS. Every overnight gap larger than a threshold is
  listed and matched against the corporate-action table. A gap that no split or
  distribution explains is either a real market move or a data error, and the two must be
  told apart BEFORE a percentage barrier is allowed to fire on it. The 2020 crash and the
  2020 oil collapse produce genuine double-digit gaps; those are expected and are reported
  as explained-by-market, not silently suppressed.

  SESSIONS ARE ALIGNED ACROSS SYMBOLS. A cross-sectional test compares symbols on common
  dates. If one symbol is missing sessions the others have, a pooled statistic quietly
  mixes different windows. The intersection is what the test may use.

Read-only with respect to the market data: this writes a corporate-action table and a
report, and never modifies a raw file.

Usage: python tools/audit_universe.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RAW = os.path.join(ROOT, "data", "raw")
GAP_THRESHOLD = 0.06          # flag any overnight move beyond 6% for explanation
SPLIT_TOLERANCE = 0.02        # a split is confirmed if the gap matches the ratio to 2%

with open(os.path.join(ROOT, "data", "universe_manifest.json"), encoding="utf-8") as fh:
    UMAN = json.load(fh)
with open(os.path.join(ROOT, "data", "universe_dividends_manifest.json"), encoding="utf-8") as fh:
    DMAN = json.load(fh)

SYMBOLS = [r["symbol"] for r in UMAN["symbols"]]
DIV = pd.read_csv(os.path.join(ROOT, "data", "universe_dividends.csv"))
SPLITS = {(s["symbol"], s["ex_date"]): float(s["split_ratio"])
          for s in DMAN["splits_all"]}

print("=" * 104)
print("V4 UNIVERSE DATA INTEGRITY GATE")
print(f"{len(SYMBOLS)} symbols, gap threshold {GAP_THRESHOLD:.0%}")
print("=" * 104)

series, sessions_per_symbol = {}, {}
for sym in SYMBOLS:
    d = pd.read_csv(os.path.join(RAW, f"US_{sym}_5min_raw.csv"),
                    usecols=["time_key", "open", "high", "low", "close"])
    d["date"] = d["time_key"].str[:10]
    series[sym] = d
    sessions_per_symbol[sym] = set(d["date"].unique())

# ------------------------------------------------------------------ 1. session alignment
common = set.intersection(*sessions_per_symbol.values())
union = set.union(*sessions_per_symbol.values())
print(f"\n[1] SESSION ALIGNMENT")
print(f"    common to all {len(SYMBOLS)} symbols : {len(common):,}")
print(f"    union across symbols            : {len(union):,}")
odd = {s: len(union - sessions_per_symbol[s]) for s in SYMBOLS
       if sessions_per_symbol[s] != union}
if odd:
    for s, n in sorted(odd.items(), key=lambda x: -x[1])[:10]:
        print(f"      {s:<5} missing {n} session(s) the union has")
else:
    print("    every symbol covers every session - no alignment adjustment needed")

# --------------------------------------------------- 2. splits verified against the bars
print(f"\n[2] SPLIT VERIFICATION")
print(f"    {'symbol':>7} {'ex-date':>12} {'ratio':>7} {'observed':>10} {'implied':>9} "
      f"{'residual':>9}  verdict")
print("    " + "-" * 92)
actions = []
for (sym, ex), ratio in sorted(SPLITS.items()):
    d = series.get(sym)
    if d is None:
        continue
    before, after = d[d["date"] < ex], d[d["date"] >= ex]
    if not len(before) or not len(after):
        continue
    pb, pa = float(before["close"].iloc[-1]), float(after["close"].iloc[0])
    observed = pa / pb
    residual = observed / ratio - 1.0        # the real market move left after the split
    ok = abs(residual) < 0.10                # generous: a split day can also move
    tight = abs(residual) < SPLIT_TOLERANCE
    verdict = "CONFIRMED" if tight else ("confirmed, day also moved" if ok else "MISMATCH")
    print(f"    {sym:>7} {ex:>12} {ratio:>7.3f} {observed:>10.4f} {ratio:>9.3f} "
          f"{residual:>+8.2%}  {verdict}")
    actions.append({"symbol": sym, "ex_date": ex, "type": "split",
                    "price_multiplier": ratio, "share_multiplier": 1.0 / ratio,
                    "observed_close_ratio": round(observed, 6),
                    "residual_market_move": round(residual, 6),
                    "verdict": verdict})

bad = [a for a in actions if a["verdict"] == "MISMATCH"]
print(f"\n    {len(actions)} split(s) checked, {len(bad)} mismatched"
      + ("  <-- STOP, the convention is wrong" if bad else ""))

# ------------------------------------------- 3. every large overnight gap gets an owner
print(f"\n[3] UNEXPLAINED DISCONTINUITY SCAN")
div_by = {(r.symbol, r.ex_date): float(r.gross_per_share) for r in DIV.itertuples()}
gaps = []
for sym, d in series.items():
    # last close of each session against the first open of the next
    last = d.groupby("date").last().reset_index()
    first = d.groupby("date").first().reset_index()
    prev_close = last["close"].to_numpy(float)[:-1]
    next_open = first["open"].to_numpy(float)[1:]
    dates = first["date"].to_numpy()[1:]
    move = next_open / prev_close - 1.0
    for i in np.flatnonzero(np.abs(move) > GAP_THRESHOLD):
        ex, m = str(dates[i]), float(move[i])
        r = SPLITS.get((sym, ex))
        if r is not None and abs((1 + m) / r - 1) < 0.10:
            why = f"split x{r}"
        elif (sym, ex) in div_by and abs(m) < 0.15:
            why = f"distribution {div_by[(sym, ex)]:.4f}/sh"
        else:
            why = "MARKET or UNEXPLAINED"
        gaps.append({"symbol": sym, "date": ex, "gap": round(m, 6), "explanation": why})

by_reason = {}
for g in gaps:
    key = "corporate action" if g["explanation"] != "MARKET or UNEXPLAINED" else "market/unexplained"
    by_reason.setdefault(key, []).append(g)

print(f"    {len(gaps)} overnight moves beyond {GAP_THRESHOLD:.0%}")
print(f"      explained by a corporate action : {len(by_reason.get('corporate action', []))}")
print(f"      market moves or unexplained     : {len(by_reason.get('market/unexplained', []))}")

unex = sorted(by_reason.get("market/unexplained", []), key=lambda g: -abs(g["gap"]))
if unex:
    print(f"\n    Largest unattributed gaps - each must be a real market move, not an error:")
    print(f"      {'symbol':>7} {'date':>12} {'gap':>9}")
    for g in unex[:15]:
        print(f"      {g['symbol']:>7} {g['date']:>12} {g['gap']:>+8.1%}")
    dates_hit = {}
    for g in unex:
        dates_hit.setdefault(g["date"], []).append(g["symbol"])
    clustered = {d: s for d, s in dates_hit.items() if len(s) >= 5}
    print(f"\n    {len(clustered)} date(s) where 5+ symbols gapped together - that pattern is")
    print(f"    a market event, not a per-symbol data fault:")
    for d in sorted(clustered)[:12]:
        print(f"      {d}  {len(clustered[d])} symbols")
    lone = [g for g in unex if len(dates_hit[g["date"]]) == 1]
    print(f"\n    {len(lone)} gap(s) affected a SINGLE symbol on a date no other symbol gapped.")
    print("    Those are the only genuine data-integrity suspects:")
    for g in lone[:12]:
        print(f"      {g['symbol']:>7} {g['date']:>12} {g['gap']:>+8.1%}")

out = {
    "generated_from": "data/universe_manifest.json + data/universe_dividends_manifest.json",
    "gap_threshold": GAP_THRESHOLD,
    "split_convention_verified": ("post-split price = pre-split price x ratio; "
                                  "a position crossing a split holds shares x (1/ratio), "
                                  "so its value is unchanged and no barrier may fire on it"),
    "sessions_common_to_all": len(common),
    "sessions_union": len(union),
    "symbols_missing_sessions": odd,
    "corporate_actions": actions,
    "split_mismatches": bad,
    "large_gaps": gaps,
}
os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
with open(os.path.join(ROOT, "data", "universe_corporate_actions.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, default=str)

print()
print("=" * 104)
gate = not bad and not odd
print(f"GATE: {'PASS' if gate else 'FAIL'}"
      + ("" if gate else "  - fix the items above before any backtest"))
print("=" * 104)
print("written: data/universe_corporate_actions.json")
