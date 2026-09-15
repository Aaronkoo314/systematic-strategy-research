# QQQ Intraday Data — Availability and Constraints

**Date: 2026-09-15.** Evidence: `reports/intraday_availability.json`,
`data/intraday_manifest.json`. Reproduce with `python tools/probe_intraday.py` and
`python tools/pull_intraday.py`.

---

## 1. The hard boundary: intraday history starts 2018-09-10

Asking for 5-minute bars from 2006, 2015 or 2018 all return the same earliest bar.
This is a server-side cutoff, not a request artefact:

| Requested from | Earliest bar served |
|---|---|
| 2006-09-01 | **2018-09-10 09:35** |
| 2015-01-01 | **2018-09-10 09:35** |
| 2020-01-01 | 2020-01-02 09:35 |
| 2023-01-01 | 2023-01-03 09:35 |

Every intraday granularity shares the cutoff — 1-minute, 5, 15, 30 and 60 all begin
**2018-09-10**.

**Consequence: 8.0 years of intraday history against 20.03 years of daily history.**
The 2008 crisis, 2011 and 2015–16 are unavailable at any intraday resolution. What
remains: 2018Q4, the 2020 COVID crash, the 2022 bear market, and 2025. That is roughly
**three to four independent stress events** — the binding limit on any claim about
behaviour across market environments, regardless of how many bars there are.

156,324 bars is a large number and a small sample. Bars are not independent
observations; regimes are.

---

## 2. What the series contains

| | |
|---|---|
| Bars | 156,324 |
| Sessions | 2,012 |
| Span | 2018-09-10 09:35 → 2026-09-11 16:00 |
| Bars per day | **78** on 1,995 sessions; **42** on 17 half-day sessions |
| Session window | **09:35 – 16:00 ET — regular session only** |
| Pre / post market | **Not included** |
| Missing sessions | **0** of 2,012, against `data/us_trading_calendar.csv` |

78 bars = 6.5 hours ÷ 5 minutes. The 42-bar days are holiday early closes
(2018-11-23, 2018-12-24, 2019-07-03, 2019-11-29, 2019-12-24, 2020-11-27, …).

**No pre/post-market bars means gap-fade, overnight-session and pre-market-breakout
designs cannot be researched on this data at all** — not "with caveats", at all.

---

## 3. Timestamp convention — verified, and critical for look-ahead

**`time_key` is the bar's CLOSE time.** The first bar of a session is stamped 09:35 and
covers 09:30–09:35. Confirmed two ways: the market opens at 09:30 yet no 09:30 bar
exists, and each bar's `last_close` equals the previous bar's `close`.

**Binding rule for the backtest: a signal computed from the bar stamped `T` uses
information through `T`, so the earliest executable moment is after `T` — in practice
the next bar, stamped `T+5min`, and at a price no better than that bar's open.**

Executing at the close of the same bar that generated the signal is look-ahead. It is
also the single easiest way to manufacture a profitable-looking intraday backtest, so
this rule is enforced in code and tested, not left to discipline.

---

## 4. Raw prices, not adjusted

The series is pulled at **`AuType.NONE`**. Forward adjustment rescales the entire
historical price level to reverse future dividends. Intraday *returns* are unaffected,
because the factor is constant within a day — but **share counts are not**. Sizing is
`floor(cash / price)`, so adjusted prices yield historically wrong share counts, wrong
notionals and wrong per-share fees. It also breaks the rule against using adjusted
research prices as executable order prices.

A strategy that is flat overnight never receives a distribution, so there is nothing to
adjust for. **If a variant holds overnight, dividends must be handled explicitly as cash
events on ex-dates — never by swapping in an adjusted series.**

*(First pull used QFQ by mistake — 2018 prices appeared as ~172 against a real level of
~185. Re-pulled raw. The QFQ copy is superseded.)*

---

## 5. Cost arithmetic at the live price

QQQ last **706.38** (2026-09-15). At TP = 10,000: **14 whole shares = USD 9,889.32**,
idle cash USD 110.68 (1.1 %).

Per round trip: platform 1.0791 × 2, settlement 0.003 × 14 × 2, SEC 0.0000206 × 9,889,
FINRA TAF min 0.01, CAT — **USD 2.4560 = 0.0246 % of TP**.

| Turnover | Orders/yr | Annual cost | % of TP |
|---|---|---|---|
| 2 round trips / month | 48 | USD 58.94 | **0.59 %** |
| 1 round trip / week | 104 | USD 127.71 | **1.28 %** |
| 1 round trip / day | 504 | USD 618.91 | **6.19 %** |

**A daily-round-trip strategy must earn 6.19 % a year before it breaks even on fees
alone** — before slippage, before the bid-ask spread, before being wrong. This is not a
cost to be optimised later; it is the constraint that determines whether any intraday
design is viable at this account size.

The fee is fixed per order, so this improves linearly with capital and worsens linearly
with turnover. At TP = 10,000 the honest ceiling is roughly **one round trip per week**.

---

## 6. Research-integrity status — worse than for the daily work

The prior search in `D:\Quant` (≈19 runs, 2026-08-28 to 2026-09-15) included
`intraday_factors_15m_*`, `intraday_factors_30m_*`, `qqq_wf_6y_*` and
`qqq_fixed_oos_*` — **QQQ intraday factor searches on the same instrument, the same
frequency band and the same 2018-onward data**, since no earlier intraday data exists.

Previously this was collateral contamination. Here it is **direct overlap**. The
operator has chosen not to review those runs, which is their decision and is recorded.
The consequence stands regardless: **no result produced on QQQ intraday data can be
described as untouched out-of-sample evidence**, because the number of prior attempts on
this exact dataset is unknown. Any report must state this in the body.

---

## 7. Decisions required before a specification can be written

| # | Question | Why it cannot be defaulted |
|---|---|---|
| 1 | **Flat at the close, or hold overnight?** | Changes the benchmark (cash vs buy-and-hold QQQ), whether dividends matter, whether overnight gap risk is carried, and whether the 20 % abandon point is reachable in a single gap |
| 2 | **Automated execution, or manual confirmation?** | The US session is 21:30–04:00 Singapore time. Manual confirmation means being awake; automated execution means an unattended process must hold the trading password for `unlock_trade` — the exact exposure the manual model was chosen to avoid |
| 3 | **Turnover ceiling** | §5 shows 1/day costs 6.19 %/yr and 1/week costs 1.28 %/yr. A number has to be fixed before parameters are searched, or the search will quietly select high-turnover variants |

Until these are answered, no intraday specification can be frozen — and freezing the
specification before searching parameters is the whole point.
