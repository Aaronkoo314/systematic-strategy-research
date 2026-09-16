# Preregistration — Candidate V3

**Frozen 2026-09-16, before any backtest of this candidate was run.**
Third candidate. V1 used 9 configurations, V2 used 6, this uses 6.
**Project total after this candidate: 21 of the 24** frozen in `selection_criteria.md` §6.

---

## 0. This is not a strategy. It is an allocation.

V1 and V2 were both timing overlays on QQQ, one betting on continuation and one on
reversion. Both lost to simply holding a fixed fraction of the instrument. Testing a
third timing rule would be testing the same family a third time.

**This candidate makes no prediction.** It holds a fixed mix and rebalances on a
calendar. There is no signal, nothing to forecast, and no parameter that adapts to
market state. That changes what "passing" can mean: there is no edge to detect, so the
power gate's signal-detection framing does not apply. What applies instead is selection
risk — choosing the best-performing mix after seeing the results — and §3 and §5 exist
to contain that.

**The honest prior: this is the most established idea in finance and is not an edge.**
Adding bonds to an equity portfolio is standard practice, not a discovery. The narrow
question is whether it relaxes *this operator's binding constraint* enough to matter.

---

## 1. The hypothesis

**Replace the idle-cash sleeve with Treasuries.**

The static sweep established the operator's real constraint: at a 20 % abandon point, the
most QQQ that survives the full 20-year sample is **35 %, giving 5.26 %/yr**. The other
65 % sits in cash earning 0 %. Two thirds of the portfolio contributes nothing.

If that sleeve held Treasuries instead, it would earn a real yield, and — historically —
would have risen precisely when equities fell.

### Measured in this sample, before any backtest

| | QQQ | IEF | TLT |
|---|---|---|---|
| 2008 crisis (2007-10 → 2009-03) | **−41.7 %** | **+15.4 %** | **+18.9 %** |
| 2022 | **−33.7 %** | **−15.9 %** | **−31.0 %** |

The thesis and its failure mode are both in the sample, which is the reason this is worth
testing rather than assuming. 2008 is the case for it. **2022 is the case against it, and
TLT fell nearly as hard as QQQ that year.**

### Economic rationale

Two channels, and they are different in kind:

1. **Diversification.** Two assets whose returns are not perfectly correlated produce a
   portfolio whose volatility is below the weighted average of theirs. This is arithmetic,
   not a forecast, and it does not depend on anyone being wrong.
2. **Flight to quality.** In equity crises driven by growth or credit fears, investors buy
   government bonds and yields fall. This is behavioural and **it is not reliable** — it
   fails when the shock is inflation rather than growth, which is exactly what 2022 was.

Channel 1 survives any regime. Channel 2 does not, and the sample contains a clean
counterexample to it.

### Failure regimes, named before measurement

1. **Inflation shocks — stocks and bonds fall together.** 2022 is in the sample and will
   be measured, not argued about.
2. **Rising-rate regimes.** A bond sleeve can be a drag for years. The 2006-2026 sample
   contains a 40-year bull market in bonds ending around 2020, then a sharp reversal, so
   it is not representative of the starting yield environment today.
3. **Duration risk mistaken for safety.** TLT has roughly 17 years of duration and moved
   −31 % in 2022. Holding it as the "safe" sleeve would have been a category error.
4. **Correlation that changes when it matters.** Stock-bond correlation was negative for
   two decades and turned positive in 2022. Nothing guarantees which regime comes next.

### What would falsify it

§5. In short: if the mix does not raise the return achievable inside a 20 % drawdown
above the 5.26 %/yr that 35 % QQQ plus cash already delivers, it has added nothing.

---

## 2. The rules, unambiguous

```
Instruments   US.QQQ (equity) and one bond ETF, both long only, whole shares
Data          DAILY raw (AuType.NONE) bars from 2006-09-01
Rebalance     the first trading session of each calendar year, and only then
              - no bands, no drift triggers, no mid-year action

At each annual rebalance:
    target_value[equity] = W_EQ * NAV
    target_value[bond]   = (1 - W_EQ) * NAV
    shares = floor(target_value / price)  for each leg, using that session's OPEN

Between rebalances: nothing. Weights drift with price.
Dividends     cash credit on ex-date for both legs, net of 30% withholding
Cash          residual from whole-share rounding earns 0%
Risk          RiskLimits() defaults, enforced pre-trade, never bypassed
```

