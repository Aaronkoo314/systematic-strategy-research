# Investment Mandate — DRAFT v0.1 (Stage A)

**Status: NOT APPROVED. NOT AUTHORIZATION TO TRADE.**
Owner: the operator. Prepared by: the working team (see project brief).
Date: 2026-09-15. Capital figures sanitised 2026-10-30 - see §2.

This document separates three things and never mixes them:

- **[C] CONFIRMED** — stated by you, or verified against your account / official documentation.
- **[P] PROVISIONAL** — a research or engineering assumption I adopted so work can continue.
  **A provisional item is my assumption, not your instruction, and carries no authorization.**
- **[U] UNRESOLVED** — needs your answer; listed in §8.

---

## 1. What "stable returns" is being translated into

You asked for "stable returns". Restated as a testable objective:

> Over a multi-year horizon, achieve a positive return **net of every cost in §5**, with drawdowns
> that stay inside a pre-declared tolerance, with an operational burden you can actually sustain,
> and with risk-adjusted performance good enough to justify the money, time and risk versus simply
> holding a passive benchmark or a cash-equivalent.

**Explicitly not promised, and not achievable by any strategy:**
a positive return every month; a fixed income stream; protection against loss; a guaranteed maximum
loss; or any specific CAGR, Sharpe ratio or win rate. Risk thresholds in §4 are *intervention
triggers* — points at which the system stops taking new risk — not loss limits. Gaps, halts,
illiquidity, broker outages and network failure can all produce losses larger than any threshold.

**[P]** The honest baseline question this project must answer is not "can we build it?" (we can) but
**"does the resulting strategy beat holding the benchmark, after costs, by enough to be worth the
work?"** A NO-GO at Stage C is a legitimate and reasonably likely outcome.

---

## 2. Capital

**Every capital figure in this repository is a NOTIONAL design parameter, not an account
figure.** The sleeve size exists so that fixed per-order fees can be expressed as a percentage
and so that the thresholds in §4 resolve to dollar amounts; the arithmetic is the same at any
size and the conclusions scale with it. Account balances, positions and buying power were
read once by a read-only probe and are not recorded anywhere in this repository.

| Item | Value | Status |
|---|---|---|
| Ownership | the operator's own money, not client money | **[C]** |
| **Trading portfolio (TP) size** | **USD 10,000, notional** | **[C]** design parameter, decision 2026-09-15 |
| Other holdings in the same account | Outside this system's authority; untouched | **[C]** decision 2026-09-15 |
| Illustrative live-pilot ceiling | USD 2,000, notional | **[P]** *subject to separate explicit approval* |

**The TP denominator is USD 10,000.** All percentage thresholds in §4 resolve against that
figure, giving: daily-loss trigger USD 100, drawdown review USD 500, drawdown intervention
USD 800, abandon point USD 2,000.

**A standing condition — see §7b.** The sleeve shares one brokerage account with other
holdings, so unencumbered cash equal to the notional TP is not guaranteed to exist at any given
moment. This does not block research, which models the TP as a design parameter, but it does
mean a pre-trade cash check is mandatory before any live order, and it must read *actual settled
cash attributable to TP*, never `power` (buying power).

### Sleeve definition (required before Stage C)

| Term | Definition |
|---|---|
| **Trading portfolio (TP)** | The capital explicitly allocated to this system, plus its own cash. All % thresholds in §4 apply to **TP net asset value**. |
| **Other holdings** | Anything else in the account, managed by the operator, outside this system's authority. |
| **Total account (TA)** | TP plus other holdings. Reported separately (Goal 6) but never used to size TP risk. |

**[P]** The system will treat any instrument held outside TP as **ineligible** for TP, to prevent
the two sleeves from silently doubling an exposure or from wash-sale-style interference in
reconciliation.

---

## 3. Horizon, liquidity, benchmark

*Benchmarks confirmed by you on 2026-09-15: report against all three, side by side.*

| Item | Status |
|---|---|
| Investment horizon | **No fixed term**, but must be realisable within a few days | **[C]** 2026-09-15 |
| Money needed back within 12 months | No stated requirement; liquidity-on-demand instead | **[C]** 2026-09-15 |
| Capital that must never be exposed to trading risk | Not specified beyond the TP/DB split | **[C]** 2026-09-15 |
| Return expectation | Still unstated by you — and I will not propose one, because a stated target invites fitting the research to it | **[U]** |
| **Primary benchmark [C]** | Buy-and-hold **SPY**, total return, same cost model, same currency |
| **Secondary benchmark [C]** | **60/40 SPY/IEF**, rebalanced annually — a fairer comparator for any defensive/rotation strategy |
| **Capital-parking benchmark [C]** | **BIL** (1–3 month T-bill ETF) held at the broker. Alternative: an SGD fixed deposit / T-bill, which avoids FX and US withholding but is not held at this broker. **[U] Q8** |

