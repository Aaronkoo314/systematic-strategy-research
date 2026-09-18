# Preregistration V4 - cross-sectional test of short-horizon state dependence

DRAFT - frozen only when committed. Written before any data beyond QQQ was pulled and
before any cross-sectional return was computed.

## 0. Why there is a V4 at all

V4 exists because `docs/swing_verdict.md` closed a door and pointed at one window.

Closed: symmetric barriers with immediate re-entry are buy-and-hold minus fees, because
the rule is in the market 100% of the time. Every level from 0.50% to 3.00% lost to
holding by approximately its fee bill.

The window: to beat holding, a rule must be OUT of the market during stretches that are
worse than average. That requires timing information. The chain measurement found a hint
of one - outcomes appeared to cluster, wins following wins and losses following losses -
but on QQQ alone the lift was smaller than its standard error at every level.

V4 tests that hint on a cross-section, because the shortfall was in independent
observations and the cross-section is where more of them live. It does not test the
barrier family again.

## 1. The hypothesis, stated so it can fail

**H1.** Short-horizon outcomes are state-dependent: P(next move is +X before -X | last
move was +X before -X) > P(next move is +X before -X | last move was -X before +X).

**H0.** They are independent. The two conditional probabilities are equal.

If H1 holds, a long/flat rule that stays in after a favourable resolution and steps aside
after an adverse one is out of the market disproportionately during bad stretches, and can
beat holding. If H0 holds it cannot, and V4 fails.

H1 is a claim about the DIFFERENCE between two conditional rates, not about either rate
being above 50%. A drifting asset makes both above 50% for free.

## 2. Universe - frozen before any of it is pulled

Selection rule, in full: **US-listed ETFs from the three named lists below, every one of
which was listed and trading on 2018-09-10, the first date of available 5-minute history.**

- Equity sectors, the SPDR Select Sector family, all eleven:
  XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY
- Broad and international equity: SPY IWM DIA EFA EEM
- Non-equity: TLT IEF LQD HYG GLD SLV USO

23 symbols. The lists are membership-defined, not performance-defined: an ETF enters
because of what it tracks, not how it did. No symbol was chosen after seeing a return.

**QQQ is excluded from the primary test.** Its full 8-year sample has been mined across
21 prior configurations and all of `docs/swing_verdict.md`. It is reported separately as
a contaminated reference and carries no weight in any decision.

Survivorship: none of the 23 was delisted or merged over the window, so the set as
constructed in 2018 equals the set available today. If any is found to have been
delisted, it stays in and is tested over its actual life; it is not replaced.

If the history-candle quota cannot cover 23, symbols are dropped from the END of this
frozen order: XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY SPY IWM DIA EFA EEM TLT IEF
LQD HYG GLD SLV USO. Never by what the data turns out to show. A truncated universe is
reported as truncated.

## 3. The rule - one free parameter, no others

A two-state machine on 5-minute bars, long or flat, never short.

```
IN   : hold a full position. Barriers at +X and -X from the entry fill.
       +X resolves first  ->  exit, re-enter on the NEXT bar, stay IN
       -X resolves first  ->  exit, go OUT
       neither within 15 sessions -> exit at that bar's close, stay IN

OUT  : hold cash, earning ZERO. Re-enter when price trades X above the exit price.
       There is no timer and no second threshold.
```

The re-entry threshold is the same X, deliberately. A second parameter would double the
search and there is no budget for it.

Cash earns zero while OUT. Over this window Treasury bills earned materially more than
zero, so this understates the rule and overstates holding. The bias runs against the
hypothesis, which is the direction a test should lean.

Everything else is inherited from the existing frozen machinery and is not re-chosen here:
signals act on the bar after the one that generated them (`src/data/bars.py`), positions
are full-NAV weights (`src/backtest/engine.py`), fees come from `src/costs/fees.py`.

### 3a. Fill assumptions - stricter than V1-V3 used

**A barrier that gaps is filled at the open, not at the barrier.** If a bar opens beyond
a barrier, the fill price is that open. Overnight gaps and opening prints go through stops
rather than stopping at them.

This is a correction, not a refinement. The chain measurement in `docs/swing_verdict.md`
filled at the barrier price, which is optimistic. That optimism made the barrier family
look BETTER than it was and it still lost to holding, so the verdict there stands
unweakened - but no V4 number may be computed that way.

Intra-bar ordering is unknowable from OHLC. When a bar's high reaches +X and its low
reaches -X, the outcome is recorded as the ADVERSE one. Ties resolve against the rule.

