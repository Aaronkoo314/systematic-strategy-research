# Preregistration — Candidate V1

**Frozen 2026-09-16, before any backtest of this candidate was run.**
Commit this file before running anything. Any later change is a separate commit with a
stated reason, and invalidates the untouched status of the final test period.

---

## 0. Standing limitation, stated first

The ex-ante power gate (`docs/power_gate_result.md`) **failed**. On this sample, a timing
overlay at 50 % exposure would need roughly 45 years to distinguish a 10 %/yr edge from
luck, and 8 years are available.

The operator elected on 2026-09-16 to run the full process regardless, to validate the
system end to end. **Every result produced under this preregistration therefore carries
the label "not statistically distinguishable from luck", and that sentence appears in
the body of every report, not a footnote.** Running the process is an engineering
validation, not evidence about the strategy.

One thing the gate did change: it identified **tracking error** as the binding quantity.
At 90 % exposure the minimum detectable alpha falls to 7.60 %/yr because the overlay
barely deviates from the benchmark. The candidate below is therefore a **continuous
exposure rule**, not a binary switch — chosen because it is more measurable, not because
it is more likely to work.

---

## 1. The hypothesis

**Volatility targeting on QQQ.** Hold a continuously-adjusted long position sized so that
the portfolio's forecast volatility stays near a constant target. Reduce exposure when
realised volatility is high; restore it when volatility falls.

### Economic rationale, stated before the rules

Volatility is persistent — high-volatility periods cluster — so recent realised volatility
forecasts near-term volatility better than chance. Moreira & Muir (2017, *Journal of
Finance*) document that scaling exposure inversely to recent volatility improves
risk-adjusted returns across asset classes. The mechanism is not prediction of direction:
it is that the return-to-risk ratio is not constant across volatility regimes, so a
constant *dollar* exposure is not a constant *risk* exposure.

**What is NOT claimed.** No claim that this predicts direction. No claim of alpha against
a risk-matched benchmark. The claim is narrower: that constant-risk sizing produces a
better drawdown profile than constant-dollar sizing, at a cost in fees that this account
can bear.

**Contamination disclosure.** Volatility targeting is a widely published rule and has
been extensively mined. Separately, QQQ intraday factor searches were run on this exact
2018-onward dataset before this project began, with the number of attempts unrecorded.
No result here may be described as untouched out-of-sample evidence.

### Why it might survive costs

Rebalancing is banded (§2), so turnover is driven by volatility regime changes rather
than by every bar. At TP = 10,000 a round trip costs USD 2.4636, and the operator's
ceiling is 10 %/yr = 405 round trips. The band is set so that expected turnover is far
below that; if a configuration exceeds it, the risk layer refuses the order and the
configuration is recorded as having breached, not silently allowed.

### Failure regimes, named before measurement

1. **Sharp V-shaped recoveries.** Volatility spikes at the bottom, so exposure is cut
   near the low and restored after the rebound. March 2020 is the archetype.
2. **Low-volatility grinds downward.** Volatility stays low while price falls; the rule
   keeps full exposure into the decline.
3. **Whipsawing volatility.** Repeated crossings of the band produce fees with no
   directional benefit.
4. **Rising-rate regimes where cash earns nothing.** This sample contains 2018-2021 at
   near-zero short rates; idle cash is modelled at 0 % throughout, which is conservative
   now and was accurate then.

### What would falsify it

Drawdown no better than buy-and-hold, or return so much worse that the drawdown
improvement is not worth it. Precisely: §5.

---

## 2. The rules, unambiguous

```
Instrument      US.QQQ, long only, whole shares
Data            5-minute raw (AuType.NONE) bars, data/raw/US_QQQ_5min_raw.csv
Overnight       permitted (operator decision 2026-09-16)

At each completed bar i:
    r_k        = log(close_k / close_{k-1}) for the trailing N bars
    sigma_hat  = stdev(r_k, ddof=1) * sqrt(78 * 252)        # annualised
    w_raw      = sigma_target / max(sigma_hat, 0.01)
    w_target   = clip(w_raw, 0.0, 0.90)                     # 0.90 = mandate cap

    if |w_target - w_current| > BAND:  order to w_target
    else:                              no order

BAND            = 0.10, FIXED. A convention, not a searched parameter.
Warmup          = N bars; no orders before that
Execution       signal from bar i, fill at bar i+1 OPEN, market order
Sizing          shares = floor(w * NAV / price), NAV = cash + market value
Cash            idle cash earns 0 %
Dividends       cash credit on ex-date, net of 30 % withholding
Risk            RiskLimits() defaults, enforced pre-trade, never bypassed
```

