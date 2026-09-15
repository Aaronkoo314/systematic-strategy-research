# Instrument and Benchmark Selection

**Date: 2026-09-15. Decided by data availability, before any backtest exists.**

Evidence: `reports/instrument_selection.json`, `reports/coverage_check.json`,
`logs/qfq_reconciliation.json`, `data/data_manifest.json`.
Reproduce with `python tools/select_instruments.py` and `python tools/check_coverage.py`.

---

## 1. The test every instrument had to pass

The broker's **dividend record must start within about four months of its first
available bar**. If it does not, the adjusted price series silently omits every
distribution before that date — and a total-return figure built on it is simply wrong.

This is not a theoretical concern. It eliminated the instrument we had been treating as
the primary benchmark.

Second test: the affine adjustment `P_adj = P × A + B` must reproduce the API's own
adjusted series when fitted per inter-ex-date segment. All instruments passed this to
float precision (worst relative residual 2.8e-11), so the adjustment machinery itself is
internally consistent — the problem is purely one of missing dividend records.

---

## 2. Results

| Instrument | Bars | First bar | Dividends on record from | Uncovered | Verdict |
|---|---|---|---|---|---|
| **US.QQQ** | 5,037 | 2006-09-01 | 2006-09-15 (82) | 0.038 y | **USABLE** |
| **US.IEF** | 5,037 | 2006-09-01 | 2006-09-01 (241) | 0.0 y | **USABLE** |
| **US.TLT** | 5,037 | 2006-09-01 | 2006-09-01 (241) | 0.0 y | **USABLE** |
| **US.SHY** | 5,037 | 2006-09-01 | 2006-09-01 | 0.0 y | **USABLE** |
| **US.SHV** | 4,948 | 2007-01-11 | 2007-02-01 | 0.057 y | **USABLE** |
| US.SGOV | 1,581 | 2020-05-28 | 2020-07-01 | 0.093 y | usable but too short |
| US.QQQM | 1,485 | 2020-10-13 | 2020-12-21 | 0.189 y | usable but too short |
| US.BIL | 3,692 | 2012-01-03 | 2012-12-27 | 0.98 y | **UNUSABLE** |
| US.VOO | 3,692 | 2012-01-03 | 2013-10-24 | 1.81 y | **UNUSABLE** |
| US.IVV | 3,691 | 2012-01-03 | 2014-06-24 | 2.47 y | **UNUSABLE** |
| US.AGG | 3,691 | 2012-01-03 | 2014-07-01 | 2.49 y | **UNUSABLE** |
| **US.SPY** | 5,014 | 2006-09-01 | 2014-06-20 (48) | **7.80 y** | **UNUSABLE** |
| US.SPLG | — | — | — | — | not carried by moomoo |

Note the pattern: IVV, VOO, BIL and AGG all begin at 2012-01-03. That appears to be a
data boundary on moomoo's side. Only QQQ, SPY, SHY, SHV, IEF and TLT reach back to 2006.

---

## 3. Consequence: no S&P 500 ETF is usable

Every S&P 500 vehicle fails — SPY by 7.8 years, IVV by 2.47, VOO by 1.81, and SPLG is not
carried at all. **The S&P 500 cannot serve as a benchmark on this data**, and no amount of
care in the backtest can repair it: the distributions are simply not in the series.

Using SPY anyway would understate the benchmark's return by roughly 15 % cumulative over
2006-2014 and therefore **flatter any strategy measured against it** — the precise failure
mode the review process is meant to catch.

---

## 4. Revised benchmark set

**This supersedes the benchmark table frozen in `selection_criteria.md` §3.** The change is
driven entirely by a data-availability fact discovered before any backtest was run, not by
any result. **No final test period has been examined, so nothing is invalidated by this
revision** — but it is recorded as its own commit, with this reason, as that document requires.

| | Old (frozen 2026-09-15, morning) | **New** | Why |
|---|---|---|---|
| B1 passive equity | SPY buy-and-hold | **QQQ buy-and-hold** | SPY's data is unusable. More importantly, QQQ is the correct comparator: the strategy trades QQQ, so the honest question is whether it beats *holding the same instrument*. SPY only entered the set from an earlier framing around "US large cap", before QQQ was chosen. |
| B2 balanced | 60/40 SPY + IEF | **60/40 QQQ + IEF** | IEF is clean (0.0 y uncovered, 241 distributions). Keeps the same structural comparator with a usable equity leg. |
| B3 capital parking | BIL | **SHV**, with **SHY** as a second reading | BIL is unusable (0.98 y uncovered). SHV is the closest clean cash proxy; SHY covers the full window but carries ~1.8 y duration, so it is a bond, not cash — reported alongside rather than instead. |

**Removing SPY is an improvement, not a compromise.** A QQQ timing strategy measured against
SPY would be partly measuring the Nasdaq-versus-S&P spread, which the strategy has no claim
to predict.

---

## 5. Test window

| | |
|---|---|
| Full window | **2006-09-01 → 2026-09-11**, 5,037 sessions, 20.03 years |
| If SHV is the defensive leg | starts **2007-01-11** (loses 4 months, still fully covers 2008) |
| Regimes covered | 2008 GFC, 2011, 2015–16, 2018Q4, 2020 COVID, 2022 |

**Honest limitation, to be repeated in the body of any conclusion:** roughly 13 of these
20 years had near-zero short rates. The cash leg's yield is a central variable for any
defensive strategy, so results from this sample do not transfer cleanly to the current rate
environment, in either direction.

---

## 6. Trading calendar

`request_trading_days` silently truncates to about ten years — a request from 1990 returns
sessions from 2016-09-15 with no error. Any twenty-year calendar built on it is quietly wrong.

The calendar is therefore derived from the bar series itself:
**`data/us_trading_calendar.csv`, 5,037 sessions, 2006-09-01 → 2026-09-11**, from QQQ daily bars.

---

## 7. Still unresolved

| # | Item | Status |
|---|---|---|
| D1 | Does Futu SG's market-data agreement permit storing history locally for personal backtesting? | **Unverified.** Data is currently under `data/raw/` and git-ignored. Must be settled before any published result relies on it. |
| D3 | Independent cross-check of QQQ's 82 distributions against Invesco's published history | Not done. Mitigates the risk that research and execution share one unaudited source. |
| D4 | Short-rate proxy for any period a clean cash ETF does not cover | **FRED DTB3** recommended — official, free, licence-clean. Requires the operator to obtain an API key. |