Rationale for the capital-parking benchmark: a defensive strategy that spends half its life in cash
must be shown to beat *actually holding cash*, net of the fixed per-order fee it pays to move in and
out. Verified: `US.BIL` is tradeable and quoted through the API (last 91.50, 2026-09-14).

---

## 4. Risk framework (provisional parameters, awaiting your approval)

All of the following are **[P]** — taken from your brief as *research and engineering test
parameters*. None is a suitability conclusion, and none is live authorization.

| Control | Provisional value | Applies to |
|---|---|---|
| Leverage | none; TP buying power capped at TP cash | TP |
| Short selling | prohibited in v1 | TP |
| Options / futures / leveraged & inverse ETFs | prohibited in v1 | TP |
| Max aggregate risk-asset exposure | 90 % of TP NAV | TP |
| Planned risk per trade (strategies with a defined stop) | 0.25 % of TP NAV | TP |
| Daily loss threshold | 1 % of TP NAV (= USD 100) → suspend new risk-taking, investigate | TP |
| Drawdown review threshold | 5 % below cash-flow-adjusted high-water mark (= USD 500) → risk-reduction review | TP |
| Drawdown intervention threshold | 8 % (= USD 800) → suspend new risk-taking, run incident procedure | TP |
| **Abandon point (preregistered)** | **20 % (= USD 2,000) → stop the system entirely** | TP | **[C]** |

**Conflicts already identified between these parameters and reality — requiring your decision:**

1. **The 0.25 %-per-trade rule is not implementable at pilot size.** On a USD 2,000 TP, 0.25 % =
   **USD 5.00** of planned risk. The round-trip cost of a single SPY trade is ≈ USD 2.21 (§5) —
   i.e. **44 % of the entire risk budget is consumed by fees before the market moves at all.** Any
   strategy sized this way at USD 2,000 is structurally uneconomic. Options: raise the pilot size,
   raise the per-trade risk, or select a strategy that sizes by *exposure and volatility* rather
   than by stop distance. My recommendation is the third — see §6.
2. **The account is a MARGIN account.** The broker will not enforce "no leverage" or "no shorting".
   Our software must, as a hard pre-trade block. Verified in the probe: `power` (buying power) did
   **not** equal `cash`, because buying power includes margin capacity — which means *buying
   power is not a safe proxy for available cash* and must never be used for sizing. (See
   `feasibility.md` §4.)
3. **An 8 % drawdown threshold on a USD 2,000 TP is USD 160.** That is smaller than a single day's
   move in an ordinary equity position. It is a fine engineering test of the control, but it
   is not a meaningful portfolio risk statement. Do not confuse the two.

**[P]** Definition of TP daily loss and drawdown, to be used consistently everywhere: mark-to-market
TP NAV including realized **and** unrealized P&L, net of all costs, with external cash flows
(deposits/withdrawals to the sleeve) neutralised by adjusting the high-water mark on the day of the
flow. The high-water mark is **never** reset by restarting the process, adding capital, or changing
the config; it is persisted to disk and reconciled at startup.

---

## 5. Cost model (verified rates; see `feasibility.md` §7 for sources)

| Component | Rate | Verified |
|---|---|---|
| Commission, US stocks/ETFs | USD 0 | yes |
| Platform fee | USD 0.99 / order | yes |
| GST | 9 % on platform fee → **USD 1.0791 / order** | yes |
| Settlement | USD 0.003 / share (max 1 % of value) | yes |
| SEC fee (sell) | 0.0000206 × value, min 0.01 | yes |
| FINRA TAF (sell) | 0.000195 / share, min 0.01, max 9.79 | yes |
| CAT | 0.000003 / share | yes |
| Algo order types (TWAP/VWAP) | +0.05 % → **forbidden in v1** | yes |
| Bid-ask spread, SPY/IEF/BIL | ≈ 1 cent (negligible vs fixed fee) | observed |
| Slippage | **[P]** model at 1 tick + 2 bps for market-on-open orders; to be calibrated in Stage C | no |
| FX (SGD↔USD) conversion | **[U] Q4** — not verified; account cash is already USD | no |
| US dividend withholding | **30 %**, no treaty relief for SG residents | yes (see caveats) |
| Market data | **USD 0** — LV1 US quotes, daily + intraday bars, calendar all work on the current entitlement | yes |
| Hosting | **USD 0** — own laptop, provisionally | n/a |
| AI API at runtime | **USD 0** — v1 makes **no** LLM calls in the signal path, by design | n/a |

### Fixed-cost drag (Goal: report against both capital bases)

Annual fixed expenses are currently **USD 0** (no subscriptions, no hosting). Therefore:

