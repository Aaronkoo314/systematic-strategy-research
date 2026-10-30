# Systematic Trading Strategy Research & Validation

A research process for systematic US-ETF strategies, built around one question:
**would this rule still beat holding the instrument, after real costs, on data it was
never tuned on - and is the sample even long enough to tell?**

The repository is the record of two phases. The first built a conventional
backtest-and-optimise toolkit and found, by using it, that its own results could not be
trusted. The second rebuilt the process around that lesson: preregistered candidates,
an ex-ante power gate, adversarial review, and a log that keeps every run including the
losers. Every candidate was rejected. The finding that survived is that **the return in
this sample is in QQQ itself, not in trading it** - and the repository shows the work
that makes that a conclusion rather than a shrug.

```bash
pip install -r requirements.txt
python -m pytest tests/ -q        # 190 passed, 11 skipped (the skips need raw data)
```

No live-order code exists here. The only broker calls are read-only probes, and
`tests/test_probe_is_readonly.py` enforces that.

---

## Phase 1 - exploration, and what it taught (2026-08-28 .. 09-15)

The first version was a framework in the usual shape: intraday EMA/VWAP and daily
mean-reversion rules, an event-driven backtester with a broker fee and slippage model,
Optuna (TPE) parameter search with random search as a control, rolling and expanding
walk-forward, parameter-perturbation and Monte Carlo stress tests, a causal factor
library with a truncation-replay check for look-ahead, and fourteen rule-based and
machine-learning candidates evaluated on a common harness.

It worked as software, and it produced three findings that shaped everything after:

1. **A look-ahead bug in the factor library.** `prev_day_ret` was not shifted, so
   "yesterday's return" contained today's close. It was caught during candidate
   development, fixed, and pinned with a test - but every result computed before the
   fix was contaminated, and nothing in the pipeline had flagged it.
2. **After costs, nothing survived out of sample.** The ML candidates reached an
   out-of-sample AUC of about 0.5; the rule-based ones lost roughly their fee bill.
   The framework was honest about this, which is to its credit, but it had no way to
   say in advance whether the sample could have shown an edge at all.
3. **The search count was unrecorded.** Roughly nineteen optimisation and walk-forward
   runs had been made on a handful of symbols before anyone asked how many looks the
   data had already had. Those symbols can no longer yield untouched out-of-sample
   evidence, and the phase-2 mandate records that as a standing limitation.

The phase-1 engines, strategies and live loop are not carried over. Its validation
ideas are: walk-forward, the bootstrap and Optuna tuning were rewritten on the phase-2
engine (`src/validation/`), with the limitations the originals footnoted fixed rather
than restated - see below.

---

## Phase 2 - the process (2026-09-15 .. 09-19)

| Step | What happened |
|---|---|
| **Stage A** - mandate and feasibility | Broker entity, data entitlements, order types and the official fee schedule verified from the API and published sources, with dates. Costs itemised per order, never a single number. |
| **Stage B** - candidate comparison | Selection criteria frozen *before* any candidate existed. Three daily-frequency candidates, nine adversarial reviews, all three rejected. SPY found unusable as a benchmark: its adjusted series omits every dividend before 2014-06-20. |
| **Data audit** | QQQ 5-minute history has a hard server-side cutoff at 2018-09-10 (8 years); daily history goes back to 2006 (20 years, contains 2008). Adjustment series reconciled against raw prices; splits located by measurement, not by the API's say-so. |
| **Power gate** | Run *before* any backtest: given the instrument's volatility and the overlay's tracking error, how many years would it take to distinguish a claimed edge from luck? Intraday timing on QQQ: ~45 years needed for a 10 %/yr edge, 8 available. **Fails.** |
| **V1** volatility targeting | Preregistered, run anyway to exercise the process. Rejected: loses to a static blend at the same average exposure. |
| **V2** buy-the-dip, daily, 20 years | Gate passes for this design shape against a static-blend comparator. Rejected on training: drawdown breaches the 20 % abandon point. |
| **V3** QQQ plus Treasuries, annual rebalance | Passed validation, **failed the once-only final test on 2022**, the year bonds and equities fell together. |
| **Swing / barrier family** | Symmetric take-profit and stop-loss barriers with immediate re-entry are in the market 100 % of the time, so they are buy-and-hold minus fees. The re-entry "lift" reported earlier on overlapping samples vanishes on disjoint chains. Rejected. |
| **V4** cross-sectional state dependence | Rejected by review *before it ran*: its OUT state is arithmetically incapable of testing its own hypothesis, and 23 co-moving ETFs are worth about 2 independent observations, not 23. |
| **Static sweep** | What holding a fixed fraction of QQQ produced over 20 years, corrected twice (see below). The whole of what this data can support. |

