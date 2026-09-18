"""Ex-ante power gate for H1 itself, across the 23-symbol cross-section.

selection_criteria.md Appendix A.5(a) makes this mandatory and highest-priority: if the
required sample exceeds the available sample, the hypothesis is rejected WITHOUT a
backtest. V4 omitted it and was rejected for that among other reasons; this does not
repeat the omission.

WHAT IS BEING GATED. Not a strategy. The hypothesis on its own:

    H1:  Delta = P(+X first | previous race resolved +X) - P(+X first | previous race
                                                                      resolved -X)  > 0

measured on DISJOINT chains - enter, hold to the first barrier touch, start the next race
on the following bar, walk the whole sample. Every race is disjoint from every other, so
the race count IS the independent sample size within a symbol.

Delta needs no fee model, no state machine, no exposure adjustment and no buy-and-hold
denominator. That last point matters: the tracking-error wall that killed every previous
overlay does not apply to a contrast between two conditional probabilities. This is the
cleanest form of the question, and if the cross-section cannot resolve it in this form it
cannot resolve it in any form.

DISCIPLINE. This script computes and prints only VARIANCE quantities - race counts,
cross-symbol correlation, effective sample size, standard error and the minimum detectable
Delta. The effect itself is computed but NOT printed unless the gate passes, because
reading the effect off a sample that cannot resolve it is how a noise draw becomes a
finding. The gate decides whether anyone is allowed to look.

Splits are back-adjusted before any race is run: prices before a split ex-date are
multiplied by the ratio, putting the whole series in post-split units. This affects only
return continuity, which is all a probability contrast uses - no share count and no order
price is involved in Delta.

Usage: python tools/h1_power_gate.py
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
BARS = 78
HORIZON = BARS * 15
LEVELS = (0.01, 0.02, 0.03)

# Bonferroni over the preregistered budget of 24 configurations, per selection_criteria.
ALPHA = 0.05 / 24
Z_ALPHA = 3.0902           # two-sided 0.00208 -> one-sided 0.00104
Z_POWER = 0.8416           # 80 % power

with open(os.path.join(ROOT, "data", "universe_corporate_actions.json"), encoding="utf-8") as fh:
    CA = json.load(fh)
SPLITS = {}
for a in CA["corporate_actions"]:
    SPLITS.setdefault(a["symbol"], []).append((a["ex_date"], float(a["price_multiplier"])))

with open(os.path.join(ROOT, "data", "universe_manifest.json"), encoding="utf-8") as fh:
    SYMBOLS = [r["symbol"] for r in json.load(fh)["symbols"]]


def load(sym):
    d = pd.read_csv(os.path.join(RAW, f"US_{sym}_5min_raw.csv"),
                    usecols=["time_key", "open", "high", "low", "close"])
    d["date"] = d["time_key"].str[:10]
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    dates = d["date"].to_numpy()
    for ex, ratio in SPLITS.get(sym, []):
        m = dates < ex                      # put pre-split bars into post-split units
        o[m] *= ratio
        h[m] *= ratio
        l[m] *= ratio
        c[m] *= ratio
    return o, h, l, dates


def chain(o, h, l, level):
    """Disjoint races. Returns (outcomes, resolution-bar indices). Ties go to -X."""
    n = len(o)
    e, outs, at = 1, [], []
    while e < n - 1:
        j_end = min(e + HORIZON, n)
        if j_end - e < 2:
            break
        p = float(o[e])
        if p <= 0:
            e += 1
            continue
        u = np.flatnonzero(h[e:j_end] >= p * (1 + level))
        dd = np.flatnonzero(l[e:j_end] <= p * (1 - level))
        ju = int(u[0]) if u.size else None
        jd = int(dd[0]) if dd.size else None
        if ju is None and jd is None:
            k, out = j_end - e - 1, 0
        elif jd is None or (ju is not None and ju < jd):
            k, out = ju, 1
        else:
            k, out = jd, -1
        outs.append(out)
        at.append(e + k)
        e = e + k + 1
    return np.array(outs), np.array(at)


print("=" * 108)
print("EX-ANTE POWER GATE FOR H1 - selection_criteria.md Appendix A.5(a), mandatory")
print(f"{len(SYMBOLS)} symbols, disjoint chains, ties resolve to -X")
print(f"threshold alpha = 0.05/24 = {ALPHA:.5f} (Bonferroni over the preregistered budget)")
print("=" * 108)

series = {s: load(s) for s in SYMBOLS}
all_dates = sorted(set(series[SYMBOLS[0]][3]))
date_ix = {d: i for i, d in enumerate(all_dates)}

report = {"alpha": ALPHA, "z_alpha": Z_ALPHA, "z_power": Z_POWER, "levels": {}}

for level in LEVELS:
    per_sym, panels = [], {}
    for sym in SYMBOLS:
        o, h, l, dates = series[sym]
        outs, at = chain(o, h, l, level)
        resolved = outs != 0
        if resolved.sum() < 10:
            continue
        prev, nxt = outs[:-1], outs[1:]
        a = nxt[prev == 1]                       # after a +X race
        b = nxt[prev == -1]                      # after a -X race
        a, b = a[a != 0], b[b != 0]
        if len(a) < 5 or len(b) < 5:
            continue
        p_a, p_b = float((a == 1).mean()), float((b == 1).mean())
        n_a, n_b = len(a), len(b)
        se_s = float(np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b))
        per_sym.append({"symbol": sym, "races": int(resolved.sum()),
                        "n_after_up": n_a, "n_after_down": n_b,
                        "delta": p_a - p_b, "se": se_s})
        # daily panel of race outcomes, for the cross-symbol correlation of the SIGNAL
        v = np.full(len(all_dates), np.nan)
        for oc, bi in zip(outs, at):
            if oc != 0:
                v[date_ix[dates[bi]]] = oc
        panels[sym] = v

    # --- cross-symbol correlation of race outcomes: what the cross-section really buys ---
    names = list(panels)
    M = np.vstack([panels[s] for s in names])
    rs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            m = ~np.isnan(M[i]) & ~np.isnan(M[j])
            if m.sum() >= 30:
                x, y = M[i][m], M[j][m]
                if x.std() > 0 and y.std() > 0:
                    rs.append(float(np.corrcoef(x, y)[0, 1]))
    rho = float(np.mean(rs)) if rs else 0.0
    N = len(per_sym)
    n_eff = N / (1 + (N - 1) * rho) if rho > -1 / max(N - 1, 1) else float(N)

    # SE of the cross-sectional mean Delta, honest about correlation
    se_naive = float(np.sqrt(np.mean([s["se"] ** 2 for s in per_sym]) / N))
    se_eff = float(np.sqrt(np.mean([s["se"] ** 2 for s in per_sym]) / n_eff))
    mde = (Z_ALPHA + Z_POWER) * se_eff
    mde_uncorrected = (1.96 + Z_POWER) * se_eff

    total_races = sum(s["races"] for s in per_sym)
    report["levels"][f"{level}"] = {
        "symbols_used": N, "total_races": total_races,
        "races_per_symbol": total_races / N,
        "rho_bar_of_race_outcomes": rho, "n_eff": n_eff,
        "se_naive_independent": se_naive, "se_effective": se_eff,
        "mde_at_bonferroni": mde, "mde_uncorrected": mde_uncorrected,
        "cross_section_gain_vs_one_symbol": float(np.sqrt(n_eff)),
    }

    print(f"\nX = {level:.0%}")
    print(f"  symbols usable                       {N}")
    print(f"  disjoint races, pooled               {total_races:,}   "
          f"({total_races / N:,.0f} per symbol)")
    print(f"  mean pairwise corr of race outcomes  {rho:+.4f}")
    print(f"  effective independent symbols        {n_eff:.2f}   of {N}"
          f"   -> cross-section buys {np.sqrt(n_eff):.2f}x on the SE, not {np.sqrt(N):.2f}x")
    print(f"  SE of mean Delta, if independent     {se_naive:.4%}")
    print(f"  SE of mean Delta, honest             {se_eff:.4%}")
    print(f"  MINIMUM DETECTABLE Delta @80% power  {mde:.3%}   (alpha={ALPHA:.5f})")
    print(f"    ... without any multiplicity control {mde_uncorrected:.3%}")

print()
print("=" * 108)
print("GATE VERDICT")
print("=" * 108)
print("  The largest conditional lift ever observed on this research line is the +5.1pp")
print("  that docs/swing_verdict.md retracted as an overlapping-sample artefact. The")
print("  honest non-overlapping estimates there ranged -0.43pp to +1.60pp, none")
print("  distinguishable from zero. Take 2.0pp as a generous ceiling on a real Delta.")
print()
passed = []
for lvl, r in report["levels"].items():
    ok = r["mde_at_bonferroni"] <= 0.02
    passed.append(ok)
    print(f"  X={float(lvl):.0%}: needs Delta >= {r['mde_at_bonferroni']:.2%} to be detectable; "
          f"generous ceiling 2.00%  ->  {'PASS' if ok else 'FAIL'}")
print()
if not any(passed):
    print("  A.5(a): the required effect exceeds anything this research line has produced.")
    print("  H1 is REJECTED WITHOUT A BACKTEST across the cross-section. The measured")
    print("  Delta is deliberately NOT printed - reading an effect off a sample that")
    print("  cannot resolve it is how a noise draw becomes a finding.")
else:
    print("  Gate passes at one or more levels; the effect may now be examined there.")

with open(os.path.join(ROOT, "reports", "h1_power_gate.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2, default=str)
print("\nwritten: reports/h1_power_gate.json")
