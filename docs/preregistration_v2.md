# Preregistration — Candidate V2

**Frozen 2026-09-16, before any backtest of this candidate was run.**
Second candidate. Counts against the project search budget: V1 used 9 configurations,
this uses 6, leaving 9 of the 24 in `selection_criteria.md` §6.

---

## 0. What changed since V1, and why this one can be measured

V1 failed the power gate before it ran, and then failed A2 on its own merits. Both
failures had the same root: it was measured against buy-and-hold, and a rule that
deviates far from buy-and-hold carries a tracking error too large for 8 years to resolve.

Two things are different here.

**The sample.** Daily QQQ back to **2006-09-01** — 5,037 sessions, 19.99 years, containing
2008, 2011, 2015-16, 2018Q4, 2020 and 2022. The wall drops 42 % on sample length alone.

**The comparator.** The benchmark is a **static 50 % blend**, not buy-and-hold. That is
the right comparator for a rule the mandate confines to about 50 %, and against it a rule
that tilts by ±10-15 points has a tracking error of 2.21-3.29 %, so an edge of
**1.72-2.56 %/yr is detectable at six configurations** (`reports/power_gate_daily.json`).

**The gate passes for this design shape.** That means an edge of that size would be
visible if it existed. It does not mean one exists.

---

## 1. The hypothesis

**Buy more after the market has fallen.** Hold a base 50 % of QQQ; increase exposure in
proportion to how far price sits below its recent high, and return to base as it recovers.

### Economic rationale, stated before the rules

Expected return on equities is not constant. When prices fall relative to fundamentals,
the expected future return rises — this is the standard reading of Campbell & Shiller's
work on predictability, and it is a statement about discount rates, not about mispricing.
Alongside it sits a mechanical channel: leveraged and constrained investors are forced to
sell during declines regardless of value, and someone is paid to absorb that supply.

**What is NOT claimed.** No claim to call bottoms. No claim that declines reverse quickly.
The claim is narrower: that capital committed after a fall earns a higher expected return
than the same capital committed at the high, and that a mechanical rule can harvest part
of that without judgement.

**This directly contradicts the momentum story** that a trend rule would rest on. Both
cannot be right at the same horizon. That is worth stating: the operator chose this one,
and choosing it is a bet on mean reversion over continuation.

**Contamination disclosure.** Buying dips is among the most heavily mined ideas in the
field. Nothing here is novel, and the prior on an undiscovered edge is low.

### Failure regimes, named before measurement

1. **A persistent decline.** The rule raises exposure all the way down, reaching maximum
   size near the worst prices. **2008 is the archetype and it is in the training sample**,
   which is the single most valuable property of this test — the failure mode gets
   measured rather than argued about.
2. **Structural repricing.** The Nasdaq fell roughly 80 % from 2000 and took 15 years to
   recover. A rule that buys deeper as it falls would have been fully invested for the
   worst of it. That episode is *not* in this sample, and its absence must be stated
   wherever the result appears.
3. **Conflict with the abandon point.** The rule increases exposure precisely when the
   portfolio is drawing down. Its own drawdown may therefore be *worse* than static 50 %,
   and it may breach the 20 % abandon point that static 50 % respects. **This is the most
   likely way this candidate dies, and it is predicted here, before the run.**
4. **A long grind at the high.** If price sits near its high for years the rule is simply
   static 50 % paying a little extra turnover for nothing.

### What would falsify it

§5. In short: worse drawdown than static 50 %, or no better return-per-drawdown.

---

## 2. The rules, unambiguous

```
Instrument   US.QQQ, long only, whole shares
Data         DAILY raw (AuType.NONE) bars, data/raw/US_QQQ_daily.csv, close_raw
Overnight    inherent - daily bars are held overnight by construction

At each completed daily bar i:
    peak_i   = max(close over the trailing L sessions, inclusive of i)
    dd_i     = close_i / peak_i - 1                      # <= 0
    w_target = clip(W_BASE + K * |dd_i|, W_MIN, W_MAX)

W_BASE = 0.50   FIXED - the level the static sweep showed respects the 20% abandon point
W_MIN  = 0.50   FIXED - the rule never holds LESS than base; it only adds on weakness
W_MAX  = 0.90   FIXED - the mandate cap
BAND   = 0.05   FIXED - no order unless |w_target - w_current| > BAND

Execution    signal from bar i, fill at bar i+1 OPEN, market order
Sizing       shares = floor(w * NAV / price), NAV = cash + market value
Cash         idle cash earns 0%
Dividends    cash credit on ex-date, net of 30% withholding
Risk         RiskLimits() defaults, enforced pre-trade, never bypassed
```

