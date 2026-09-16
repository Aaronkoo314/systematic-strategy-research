# Backtest Report SOP

**Frozen 2026-09-16, before any backtest exists.** This is a reporting standard, not a
strategy change. It is written now, deliberately, so the report format cannot be chosen
after seeing which presentation makes a result look best.

**Nothing in this document is a result. No backtest has been run.**

---

## 0. The two rules that override everything else

**R1 — The denominator is always the full trading portfolio.** Every return, every
drawdown, every ratio is computed on **NAV = cash + market value**, where cash includes
whatever is idle because of whole-share rounding. At QQQ 706 one share is 7.6 % of a
USD 10,000 portfolio, so 1-4 % typically sits idle; computing returns on *deployed
capital only* would inflate them by roughly that amount, every period, invisibly.

A report may show deployed-capital return as a **secondary** line, clearly labelled,
never as the headline.

**R2 — Every chart states the cost basis in its own title.** "net of all modelled costs"
or "gross". A chart whose basis has to be looked up elsewhere will eventually be read
with the wrong one.

---

## 1. Required figures

### F1 — Equity curve
TP NAV over time, with the benchmark overlaid on the same axis and the same cost model.
Log scale. Annotated with the preregistered thresholds as horizontal reference lines:
review at −5 %, intervention at −8 %, **abandon at −20 %** from the running high-water
mark. If the curve crosses −20 % anywhere in the test period, that must be stated in the
figure caption, not left for the reader to spot.

### F2 — Price chart with entry and exit markers ← *operator request, 2026-09-16*
QQQ price with every fill marked:

| Marker | Meaning |
|---|---|
| ▲ green | buy fill |
| ▼ red | sell fill |
| hollow marker | **overnight fill** — the position crossed a session boundary |
| shaded span | period holding a position |

Overnight fills are drawn differently because they are a different animal: they carry
17-hour-old information and gap risk, and now that overnight holding is allowed
(operator decision, 2026-09-16) they need to be visually separable from ordinary
five-minute fills.

Because 8 years of 5-minute bars cannot be read on one page, F2 is produced at three
zoom levels, all from the same trade log:
- **full period** — markers only, no bars, to show when activity clusters
- **per year** — daily bars with markers
- **the 10 largest winners and 10 largest losers** — 5-minute bars, one panel each,
  a few sessions around the trade

### F3 — Return attribution by year ← *operator request, 2026-09-16*
A table and a bar chart, one row per calendar year:

| Year | Net return | Benchmark | Difference | Max drawdown | Trades | Fees paid | Fees as % of NAV | Days in market |
|---|---|---|---|---|---|---|---|---|

Plus the sentence that matters: **what share of the total net return came from the
single best year**, and what the total becomes with that year removed. A strategy whose
entire result is one good year is a different proposition from one that earns steadily,
and the equity curve alone does not distinguish them.

### F4 — Concentration of returns
Because a handful of trades can carry an entire backtest:
- cumulative contribution curve — trades sorted by P&L, cumulative share of total
- **net result excluding the best 1 %, 5 % and 10 % of trades**
- **net result excluding the best 20 sessions** — the red-team review showed that
  removing the worst 20 sessions of QQQ (1 % of the sample) moves CAGR from 5.57 % to
  16.60 %; the same leverage applies in reverse to a strategy's own results
- monthly P&L heatmap, year × month

### F5 — Drawdown
Underwater curve with the three thresholds marked, plus a table of the five deepest
drawdowns: start, trough, recovery, depth, duration in sessions.

### F6 — Cost breakdown
Stacked bar by year, itemised — platform fee including GST, settlement, SEC, FINRA TAF,
CAT, modelled slippage, modelled spread, dividend withholding. Plus **fees as a share of
gross P&L**: if fees consumed more than half the gross, the headline must say so.

The operator's ceiling is **10 %/yr of NAV**. A horizontal line marks it, and any year
that breaches it is flagged in the caption.

### F7 — Exposure
Share of time holding a position, split into intraday and overnight. An honest strategy
comparison needs to know whether an advantage came from skill or simply from being
exposed more of the time.

---

## 2. Required tables

| File | Content |
|---|---|
| `reports/trades.csv` | one row per round trip: entry/exit timestamps and indices, fill prices, shares, gross P&L, each fee component, net P&L, whether it crossed a session, holding time in bars and in calendar time |
| `reports/equity.csv` | one row per bar: NAV, cash, position, market value, drawdown from high-water mark |
| `reports/annual.csv` | F3's table |
| `reports/costs.csv` | F6's itemisation |
| `logs/experiment_log.jsonl` | one line per run — parameters, period, seed, data checksums, metrics. **Failed and abandoned runs are recorded, never deleted.** |

---

## 3. Metric definitions, fixed here so they cannot drift

| Metric | Definition |
|---|---|
| Return | geometric, on full TP NAV (R1) |
| Annualisation | geometric; 252 sessions/yr, stated wherever used |
| Sharpe | monthly excess returns over the **after-tax** cash yield, × √12. **The number of parameter configurations searched is printed next to every Sharpe ratio**, because the best of N is inflated by selection |
| Sortino | same, downside deviation below zero excess |
| Max drawdown | peak-to-trough on daily TP NAV, high-water mark **never reset** by restart, config change or capital added |
| Turnover | orders per year, and fees as % of NAV |
| Exposure | share of bars holding a position |
| Win rate | **reported only when the trade count supports it**, always beside average win/loss. Never used as a headline |

---

## 4. What every report must state in its body, not a footnote

These are the standing limitations of this project. They do not become less true because
a result looks good.

1. **8 years of intraday data, 2018-09-10 onward.** 2008, 2011 and 2015-16 do not exist
   at any intraday resolution. Roughly three to four independent stress events.
2. **Prior search contamination.** QQQ intraday factor searches were run on this same
   dataset before this project began, and the number of attempts is unrecorded. **No QQQ
   intraday result may be described as untouched out-of-sample evidence.**
3. **Execution friction is optimistic unless explicitly charged.** `open[i+1]` is the
   price at the instant `close[i]` prints — 20.05 % of pairs are exactly equal, 62.93 %
   within one cent. "Fill on the next bar" is a bookkeeping delay, not a time delay.
4. **Effective sample size, not bar count.** 156,324 bars is a large number and a small
   sample; bars are not independent observations.
5. **Whether the result would have survived costs that are not yet modelled** —
   account-level fixed fees, and whether the platform fee is charged per submitted or
   per filled order. Both are unverified and both make results look better than reality.
6. **Overnight regime.** Since 2026-09-16 positions may be held across the close. Over
   2018-2026, 66.3 % of QQQ's total drift occurred overnight and 33.7 % intraday, so an
   overnight-capable strategy is exposed to a different and larger return source than an
   intraday-only one — and to gap risk that a five-minute stop cannot contain.

---

## 5. What a report may never do

- Quote a return computed on deployed capital as the headline (R1)
- Show a chart whose cost basis is not in its own title (R2)
- Report a Sharpe ratio without the number of configurations searched
- Present a result on the final test period after the strategy was modified in response
  to that period — once that happens it stops being out-of-sample and must be relabelled
- Omit a losing run from the experiment log
- Describe a paper-trading figure as performance. Paper cannot query fees, charges a
  different commission structure, settles T+0, and is funded at 100× the real portfolio
