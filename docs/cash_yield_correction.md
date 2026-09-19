# Idle cash was booked at 0%. The fallback is worth more than the record said.

Status: **RECORD CORRECTED.** Changes the bar every research direction is judged against.

## 1. The error

Every model in this project pays the un-invested part of the sleeve nothing: the
static-weight fallback, V1, V2, every long/flat rule, every barrier chain. The -20%
abandon point forces that un-invested part to 50-75% of the sleeve. A zero-duration
Treasury ETF earned 1.1-1.9%/yr over the sample and has paid 4-4.5%/yr since late 2023.
On a 75% cash sleeve that is 1-3%/yr of the WHOLE sleeve - larger than any edge this
project has measured or could plausibly detect.

The omission was not a modelling choice anyone made; it was a default nobody questioned,
in the same way the drawdown halt was a default nobody questioned
(`docs/halt_contamination.md`).

## 2. The measurement - `tools/cash_yield_correction.py`

Pure daily-return arithmetic, no engine, no fees (an annual two-asset rebalance is 2-4
orders a year, 0.02-0.04%/yr). QQQ leg: raw price return plus net dividend on ex-dates.
Cash leg: a Treasury ETF's raw price return plus its ACTUAL distribution on each ex-date,
net of 30% withholding, pulled via `tools/pull_cash_dividends.py`. Annual calendar
rebalance to target weights.

A first version decomposed the QFQ series daily and clipped the noise at zero; it gave
BIL 5.98%/yr over 2012-2026, four times the truth, because QFQ is affine and the daily
adjusted-minus-raw difference is noise on every day. That version was discarded before
any number from it was used. Same artefact family as the QQQ and XLF ratio-step false
alarms - the third time this project has hit it.

BIL reverse-split 1-for-2 on 2017-11-30 (45.74 -> 91.48); handled as a price multiplier
on the pre-split return series, with dividend yield computed on contemporaneous prices so
per-share cash and price stay in matching units.

### 20 years, 2006-09 .. 2026-09, contains 2008

| QQQ weight | cash leg | CAGR | max DD | uplift vs cash@0 |
|---:|---|---:|---:|---:|
| 25% | cash @ 0% | 4.61% | -15.2% | - |
| 25% | **SHY net 30%** | **5.62%** | **-13.0%** | **+1.01%** |
| 25% | SHY untaxed | 6.03% | -12.8% | +1.42% |
| 35% | cash @ 0% | 6.36% | -20.9% | - |
| 35% | SHY net 30% | 7.24% | -17.0% | +0.87% |
| 50% | cash @ 0% | 8.88% | -29.1% | - |
| 50% | SHY net 30% | 9.55% | -26.2% | +0.67% |

The cash leg **lowers** the maximum drawdown as well as raising the return, because short
Treasuries rallied in 2008 and 2020 while QQQ fell. That is not a timing effect; it is
what the un-invested 75% was doing all along while the models booked it at zero.

Note the 35% row: with the cash leg at SHY it draws down -17.0%, **inside** the abandon
point, where the engine's cash-at-0 version drew -20.9% to -23.4% (`static_weight_correction.md`).
The difference between "25% is the largest weight that holds" and "35% holds" is partly
this correction. It is stated, not adopted: SHY carries ~1.9 years of duration and a
-6.1% own drawdown; BIL (zero duration) has no 2008 history to test with.

### 14.7 years, 2012-01 .. 2026-09

| QQQ weight | cash leg | CAGR | max DD | uplift |
|---:|---|---:|---:|---:|
| 25% | cash @ 0% | 5.30% | -9.0% | - |
| 25% | BIL net 30% | 6.11% | -8.6% | +0.82% |
| 25% | BIL untaxed | 6.47% | -8.5% | +1.17% |
| 50% | cash @ 0% | 10.34% | -17.8% | - |
| 50% | BIL net 30% | 10.90% | -17.6% | +0.55% |

Smaller uplift because 2012-2021 was mostly a zero-rate decade. That decade is over.

### The proxies themselves

| leg | CAGR | max DD | since 2023-09 |
|---|---:|---:|---:|
| SHY net 30% | 1.34% | -6.1% | 2.75%/yr |
| SHY untaxed | 1.89% | -5.7% | 3.93%/yr |
| BIL net 30% | 1.09% | -0.3% | 3.09%/yr |
| BIL untaxed | 1.56% | -0.3% | 4.50%/yr |

### Forward, at today's ~4.3% bill yield - arithmetic, not a backtest

| QQQ / bills | uplift net of 30% withholding | if section 871(k) exempts |
|---|---:|---:|
| 25 / 75 | **+2.26%/yr** | +3.23%/yr |
| 35 / 65 | +1.96%/yr | +2.79%/yr |
| 50 / 50 | +1.50%/yr | +2.15%/yr |

## 3. The corrected fallback

What the operator can implement tomorrow with 2-4 orders a year, no research, no
signal, no model:

**25% QQQ + 75% BIL (live) / SHY (20-year backtest proxy), annual rebalance.**
In-sample 5.6%/yr with -13% maximum drawdown including 2008; forward roughly
4.6% + 2.3% = **~6.9%/yr at current bill yields**, ~7.8% if 871(k) applies.

This replaces the "3.66%/yr" figure in `static_weight_correction.md` as the bar. Two
things were wrong with 3.66%: it paid the cash leg nothing, and it was produced by the
engine's rebalance-on-every-share-change churn (0.6-0.9%/yr in fees) rather than an
annual rebalance. Both corrections are now in.

## 4. Two things this changes about the research programme

**Every cash-heavy candidate was under-priced by roughly its cash fraction times the
uplift column.** V1 and V2 spent 25-70% of their time in cash; their measured returns
understate the un-halted, cash-paid truth by 0.3-1.0%/yr. They remain rejected on grounds
this does not touch (`halt_contamination.md`), but the sentence "timing lost to holding"
was never a clean measurement of timing.

**Every research direction proposed from here must clear ~6.9%/yr forward at -13%
drawdown, not 3.66% at -17.6%.** That is a materially higher bar, and it is the honest one.

## 5. Open item, worth ~1%/yr on the sleeve

Whether **section 871(k)** exempts a Singapore resident from the 30% withholding on a
Treasury ETF's qualified interest income. It has been an open Stage A item since
`feasibility.md`. It is worth 0.75 x 4.3% x 0.30 = ~1.0%/yr on a 75% bill sleeve - more
than every modelled trading cost combined. It is resolved by reading one real BIL or SGOV
distribution line on a brokerage statement, not by research. The operator should do that
before anything else.

## 6. Reproduce

```
python tools/pull_cash_dividends.py       # SHY, BIL distributions + BIL split
python tools/cash_yield_correction.py     # the tables above -> reports/cash_yield_correction.json
```
