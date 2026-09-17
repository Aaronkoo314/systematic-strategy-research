# Swing-trading hypothesis: measurement and verdict

Status: **REJECTED.** Recorded here because a rejected hypothesis with its evidence is
worth more than an unrecorded one, and because the reasoning generalises beyond QQQ.

Window: 2018-09-10 .. 2026-09-11, QQQ 5-minute bars, 2,012 sessions, 156,324 bars.
Costs: USD 2.4636 per round trip on a 10,000 portfolio (0.0246%), from `src/costs/fees.py`.

## 1. The hypothesis as stated

Full position per trade, symmetric take-profit and stop-loss barriers on 5-minute bars.
Backtest to find the swings that were profitable, extract their common features, and use
those features to train an entry/exit rule. Barrier percentages not fixed - report any
setting with a better win rate.

Two sub-claims had to hold for this to work:

  **C1.** Winning swings form a distinguishable subset - they share features a rule can
  learn, rather than being an arbitrary 50-something percent of a coin flip.

  **C2.** A take-profit exit carries continuation information, so re-entering after one
  beats re-entering at random. (Raised by the operator: "if a big green candle takes me
  out at 3%, does it re-enter immediately?")

Both were measured. Both failed.

## 2. C2 failed: the re-entry lift is noise

An earlier measurement using **overlapping** samples - an entry every 30 minutes, each
trade's horizon covering dozens of others - showed a +5.1pp lift after a take-profit.
That figure was reported to the operator and **it does not survive proper measurement.**
Overlapping windows inflate the apparent sample by roughly an order of magnitude.

`tools/reentry_chain.py` re-measures it on non-overlapping chains: enter, hold to a
barrier, re-enter on the next bar, walk the whole sample. Every trade is disjoint, so the
trade count IS the independent sample size.

| level | base win | after a win | lift | SE | z | verdict |
|------:|---------:|------------:|-----:|---:|--:|:--------|
| 0.50% | 50.9% | 51.5% | +0.55% | 0.87% | 0.63 | noise |
| 0.75% | 51.3% | 52.7% | +1.39% | 1.21% | 1.14 | noise |
| 1.00% | 52.5% | 53.5% | +1.02% | 1.55% | 0.66 | noise |
| 1.50% | 53.5% | 53.7% | +0.24% | 2.18% | 0.11 | noise |
| 2.00% | 53.9% | 53.5% | -0.43% | 2.79% | -0.16 | noise |
| 3.00% | 52.0% | 53.6% | +1.60% | 4.11% | 0.39 | noise |

Every lift is smaller than its own standard error. The signs are not consistent and the
magnitudes are not monotone in the level - the signature of sampling noise, not an
effect. Resolving the lifts as observed would need 32 to 3,412 years of QQQ.

## 3. C1 failed, and for a structural reason

The chain is **in the market 100.0% of the time** - it re-enters on the bar after every
exit. A rule that is always long is buy-and-hold. The barriers cannot add return to it;
they can only subtract, through fees and through cutting moves short.

| level | net/yr | vs holding | max DD | fees/yr |
|------:|-------:|-----------:|-------:|--------:|
| 0.50% | -18.33% | -37.05% | -81.7% | 30.11% |
| 0.75% |  -4.41% | -23.13% | -50.0% | 15.42% |
| 1.00% |  +8.32% | -10.40% | -40.7% |  9.28% |
| 1.50% | +14.49% |  -4.23% | -36.6% |  4.65% |
| 2.00% | +15.27% |  -3.45% | -38.8% |  2.82% |
| 3.00% | +17.41% |  -1.31% | -34.4% |  1.33% |
| **buy and hold** | **+18.72%** | - | **-37.6%** | ~0% |

Six levels, six losses to holding, and the shortfall tracks the fee column almost exactly.
The best chain (3.00%, +17.41%/yr) is not a strategy result - it is QQQ's drift minus
1.31%/yr of fees.

**The stop-loss made drawdown worse, not better.** At 0.50% the chain drew down -81.7%
against holding's -37.6%. A stop sells at a low and re-arms the same *percentage* stop
against the new, lower price: a downward ratchet in which each successive stop cuts a
smaller absolute amount but compounds against a shrinking base. A stop-loss without a
re-entry signal is not risk control; it is a mechanism for converting volatility into
realised losses.

This is why C1 cannot be rescued by better feature engineering. The winning swings are
not a special subset to be characterised - at 52-54% they are close to what a drifting
asset hands to any entry whatsoever. There is no separable population to extract features
from.

## 4. Why the arithmetic never closes

Tightening the barrier is the natural response to a power shortfall: trades resolve
faster, so the sample holds more independent observations. It does not work, and the
reason is dimensional.

- Independent trades scale as **1/level^1.7** (measured; a random walk's hitting time
  scales as the square of the distance, and QQQ is close to that).
- The detectable effect scales roughly as **level** - a smaller target admits a smaller
  edge.
- Required sample scales as **1/effect²**, i.e. **1/level²**.

Required sample grows faster than available sample as the level shrinks. There is no
crossing point going tighter, only going wider - and going wider runs out of trades.
`tools/find_testable_level.py` found three levels that appeared to pass a power gate, but
only by assuming the 3%-level lift held at every level. Section 2 shows it does not.

Independently: 66.3% of QQQ's drift over this window is **overnight** and 33.7%
intraday (`docs/intraday_data.md`). An intraday rule competes for a third of the return
while paying all of the fees.

## 5. What this does and does not establish

Establishes, on this sample:

- Symmetric barriers on 5-minute QQQ bars with immediate re-entry lose to holding at
  every level from 0.50% to 3.00%, by approximately the fee bill.
- A take-profit exit carries no measurable continuation information.
- A percentage stop-loss with automatic re-entry increases maximum drawdown.

Does **not** establish:

- That no intraday QQQ strategy can work. It establishes that *this* family cannot, and
  that this sample cannot resolve effects of the size that survive these costs.
- Anything about asymmetric barriers, conditional entry, or shorting - untested.

## 6. Sample status after this work

The measurements in sections 2-4 were run on the **full 8-year sample**, including the
segments reserved as validation and test. They are unconditional and mechanical - no
parameter was fitted - but the *choice of what to pursue next* has now been informed by
the whole sample. Any rule selected on the basis of these tables cannot be validated on
this data. A genuine out-of-sample test of anything downstream requires either new data
or a different instrument.

Search budget: 21 of 24 configurations consumed before this work. This section spent no
further configurations, and by section 3 there is nothing here worth spending them on.

## 7. Abandon conditions triggered

From `docs/selection_criteria.md`:

- **A2** - loses to a passive benchmark over the same window. Triggered at all six levels.
- **A9** - the ex-ante power gate rejects the effect the strategy depends on. Triggered:
  the required sample exceeds the available sample by 4x to 426x.

Per the frozen rules, the hypothesis is abandoned rather than re-parameterised.

## 8. Reproduce

```
python tools/sweep_barriers.py        # unconditional base rates, overlapping
python tools/analyse_stops.py         # MAE of winners, whipsaw after a stop
python tools/analyse_reentry.py       # conditional lift, overlapping (superseded)
python tools/find_testable_level.py   # power vs economics, assumes a constant lift
python tools/reentry_chain.py         # non-overlapping chains - the governing result
```

Outputs: `reports/barrier_sweep.{csv,json}`, `reports/stop_analysis.json`,
`reports/reentry_tight.json`, `reports/testable_level.json`, `reports/reentry_chain.json`.
