# Validation Report — Candidate V3, QQQ plus Treasuries

**Date 2026-09-16.** Preregistration: `docs/preregistration_v3.md`, frozen before any run.
Reproduce: `python tools/run_experiment_v3.py`.

---

## 1. Verdict: NO-GO — passed validation, failed the final test

This is the first candidate in the project to clear every abandon condition on validation.
It then lost on the test period, and the loss is the informative kind: the split was
built so training held the episode that supports the hypothesis and the test held the one
that refutes it.

| Final test 2021-01 → 2026-09 (contains 2022) | Return | CAGR | Max DD | |
|---|---|---|---|---|
| **Candidate — QQQ 35 % / TLT 65 %** | +3.9 % | **+0.68 %** | **−31.89 %** | **breached 20 %** |
| **35 % QQQ + cash — incumbent** | +36.2 % | **+5.60 %** | **−11.61 %** | survived |
| 50 % QQQ + cash | +54.9 % | +8.02 % | −17.28 % | survived |
| 100 % QQQ | +132.6 % | +16.05 % | −34.76 % | breached |
| **100 % TLT alone** | **−39.6 %** | **−8.51 %** | −43.29 % | breached |

**The defensive sleeve lost 39.6 %.** Holding 65 % of the portfolio in long Treasuries
produced a deeper drawdown than holding 100 % QQQ.

---

## 2. What it looked like before the test

| Training 2006-09 → 2014-12 (contains 2008) | CAGR | Max DD | |
|---|---|---|---|
| QQQ 35 % / IEF 65 % | +7.63 % | −13.37 % | inside 20 % |
| **QQQ 35 % / TLT 65 % — selected** | **+8.52 %** | **−14.18 %** | inside 20 % |
| QQQ 50 % / TLT 50 % | +9.46 % | −21.53 % | breached |
| QQQ 65 % / TLT 35 % | +10.40 % | −30.45 % | breached |
| *35 % QQQ + cash — incumbent* | *+4.57 %* | *−19.96 %* | inside 20 % |

Two of six configurations stayed inside 20 %. The selected one nearly doubled the
incumbent's return **with a smaller drawdown**, in the period containing the 2008 crash.

| Validation 2015-01 → 2020-12 | CAGR | Max DD |
|---|---|---|
| Candidate | **+10.23 %** | −12.07 % |

All abandon conditions cleared: no 20 % breach, CAGR above the incumbent, turnover
trivial at 0.013 %/yr.

**On two of three periods this was the best thing the project had found.**

---

## 3. Why it failed, and why that was predictable

The preregistration separated two channels and said only one was reliable:

> *Diversification is arithmetic and survives any regime. Flight to quality is
> behavioural and is not reliable — it fails when the shock is inflation rather than
> growth, which is exactly what 2022 was.*

Measured before the run, and recorded in the preregistration:

| | QQQ | IEF | TLT |
|---|---|---|---|
| 2008 crisis | −41.7 % | **+15.4 %** | **+18.9 %** |
| 2022 | −33.7 % | −15.9 % | **−31.0 %** |

The selection rule picked TLT over IEF because TLT had the higher CAGR on training — and
training is 2006-2014, where TLT's long duration was an asset. The same long duration
made it the worst holding in the sample when rates rose.

**The candidate was selected for a property that reversed sign.** This is not a flaw in
the process; it is the process working. A split designed to test the hypothesis on the
regime it was not chosen for did exactly that.

---

## 4. Stress variants

| | CAGR | Max DD | |
|---|---|---|---|
| S0 baseline (validation) | +10.23 % | −12.07 % | |
| S1 costs × 2.0 | +10.22 % | −12.08 % | costs are irrelevant at 7 orders in 6 years |
| S2 withholding 0 % | +10.82 % | −12.07 % | |
| S3 rebalance in July | +10.39 % | −12.01 % | not an artefact of the January date |
| **S4 train from 2010, no 2008** | **+12.51 %** | **−8.85 %** | |
| **S5 full sample, one pass** | **+7.32 %** | **−21.48 %** | **breached 20 %** |

**S4 and S5 together are the whole story.** Excluding 2008 the mix looks better than ever,
because 2010-2020 is precisely the regime where falling rates made bonds a free lunch.
Run across the entire 20 years in one pass it breaches the abandon point anyway.

---

## 5. Where this leaves the project

Three candidates, three structurally different families, all rejected:

| | Hypothesis | Verdict |
|---|---|---|
| V1 | Volatility targeting — momentum-adjacent risk sizing | lost to a static blend at the same average weight |
| V2 | Dip buying — mean reversion | worse drawdown than static 50 %, at a sixth of the exposure |
| V3 | Stocks plus Treasuries — diversification | best result yet on two of three periods, then −31.89 % on the third |

**Search budget: 21 of 24 configurations used. 3 remain.**

**The only allocation that survived every period inside the operator's 20 % abandon point
is the incumbent: 35 % QQQ and 65 % cash.** Over the full 20 years that is 5.26 %/yr,
turning 10,000 into 27,847, with about ten orders a year and 0.12 %/yr in fees.

A final honest note on that incumbent. It survived not because cash is clever but because
cash cannot fall. In a sample where the equity leg fell 53 % and the "safe" bond leg fell
40 % in different decades, the thing that held up was the sleeve that earns nothing. That
is a statement about the 20 % constraint, not about cash being a good asset — and the
operator may reasonably conclude the constraint is what should change.