**Annual rebalancing is fixed, not searched.** Monthly or threshold rebalancing was
excluded by arithmetic in Stage B: at TP = 10,000 the fixed per-order fee makes frequent
calendar rebalancing cost more than the rebalancing premium is worth.

---

## 3. Parameter grid, frozen

| Parameter | Values |
|---|---|
| `W_EQ` — QQQ weight | 0.35, 0.50, 0.65 |
| bond leg | **IEF** (7-10y Treasuries), **TLT** (20y+ Treasuries) |

**6 configurations.** SHY and SHV were considered and excluded before running: their
duration is too short for the flight-to-quality channel to operate, so including them
would be testing a different hypothesis under the same name.

---

## 4. Date splits, frozen

Same splits as V2, so results are directly comparable.

| Segment | Dates | Contains |
|---|---|---|
| Training | 2006-09-01 → 2014-12-31 | **2008** — the case FOR the bond sleeve |
| Validation | 2015-01-01 → 2020-12-31 | 2015-16, 2018Q4, 2020 |
| Final test | 2021-01-01 → 2026-09-11 | **2022** — the case AGAINST it. Run once. |

**This split is unusually well suited to the hypothesis**: training contains the episode
that supports it and the final test contains the episode that refutes it. A configuration
chosen on training is therefore being tested on exactly the regime it was not chosen for.

---

## 5. Selection rule and acceptance criteria, frozen

**Selection on training:** the configuration with the **highest CAGR among those whose
maximum drawdown stays inside 20 %**. If none stays inside 20 %, none is selected and the
candidate is rejected on training.

This rule is different from V1 and V2 and the difference is deliberate. The operator's
constraint is the drawdown; the objective inside it is return. Ranking by
return-per-drawdown would reward a configuration that is merely small.

**Comparators**, all reported on every segment:

1. **35 % QQQ + 65 % cash — the incumbent.** The current best answer, 5.26 %/yr over the
   full sample. **This is the bar.**
2. 50 % QQQ + 50 % cash — what the operator would hold if the abandon point were relaxed.
3. 100 % QQQ.
4. 100 % bond leg alone.

**Abandon conditions — any one ends the candidate:**

| | |
|---|---|
| A1 | No configuration stays inside a 20 % drawdown on training |
| A2 | Selected configuration breaches 20 % on validation |
| A3 | CAGR does not exceed the incumbent's on validation |
| A4 | Turnover breaches the 10 %/yr fee ceiling — implausible at 2 orders/yr, checked anyway |
| A5 | Result reverses under any stress variant in §6 |
| A6 | The selected bond leg differs between training and validation when re-fitted |

**Conditions to look at the final test:** all of A1-A6 clear. The test is then run once
and recorded before any further change. Given that the test period contains 2022, a
configuration that passes validation and then fails the test would be informative rather
than disappointing — it would mean the bond sleeve works only in the regime it was
selected in.

---

## 6. Stress variants, all reported

| | |
|---|---|
| S1 | costs × 2.0 |
| S2 | dividend withholding 0 % on the bond leg — its yield is the point, so this matters more here than for an equity strategy |
| S3 | rebalance on the first session of July instead of January — tests whether the result depends on an arbitrary calendar choice |
| S4 | **training starting 2010, excluding 2008** — with the warmup problem that made V2's equivalent variant degenerate now avoided, since this candidate has no lookback |
| S5 | full sample run in one pass, no splits, for the record |

S4 is the decisive one. If the bond sleeve's whole contribution is 2008, that is one
episode, and the operator should know the result rests on it.

---

## 7. What passing would and would not mean

Passing would mean: **on this one 20-year path, replacing cash with Treasuries raised the
return achievable inside a 20 % drawdown.** It would not mean a bond sleeve will do that
again. The stock-bond correlation that makes it work was negative for two decades and
turned positive in 2022, and today's starting yields differ from most of the sample.

It would, however, be the first thing this project has tested that both cleared its
criteria and required no forecast to work.