- Drag on the notional USD 10,000 TP = 0 / 10,000 = **0.00 %**
- Drag on a USD 2,000 pilot = 0 / 2,000 = **0.00 %**

**Variable** cost is what matters here, and it behaves like a fixed cost at small size:

**Corrected 2026-09-15.** The table below now uses **full-scope** cost (platform fee + GST +
settlement + SEC + FINRA TAF + CAT), not the platform fee alone. The earlier platform-fee-only
figures understated cost by roughly 27 % and biased comparisons toward higher-turnover designs.

| Orders/yr | Full-scope annual cost | on USD 10,000 TP (notional) | on USD 2,000 |
|---|---|---|---|
| 4 (one SPY↔BIL round trip) | ≈ 5.49 | 0.055 % | 0.27 % |
| 12 | ≈ 16.4 | 0.164 % | 0.82 % |
| 24 | ≈ 32.9 | **0.329 %** | 1.65 % |
| 120 | ≈ 165 | **1.65 %** | 8.2 % |

**[P] Mandate constraint derived from this:** any v1 candidate must keep total orders at or below
**~24 per year**, and must hold **no more than 2–3 instruments**. **Additionally established in
Stage B:** monthly-or-faster *calendar* rebalancing is excluded by arithmetic at this size — 24
orders/yr ≈ 0.329 %/yr against a theoretical rebalancing premium ceiling of ≈ 0.344 %/yr, and at
typical monthly drift of USD 50–100 notional the fixed fee alone is 1.1–2.2 % of the trade. This is not a stylistic
preference; it is arithmetic. Stage B candidates that violate it will be rejected on cost grounds
before their signal quality is even examined.

---

## 6. Provisional strategy constraints for Stage B (not a selection)

**[P]** Derived from §4 and §5, the Stage B search will be restricted to:

- Long-only, unlevered, US-listed ETFs with tight spreads and multi-decade histories.
- Signals computed on **completed daily bars**; earliest executable time is the **next** session —
  no same-bar close execution.
- Order types limited to `NORMAL` (limit) and `MARKET` only, because paper trading supports nothing
  else and the paper stage must faithfully rehearse live.
- No broker-side stop orders in v1 (they cannot be paper-tested; and a stop does not guarantee a
  fill at its trigger price).
- Rebalance frequency monthly or slower.
- Sizing by target exposure and volatility, not by stop distance (see §4 conflict 1).

**[P]** The null hypothesis for Stage B is: *"this strategy does not beat buy-and-hold SPY, nor BIL,
after costs and withholding."* Stage B will preregister what would refute it **before** any final
test period is examined.

---

## 7. Decisions confirmed by you on 2026-09-15 **[C]**

| # | Question | Your decision | Consequences I will carry forward |
|---|---|---|---|
| Q1 | Relationship to other holdings in the same account | **Ring-fenced.** Other holdings stay as they are; the notional USD 10,000 trading portfolio is a carve-out. | The system gains no authority over other holdings and will never act on them. The two sleeves coexist inside one margin account, which creates the interactions catalogued in §7b. |
| Q2 | Operating model | **Manual confirmation of every order.** | v1 is a *decision-support and order-staging* system, not unattended automation. See §7a — this materially improves safety and changes the paper-trading plan. |
| Q3 | Prior phase-1 research | **Ignore entirely.** | Noted and accepted. I flagged the research-integrity cost and you reaffirmed; recorded in §7b so the limitation is never quietly dropped. |
| Q4 | Benchmark | **Report against SPY, 60/40 SPY/IEF, and BIL side by side.** | All three become preregistered comparators in Stage B. No post-hoc benchmark selection is permitted. |

### 7a. Consequences of "manual confirmation of every order"

**Improvements — these are real safety gains, not consolation:**

- The trading password is **never** needed by an unattended process. `unlock_trade` happens only in
  a session you are present for. This removes the entire unattended-secret-storage problem that
  would otherwise have been the project's largest security exposure.
- A human check sits between a strategy bug and a live order. Goal 8's "missing configuration or
  authorization cannot result in an accidental live order" becomes structurally true, not just
  test-verified.
- No VPS is needed. Running cost stays **USD 0 / year**.

**Costs — these must not be glossed over:**

- The system **is not unattended and must never be described as such.** If you are asleep,
  travelling, or ill, the strategy does not trade. Stage B must therefore pick a strategy whose
  edge, if any, does not decay when a decision slips by a day or two. This is a genuine constraint
  on strategy choice, and it argues strongly for monthly-or-slower rebalancing.
- **[P]** Proposed decision/execution timing, for your confirmation: signal computed from the
  **previous completed daily bar**; you review and confirm; order sent as a **limit order shortly
  after the US open (22:30 SGT / 21:30 SGT under US DST)**. This is a waking hour in Singapore and
  avoids the 04:00 close entirely. The backtest must then assume execution **at the next open, not
  the signal close** — no same-bar fills.
