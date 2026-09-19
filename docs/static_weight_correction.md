# Static-weight benchmark: correction of a risk-control artefact

Status: **CORRECTED.** The numbers previously quoted for "hold a fixed fraction of QQQ"
were wrong for what they claimed to measure. The old reports are kept as
`reports/*_VOID_halt_sellonly.*` and must not be cited.

## 1. What was wrong

`tools/static_sweep_daily.py` and `tools/static_sweep.py` ran the fixed-weight benchmark
**under the live RiskManager**, with only `max_weight` overridden. The DRAWDOWN halt
(default -8%) therefore fired at the first -8% drawdown - 2008-02-06 on the 20-year
window, 2010-07-01 post-GFC - and, by design, never auto-resumes: it needs a human
`resume()` that a backtest never supplies.

The halt does not freeze the position. `src/risk/controls.py` lets **risk-reducing orders
through and blocks buys**. So after its first drawdown every "static weight" became:

> sell on the way up to hold weight at or below target; never buy back on the way down.

Realised weight sagged to 21.5% at the March 2009 bottom against a 35% target, 26.9% in
March 2020, 25.0% in December 2022. The strategy that was measured bought none of those
lows. 2,842 orders were blocked as `HALTED` on the 35% / 20-year run alone.

This is the same class of defect as the daily-loss halt with no expiry that once made an
entire experiment measure its own bug. The difference is that this one contaminated a
BENCHMARK, and the benchmark was what the allocation recommendation rested on.

## 2. Why it was hard to see

The contaminated runs looked plausible: they still traded (213 fills on the 35% run,
because sells were allowed), the realised mean weight was close to target (32.8% against
35%, because in a rising market the only rebalancing needed is selling), and CAGR barely
moved (5.26% against the corrected 5.24%). The only number that changed materially was
the one that mattered - **maximum drawdown** - because a position that cannot buy the dip
has less exposure at the bottom.

The benchmark understated its own risk in exactly the region the abandon rule tests.

## 3. Corrected numbers - true two-way rebalancing

Risk manager bypassed via the named engine flag, recorded in `summary["risk_controls"]`.
Net of modelled costs, dividends net of 30% withholding, idle cash at 0%. Rebalance rule
is "trade whenever the integer share target changes", inherited from the engine.

**20 years, 2006-09 .. 2026-09, contains 2008**

| weight | CAGR | max DD | DD date | inside -20%? | old (VOID) DD |
|---:|---:|---:|---|---|---:|
| 25% | 3.66% | **-17.57%** | 2009-03-09 | **yes** | -16.0% |
| 30% | 4.47% | -20.36% | 2008-11-20 | no | -17.0% |
| 35% | 5.24% | -23.35% | 2008-11-20 | no | -19.8% |
| 40% | 6.04% | -26.24% | 2008-11-20 | no | -22.3% |
| 50% | 7.69% | -31.63% | 2008-11-20 | no | -27.7% |

**Previously stated: 35% was the largest weight inside the abandon point. Corrected: 25%.**

**16.7 years, 2010-01 .. 2026-09, no 2008**

| weight | CAGR | max DD | DD date | inside -20%? | old (VOID) DD |
|---:|---:|---:|---|---|---:|
| 40% | 6.95% | -15.24% | 2022-10-14 | yes | -13.8% |
| 50% | 8.79% | **-18.71%** | 2022-11-03 | **yes** | -17.5% |
| 60% | 10.70% | -22.28% | 2022 | no | -21.1% |

Conclusion unchanged here: 50% holds without 2008 in the sample.

**8 years, 2018-09 .. 2026-09, 5-minute engine, no 2008**

| weight | CAGR | max DD | inside -20%? | old (VOID) DD | fills / 8y | fees/yr |
|---:|---:|---:|---|---:|---:|---:|
| 40% | 6.04% | **-17.33%** | **yes** | -14.5% | 1,424 | 1.95% |
| 50% | 8.07% | -20.92% | no | -18.4% | 1,396 | 1.91% |

**Previously stated: 50% held inside 20% on this window. Corrected: it breaches; 40% is
the largest that holds.**

## 4. A second defect, exposed by the correction

The engine trades whenever `floor(weight x NAV / price)` changes by one share
(`engine.py` line 217, `if delta != 0`). On daily bars over 20 years that is 1,087-1,590
orders and 0.60-0.87%/yr in fees; on 5-minute bars over 8 years it is 1,178-1,524 orders
and **1.6-2.1%/yr**. That is not a rebalancing policy, it is an integer-rounding artefact,
and at these fee levels it eats a third of the 40% weight's return.

A deployable fixed-weight allocation needs an explicit rebalance band (trade only when
realised weight drifts more than some tolerance from target) or a calendar rule. Neither
exists in the codebase. `src/backtest/portfolio.py` has an annual calendar rebalance for
the multi-asset case; the single-asset path has nothing.

## 5. What this does to "option A"

Option A was described as "no research needed - the facts are already measured". That
was true only if the facts were right. Corrected:

- With 2008 in sample, the largest QQQ weight inside a 20% abandon point is **25%**,
  earning **3.66%/yr** - not 35% at 5.26%.
- Without 2008, 50% at 8.79%/yr stands.
- The gap between those two rows is a single judgement: whether a 2008-scale drawdown is
  in the risk budget. Nothing in the data decides that.
- A is **not a formed strategy**. It has no rebalance rule, no specification of what the
  live risk controls do when the -8% halt fires and no one is watching, and no treatment
  of how a 10,000 USD sleeve interacts with the operator's existing positions in a shared
  margin account. It is an allocation number with three open design questions.

## 6. Reproduce

```
python tools/static_sweep_daily.py     # 20y and post-GFC, daily, bypass recorded
python tools/static_sweep.py           # 8y, 5-minute, bypass recorded
```

Void reports: `reports/static_sweep_daily_VOID_halt_sellonly.json`,
`reports/static_sweep_VOID_halt_sellonly.{json,csv}`.
