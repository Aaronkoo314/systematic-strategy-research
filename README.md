# Personal Quantitative Trading System — QQQ

**Status 2026-09-16: candidate V1 REJECTED. No strategy approved. Nothing authorised to trade.**

There is no live-order code in this repository. The only broker calls that exist are
read-only probes, enforced by `tests/test_probe_is_readonly.py`.

```bash
python -m pytest tests/ -q        # 145 passed
```

---

## What happened, in order

| | Outcome |
|---|---|
| **Stage A** — mandate and feasibility | Entity confirmed **Futu Singapore** from the API itself. Market data, quotas, order types and the official fee schedule verified with sources and dates. |
| **Stage B** — candidate comparison | Three daily-frequency candidates, nine adversarial reviews, **all three rejected**. SPY found unusable as a benchmark: its adjusted series omits every dividend before 2014-06-20. |
| **Data** | QQQ 5-minute history has a hard server-side cutoff at **2018-09-10** — 8 years, against 20 years of daily. |
| **Power gate** | **FAILED.** Detecting a 10 %/yr edge on the intraday sample needs ~45 years. 8 exist. |
| **Full process run anyway** | Volatility targeting, preregistered before any run. **A2 tripped**: it loses to simply holding the same average exposure, with a worse drawdown and 27× the fees. |
| **Static sweep** | Holding a fixed 50 % of QQQ: **8.88 %/yr**, worst drawdown −18.36 %, 61 orders in 8 years. Holding 100 %: 18.97 %/yr, −36.86 %, terminated by the operator's own 20 % abandon point. |

**The profit in this sample is in QQQ itself, not in trading it.** What the system has
demonstrated so far is that the things which looked like they could beat it cannot.

---

## Layout

```
docs/
  investment_mandate.md      confirmed / provisional / unresolved, with the decision log
  feasibility.md             verified entity, API, data, costs - sources and dates
  selection_criteria.md      Stage B criteria, frozen before any candidate existed
  candidate_comparison.md    Stage B verdict, all three rejected
  data_sources.md            six of seven external free sources eliminated on licence
  instrument_selection.md    dividend-coverage test; SPY, IVV, VOO, BIL, AGG all fail
  intraday_data.md           the 2018 cutoff, bar conventions, cost arithmetic
  power_gate_result.md       the ex-ante gate and why it failed
  preregistration_v1.md      candidate V1, frozen before any run
  report_sop.md              reporting standard, frozen before any backtest existed
src/
  data/bars.py               session-aware bars, structural look-ahead prevention
  costs/fees.py              moomoo SG fee schedule, itemised
  backtest/engine.py         event loop, full-NAV accounting, explicit friction
  risk/controls.py           independent pre-trade controls, cannot be bypassed
  strategy/vol_target.py     candidate V1
  validation/power.py        the ex-ante power gate
  reporting/charts.py        figures F1-F6
tools/                       probes, data pulls, experiment and chart runners
reports/                     experiment outputs, figures, validation_report.md
logs/                        experiment_log.jsonl - every run including losers
data/                        manifests and the trading calendar (raw data git-ignored)
```

---

## Reproducing

```bash
python tools/audit_data.py          # pull daily, verify adjustment, write manifest
python tools/pull_intraday.py       # pull 5-minute raw bars
python tools/pull_dividends.py      # distributions, net of 30% withholding
python tools/run_power_gate.py      # the gate that runs before any candidate
python tools/run_experiment.py      # the preregistered experiment
python tools/make_charts.py         # figures F1-F6
python tools/static_sweep.py        # what holding a fixed fraction produces
```

Probe and pull scripts need moomoo OpenD running and logged in on `127.0.0.1:11111`.
**OpenD requires manual re-login after a restart** — observed 2026-09-16, the process was
running while port 11111 was not listening. The system is therefore **not unattended**.

---

## Things that were wrong and were caught

Recorded because a project that lists only its successes is not auditable.

| | Commit |
|---|---|
| **Look-ahead prevention was false.** `history_upto` returned numpy views; `.base` exposed all 156,324 bars. An oracle strategy built on it returned 631× a year **while passing all 49 tests**. Fixed by ownership; 23 regression tests. | `bdb60bc` |
| **A false claim of enforcement.** The fee module said the turnover ceiling was "enforced as a pre-trade risk control". Nothing consumed it. | `2bca695` |
| **The exposure cap was computed in two places** that disagreed — the gate sized net of fees, the engine gross — so it leaked by the fee fraction. | `6c502d0` |
| **The daily-loss halt had no expiry**, so after the first 1 % down day the system could only reduce exposure. A whole experiment run measured that artefact and was voided, not deleted. | `3b1e3b8` |
| **SPY's adjusted series omits 7.8 years of dividends.** Using it as a benchmark would have understated the bar and flattered every strategy. | `4a862a8` |
| **`request_trading_days` silently truncates to ten years.** A 20-year calendar built on it is quietly wrong. | `2dbed45` |
| Two arithmetic slips in hand-written test values, caught because expectations are computed from the published rates rather than captured from the code. | `f9c32a4`, `11b61c4` |

---

## Standing limitations

1. **8 years of intraday data.** 2008, 2011 and 2015-16 do not exist at any intraday
   resolution. Roughly three independent stress events.
2. **Prior search contamination.** QQQ intraday factor searches were run on this same
   dataset before this project began, with the count unrecorded. No QQQ intraday result
   may be called untouched out-of-sample evidence.
3. **The mandate's risk limits and QQQ are not compatible.** QQQ spends 32.3 % of the
   time more than 8 % below its high-water mark, and buy-and-hold itself breaches the
   20 % abandon point. The limits and the instrument were chosen independently.
4. **Unverified costs** — account-level fixed fees, and whether the platform fee is
   charged per submitted or per filled order. Both would make results look worse.
5. **Market-data storage licence unverified.** Raw data is git-ignored pending that.
6. **No account data is in this repository.** Balances, positions and identifiers are
   excluded; `logs/redacted/` holds capability-only copies. Keep the repo private.

---

## Next

The operator chose on 2026-09-16 to move to the **daily series back to 2006** — 20.03
years, 5,037 bars, containing 2008. The first step is not a strategy: it is re-running
the power gate on that sample. If the gate fails there too, the honest answer is that
this account and this data cannot support an active strategy, and the static sweep is
the whole of what is available.