- **Missed-decision handling must be specified, not improvised.** **[P]** If a scheduled rebalance
  is not confirmed within N sessions, the system does *not* silently catch up later at a stale
  price; it re-computes from the latest completed bar and re-proposes. Stage B will fix N and
  Stage C will test it.
- **Paper-trading evidence is weakened.** A monthly-rebalanced strategy generates roughly **3
  decisions in 60 trading days** — nowhere near enough to validate the order lifecycle. Stage D
  therefore needs two separate tracks: (i) the real strategy's decisions, for operational realism,
  and (ii) a deliberately higher-frequency **engineering drill** on the paper account purely to
  exercise partial fills, rejections, timeouts, restarts and reconciliation. Track (ii) produces
  **no performance evidence whatsoever** and will be labelled as such everywhere it appears.

### 7b. Consequences of sharing one account with other holdings

The trading portfolio is a carve-out inside an account that also holds positions outside this
system's authority. These consequences are live, not hypothetical:

1. **Unencumbered cash equal to the notional TP is not guaranteed to exist.** Other holdings
   consume buying power and margin. Stage B may model a USD 10,000 TP as a design parameter, but
   before any live order the system must verify *actual settled cash attributable to TP* and
   refuse to proceed otherwise. **`power` (buying power) must never be used for this check** — it
   includes margin capacity and moves with the marks of the other holdings.

2. **The TP's available cash depends on positions it does not control.** If the margin
   requirement of other holdings rises, the cash the TP can safely use falls — with no signal from
   the strategy and no warning. In the worst case an account-level margin call could force
   liquidation of *TP* positions. **This is a genuine path by which other holdings can cause a
   loss inside the trading portfolio, and no risk control in this system can prevent it.** It
   must be stated in every performance report.

3. **Account-level guardrails are not this system's to claim.** The v1 guardrails "long-only"
   and "no leverage" apply to the TP only. No report may claim anything about the account as a
   whole.

4. **The 20 % abandon point applies to TP NAV only.** Total-account drawdown can differ and is
   not driven by this system. Goal 6 requires both to be reported separately; with a shared
   account that separation is essential rather than cosmetic.

5. **Reconciliation needs instrument-level ownership.** Both sleeves share one account, so broker
   position data mixes them. The system will maintain an explicit TP instrument allowlist and treat
   any quantity in an allowlisted instrument that it did not itself create as an **unreconciled
   discrepancy that blocks trading**, rather than silently adopting or selling it.

6. **Overlap is forbidden.** If a TP instrument is ever bought outside the system, reconciliation
   breaks. Stage B excludes every instrument held outside TP from the TP universe, and the runbook
   requires the operator to say so before trading a TP instrument by hand.

### 7c. Research-integrity limitation you accepted (Q3)

You chose to disregard the prior `D:\Quant` search. I recommended reviewing and logging it, you
reaffirmed, and I am proceeding. The limitation this creates is recorded here permanently so that no
later report can imply evidence it does not have:

> Between roughly 2026-08-28 and 2026-09-15 a substantial parameter search was run on
> a small set of US single names and leveraged ETFs (≈19 optimisation / walk-forward result sets).
> Results obtained on **those** symbols cannot be presented as untouched out-of-sample evidence,
> because the number of prior attempts on them is unrecorded. The symbol list is held in the
> operator's local, git-ignored notes; Stage B excludes them by reference to that list.

**[P]** Mitigation I will apply unless you object: Stage B will avoid those symbols as primary
instruments. Where an overlap is unavoidable, the report will state it explicitly rather than claim
a clean out-of-sample result.

## 8. Remaining open items (do NOT block Stage B)

| Item | Status |
|---|---|
| Return expectation | Deliberately unstated. I will not set a target; Stage B reports what the evidence shows against the three benchmarks. |
| Tax residency | **Singapore [C]**. **W-8BEN status unconfirmed [U]** — model 30 % US dividend withholding; flag as an unverified tax assumption in every report. |
| Budget for data / hosting / AI | **USD 0 per year [P, operator did not object]**. No subscription, VPS or paid API will be proposed without a written gap analysis and your explicit confirmation. |
| Unencumbered cash for the notional TP | **[U] — to be verified by a settled-cash check before any live order (§7b.1).** Blocks *live deployment*, not research. |

---

## 9. What is explicitly NOT authorized

- No live order may be submitted. `dry_run = true`, `live_enabled = false` remain the defaults and
  no code path will exist in Stage B that can reach `place_order`.
- No purchase of any data subscription, VPS, or paid API.
- No modification of the phase-1 research code or of any existing position.
- No change to broker settings, permissions, or account configuration.
- No credential will be requested in chat, stored in source, or written to a config file or log.
