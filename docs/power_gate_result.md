# Ex-Ante Power Gate — Result

**Run 2026-09-16, before any strategy was proposed and before any backtest was run.**

Gate defined in `selection_criteria.md` appendix A.5(a), frozen 2026-09-15:

> A candidate must submit a power calculation with its proposal, and **if the required
> sample length exceeds the available sample length, it is rejected without a backtest.**

Reproduce: `python tools/run_power_gate.py` → `reports/power_gate.json`

---

## Result: the gate FAILS for intraday QQQ timing

| Sample | |
|---|---|
| Sessions | 2,012 |
| Years | 7.98 |
| Annualised volatility | 24.20 % |
| Raw daily observations | 2,011 |
| Effective sample size | 2,756 independent-equivalent daily observations |

*(Effective size exceeds the raw count because QQQ daily returns are slightly
negatively autocorrelated over this window. That helps, and it is nowhere near enough.)*

### Minimum detectable annualised excess return vs buy-and-hold, 80 % power

| Exposure | Tracking error | Min detectable alpha | |
|---|---|---|---|
| 25 % | 21.00 % | **20.82 %/yr** | above the 10 %/yr fee ceiling |
| 50 % | 17.11 % | **16.97 %/yr** | above the 10 %/yr fee ceiling |
| 75 % | 12.11 % | **12.00 %/yr** | above the 10 %/yr fee ceiling |
| 90 % | 7.67 % | 7.60 %/yr | below the ceiling — but 90 % exposure is buy-and-hold with extra steps, and buy-and-hold is abandoned at the 20 % drawdown line |

### With the frozen search budget applied

Bonferroni over configurations tried, at 50 % exposure:

| Configurations searched | Critical z | Min detectable alpha |
|---|---|---|
| 1 | 1.960 | 16.97 %/yr |
| 6 | 2.638 | 21.07 %/yr |
| **24** (the training budget frozen in §6) | 3.078 | **23.74 %/yr** |

### Years required to detect a given alpha — 50 % exposure, 24 configurations

| Claimed alpha | Years needed | Available | |
|---|---|---|---|
| 2 %/yr | 1,124.7 | 7.98 | **FAIL** |
| 5 %/yr | 179.9 | 7.98 | **FAIL** |
| **10 %/yr** | **45.0** | 7.98 | **FAIL** |
| 15 %/yr | 20.0 | 7.98 | **FAIL** |
| 20 %/yr | 11.2 | 7.98 | **FAIL** |

---

## What this means, stated plainly

**To demonstrate a 10 %/yr edge on this instrument, at this exposure, with the search
budget already frozen, would require about 45 years of data. There are 8.**

Even a 20 %/yr edge — larger than QQQ's entire realised return over the period — needs
11.2 years and still fails.

The binding quantity is the **tracking error**, and the reason it is binding is
structural: a timing overlay that is out of a 24 %-volatility asset half the time
deviates from buy-and-hold by about 17 %/yr *regardless of whether the timing is any
good*. A skilful rule and a worthless one carry the same denominator. Only the numerator
differs, and 8 years cannot resolve a numerator smaller than the denominator.

Two further points that make it worse rather than better:

1. **The fee ceiling is 10 %/yr.** Anything this sample could prove is already being
   spent on fees. The detectable region and the economically useful region do not
   overlap.
2. **The sample is contaminated.** QQQ intraday factor searches were run on this same
   2018-onward data before this project began, and the number of attempts is unrecorded.
   The Bonferroni correction above uses 24, the *planned* budget. The true N is unknown
   and larger, so 23.74 %/yr is a floor, not an estimate.

---

## What this does not mean

It does **not** say no intraday edge exists in QQQ. It says **this sample cannot
distinguish one from luck at any effect size that would also be worth trading.**

That distinction matters for what happens next. The failure is not a property of any
strategy — no strategy has been proposed. It is a property of the data available, the
volatility of the instrument, and the search budget. Proposing a cleverer rule does not
change any of those three.

---

## Consequence under the frozen criteria

Appendix A.5(a) is unambiguous: rejected without a backtest. Running one anyway would
produce a number that cannot carry the weight that would be placed on it — which is the
exact failure the gate was written, a day earlier and before any result existed, to
prevent.

**Options that would change the answer, in order of how much they actually help:**

| | Effect |
|---|---|
| **Lengthen the sample.** Daily QQQ data reaches back to 2006-09 — 20 years instead of 8. A daily-frequency strategy has 2.5× the sample. It does not fix the tracking-error problem but it moves every number in the right direction. | large |
| **Reduce the tracking error.** A rule that stays close to the benchmark most of the time is easier to measure — but that is the 90 % exposure row, which is buy-and-hold, which the 20 % abandon point rejects. | contradictory |
| **Shrink the search budget.** Going from 24 configurations to 1 lowers the bar from 23.74 % to 16.97 %. Still far above anything plausible. | small |
| **Accept a lower confidence standard.** Possible, and it must then be stated in every report that the result is not statistically distinguishable from luck. | honest but weak |
| **Abandon the timing-overlay framing** and test something whose signal is not competing against a 24 %-volatility benchmark. | unexplored |

---

## Recorded for the log

This is a preregistered gate producing a rejection before any backtest was run. It cost
one day of work and prevented an unknown number spent on a result that could not have
been interpreted. That is the gate working as designed, and it is recorded here as a
result in its own right — not as a setback.