**Free parameters: exactly 2.** `K` and `L`.

Worked example so the rule is unambiguous: with K = 1.5 and price 10 % below its trailing
peak, `w = 0.50 + 1.5 × 0.10 = 0.65`. At 20 % below, `w = 0.80`. At 27 % below or worse,
the 0.90 cap binds.

**W_MIN = W_BASE is deliberate.** The rule adds on weakness and never reduces below base.
A version that also trimmed at highs would be two hypotheses wearing one coat, and would
need its own preregistration.

---

## 3. Parameter grid, frozen

| Parameter | Values | Meaning |
|---|---|---|
| `K` | 1.0, 1.5, 2.0 | how hard to lean into a decline |
| `L` | 252, 1260 | trailing peak over 1 year or 5 years |

**6 configurations.** Bonferroni N = 6 for every reported statistic, printed beside every
Sharpe ratio. Project total after this candidate: 15 of 24.

---

## 4. Date splits, frozen

| Segment | Dates | Sessions | Contains |
|---|---|---|---|
| **Training** | 2006-09-01 → 2014-12-31 | ~2,100 | **2008 GFC**, 2011 |
| **Validation** | 2015-01-01 → 2020-12-31 | ~1,510 | 2015-16, 2018Q4, **2020 COVID** |
| **Final test** | 2021-01-01 → 2026-09-11 | ~1,430 | **2022 bear market** — run exactly once |

Unlike V1, **every segment contains at least one stress event.** The final test contains
2022, so for the first time in this project the test period can actually test the
drawdown claim.

---

## 5. Selection rule and acceptance criteria, frozen

**Selection on training:** the configuration maximising `total_return / |max_drawdown|`.
Ties to lower turnover. Fixed now so the choice cannot be made by eye afterwards.

**Comparators**, all reported:
1. **Static 50 % QQQ — the primary benchmark.** The rule must beat this or it has done
   nothing.
2. Buy-and-hold QQQ, uncapped — context only; it breaches the abandon point.
3. Static blend at the candidate's own *average realised* weight — isolates the timing
   from the mere fact of holding more on average. **If the candidate beats static 50 %
   only because its average weight is 60 %, this comparator will say so.**
4. Cash at 0 %.

**Abandon conditions — any one ends the candidate:**

| | |
|---|---|
| A1 | Max drawdown worse than **static 50 %** on validation |
| A2 | Fails to beat comparator 3 on `return / \|max_drawdown\|` on validation |
| A3 | Realised turnover breaches the 10 %/yr fee ceiling |
| A4 | The 20 % abandon point is triggered on training or validation |
| A5 | Result reverses under any stress variant in §6 |
| A6 | Selected parameters differ materially between training and validation when re-fitted |

**A4 is expected to be the live risk**, per §1 failure regime 3.

**Conditions to look at the final test:** all of A1-A6 clear on validation. The test is
then run once and recorded before any further change.

---

## 6. Stress variants, all reported

| | |
|---|---|
| S1 | costs × 2.0 |
| S2 | slippage 10 bp |
| S3 | execution delayed one extra session |
| S4 | `BAND` 0.02 and 0.10 |
| S5 | dividend withholding 0 % |
| S6 | **training period excluding 2008** — how much of any result is that one episode |

S6 is the one that matters most. If the entire result comes from buying the 2008 bottom,
that is one observation, not an edge.

---

## 7. Honest prior

Buying dips is heavily mined, the economic channel is real but slow-moving, and the rule's
structure fights the operator's own drawdown limit. **My prior on this passing is low.**
It is worth running because the failure mode is concrete, 2008 is in the sample to test
it, and a clean rejection costs one day and removes a whole family of ideas.
