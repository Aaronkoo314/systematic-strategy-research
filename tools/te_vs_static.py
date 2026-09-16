"""Does a mandate-compliant AND measurable design exist?

The earlier table computed tracking error against buy-and-hold at 100%. But the mandate
caps exposure well below that, so buy-and-hold is not the right comparator for a rule
that lives at 50%. The honest comparator - preregistration comparator 4 - is a STATIC
blend at the rule's own average weight.

A rule whose weight is w0 + d_t, compared against static w0, has return difference
d_t * r_t. Its tracking error is roughly std(d) * sigma_annual, and that is small when
the deviations are small - which is exactly the regime the mandate forces.
"""
import sys
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
from src.validation.power import power_gate

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_daily.csv"))
c = d["close_raw"].to_numpy(float)
r = np.diff(c) / c[:-1]
years = (len(r) + 1) / 252.0
sig = float(np.std(r, ddof=1) * np.sqrt(252))
rng = np.random.default_rng(0)

print("=" * 88)
print("Tracking error against a STATIC blend at the same average weight")
print(f"QQQ daily 2006-09..2026-09, {years:.2f} years, annualised vol {sig:.2%}")
print("=" * 88)
print(f"{'base w':>7} {'tilt sd':>8} {'track err':>10} | "
      f"{'MDA n=1':>9} {'MDA n=6':>9} {'MDA n=24':>9} | {'alpha needed to pass':>21}")
print("-" * 88)

rows = []
for w0 in (0.50, 0.56):
    for sd in (0.05, 0.10, 0.15, 0.20):
        # weight wanders around w0 with standard deviation sd, clipped to [0, 0.90]
        tes = []
        for _ in range(200):
            dev = rng.normal(0.0, sd, len(r))
            w = np.clip(w0 + dev, 0.0, 0.90)
            diff = (w - w0) * r                    # rule minus static-w0
            tes.append(np.std(diff, ddof=1))
        te = float(np.mean(tes) * np.sqrt(252))
        m1 = power_gate(te, years, n_configs=1).min_detectable_alpha_80pct_power
        m6 = power_gate(te, years, n_configs=6).min_detectable_alpha_80pct_power
        m24 = power_gate(te, years, n_configs=24).min_detectable_alpha_80pct_power
        print(f"{w0:>7.0%} {sd:>8.2f} {te:>10.2%} | {m1:>9.2%} {m6:>9.2%} {m24:>9.2%} | "
              f"{'>= ' + format(m6, '.2%') + ' at n=6':>21}")
        rows.append((w0, sd, te, m1, m6, m24))

print()
print("For scale: the static sweep showed holding a fixed 50% of QQQ produced 8.88%/yr")
print("over 2018-2026. An edge of 1-3%/yr on top of that would be a 11-34% improvement")
print("in return - and the table above says an edge that size is measurable on 20 years")
print("provided the tilts stay small and the search budget stays small.")
print()
print("The catch, stated plainly: a rule that only tilts by +/-5 to 10 percentage points")
print("cannot rescue a drawdown. It is a return-improvement hypothesis, not a")
print("risk-reduction one. The 20% abandon point still has to be met by the BASE weight,")
print("which the static sweep already fixed at about 50%.")
