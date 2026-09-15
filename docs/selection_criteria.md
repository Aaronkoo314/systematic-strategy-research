# Stage B — Strategy Comparison Criteria and Preregistration

**Frozen: 2026-09-15, before any candidate was evaluated and before any backtest existed.**

This document exists so that the criteria cannot be reverse-engineered from a result I liked.
It is committed before the candidate comparison. Any later change to it must be a separate commit
with a stated reason, and invalidates the untouched status of the final test period.

**No performance claim appears anywhere in this document. No backtest has been run.**

---

## 0. Method: gates and evidence, not scores

Candidates are **not** given subjective scores or weighted rankings. A 1–10 score would be my
opinion wearing a number's clothing, and a weighted total would let a strong opinion on one axis
launder a fatal flaw on another.

Instead:

- **Tier 0 — hard gates.** Binary. Any single failure rejects the candidate outright. No trade-offs,
  no compensation from other strengths.
- **Tier 1 — economic admissibility.** Each candidate must answer a fixed list of questions. An
  unanswerable question is a rejection, not a low score.
- **Tier 2 — empirical evidence.** Only candidates surviving Tier 0 and Tier 1 proceed to Stage C
  measurement, against the preregistered thresholds in §6–§8.

Ordering matters: **Tier 0 and Tier 1 are decided without any backtest**, so a candidate cannot be
rescued by an attractive equity curve.

---

## 1. Tier 0 — hard gates (binary; any FAIL rejects)

Every gate below is derived from something already verified in `feasibility.md`, not from taste.

| # | Gate | Source of the constraint |
|---|---|---|
| G1 | Long-only, unlevered, no shorting, no options, futures, leveraged or inverse ETFs | Mandate §4, operator's v1 guardrails |
| G2 | Uses only `NORMAL` (limit) and `MARKET` order types; no reliance on broker-side `STOP` / `TRAILING_STOP` | Verified: paper trading supports only these two, and the paper stage must faithfully rehearse live |
| G3 | Signal computed from a **completed** daily bar; earliest execution the **next** US session. No same-bar close execution. | Look-ahead prevention; operator is asleep at the US close (04:00 SGT) |
| G4 | Executable under **manual per-order confirmation**, and tolerant of a decision slipping by 1–2 sessions | Operator's confirmed operating model |
| G5 | ≤ 30 orders per year, ≤ 3 instruments held | Cost arithmetic at TP = 10,000. **Corrected 2026-09-15:** full-scope (platform + GST + settlement + SEC + TAF + CAT) 24 orders ≈ **0.329 %/yr**, 120 orders ≈ **1.65 %/yr**. The earlier figures (0.26 % / 1.29 %) counted the platform fee only and understated cost by ~27 %, biasing comparisons toward higher turnover. |
| G6 | Instruments are US-listed, tight-spread, and were continuously tradeable across the test window | Liquidity requirement; operator needs realisability within days |
| G7 | Required data obtainable from a source whose licence permits personal research, with history long enough for §5, **and whose dividend record covers the test window** | moomoo daily history starts 2006-09 for QQQ/IEF/TLT/SHY, 2012-01 for others; `listing_date` unusable; **dividend coverage verified per instrument in `instrument_selection.md` — SPY, IVV, VOO, BIL and AGG all fail** |
| G8 | Universe excludes every instrument held outside TP in the same account | Mandate §7b.6 — shared account, reconciliation would break |
| G9 | Universe excludes the symbols already parameter-searched in `D:\Quant` as **primary** instruments | Mandate §7c — prior search budget is unrecorded |
| G10 | No martingale, unbounded averaging down, uncapped grid, or any structure whose frequent small gains conceal unbounded tail loss | Operator's v1 guardrails |
| G11 | Does not require the system to run unattended | Verified: the system is not unattended and must never be described as such |

**G2 note — an honest consequence.** Because broker-side stops are excluded, any candidate whose
risk control depends on a guaranteed stop price is rejected. A stop implemented in our own software
is an *intention to exit*, executed at the next session's open at whatever price exists then. The
mandate's "0.25 % planned risk per trade" therefore cannot be honoured as a loss ceiling in v1, and
will not be described as one.

---

## 2. Tier 1 — economic admissibility (each question must be answered, or the candidate is rejected)

