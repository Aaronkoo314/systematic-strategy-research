# Stage B — Candidate Comparison and Verdict

**Date: 2026-09-15. Evaluated against the criteria frozen in `selection_criteria.md` (commit 7696dc3),
which was committed before any candidate existed.**

**VERDICT: NO CANDIDATE SELECTED. All three rejected. Stage C is not entered.**

**No backtest was run. No performance figure in this document is a measurement.** Every number is
either an official fee rate, arithmetic on those rates, a published index characteristic cited as
literature, or a power calculation from stated assumptions. All are labelled as such.

---

## 1. How the candidates were produced and tested

Three candidates were generated independently from three different economic angles, each required
to state its economic thesis before its rules. Each was then attacked by three independent review
lenses — cost and capacity, overfitting and selection bias, execution and operations — with each
reviewer instructed to refute rather than improve, and to recompute the cost arithmetic itself
rather than accept the candidate's figures.

**Result: 9 of 9 reviews returned `survives: false`. 8 of 9 flagged `fatal_flaw: true`.
One candidate's own author self-assessed `reject`.**

The vote is not the finding. The finding is that the three candidates **failed on the same
structural problems, and none of those problems is at the strategy layer.**

---

## 2. Comparison table

| | **C1 — SPY 10-month SMA switch (SPY↔BIL)** | **C2 — 60/40 + 5pp threshold rebalance** | **C3 — Cash-default + monthly trend gate, 55% equity cap** |
|---|---|---|---|
| Economic source claimed | Slow information diffusion; forced deleveraging; volatility clustering. **Explicitly disclaims alpha** — positions itself as a risk converter | Diversification return `γ* = ½(Σwᵢσᵢ² − σ_p²)` — a mathematical identity, not a prediction | Same as C1, plus an exposure cap sized to the 20 % abandon point |
| Self-assessment | worth_researching (author's own deployment prior < 20 %) | **reject (author self-rejected)** | worth_researching |
| Cost & capacity lens | **fatal** | **fatal** | **fatal** |
| Overfitting lens | **fatal** | **fatal** | **fatal** |
| Execution & ops lens | **fatal** | **fatal** | **fatal** |
| Tier 0 gate failed | — (passes G1–G11) | — (passes G1–G11) | — (passes G1–G11) |
| Tier 1 question failed | **E7** (a simpler alternative dominates it) and **E5** (falsification test cannot return a verdict) | **E5** (unfalsifiable) and **E7** | **E7**, **E5**, plus an undeclared free parameter |
| **Decisive rejection reason** | Once it abandons the alpha claim, a **zero-parameter static de-risked portfolio arithmetically dominates it** on the same constraint — and it never compared itself to that, only because it was not in the given benchmark set | The increment it fights for is ≈ **USD 2/year**, smaller than one round-trip's commission, and detecting it needs a sample of **centuries** | Inherits all of C1, plus: the 55 % cap is reverse-engineered, and its own null-hypothesis fallback also breaches the 20 % abandon point |
| Salvageable output | Gate 1 (§871(k) verification) and Gate 2 (PTLC public live record), both usable only as one-way rejection tests | The hard constraint that **monthly-or-faster calendar rebalancing is mathematically excluded** at TP = 10,000 | The framing that the 20 % abandon point is an **absorbing barrier**, not a soft target |
| **Verdict** | **REJECT — no further parameter tuning** | **REJECT** | **REJECT — no further parameter tuning** |

---

## 3. Per-candidate rejection reasoning

### C1 — SPY 10-month SMA switch

**Primary reason: internal collapse of its own argument.** C1 states plainly that it does not claim
alpha, and rewrites the objective as *growth subject to maximum drawdown < 20 %*. But once alpha is
abandoned, that constraint has a **zero-parameter solution**: a static blend `w·SPY + (1−w)·cash`.
Taking the published S&P 500 peak-to-trough of roughly −55 % (2007-10 to 2009-03, literature/index
characteristic, **not** a measurement of ours), `w = 0.35` bounds portfolio drawdown at ≈ 19.25 %
**by arithmetic, independent of the crash path's shape**.

The trend rule's drawdown protection, by contrast, is a *function* of path shape — it works on slow
declines and fails on V-shaped crashes, which C1 itself lists as its first failure regime and
explicitly says cannot be fixed by parameters. It stakes its entire value on a mechanism it admits
fails periodically, in order to satisfy a constraint that arithmetic satisfies unconditionally.

Secondary reasons, each independently sufficient:

- **The omitted cost items exceed the included ones by an order of magnitude.** C1 reports
  0.11–0.33 %/yr. Reviewers independently restored: whole-share rounding cash drag 0.10–0.19 %/yr
  (which C1's own rules book at 0 % return), forgone equity risk premium 0.9–1.8 %/yr, and the
  whipsaw and overnight-gap costs C1 concedes exist but excludes from its budget, 0.5–2.0 %/yr.
  Full-scope ≈ **1.0–2.9 %/yr**. The same document quotes the smaller figure externally.
- **Its only quantitative gate cannot return a verdict by construction.** Gate 3's rejection
  threshold is 1.5 %/yr of whipsaw drag; the 95 % confidence half-width of that statistic is ≈
  ±2.1 %/yr. A test whose decision line sits inside its own confidence interval is not a test.
- **Parameter provenance is contaminated and no clean sample remains.** 10-month / 200-day is a
  survivor of a long public search. The genuine out-of-sample window after Faber (2007) —
  2009–2026 — **has already been run and reported**, and Zakamulin (2014, 2017) and Marshall et al.
  (2017) read negative (literature conclusions, not our measurements).
- **Gate 1's sign is inverted.** If BIL distributions are withheld at 30 %, the damage to the *BIL
  benchmark* (100 % in that leg) is more than triple the damage to the strategy (~30 % of the time
  in that leg). A gate that cannot produce a rejection under either outcome is fact-gathering, not
  falsification.
- **Its cost arithmetic used a stale price.** It assumed SPY ≈ 650; our verified 2026-09-14 close
  is 760.88, making one share **7.61 %** of TP, not 6.5 %.

### C2 — 60/40 + 5pp threshold rebalance

**The author reached the correct answer and self-rejected. Confirmed.** Three additions:

- **What it fights for is smaller than the system's minimum cost granule.** The net increment over
  plain annual calendar rebalancing recomputes to ≈ **USD 2/year** — less than one rebalance
  round-trip's cost (≈ USD 2.21), and about 1/11 of the measurement's confidence half-width. At
  least three unverified items could each flip it negative.
- **Its recommendation would write contamination permanently into the project.** It proposed
  adopting the 5pp band as the benchmark's engineering default "without spending research budget to
  prove it". But 5pp is itself a grid-optimised recommendation from published work. Embedding a
  data-mined parameter into the **benchmark** means every future candidate is measured against a
  tuned ruler — and because it is flagged "needs no proof", that tuning would never be revisited.
  **This recommendation is rejected.**
- **Salvageable hard constraint:** at TP = 10,000, monthly-or-faster calendar rebalancing is
  excluded by arithmetic — 24 orders/yr ≈ 0.33 %/yr full-scope against a theoretical ceiling of
  γ* ≈ 0.344 %/yr, and at typical monthly drift of USD 50–100 notional the fixed fee alone is
  1.1–2.2 % of the trade.

### C3 — Cash-default + monthly trend gate (55 % equity cap)

Inherits all of C1's fatal problems, plus three of its own:

- **55 % is reverse-engineered, not derived.** In `20 % ÷ 37.5 % ≈ 0.53`, the 37.5 % is the only
  substantive input, has no stated source, is unfalsifiable, and lands the answer on a round 55 %.
  Published index records contradict it: roughly −40 % in about two months (2008-09-19 to
  2008-11-20) and roughly −34 % in about five weeks (2020-02-19 to 2020-03-23) — so the assumption
  "worst fall between two month-end signals ≤ 37.5 %" has been violated at least once in the record.
- **"Either result is informative" is false.** Its null-hypothesis fallback is a static 37 % SPY.
  Under a 2008 repeat (≈ −55 %), that is 0.37 × 55 % ≈ 20.4 % of TP — **it breaches the USD 2,000
  abandon point directly**. Staying under 20 % requires exposure ≤ 36.4 %, and with policy headroom
  ≤ 25–30 % — a conclusion available from barrier arithmetic with no backtest at all. The research
  therefore has zero decision value.
- **A silent-failure defect at the specification layer.** Ordering written as "place an order only
  when `S_t ≠ S_{t-1}`" is event-driven, not target-driven. A single missed confirmation or an
  unfilled limit order decouples the recorded state from the actual holding **permanently, with no
  corrective order ever generated afterwards**. The worst branch: miss one exit and the system
  silently degrades into fully-invested buy-and-hold — its entire reason for existing evaporates
  and nothing detects it. At 97 % attendance over ~40 events in 5 years, the probability of at
  least one miss is ≈ 70 % (still ≈ 33 % at 99 % attendance).

---

## 4. Why "reject all three" is structural, not three unlucky draws

These five apply to **any** portfolio-layer candidate in this account, which is why they decide
both this round's verdict and what the next round must be.

**S1 — The account structure makes TP non-attributable.** A margin account has one account-wide
computation; there is no "cash attributable to TP" field — that exists only in a spreadsheet.
Consequences: (a) the sizing formula `floor(TP cash / price)` has no readable input on the screen;
(b) a rising short drains buying power, and a rising short means a rising market, which is exactly
when a trend rule must buy equity back — the two are positively correlated; (c) in a margin call the
broker liquidates by liquidity preference, and SPY/BIL are the most saleable positions in the whole
account — **TP is the first thing cut**. Therefore **the USD 2,000 abandon point is unenforceable in
TP terms**: an account-level event can end TP at any drawdown level, including zero.

**S2 — The validation environment cannot validate what the decision depends on.** Verified: paper
cannot query order fees; supports no deal detail or deal push; is funded at USD 1,000,000 (100× TP,
so the fixed-fee drag is nearly invisible on its equity curve); charges per-share commission rather
than Futu SG's fixed platform fee; settles T+0 not T+1; supports DAY only, not GTC; needs no
`unlock_trade`; and the paper account is clean — it contains neither the existing short nor the
concentrated positions, so the whole of S1's risk surface is uncovered. Official wording:
*"The paper trading system may not necessarily be consistent with the real stock market."*

**S3 — The only usable data source has two unresolved prerequisites.** Seven external free sources
were eliminated one by one — see `data_sources.md`. What remains is moomoo's own data, whose
**storage licence for personal backtesting is unverified** and whose **US QFQ series is not
documented as including cash dividends**. Until both are settled, a price series with a clear
licence and auditable adjustment does not yet exist for this project.

**S4 — The quantities the decision depends on cannot be estimated on the available sample.** Power
calculations from stated assumptions (not measurements): for the trend candidate versus a static
blend, the 95 % confidence half-width of the annualised return difference over 20 years is ≈
±3.8–5.0 %/yr, while translating "+0.15 Sharpe" into a testable quantity requires ≈ 1.4 %/yr of
timing alpha — **the decision line sits inside its own confidence interval**. Reaching 2σ needs
≈ 32 years; 80 % power needs ≈ 62 years. The rebalancing candidate needs centuries. Available clean
data is ~19 years with about 3 genuinely relevant downside events, and **the only −50 %-class event
sits at the very start of the sample**, which means the drawdown claim can never be tested
out-of-sample within this project.

**S5 — Scale contaminates the research design itself.** One SPY share = 7.61 % of TP. Whole-share
rounding error is the same order as the effect being measured. Worse, the literature's standard
anti-mining defence — ensembling several lookback periods in fractional tranches — is **physically
unimplementable** at this size, forcing the candidate onto the single most heavily data-mined
parameter configuration in the field. **A capacity constraint converts directly into a
research-integrity problem.**

---

## 5. The benchmark comparison, answered directly

**Versus SPY buy-and-hold — not an opponent, a scoreboard.** Published index characteristics: SPY
drew down ≈ −55 % (2007-10 to 2009-03), ≈ −34 % (2020), ≈ −25 % (2022). It would have breached the
operator's own preregistered 20 % abandon point at least three times in 19 years. **SPY B&H is not
deployable under this mandate.** Beating an opponent that was never on the field is not a reason.

**Versus BIL — uninformative, and not computable today.** All of BIL's return is distribution. Any
positive equity exposure beating it over multi-year horizons is near-tautological at published
equity-premium levels. Worse, **BIL's after-tax baseline depends entirely on the unverified
§871(k) question**, worth ≈ 1.29 %/yr — larger than every trading cost combined. The benchmark's
own value is currently undefined.

**Versus 60/40 — by the same ruler, also not deployable.** Published index characteristics: ≈ −30 %
in 2008, ≈ −20 % in 2022. It too has a material chance of triggering the 20 % abandon point in a
normal cycle. **Two of the three mandated benchmarks are undeployable and the third is
uninformative.**

**The real opponent was never in the comparison set.** After the alpha claim is dropped, the one
option that simultaneously (i) satisfies the 20 % constraint, (ii) is deployable, and (iii) carries
no execution risk is the static de-risked blend `w·SPY + (1−w)·cash`: one purchase, an annual check,
no 04:00 signals, no 22:30 manual confirmation, no unfilled-order branch, no whipsaw, no overnight
gap. Its drawdown bound comes from arithmetic rather than estimation. No candidate compared itself
to it — **only because it was not among the three given benchmarks. That is selection bias at the
level of the comparison object, and it is my error in framing Stage B, not the candidates'.**

**Reconciliation of money and time** (arithmetic on stated assumptions, not measurements): a full
SPY↔BIL round trip of 4 orders ≈ USD 5.49 = 0.055 % of TP; 24 orders/yr full-scope ≈ USD 32.9 =
**0.329 %/yr**; 120 orders ≈ USD 165 = **1.65 %/yr**. Adding expected idle cash from whole-share
rounding, SPY dividend withholding, and the conceded-but-unbudgeted whipsaw and gap costs, the net
expected excess recomputes to roughly **−USD 52 to +USD 130 per year, point estimate ≈ USD 26 — an
interval wider than the point estimate itself.**

The price is 8–12 late-night manual confirmations a year with no backup, drawdowns of 10–15 %, an
uncommitted multi-year horizon, and a 26–70 % chance of missing at least one critical confirmation
within 5 years — where missing one exit terminates the project by its own terms.

**In one sentence: this trades certain time, certain operational risk, and an expected value whose
sign is undetermined, for an advantage that cannot be statistically confirmed at any sample length
available. Not worth doing.**

---

## 6. Correction to a figure I published earlier

`selection_criteria.md` §1 G5 and `investment_mandate.md` §5 stated "24 orders ≈ 0.26 %/yr,
120 orders ≈ 1.29 %/yr". **Those counted the platform fee only.** Full-scope, including settlement,
SEC, FINRA TAF and CAT, the figures are ≈ **0.329 %/yr** and ≈ **1.65 %/yr** — an understatement of
about 27 %, which biases comparisons **in favour of higher-turnover designs**. Corrected in both
documents in the same commit as this one.

---

## 7. What happens next — and what must not

**This round does not proceed to Stage C.** Per the mandate, "if it does not qualify, stop, rather
than keep tuning until it looks qualified."

### P0 — blocking decisions for the operator (nothing else can be decided first)

1. **Account isolation.** Can TP be moved into a separate account with no other holdings and no
   margin borrowing — a cash account for preference? Or can the other holdings be ring-fenced?
   This is not a robustness question, it is a feasibility question: only then is "TP available cash"
   a number readable on a screen, only then can an account-level forced liquidation not reach TP,
   and only then does the 20 % abandon point mean anything.
   **If neither is possible, the correct project conclusion is that this account cannot produce
   attributable portfolio-level performance, and all portfolio-layer candidates terminate.**
2. **Resolve the stale instruction in `README.md`** ("positions to be liquidated before allocation")
   against the current decision (do not liquidate; a short remains open). Fixed in this commit.

### P1 — administrative facts (≈ one day each, deterministic arithmetic, no statistics)

3. §871(k) QII treatment — pull one real US bond-ETF distribution entry and compare gross, net and
   withheld. Worth 0.45–1.29 %/yr and sets the after-tax baseline for two of three benchmarks.
4. **Any account-level fixed fees** (custody, monthly, inactivity, FX). At TP = 10,000, USD 5/month
   = 0.60 %/yr — larger than everything computed above, and **not a single such item appears in the
   current cost model**.
5. Whether the platform fee is charged per **submitted** or per **filled** order, and how re-posted
   or partially filled orders are billed. Every candidate's order budget assumed one fee per leg.
6. Whether Futu SG's market-data agreement permits storing history locally for personal backtesting.
7. Idle USD interest and its tax treatment — determines whether the defensive leg should be BIL or
   cash; reviewers put the cost of choosing wrong at ≈ 1.67 %/yr.
8. Fractional-share support via API, live and paper separately.

### P2 — data integrity (before any backtest)

9. Recompute QFQ from `AuType.NONE` raw prices and reconcile against the API's QFQ series
   bar by bar; cross-check ten SPY ex-dividend dates against the issuer's published distributions.
   **If this fails, the data plan is void and the conclusion returns to "no usable data source".**
   Script prepared: `tools/check_adjustment.py` — **not yet run.**
10. Probe the earliest available daily bar for IEF and BIL; hard-code tradeable start dates from
    verified issuer inception dates (SPY 1993-01-22, BIL 2007-05-25, IEF 2002-07-22,
    AGG 2003-09-22) and truncate any backtest window starting earlier.
11. Three paper-account probes: a deliberately far-off limit order to observe post-close order
    status; `get_acc_list` to confirm the paper account type returned under a Futu SG login; a small
    order to establish which fields can rebuild the ledger.

### Admission bar for any future candidate — **not activated this round**

Recorded in full in `selection_criteria.md` as an appendix. The governing item is an **ex-ante power
gate**: a candidate must submit a power calculation with its proposal, and **if the required sample
length exceeds the available sample length, it is rejected without a backtest.** By the three
independent calculations in this round, trend-type candidates are eliminated at that gate.

---

## 8. Honest statement of what this round concluded

The three candidates did not fail because we picked the wrong strategies. They failed because **this
account, at this size, with this validation environment and this data length, cannot produce
evidence sufficient to support deploying any portfolio-layer timing or rebalancing hypothesis.**

Even if every P0/P1/P2 item above is resolved, the project's final conclusion may still be
**do not deploy**. Stating that plainly is worth more than forcing a candidate into implementation.