**Free parameters: exactly 2.** Everything else above is fixed.

---

## 3. Parameter grid, frozen

| Parameter | Values | Meaning |
|---|---|---|
| `N` | 78, 390, 780 | 1, 5, 10 sessions of 5-minute bars |
| `sigma_target` | 0.15, 0.20, 0.25 | annualised volatility target |

**9 configurations.** Budget in `selection_criteria.md` §6 is 24 on training; 9 is used
and 15 are left unused, which is recorded rather than spent.

**Bonferroni N for every reported statistic = 9**, and the figure is printed beside every
Sharpe ratio.

---

## 4. Date splits, frozen

Adapted from `selection_criteria.md` appendix A.2, which was written for the 20-year
daily series. Intraday data begins 2018-09-10, so the split is re-derived here — and
this adaptation is itself a deviation, recorded now rather than discovered later.

| Segment | Dates | Sessions | Permitted use |
|---|---|---|---|
| **Training** | 2018-09-10 → 2022-12-31 | ~1,080 | grid search, free exploration |
| **Validation** | 2023-01-01 → 2024-12-31 | ~500 | confirm the single chosen config |
| **Final test** | 2025-01-01 → 2026-09-11 | ~430 | **run exactly once** |

Training deliberately contains the three stress events available: 2018Q4, the 2020 COVID
crash, and the 2022 bear market. **The final test period contains none of them**, which
must be stated wherever the test result appears — it is a calm-market sample and cannot
test the drawdown claim at all.

---

## 5. Selection rule and acceptance criteria, frozen

### Selection on training

Choose the configuration maximising **return per unit of maximum drawdown**
(`total_return / |max_drawdown|`) on the training segment. One number, fixed now, so the
choice cannot be made by eye afterwards. Ties broken by lower turnover.

### Comparators

Every result is reported against all four:
1. Buy-and-hold QQQ, same cost model, uncapped
2. Cash (0 %)
3. Static de-risked blend `w·QQQ + (1−w)·cash` with `w = 0.90` — the constant-dollar
   version of the same exposure
4. Static blend at the candidate's own *average realised* exposure — the fairest
   comparator, since it isolates the timing from the sizing

Comparator 4 matters most. If the candidate cannot beat a static blend holding the same
average exposure, then its volatility timing contributed nothing and only its lower
average exposure did.

### Abandon conditions — any one ends the candidate

| | |
|---|---|
| A1 | Max drawdown worse than buy-and-hold on validation |
| A2 | Fails to beat comparator 4 on `return / |max_drawdown|` on validation |
| A3 | Realised turnover breaches the 10 %/yr fee ceiling |
| A4 | The 20 % abandon point is triggered on training or validation |
| A5 | Result reverses under any stress variant in §6 |
| A6 | Chosen parameters differ materially between training and validation when re-fitted |

### Conditions to look at the final test

All of A1–A6 clear on validation. The test is then run **once**, and the result recorded
before any further change. If the strategy is modified after seeing it, the test period
stops being out-of-sample and every later report must say so.

---

## 6. Stress variants, all reported

| | |
|---|---|
| S1 | costs × 1.5 |
| S2 | costs × 2.0 |
| S3 | slippage 10 bp intraday, 25 bp overnight |
| S4 | execution delayed one extra bar |
| S5 | `BAND` 0.05 and 0.15 (turnover sensitivity) |
| S6 | dividend withholding 0 % (the unverified QII case) |

---

## 7. What this preregistration cannot fix

The power gate failed before this document was written. No selection rule, no split and
no stress test makes an 8-year sample able to resolve an effect smaller than its own
tracking error. **If the candidate passes every criterion above, the correct conclusion
is still "passed the process, not shown to work".**
