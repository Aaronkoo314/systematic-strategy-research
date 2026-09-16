# Validation Report — Candidate V1, Volatility Targeting on QQQ

**Date 2026-09-16.** Preregistration: `docs/preregistration_v1.md`, frozen before any run.
Reproduce: `python tools/run_experiment.py` then `python tools/make_charts.py`.
Every run including losers: `logs/experiment_log.jsonl`.

---

## 0. The caveat that governs everything below

**The ex-ante power gate failed before this experiment was run.** On this sample a timing
overlay at 50 % exposure needs ~45 years to distinguish a 10 %/yr edge from luck; 8 years
exist. **No number in this report is statistically distinguishable from luck.** The
operator elected to run the process end to end anyway, to validate the system. That is
what this is: an engineering validation, not evidence about the strategy.

As it happens the result is negative by a margin that does not need statistics, which
makes the caveat easier to live with than it would have been.

---

## 1. Verdict: NO-GO

**A2 tripped.** The candidate fails to beat a static blend holding the same average
exposure — the comparator the preregistration named as decisive, precisely because it
isolates what the volatility timing added.

| Validation 2023-01-01 → 2024-12-31 | Return | Max DD | Return / \|DD\| | Avg weight | Fills/yr | Fees/yr |
|---|---|---|---|---|---|---|
| **Candidate** | +46.57 % | −12.03 % | **3.87** | 71.4 % | 206.3 | 2.27 % |
| Buy & hold QQQ | +90.78 % | −14.96 % | 6.07 | 99.5 % | 0.5 | 0.01 % |
| Static 90 % | +77.67 % | −13.44 % | 5.78 | 88.6 % | 10.5 | 0.12 % |
| **Static 71 % — same average exposure** | +55.43 % | **−10.37 %** | **5.35** | 69.1 % | 72.3 | 0.79 % |

Read the last two rows together. Simply holding 71 % of the portfolio in QQQ, all the
time, produced **a higher return, a smaller drawdown, a third of the turnover and a third
of the fees**. Everything the candidate achieved came from its lower average exposure.
**The volatility timing subtracted value.**

### Every calendar year, without exception

| Year | Candidate | Benchmark | Difference |
|---|---|---|---|
| 2023 | +28.53 % | +52.41 % | **−23.88 pp** |
| 2024 | +15.03 % | +26.54 % | −11.51 pp |
| 2025 | **−3.50 %** | +20.12 % | −23.62 pp |
| 2026 (to Sep) | +4.96 % | +15.06 % | −10.10 pp |

There is no year in which the candidate wins, and no year in which the concentration of
results could rescue it.

---

## 2. Training and selection

Grid of 9 configurations of the 24 budgeted. Training 2018-09-10 → 2022-12-31.

| N | sigma | Return | Max DD | Ret/\|DD\| | Avg w | Fills/yr | Fees/yr |
|---|---|---|---|---|---|---|---|
| 78 | 0.15 | −5.08 % | −11.49 % | −0.44 | 7.7 % | 67.1 | 0.74 % |
| 78 | 0.20 | −3.46 % | −11.34 % | −0.31 | 9.4 % | 50.8 | 0.56 % |
| 78 | 0.25 | +1.53 % | −13.13 % | 0.12 | 18.1 % | 49.4 | 0.55 % |
| 390 | 0.15 | −3.17 % | −11.28 % | −0.28 | 9.7 % | 41.3 | 0.46 % |
| 390 | 0.20 | +0.62 % | −13.12 % | 0.05 | 19.4 % | 42.9 | 0.47 % |
| 390 | 0.25 | +3.53 % | −14.89 % | 0.24 | 26.7 % | 44.8 | 0.49 % |
| 780 | 0.15 | −0.81 % | −12.23 % | −0.07 | 13.3 % | 34.1 | 0.38 % |
| 780 | 0.20 | +3.90 % | −14.14 % | 0.28 | 23.7 % | 36.7 | 0.40 % |
| **780** | **0.25** | **+6.10 %** | −16.75 % | **0.36** | 31.0 % | 36.2 | 0.40 % |
| *buy & hold* | *+49.92 %* | *−36.86 %* | *1.35* | *99.0 %* | *0.2* | *0.00 %* | **ABANDONED** |

Selected N=780, sigma=0.25 by the frozen rule. **Every configuration returned between
−5 % and +6 % over 4.3 years** while the benchmark made +49.92 %.