---

## Things that were wrong and were caught

Recorded because a project that lists only its successes is not auditable. The first
row is phase 1; the rest are phase 2, with the commit or document that fixed each.

| | Where |
|---|---|
| **`prev_day_ret` leaked today's close** into a "yesterday" feature. Fixed, pinned with `test_prev_day_ret_is_yesterdays_return`. | phase 1 |
| **Look-ahead prevention was false.** `history_upto` returned numpy views; `.base` exposed all 156,324 bars. An oracle strategy built on the hole returned 631x a year *while passing all 49 tests*. Fixed by ownership: every array handed out must satisfy `base is None`. 23 regression tests. | `bdb60bc` |
| **A false claim of enforcement.** The fee module said the turnover ceiling was "enforced as a pre-trade risk control". Nothing consumed it. | `2bca695` |
| **The exposure cap was computed in two places** that disagreed - the gate sized net of fees, the engine gross - so it leaked by the fee fraction. | `6c502d0` |
| **The daily-loss halt had no expiry.** An entire experiment measured that artefact; voided, not deleted. | `3b1e3b8` |
| **Every candidate and benchmark ran under a drawdown halt that never resumes** inside a backtest, so after the first -8 % each became "sell on strength, never buy the dip". V3 lost 2.2 %/yr to it. Each rejection re-examined; the grounds that survive are named, the ones that do not are withdrawn. | `docs/halt_contamination.md` |
| **The static-weight benchmark was contaminated the same way.** The largest weight inside the abandon point moved from 35 % to 25 %. | `docs/static_weight_correction.md` |
| **Idle cash was booked at 0 %.** A 75 % cash sleeve in short Treasuries is worth 1-3 %/yr of the whole sleeve - larger than any edge this project measured or could detect. | `docs/cash_yield_correction.md` |
| **SPY's adjusted series omits 7.8 years of dividends.** As a benchmark it would have flattered every strategy. | `4a862a8` |
| **`request_trading_days` silently truncates to ten years.** | `2dbed45` |
| **An overlapping-sample "lift" of +5.1pp** did not survive measurement on disjoint chains. Withdrawn in writing. | `docs/swing_verdict.md` |
| Two arithmetic slips in hand-written test values, caught because expectations are computed from the published rates rather than captured from the code. | `f9c32a4`, `11b61c4` |

---

## Layout

```
src/
  data/bars.py                 session-aware bars; strategies receive OWNED copies ending at bar i
  costs/fees.py                broker fee schedule, itemised; unmodelled costs listed by name
  backtest/engine.py           event loop, next-bar-open fills, full-NAV accounting, explicit friction
  backtest/portfolio.py        fixed-mix, calendar-rebalanced portfolio (V3)
  risk/controls.py             independent pre-trade gate; cannot be bypassed by accident
  strategy/                    the candidates, each two parameters, each frozen in a preregistration
  validation/power.py          the ex-ante power gate
  validation/walk_forward.py   session-counted folds; the selector is handed only training bars
  validation/monte_carlo.py    bootstrap of trade returns ON NAV, i.i.d. or block
  validation/tuning.py         Optuna on the training window, random sampler as control, plateau check
  validation/barriers.py       triple-barrier labelling with a non-overlapping event count
  reporting/charts.py          figures F1-F6
tools/                         data pulls (read-only), gates, preregistered experiment runners, corrections
docs/                          mandate, criteria, preregistrations V1-V4, verdicts, corrections
reports/, logs/                every run including losers; experiment_log.jsonl is append-only
```

