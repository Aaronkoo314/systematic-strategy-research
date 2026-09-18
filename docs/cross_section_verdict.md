# Cross-sectional expansion: rejected under A.5(a), without a backtest

Status: **CLOSED.** Not by a failed test - by the mandatory ex-ante power gate, which is
the cheapest and most honest way for a research line to end.

## 0. What was being attempted and why

`docs/swing_verdict.md` rejected the barrier family and left one stated window: the
measurements lacked independent observations, and a cross-section is where more of them
were supposed to live. The operator chose that direction.

The plan was: pull a survivorship-free universe of liquid US ETFs, and test the one
hypothesis that had survived as a candidate -

    H1:  Delta = P(+X first | previous race resolved +X)
               - P(+X first | previous race resolved -X)  >  0

on disjoint chains, pooled across symbols, with a block bootstrap preserving the
cross-sectional correlation.

It failed the power gate. The reason generalises past this hypothesis and past this
universe, which is why it is written down separately.

## 1. What was built before the gate was run

All of it stands and is reusable; none of it was wasted.

- 23 ETFs pulled at 5-minute resolution, 156,163-156,164 bars each, exactly 2,010
  sessions each, 2018-09-12 .. 2026-09-11. Session sets identical across all 23
  (intersection = union), so no symbol contributes a different window.
- Universe frozen by what each fund tracks, never by how it did. QQQ excluded from the
  primary test as contaminated by 21 prior configurations.
- Six in-sample splits found and verified against the bars, not against the API's
  documentation: five SPDR sector funds 2-for-1 on 2025-12-05, and USO 1-for-8 on
  2020-04-29 (close 2.13 -> open 18.00, +745%). Left unhandled, USO alone would have
  booked a +745% single-bar gain, enough to turn a cross-sectional mean positive on its
  own. The 2025-12-05 cluster sits inside the segment reserved for the single, once-only
  final test.
- Distributions pulled and sized: net of 30% withholding, HYG yields 3.52%/yr, XLRE
  2.74%, LQD 2.53%. A long/flat rule that ignores them collects a free advantage of
  exactly (yield x fraction of time OUT) - up to 1.76%/yr, larger than any edge this
  research line has ever produced.
- Per-symbol fee model shown to be necessary: a 10,000 USD round trip costs 0.0441% in
  SLV at 33/share against 0.0246% in SPY at 660, because per-share fees scale with share
  count.
- Integrity gate passes: of 137 overnight moves beyond 6%, six are splits, seven dates
  had 5+ symbols gapping together (March 2020), and the 42 single-symbol gaps are almost
  entirely SLV and USO - silver and oil genuinely move alone.

## 2. The gate, and the number that closes the line

`tools/h1_power_gate.py`, run on the cleanest available form of the question. Delta needs
no fee model, no state machine, no exposure adjustment and **no buy-and-hold denominator**
- so the tracking-error wall that killed every previous overlay does not apply to it. If
the cross-section cannot resolve H1 in this form, it cannot resolve it in any form.

| X | disjoint races | mean pairwise rho of race outcomes | N_eff of 23 | SE if independent | SE honest | **MDE @80%** |
|---:|---:|---:|---:|---:|---:|---:|
| 1% | 16,420+ | +0.320 | **2.86** | 0.571% | 1.620% | **6.37pp** |
| 2% | 16,420 | +0.449 | **2.11** | 1.170% | 3.861% | **15.18pp** |
| 3% | 7,862 | +0.522 | **1.84** | 2.064% | 7.292% | **28.67pp** |

Against a generous ceiling of 2.0pp on any real Delta - the largest honest
non-overlapping estimate anywhere on this line is +1.60pp, and it was not distinguishable
from zero - **all three levels fail, by 3x to 14x.**

The premise of the whole exercise was that 23 symbols would buy sqrt(23) = 4.80x on the
standard error. Measured, they buy **1.36x to 1.69x**.

## 3. Why no larger universe fixes it

`N_eff = N / (1 + (N-1) * rho)` tends to `1 / rho` as N grows. The cap is therefore set by
co-movement alone, and is reached almost immediately:

| X | rho | N_eff at 23 symbols | **N_eff with infinitely many** | MDE at that cap | N_eff needed for 2.0pp |
|---:|---:|---:|---:|---:|---:|
| 1% | 0.320 | 2.86 | **3.13** | 6.09pp | **29.0** |
| 2% | 0.449 | 2.11 | **2.23** | 14.79pp | **121.7** |
| 3% | 0.522 | 1.84 | **1.92** | 28.11pp | **378.6** |