**Why average weight is 8-31 % against an intended 58-90 %:** the mandate's 8 % drawdown
halt persists until a human reviews it, and the engine has no human. Once the portfolio
fell 8 % below its high-water mark — which 2018Q4 delivered in the first quarter of the
window — the strategy could never increase exposure again for the remaining four years.

**That is not a bug, it is the mandate applied literally**, and it is the most
operationally important finding in this report. See §5.

---

## 3. Final test — run once, and not out-of-sample evidence

Validation tripped A2, so under the preregistration the candidate was already rejected.
The test was run at the operator's instruction to complete the process. It is a run of
the machinery, not evidence for the candidate.

| Test 2025-01-01 → 2026-09-11 | Return | Max DD | Ret/\|DD\| | Avg w |
|---|---|---|---|---|
| Candidate | +1.58 % | −18.73 % | 0.08 | 37.0 % |
| Buy & hold QQQ | +39.44 % | −24.41 % | 1.62 | 97.1 % — **ABANDONED** |
| Static 37 % — same average exposure | **+12.31 %** | **−9.65 %** | **1.28** | 33.9 % |

The candidate lost to the static blend at its own average exposure again, by a wider
margin, with a drawdown twice as deep.

**The test window contains none of 2018Q4, 2020 or 2022.** It is a calm sample and cannot
test the drawdown claim at all. This is stated in the body, as the preregistration requires.

---

## 4. Stress variants — all reported

| Variant | Return | Max DD | Ret/\|DD\| | Fees/yr |
|---|---|---|---|---|
| S0 baseline | +46.57 % | −12.03 % | 3.87 | 2.27 % |
| S1 costs × 1.5 | +45.09 % | −11.70 % | 3.85 | 3.06 % |
| S2 costs × 2.0 | +42.35 % | −11.91 % | 3.55 | 3.89 % |
| S3 slippage 10/25 bp | +45.26 % | −11.68 % | 3.87 | 2.13 % |
| S6 withholding 0 % | *see experiment_summary.json* | | | |

A5 did not trip — no variant reverses the sign. The conclusion was never close enough to
the boundary for costs to decide it. Note that even at baseline the candidate pays
**2.27 %/yr in fees against the static comparator's 0.79 %**, and still loses on return.

---

## 5. The operationally important finding

**Applied literally, the mandate's risk framework freezes the strategy.**

- The 8 % drawdown halt requires human review to lift. QQQ spends **32.3 % of the time**
  more than 8 % below its high-water mark. With no review the system is halted for most
  of its life — visible above as average weight of 8-31 % in a window containing three
  stress events.
- The 1 % daily loss threshold fires on **16.8 % of sessions, about 42 times a year** at
  90 % weight. A first run of this experiment had no expiry for it at all and measured
  pure artefact; the semantics were corrected (daily halt expires at the next session,
  drawdown halt does not) and everything above is from the corrected re-run. The voided
  log is kept at `logs/experiment_log_VOID_halt_bug.jsonl`.
- **Buy & hold QQQ itself breaches the 20 % abandon point** — on training and on test.
  The benchmark is not deployable under this mandate.

None of this is a reason to loosen the limits. It is a reason to notice that the limits
and the instrument were chosen independently of each other, and are not compatible.

---

## 6. Figures

`reports/figures/` — F1 equity, F2 fills on price with overnight fills hollow, F3 annual
attribution, F4 concentration, F5 underwater, F6 itemised costs. Each for validation and
test. Every figure carries the power-gate caveat in its own footer, so none can be lifted
out and shown without it.

---

## 7. What was actually validated

The strategy failed. The system worked:

- look-ahead prevention held under adversarial attack after the ownership fix
- the identity `nav = cash + shares × price` held to 0.00e+00 across 156,324 bars
- 33 dividends credited exactly once each, net of 30 % withholding
- risk controls blocked what they were supposed to block and could not be bypassed
- the preregistration made the decision, not the equity curve — A2 was named as decisive
  before the number existed, and it is what settled the verdict
- two harness bugs were caught by the process rather than by luck: the halt that never
  expired, and the exposure cap computed in two places that disagreed

**Recommendation: do not proceed with this candidate.** Under `selection_criteria.md`
the correct next step is not another parameter, it is a different question — and the
power gate says any question asked of this 8-year intraday sample will meet the same
wall. The daily series back to 2006 is 2.5× longer and contains 2008.