| # | Question | Rejection trigger |
|---|---|---|
| E1 | What is the economic source of return — who is on the other side, and why do they persistently accept the worse end? | "It worked in a backtest" is not an answer |
| E2 | Why might the edge survive USD 1.0791 per order plus 30 % US dividend withholding? Answer must contain arithmetic using the frozen cost model in §4. | Hand-waving, or arithmetic that does not close |
| E3 | In which specific market regimes does it fail, and how would it have behaved in them? | Cannot name concrete failure regimes |
| E4 | How heavily has this idea already been data-mined by the public literature and industry? | Undisclosed contamination |
| E5 | What single observable result would falsify the hypothesis? | No falsification test |
| E6 | Can this exact account implement it — entity, permissions, order types, settlement, manual confirmation? | Any "no" |
| E7 | Does it beat the *simplest* alternative that achieves the same stated goal? | A simpler alternative dominates it |

**E7 is deliberately hostile to this project.** If a candidate's goal is "equity exposure with lower
drawdown", the simplest alternative is holding 60/40 and rebalancing annually — two orders a year,
no model risk, no operational burden. A candidate must explain what it adds over that, *before*
any measurement.

---

## 3. Benchmarks

> **REVISED 2026-09-15 — see `instrument_selection.md`.** SPY and BIL were found to have
> incomplete dividend records on the only available data source (SPY: 7.80 years unadjusted;
> BIL: 0.98 years), which would understate both benchmarks and flatter any strategy measured
> against them. Every S&P 500 vehicle failed the same test. The revision is driven by a data
> fact discovered **before any backtest was run**; no final test period has been examined, so
> no out-of-sample status is affected. The original table is kept below, struck through, so the
> change is visible rather than silent.

| Benchmark | Definition | Purpose |
|---|---|---|
| **B1 — Passive equity** | Buy and hold **QQQ**, total return (distributions net of 30 % withholding), bought once at period start with the same cost model | The strategy trades QQQ, so the honest bar is holding the same instrument |
| **B2 — Passive balanced** | **60 % QQQ / 40 % IEF**, rebalanced **once per calendar year** on the first US session, same cost model | Fair comparator for anything claiming lower drawdown |
| **B3 — Capital parking** | Buy and hold **SHV**, same cost model; **SHY** reported as a second reading | A defensive strategy must beat *actually holding cash* after the fixed fees it pays to move in and out |

*Superseded:* ~~B1 SPY buy-and-hold · B2 60/40 SPY+IEF · B3 BIL~~ — all three equity/cash legs
unusable for total return on this data source.

All three bear the identical cost model in §4. A strategy is not credited for costs a benchmark
also pays.

**B3 is the decisive benchmark for defensive candidates**, and the one most often quietly omitted.

---

## 4. Cost model (frozen; applied identically to strategy and benchmarks)

Verified rates from `feasibility.md` §7.

| Component | Frozen value |
|---|---|
| Commission | USD 0 |
| Platform fee + 9 % GST | **USD 1.0791 per order** |
| Settlement | USD 0.003 per share, capped at 1 % of order value |
| SEC fee (sell only) | 0.0000206 × value, minimum USD 0.01 |
| FINRA TAF (sell only) | 0.000195 per share, min 0.01, max 9.79 |
| CAT | 0.000003 per share |
| **Execution price** | The **next session's official open**, plus slippage below |
| **Slippage (baseline)** | `max(USD 0.01, 2 bps of price)` per share, adverse direction |
| **US dividend withholding** | **30 %** of distributions from US-domiciled ETFs |
| Whole shares only | Yes — fractional-share support via API is unverified |
| FX | None modelled; TP is USD and the account cash is USD |

**Unresolved and therefore modelled conservatively:** whether US T-bill ETF distributions qualify
as interest-related dividends exempt from the 30 % (QII). **Baseline assumes no exemption.** A
sensitivity run at 0 % withholding on BIL will be reported separately and labelled as an
unverified tax assumption. A pre-tax figure will never be labelled after-tax.

### Mandatory stress variants (all reported, not just the favourable one)

| Variant | Setting |
|---|---|
| S1 | Costs × 1.5 |
| S2 | Costs × 2.0 |
| S3 | Execution delayed by one additional session |
| S4 | Slippage 10 bps |
| S5 | Withholding 0 % on T-bill ETF distributions only |
| S6 | Parameters perturbed ± 1 step on every axis |