## 4. Parameter grid - exhausts the search budget

X in {1%, 2%, 3%}. Three configurations. The preregistered budget in
`docs/selection_criteria.md` stands at 21 of 24 used; this takes it to 24 of 24.

**When these three are spent the search is over under the project's own frozen rules.**
A fourth value of X, a second re-entry threshold, or a different horizon is not a
refinement of V4, it is a new search requiring a new budget and a stated reason.

## 5. Benchmark

Buy and hold the same symbol over the same window, one purchase, no further fees.

Nothing else is a benchmark. Not cash, not the rule at a different X, not QQQ. The single
question is whether stepping aside pays for itself against never stepping aside.

## 6. Test statistic and the correlation problem

Per symbol s: `d_s = (annualised net return of the rule) - (annualised return of holding)`.

The naive test - a t-test on the 23 values of d_s - is **wrong and must not be reported
as the primary result.** The 23 symbols are not 23 independent experiments; eleven are US
equity sectors moving together, and in a drawdown nearly all of them move together. A
naive t-test on correlated units overstates significance, sometimes by several fold.

Primary test: **stationary block bootstrap over TIME, resampling blocks simultaneously
across all symbols**, which preserves whatever cross-sectional correlation exists on each
resampled date rather than assuming it away.

- Block length: 21 sessions (one month), frozen.
- Resamples: 10,000, frozen.
- Statistic: the cross-sectional mean of d_s on each resample.
- Reported: the share of resamples with mean d <= 0, as a one-sided p-value.

Also reported, as diagnostics and NOT as the decision: the naive t-statistic, the mean
pairwise correlation of the per-symbol daily rule returns, and the implied effective
number of independent symbols `N_eff = N / (1 + (N-1) * rho_bar)`. If N_eff is under 3,
that is stated in the headline of the result, whatever the bootstrap says.

## 7. Splits

- Train 2018-09-10 .. 2022-12-31
- Validation 2023-01-01 .. 2024-12-31
- Test 2025-01-01 .. 2026-09-11

The test segment is opened ONCE, for whichever single X survives train and validation. If
none survives, the test segment is not opened at all and no test-segment number is
computed, quoted or estimated.

## 8. Decision threshold

Bonferroni over the full preregistered budget of 24 configurations: the primary bootstrap
p-value must be **below 0.05 / 24 = 0.00208** on the training segment.

This is deliberately severe and it is the correct severity. 24 configurations have been
tried against this data; the threshold has to price that in.

## 9. Abandon conditions - stated before the entry conditions, per Goal 4

V4 is abandoned, with no re-parameterisation, if ANY of:

- **A1.** The training-segment bootstrap p-value is at or above 0.00208 for all three X.
- **A2.** The cross-sectional mean d_s is negative on the training segment for all three X.
  (The rule loses to holding on average; no p-value can rescue that.)
- **A3.** N_eff falls below 2.0, meaning the cross-section supplied essentially no
  independent observations and the exercise did not do what it was for.
- **A4.** The surviving X wins on the training segment but the validation-segment mean
  d_s is negative.
- **A5.** Removing the three largest per-symbol contributions turns the training-segment
  mean d_s negative, i.e. the result is a handful of symbols rather than a
  cross-sectional regularity.
- **A6.** The result reverses sign between the equity block (16 symbols) and the
  non-equity block (7 symbols). A mechanism that exists in one and inverts in the other
  is not a mechanism.
- **A7.** Any look-ahead, survivorship or cost error is found in the implementation that
  materially moves the result. The run is voided and the log kept, per prior practice.

## 10. Entry conditions - what would justify going further

ALL of the following, on the single surviving X:

- **E1.** Training bootstrap p < 0.00208.
- **E2.** Validation-segment cross-sectional mean d_s > 0, with the same sign as training.
- **E3.** N_eff >= 3.0.
- **E4.** Positive mean d_s in BOTH the equity and non-equity blocks.
- **E5.** Positive median d_s, not just positive mean, so the result is not one symbol.
- **E6.** The advantage survives the stress variants in `docs/selection_criteria.md`
  S1-S6, in particular doubled fees.

Meeting E1-E6 justifies opening the test segment. It does not justify trading. It
justifies computing ONE test-segment number and reporting it.

## 11. What this preregistration does not claim

It does not claim the effect exists. The QQQ measurement that motivated it was, on its
own sample, indistinguishable from noise - that is precisely why it needs a larger
cross-section. A null result here is an ordinary and likely outcome, and by section 4 it
ends the search rather than starting the next variant.
