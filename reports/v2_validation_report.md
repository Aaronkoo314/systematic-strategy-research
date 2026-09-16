# Validation Report — Candidate V2, Buy-the-Dip on 20 Years of Daily QQQ

**Date 2026-09-16.** Preregistration: `docs/preregistration_v2.md`, frozen before any run.
Reproduce: `python tools/run_experiment_v2.py`, `python tools/static_sweep_daily.py`.

---

## 1. Verdict: NO-GO. A1 and A2 both tripped.

| Validation 2015-01 → 2020-12 (contains 2020) | Return | Max DD | Ret/\|DD\| | Avg w |
|---|---|---|---|---|
| **Candidate** (k=2.0, L=1260) | +22.61 % | **−18.49 %** | **1.22** | 8.9 % |
| **Static 50 % — primary benchmark** | +77.38 % | **−14.05 %** | 5.51 | 48.6 % |
| Static 9 % — candidate's own average weight | +9.90 % | −2.73 % | **3.62** | 8.2 % |
| Buy & hold, uncapped | +213.60 % | −27.96 % | 7.64 | 98.3 % — abandoned |

- **A1 tripped**: drawdown −18.49 % is *worse* than static 50 %'s −14.05 %, while holding
  a sixth of the exposure. This was predicted in the preregistration as failure regime 3:
  a rule that adds exposure into declines deepens its own drawdown.
- **A2 tripped**: 1.22 against 3.62 for a static blend at the same average weight. The
  dip-buying subtracted value.

Final test 2021-2026 (contains 2022), run once and not out-of-sample evidence since
validation had already rejected it: candidate +8.14 % against static 50 %'s +52.64 %.

---

## 2. Why the candidate held only 9 % when its base is 50 %

The rule's only move is to *increase* exposure. The risk framework's response to a
drawdown is to *block increases*. Once the portfolio fell 8 % below its high-water mark
the drawdown halt engaged, and the candidate could never reach its own base weight again.

**The strategy and the risk framework are in direct opposition by construction.** The
preregistration anticipated this. It is not a bug in either one; it is what happens when
a rule that buys weakness is governed by limits that forbid buying during weakness.

---

## 3. The finding that matters more than the candidate

Adding 2008 to the sample changes the allocation answer, and this is the real return on
the operator's decision to move to daily data.

**Static QQQ weight, full 20 years, 2006-09 to 2026-09 — contains 2008:**

| Weight | CAGR | Max DD | 10,000 becomes | 20 % abandon point |
|---|---|---|---|---|
| 30 % | 4.46 % | −16.98 % | 23,914 | no |
| **35 %** | **5.26 %** | **−19.79 %** | **27,847** | **no — the highest that survives** |
| 37.5 % | 5.66 % | −20.90 % | 30,059 | **breached** |
| 50 % | 7.68 % | −27.73 % | 43,921 | **breached** |
| 100 % | 15.80 % | −53.32 % | 187,819 | **breached** |

**The same sweep excluding 2008 (2010 onward, 16.7 years):**

| Weight | CAGR | Max DD | 20 % abandon point |
|---|---|---|---|
| **50 %** | **8.73 %** | **−17.46 %** | **no — the highest that survives** |
| 60 % | 10.61 % | −21.07 % | breached |

**One episode moves the answer from 50 % to 35 %, and the return from 8.73 %/yr to
5.26 %/yr.** Nothing else about the method changed.

---

## 4. So the decision is not about strategy

It reduces to a single question the data cannot answer:

> **Do you expect another 2008?**

| | Weight | CAGR | Worst drawdown |
|---|---|---|---|
| Yes, size for it | **35 %** | **5.26 %/yr** | −19.79 % |
| No, the last 16 years are the better guide | **50 %** | **8.73 %/yr** | −17.46 % |

That is a judgement about the world, not a statistic. Both numbers come from the same
validated engine, the same costs, the same withholding and the same full-NAV denominator.

Two things worth holding alongside it. The Nasdaq's 2000 decline of roughly 80 % is in
neither sample, so even the 20-year answer is optimistic against the worst this index
has actually done. And a 20 % abandon point is a rule about *stopping*, not a promise
that losses stop there — a gap can exceed it before anything can be sold.

---

## 5. Stress variants

| | Return | Max DD | Ret/\|DD\| |
|---|---|---|---|
| S0 baseline | +22.61 % | −18.49 % | 1.22 |
| S1 costs × 2.0 | +22.81 % | −18.50 % | 1.23 |
| S2 slippage 10 bp | +22.64 % | −18.52 % | 1.22 |
| S5 withholding 0 % | +22.93 % | −18.49 % | 1.24 |

Costs are irrelevant at this turnover — 3.8 fills a year, 0.04 %/yr in fees. The
rejection has nothing to do with costs.

**S6 was degenerate and produced no information.** It was meant to re-run training from
2010 to measure how much of the result came from 2008 alone. But the selected
configuration has L = 1260 sessions of warmup and the shortened window is about 1,258
sessions, so the run never emerged from warmup and placed zero orders. **The 0.00 %
printed for S6 is an artefact of that, not a finding**, and the question it was meant to
answer — how much of the result is one episode — remains unanswered for V2.

---

## 6. Budget

| | |
|---|---|
| V1 | 9 configurations |
| V2 | 6 configurations |
| **Used** | **15 of the 24** frozen in `selection_criteria.md` §6 |
| Remaining | 9 |

Both candidates rejected. Two hypotheses — momentum-style volatility targeting and
mean-reversion dip buying — have now been tested on this instrument and both lost to
simply holding a fixed fraction of it.