---

## 5. Data periods (frozen chronological split)

Contingent on securing a source that satisfies G7; the data-source decision is recorded separately
in the data manifest with retrieval date, coverage, adjustment method and checksums.

| Segment | Dates | Permitted use |
|---|---|---|
| **Design / training** | period start → **2007-12-31** | Free exploration, parameter search, feature construction |
| **Validation** | **2008-01-01 → 2015-12-31** | Confirmation only; includes 2008 and 2011 |
| **Final test — UNTOUCHED** | **2016-01-01 → 2026-09-12** | **Examined exactly once**, after §7 is satisfied |

Walk-forward evaluation is run **within training + validation only**, never across the final test
boundary.

**Rule with teeth:** the moment the strategy is modified in response to anything seen in the final
test period, that period **stops being out-of-sample evidence** and must be relabelled in every
report thereafter. There is no version of this where I quietly re-tune and still call it clean.

If the chosen data source cannot reach back far enough to make training end at 2007-12-31, the
split shifts forward and **the strength of every conclusion is reduced accordingly and stated**.

---

## 6. Experiment budget (frozen; exceeding it is itself a failure)

| Limit | Value |
|---|---|
| Distinct parameter configurations evaluated on **training** | **≤ 24** |
| Configurations promoted to **validation** | **≤ 6** |
| Configurations evaluated on the **final test** | **exactly 1, exactly once** |
| Instrument sets tried | **≤ 2** |
| Total candidate strategies carried into Stage C | **≤ 1** |

Every run — including failures and abandoned directions — is appended to `logs/experiment_log.jsonl`
with its parameters, period, metrics and a timestamp. **Deleting or omitting a failed run is
research misconduct for the purposes of this project.**

With 24 configurations searched, the best in-sample result is inflated by selection. Reported
statistics must acknowledge this explicitly; the number of trials will be stated next to any
Sharpe ratio quoted.

---

## 7. Abandon conditions — stated FIRST, before any entry condition

**Any one of these ends the candidate.** Not a review, not a parameter tweak — the strategy is
dropped and the alternative is passive investing or cash.