### The validation modules

Each exists to answer one question, and each states what it cannot answer.

- **Power gate** (`power.py`) - *could this sample show the edge being claimed?* Uses
  only the instrument's volatility and the overlay's exposure; Bonferroni over the
  number of configurations searched. Runs before any backtest; a FAIL is a rejection.
- **Walk-forward** (`walk_forward.py`) - *does a rule chosen on one window hold on the
  next?* The selector receives a `BarSeries` sliced to the training window - an object
  that does not contain the test bars, rather than one it is asked not to read. Folds are
  counted in sessions so the same code serves daily and 5-minute data. Buy-and-hold runs
  on every test window with the same fees. Spearman between training rank and OOS result
  asks whether the ranking meant anything.
- **Tuning** (`tuning.py`) - *which parameters, on the training window only?* Optuna TPE
  with a random sampler at the same budget as the control; a risk-adjusted score (Sharpe
  plus a fraction of Calmar, clipped, penalised for few fills and excess drawdown); a
  neighbourhood enumerator for the plateau-or-spike check. Trials count against the
  preregistered configuration budget exactly as grid points did.
- **Bootstrap** (`monte_carlo.py`) - *how much of this was the order of the trades?*
  Trade returns are measured on NAV at entry, so a half-exposed trade is not simulated
  at full exposure; block resampling keeps clustering. It cannot invent a regime the
  sample lacks - that is the power gate's job.

```bash
python tools/validate_candidate.py --synthetic   # the whole chain on a random walk; any edge it finds is noise
python tools/validate_candidate.py               # on daily QQQ, after tools/audit_data.py
```

---

## Reproducing the record

```bash
python tools/audit_data.py            # pull daily bars, verify adjustment, write manifest
python tools/pull_intraday.py         # 5-minute raw bars
python tools/pull_dividends.py        # distributions, net of withholding
python tools/run_power_gate.py        # the gate that runs before any candidate
python tools/run_experiment.py        # V1, as preregistered
python tools/run_experiment_v2.py     # V2
python tools/run_experiment_v3.py     # V3
python tools/static_sweep_daily.py    # the fixed-weight sweep
python tools/make_charts.py           # figures F1-F6
```

Pull and probe scripts need a moomoo OpenD gateway running locally. Raw market data is
git-ignored pending a storage-licence check; manifests, calendars and dividend tables
are committed.

---

## Standing limitations

1. **8 years of intraday data, 20 of daily.** 2008, 2011 and 2015-16 do not exist at
   intraday resolution.
2. **Prior search contamination.** Phase-1 searches ran on QQQ and a few other symbols
   before the count was being recorded. No result on them is untouched out-of-sample
   evidence.
3. **The risk limits and the instrument were chosen independently** and are not
   compatible: QQQ spends 32 % of the time more than 8 % below its high-water mark, and
   buy-and-hold itself breaches the 20 % abandon point.
4. **Unverified costs** - account-level fixed fees, and whether the platform fee is
   charged per submitted or per filled order. Both would make results worse.
5. Capital figures throughout are a **notional USD 10,000 sleeve**, a design parameter
   for the cost arithmetic, not a statement about any account.

---

## What the record supports

A notional sleeve confined to a 20 % drawdown can hold roughly a quarter of QQQ with
the rest in short Treasuries, rebalanced annually, and nothing tested here improves on
that after costs. Every candidate that looked like it might was rejected by a
preregistered condition, by the power gate, or by a review that found the design could
not test its own hypothesis. The useful output is the process and the corrections, not
a strategy - and the repository is organised so that claim can be checked.