At X=1% the requirement is 29.0 independent units and the ceiling, with every US-listed
ETF that exists, is 3.13. **Adding symbols cannot pass this gate.** What binds is not the
symbol count but the co-movement: every ETF added to a US universe is mostly a repeat of
the ones already in it.

Note the direction of the correlation: rho RISES with the barrier level, 0.320 -> 0.449
-> 0.522. Larger moves are more market-wide, so widening the barrier makes the
cross-section less useful, not more, while narrowing it runs into the costs already
measured in `docs/swing_verdict.md`. There is no level at which the two curves cross.

## 4. The rule that was going to be run, and the defect in it

Preregistration V4 proposed a long/flat state machine: stay IN after a +X resolution, go
OUT after a -X resolution, re-enter when price trades X above the exit price.

An adversarial review of the design - five independent lenses, each finding checked by two
skeptics, run before any cross-sectional number was computed - found that rule
**arithmetically incapable** of testing H1, independently on two lenses, and confirmed it
both analytically and by simulation.

The re-entry trigger sits X *above* the exit price. Every completed OUT episode therefore
spans an interval over which the asset returns exactly +X and the rule returns 0:

```
ln(W_rule / W_hold) = - SUM over completed OUT episodes of ln(P_refill / P_exit)
                      - SUM over take-profit hops
                      - terminal stub
                      - fees
```

with every term of the first sum at least ln(1+X) > 0, **independent of the path and
independent of whether H1 is true or false.** The rule is out of the market only over
stretches whose end-to-end return is exactly +X. It sits out the crash and the entire
recovery back to X above where it sold. The claim in V4 section 1 - "out of the market
disproportionately during bad stretches" - is false for the rule in V4 section 3, not
merely optimistic.

Measured on the real bars, the minimum of `P_refill / P_exit` across roughly 2,000
completed OUT episodes is exactly 1+X to six decimal places. The identity is not a worry;
it is arithmetic.

This is a defect of the same family as the ones this project has already logged: a
look-ahead leak that survived 49 tests, a fee ceiling documented as enforced that nothing
consumed, a daily-loss halt with no expiry that turned an experiment into a measurement of
its own bug. It was caught this time before anything was run, which is the only reason it
costs nothing.

## 5. Search budget

**21 of 24 configurations remain spent; V4 consumed none.** A.5(a) rejections cost no
configurations - `docs/power_gate_result.md` is the precedent and is filed as a result in
its own right.

Disclosure, because it bears on what may be revived: during the design review one agent
implemented V4's state machine and ran it on the training segment at all three X to verify
the identity above. It found the cross-sectional mean d_s negative at every X
(-3.19%, -3.64%, -3.37%/yr) and 21 of 21 symbols ending training inside an open,
underwater OUT episode worth +5.4pp of the mean - meaning a "pass" would have measured
where the calendar was cut, not H1. Those numbers were produced to demonstrate the design
was invalid, not to select anything, and the design is rejected on the gate rather than on
them. **V4 specifically may not be revived**, since its training answer has been seen.

## 6. What this establishes, and what it does not

Establishes:

- Short-horizon state dependence in barrier outcomes cannot be resolved on liquid US ETFs
  at 5-minute resolution with 8 years of history, at any barrier level from 1% to 3%, with
  any number of symbols. The binding constraint is co-movement, and it caps the effective
  sample near 2-3 regardless of universe size.
- The cross-sectional remedy proposed after `swing_verdict.md` does not work, and this was
  determinable without spending a configuration.

Does **not** establish:

- That H1 is false. The gate says the sample cannot answer, which is a different
  statement, and one this project has previously been careful to keep separate.
- Anything about markets that genuinely do not co-move with US equities. The cap is
  `1/rho`, so the only lever that raises it is a lower rho - not a longer list.

## 7. Reproduce

```
python tools/pull_universe.py              # 23 symbols, frozen order
python tools/pull_universe_dividends.py    # distributions and splits
python tools/audit_universe.py             # integrity gate: splits, gaps, alignment
python tools/h1_power_gate.py              # the gate that closed this line
```

Outputs: `data/universe_manifest.json`, `data/universe_dividends_manifest.json`,
`data/universe_corporate_actions.json`, `reports/h1_power_gate.json`.