| # | Abandon trigger |
|---|---|
| A1 | Does not beat **B3 (BIL)** on risk-adjusted terms, net of all costs, over the validation period. *A strategy that cannot beat cash has no reason to exist.* |
| A2 | Does not beat **B1 (SPY)** or **B2 (60/40)** on **both** return **and** maximum drawdown over the validation period — i.e. it is dominated by a passive alternative |
| A3 | Maximum drawdown over training or validation exceeds **20 %** (the operator's preregistered abandon point) |
| A4 | Realised turnover implies **> 30 orders/year**, breaching G5 |
| A5 | Any stress variant S1–S6 reverses the conclusion. *An edge that survives only at baseline costs is not an edge.* |
| A6 | Walk-forward parameter instability: the selected parameters change materially between adjacent windows without an economic reason |
| A7 | Effective sample size too small to distinguish the result from luck — monthly/annual observations are strongly autocorrelated and will not be counted as independent |
| A8 | The experiment budget in §6 is exhausted without a configuration meeting §8 |
| A9 | Advantage over B1/B2/B3 is smaller than the annual cost drag at TP = 10,000 — i.e. the edge exists only before costs |

**A9 restated plainly:** if the measured advantage is thinner than roughly 0.26 %/yr of fixed fees
plus withholding, the correct answer is NO-GO regardless of how attractive the equity curve looks.

---

## 8. Conditions to enter paper trading (Stage D)

Only after §7 produces no abandon trigger. **All** of the following, not a majority:

| # | Requirement |
|---|---|
| P1 | No abandon condition A1–A9 triggered |
| P2 | Final test examined exactly once, with the result recorded before any further change |
| P3 | Advantage over **all three** benchmarks survives every stress variant S1–S6 |
| P4 | Backtest reproducible from a clean checkout: documented command, pinned dependencies, data manifest with checksums, identical outputs |
| P5 | Strategy and sizing logic shared between backtest and live paths, with only data/execution adapters differing |
| P6 | Independent risk controls implemented **outside** signal logic and unit-tested: capital and exposure limits, duplicate-order protection, abnormal-price check, data-freshness check, session validation, reconciliation, emergency stop |
| P7 | Failure-mode tests pass with documented expected vs actual behaviour: duplicate signals, request timeout, partial fill, rejection, out-of-order callback, network interruption, process restart, stale data, insufficient buying power |
| P8 | `dry_run = true`, `live_enabled = false` verified as defaults; a missing or conflicting config provably cannot emit an order |
| P9 | Operator reviews and approves the frozen spec in writing |

---

## 9. What paper trading can and cannot establish — **verified, and narrower than expected**

Sources: moomoo OpenAPI documentation and moomoo help centre, retrieved 2026-09-15.

**Paper trading CAN validate:** the engineering path (OpenD connection, data retrieval, signal
computation, order submission, order-state polling, retry, logging, ledger persistence); whether
manual confirmation at 22:30 SGT is actually sustainable; signal-to-execution timing correctness.

**Paper trading CANNOT validate — these are permanent blind spots, not gaps to be closed:**

| # | Blind spot | Evidence |
|---|---|---|
| N1 | **Costs.** Paper accounts cannot query order fees, and paper charges a per-share commission, not Futu SG's fixed platform fee + GST. | *"Paper trading accounts do not support querying order fees"* |
| N2 | **Fill quality.** Matching is a simplified price condition with no real queue position, so fill rates are systematically optimistic. The two official descriptions of the matching benchmark are mutually inconsistent (last price vs best bid/ask). | moomoo help centre, US and SG pages |
| N3 | **Fill detail.** Deal-related operations are unsupported — no today's deals, no historical deals, no transaction push callback. | *"Paper trading does not support deals related operations"* |
| N4 | **`unlock_trade`** and its failure modes are live-only. | *"when using paper trading accounts, you do not need to unlock trade"* |
| N5 | **T+1 settlement.** Paper settles T+0, so unsettled-funds rejections cannot occur. | *"funds settling on a T+0 basis"* |
| N6 | **GTC behaviour.** Paper supports day orders only. | *"Paper trading only supports good for day order"* |
| N7 | **Account-scale risk thresholds.** The paper account is funded at USD 1,000,000 against a TP of USD 10,000, so the fixed per-order fee is ~100× less visible. | moomoo help centre |
| N8 | **The margin interaction with other holdings.** The paper account is clean and contains none of them. | Mandate §7b |
| N9 | `cancel_all_order` is unsupported in paper — incident scripts must cancel order by order. | OpenAPI modify-order page |

**Official statement, to be quoted at the head of every Stage D report:**
> *"The paper trading system may not necessarily be consistent with the real stock market."*

**Binding consequence for Stage D's design:** Stage D will report **only** operational metrics —
did the process run, was the order state machine correct, was manual confirmation sustainable.
**It will report no return, no Sharpe ratio and no drawdown.** Any performance figure derived from
a paper account whose costs and fills are both unrepresentative would be a fabricated number used
to justify risking real money.

---

## 10. What this document does not do

It does not claim any strategy is profitable. It does not rank candidates by any performance number,
because no performance number exists. It does not authorise trading. It fixes the bar that evidence
must clear, so that the evidence gets to decide.

---

## Appendix A — Admission bar for any FUTURE candidate

**Added 2026-09-15, after the Stage B verdict (`candidate_comparison.md`). NOT ACTIVATED — no
candidate is currently in scope. Recorded now so the next round cannot repeat this round's errors.**

### A.1 Candidate register and attempt budget (logged before any backtest; immutable thereafter)

- Register the total candidate count N. The ~19 prior parameter searches run on US single names and
  leveraged ETFs between 2026-08-28 and 2026-09-15 **must be counted in N**; a different instrument
  does not exempt them.
- **Searches against price data: 3 for the entire project** (one per candidate, no re-runs).
  Free parameters per candidate ≤ 2, grid frozen before any result is seen.
- Changing parameters, benchmarks or the objective function *after* seeing a result **permanently
  rejects that candidate**. It may not be revived under the name "robustness check".

### A.2 Date split (written once, never moved)

Given the data source actually available, the §5 split is superseded for future candidates by:

| Segment | Dates |
|---|---|
| Training | 2006-09-01 → 2014-12-31 |
| Validation | 2015-01-01 → 2020-12-31 |
| **Final test — run once** | 2021-01-01 → 2026-08-31 |

**Honest limitation that must appear in the body of any conclusion, never in a footnote:** each
segment contains roughly 2 independent regime events, so the final-test segment **has no statistical
power** and may serve only as a one-way rejection gate for catastrophic inconsistency — **never as
supporting evidence**. The only −50 %-class event sits in the training segment, which means a
drawdown claim can never be tested out-of-sample within this project.

### A.3 Metrics and conventions

- **Signals use the price series; performance uses the total-return series** (distributions included,
  30 % withholding applied unless §871(k) exemption is verified). The two must be **separate data
  objects**, and mixing them must be prohibited at the code level.
- Annualisation geometric throughout. Sharpe from monthly excess returns over the **after-tax** cash
  yield, × √12. Maximum drawdown on daily TP-level NAV.
- Every candidate must report against **four** comparators, not three: SPY B&H, 60/40 SPY+IEF, BIL,
  **and the static de-risked blend `w·SPY + (1−w)·cash`**, where w is fixed by an assumed worst-case
  crash depth and **may never be chosen from historical performance**. If a candidate's ranking
  against the four flips with the choice of benchmark rebalancing convention, it is auto-rejected.
- Benchmark rebalancing rules must be declared an **arbitrary convention**, not a discovery: annual,
  first US session, no band, no tolerance. **No parameter taken from published grid-search results
  may be used** — this specifically forbids adopting a 5pp band as a benchmark default.

### A.4 Cost assumptions — complete list, none optional

Platform fee USD 0.99 × 1.09 = 1.0791 per order, **charged per submitted order** unless verified
otherwise (P1-5); settlement 0.003/share capped at 1 % of value; sell-side SEC 0.0000206 × value
(min 0.01), FINRA TAF 0.000195/share (min 0.01, max 9.79); CAT 0.000003/share; **idle cash from
whole-share rounding booked at 0 % return, with its opportunity cost listed separately** (expected
idle ≈ price/2, multiplied by the portfolio's own expected return, not the short rate); limit-order
price concession provisioned at the **rule's stated concession**, not at the quoted spread;
overnight gap provisioned from a distribution **conditioned on signal direction**, never assumed
zero-mean; ETF expense ratios included; 30 % dividend withholding. TWAP/VWAP forbidden — the API
does not accept them for order placement in any case.

### A.5 Failure criteria (written before any data is seen)

- **(a) Ex-ante power gate — highest priority.** Each candidate must submit a power calculation:
  assumed effect size, event count n, standard error of the annualised difference, and the 95 %
  confidence half-width, compared against its own rejection threshold. **If the required sample
  length exceeds the available sample length, the candidate is rejected without a backtest.**
  By this round's three independent calculations, trend-type candidates are eliminated here.
- **(b) Excess threshold.** The candidate must exceed the **static de-risked comparator's**
  annualised after-tax total return by X %/yr in the final test, where X is written down before any
  data is seen and **X must be larger than the 95 % confidence half-width of that statistic**. If,
  having written X down honestly, X turns out not to be estimable, **that is itself the answer**:
  close as "insufficient evidence, do not deploy".
- **(c) Drawdown threshold.** Maximum drawdown must not exceed the comparator's.
- **(d) Execution threshold.** Any missed confirmation, any expired unfilled order, or any
  divergence between recorded state and actual holdings during paper trading is recorded as a
  **design defect**: the specification must be fixed and re-preregistered from the start. It may not
  be logged as "be careful next time".
- **(e) Specification requirements.** Ordering logic must be **target-reconciling** — every period,
  unconditionally compare target holdings against actual holdings and correct any difference.
  Event-driven ordering ("place an order only when the state flips") is **forbidden**: it decouples
  recorded state from reality permanently after a single miss. Failure must fall to the **defensive
  state**, never default to remaining in the risk state. Execution timing must be driven by the
  trading calendar and bar timestamps, **never by a hard-coded Singapore wall-clock time** — US DST
  makes the open 21:30 SGT and standard time 22:30 SGT, and two candidates in this round had a
  one-hour error here. A heartbeat log is required; **silence must never be interpreted as
  "no signal"**.
