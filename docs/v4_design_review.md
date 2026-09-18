## 0. WHAT I VERIFIED BEFORE WRITING THIS

The five lenses disagreed with each other by an order of magnitude on every magnitude they quoted, so I implemented §3 + §3a verbatim and measured the load-bearing claims on the project's own bars. Three things changed as a result: two findings got *stronger* than their reviewers argued, one premise of §0 turned out to be false by measurement, and one defect nobody raised turned out to sit in the final-test segment.

**Disclosure first, because it is decision-relevant.** All 23 symbols are now on disk (`D:/QuantSystem/data/raw/US_*_5min_raw.csv`, pulled 2026-09-18, after the draft's 21:26 timestamp). To check the identity in Findings 1/5/6 I ran §3's machine on the **training segment at all three grid values of X**. That is the computation §4 budgets as configurations 22-24. Whether it consumed them is yours to rule on under §4/§A.1, but it is no longer true that V4's training answer is unseen, and nothing below should be read as if it were. Scripts: `.../scratchpad/v4_machine.py`, `v4_summary.py`, `v4_power.py`.

Measured, training segment 2018-09-10..2022-12-31 (1,083 sessions, 4.30 yr), 21-23 symbols, QQQ excluded:

| quantity | X=1% | X=2% | X=3% |
|---|---|---|---|
| cross-sectional mean d_s | **-3.19%/yr** | **-3.64%/yr** | **-3.37%/yr** |
| median d_s | -3.97% | -6.36% | -3.65% |
| **min OUT-episode factor P_reentry/P_exit, all symbols** | **1.010000** | **1.020000** | **1.030000** |
| mean time in market | 15.5% | 25.0% | 35.5% |
| symbols ending training in an open, underwater OUT episode | **21/21** | 21/21 | 20/21 |
| mean d_s with that terminal stub neutralised | **-8.57%** | -8.74% | -7.92% |
| per-symbol tracking error of d_t | 24.9%/yr | 24.5%/yr | 24.1%/yr |
| rho_bar of **rule returns** (§6 as written) -> N_eff | 0.106 -> **6.31** | 0.160 -> 4.78 | 0.204 -> 3.99 |
| rho_bar of **d_t**, which sets SE(mean d_s) -> N_eff | 0.627 -> **1.54** | 0.625 -> 1.55 | 0.624 -> 1.55 |
| SE(cross-sectional mean d_s) | 10.5%/yr | 10.2%/yr | 10.0%/yr |
| **MDE @80% power at §8's p<0.00208** | **38.7%/yr** | 37.9%/yr | 37.2%/yr |

Years required at §8's threshold, project's own A.5(a)/`power_gate_result.md` formula: 1%/yr edge -> 5,500 yr; 3%/yr -> ~600 yr; 5%/yr -> ~215 yr; 10%/yr -> ~53 yr; 20%/yr -> ~13 yr. Available: **4.30**.

Four consequences that no reviewer had:

- **The identity is exact on real data.** Across roughly 2,000 completed OUT episodes spanning 21 symbols and three X, the minimum of P_reentry/P_exit is *exactly* 1+X to six decimals. Findings 1, 5 and 6 are not a worry; they are arithmetic, confirmed.
- **A2 already fires.** Mean d_s is negative at all three X. The preregistration's terminal conclusion is determined.
- **§0's premise is false, and measurably so.** The cross-section's independence is governed by the correlation of the *difference* series, which is 0.62-0.63 because all 23 symbols go OUT in the same drawdowns. 23 symbols buy a factor of **sqrt(1.55) = 1.24** on the SE, not sqrt(23) = 4.8. Worse, §6's diagnostic measures rho_bar on *rule returns*, which is 0.11-0.20 only because the rule is in cash 65-85% of the time and cash returns are uncorrelated zeros. So **A3 and E3 read N_eff = 4.0-6.3 and issue a pass**, while the number that governs the p-value is 1.55. The one safeguard pointed at the power problem is reading an instrument that cannot see it. (This is *not* the refuted rho_bar finding, whose stated mechanism ran the other way — "the rule is long most of the time... rho_bar measures asset-class composition." The measured sign is the opposite and the consequence is anti-conservative, not conservative.)
- **New, and nobody raised it:** an overnight-return screen over all 23 raw series returns exactly three exceptions above 20%: USO 2020-03-09 (-21.9%, a genuine oil move), USO 2020-04-29 (**+745.5%**), and **2025-12-05 on XLB, XLE, XLK, XLU and XLY (-49.8% to -50.1% each)**. The second is the 1-for-8 USO reverse split Finding 4 predicted (close 2.13 -> open 18.01, volume 146M -> 22M). The third is an unadjusted **2-for-1 forward split across five SPDR sector funds on one shared date** (XLK 291.07 -> 146.21, XLY 238.14 -> 119.18, etc., volume roughly doubling; XLF on the same date is untouched, so it is corporate action, not a data fault). **2025-12-05 sits inside §7's test segment** — the project's single, once-only, irreversible final-test opening.

---

## 1. REVISION LIST

### EDIT 1 — §3 OUT state (lines 73-75). Findings 1, 5, 6. FATAL. Not fixable inside V4.

**Currently:**
```
OUT  : hold cash, earning ZERO. Re-enter when price trades X above the exit price.
       There is no timer and no second threshold.
```

**Mechanism, restated as the identity it is.** Both rule and benchmark hold the same instrument at full NAV (§3 L86, §5 L113), so their wealth curves are products over the same partition of time and differ only where one is flat. The flat legs are the OUT episodes. §3 pins each completed episode's terminal price at P_exit(1+X), and §3a can only push the refill *above* that, never below. Hence

```
ln(W_rule/W_hold) = - SUM_completed_OUT ln(P_refill/P_exit)  - SUM_TP_hops ln(o_next/P_tp)
                    - ln(P_T/P_exit_last)[terminal stub]      - fees
```
with every term in the first sum >= ln(1+X) > 0, **independent of the path inside the episode and independent of whether H1 or H0 holds**. The rule is out of the market only over stretches whose end-to-end return is exactly +X. §1 L30-32 ("out of the market disproportionately during bad stretches, and can beat holding") is therefore false for the rule in §3, not merely optimistic. It sits out the crash and the entire recovery back to X above where it sold, and the holder recovers too.

**No edit to §6, §8 or §9 repairs this,** because the defect is that the statistic is decoupled from the hypothesis, not that it is measured badly. The two repairs the reviewers propose are:

- (a) **Shadow ±X chain while OUT** — walk the disjoint chain `reentry_chain.py` already builds from the bar after each resolution, re-enter when a shadow race resolves +X first, re-anchoring X lower after each adverse shadow race. The OUT interval then returns (1-X)^k(1+X)-1, negative for any k>=1, so stepping aside can pay, and the re-entry event becomes exactly H1's conditioning event. Costs no extra free parameter, so §3 L77-78's budget rationale does not block it.
- (b) **Timer re-entry** — removes the pin but adds a second parameter, which §3 L77-78 forbids.

**Both are barred by §4 L107-109 as written:** "a second re-entry threshold... is not a refinement of V4, it is a new search requiring a new budget and a stated reason." A re-entry rule whose fills can land below the exit price is a different strategy. So the honest edit is not a patch to §3 — it is:

> **§3 must be retired as a return-generating rule, and §1 L30-32 struck.** If the shadow-chain variant is wanted, it is V5 with its own budget, its own §A.5(a) submission, and its own commit. It may not be run under V4's remaining configurations.

If the document is nonetheless kept alive in any form, §1 and §6 must additionally carry the sentence that is currently missing everywhere: *"By §3's re-entry anchor, every completed OUT episode hands buy-and-hold exactly +X and the rule 0. d_s is therefore bounded above by the terminal open OUT episode minus fees, and cannot be positive for any reason connected to H1."* §3 L80-82 currently concedes only the zero cash yield and asserts the accepted biases "run against the hypothesis" — that framing is what makes the pin dangerous, because the pin is 5-7x larger than every acknowledged conservatism combined and is disclosed nowhere.

**Trim these overstatements before they enter the record.** The reviewers' magnitudes are wrong by 3-20x. "~190 adverse exits/yr", "-66%/-47%/-37% per year", "10^2 completed OUT spells per symbol-year" all import swing_verdict §3's trade counts from the *always-in* chain. Measured: 7-25 completed OUT episodes per symbol-year at X=1%, falling to 2-5 at X=3%, and structural drag of 3-9%/yr, not 40-80%. "Zero power against H1" is also loose — d_s depends on H1 weakly through the episode count. It has zero power against the *preregistered decision rule*, which is what matters. The sign is unaffected by all three corrections.

### EDIT 2 — §4 and §8: the missing ex-ante power gate. Findings 3 and 7. FATAL, and it is the cheapest exit.

**Currently:** §4 L102-109 is grid and budget only. §8 L151-157 states the threshold and nothing else. The strings "power", "detectable", "standard error", "MDE" and "A.5" do not appear anywhere in the 200-line document. V1 L11 opens on the gate and records it failing; V2 L23-26 submits the arithmetic and states the gate passes; V3 L18 argues an exemption on the ground that V3 "makes no prediction". **V4 is the only candidate in the project that neither submits the calculation nor argues its way out**, and §1 H1 is an explicit directional prediction, so V3's exemption cannot transfer.

**Must say instead — insert as §4a, before §9, with these measured numbers, not assumed ones:**

> **4a. Ex-ante power gate (`selection_criteria.md` §A.5(a)).** Training segment 4.30 years. Per-symbol tracking error of d_t, measured on the frozen universe: 24.1-24.9%/yr (range 16.1-38.7%), high because the rule holds cash 65-85% of the time and therefore deviates from a full-NAV benchmark by most of the benchmark's own volatility. Mean pairwise correlation of the per-symbol d_t series: 0.62-0.63, giving N_eff = 1.54-1.55. SE of the cross-sectional mean d_s = 10.0-10.5%/yr. Minimum detectable cross-sectional mean d_s at 80% power and §8's p<0.00208: **37.2-38.7%/yr**. Uncorrected at alpha=0.05 it is still 28.1-29.3%/yr. Years required: 5,500 for a 1%/yr effect, ~600 for 3%/yr, ~53 for 10%/yr, ~13 for 20%/yr, against 4.30 available.
>
> **A0 (stated before A1).** If the minimum detectable cross-sectional mean d_s exceeds the largest d_s plausibly available from this family, V4 is rejected **without a backtest**, per A.5(a). Plausible d_s for this family is 1-3%/yr; swing_verdict §3 puts the realised barrier family at -1.31% to -37.05%/yr versus holding. **A0 is triggered.**

Also add to §11: *a null at this SE is reported as a power rejection, not as evidence about H1.* As written, §11 L198-199 converts a preordained null into "H1 unsupported, search over" — the exact failure `power_gate_result.md` L98-101 exists to prevent.

**Conflict resolved: Finding 3's headline fix is rejected.** Both skeptics independently refuted the "Bonferroni family is 3, not 24" limb, and they are right. The 21 prior configurations are three prior *candidates* (`preregistration_v3.md` L4-5: "V1 used 9, V2 used 6, this uses 6... 21 of the 24"), not the barrier family — swing_verdict §6 L129 says that work "spent no further configurations." V1 and V2 tested the same operational null (beat buy-and-hold on the same instrument family), and `selection_criteria.md` §A.1 forecloses the instrument carve-out explicitly: "a different instrument does not exempt them." **Keep /24.** It is also immaterial: the measured MDE moves from 38.7% to 29.3%/yr if you delete multiplicity control entirely. Adopt only Finding 3's third prong, which is Finding 7's, which is EDIT 2. The step-down max-T over the three X is correct textbook practice and slightly more powerful; it is a refinement worth at most 2.7pp of MDE and should not be traded for the /24 breach.

**Correction to both reviewers, in the direction that makes it worse.** Finding 7 assumed TE ~12.6%/yr at 60% exposure; Finding 3's skeptic assumed 13.4%. Measured TE is **~25%/yr**, because measured time in market is 15-36%, not 60-85%. Finding 3's skeptic guessed N_eff for the differences "plausibly 5-7"; measured, it is **1.55**. Both errors run the same way. The gate fails by ~100x, not by the ~3-15x either argued.

### EDIT 3 — §2, corporate-action screen. Finding 4, extended. MATERIAL in training, FATAL for the test segment.

**Currently (L54-56):** "Survivorship: none of the 23 was delisted or merged over the window..." — delisting and merger only. The words split, corporate action, adjustment and rehab appear nowhere. The series is `AuType.NONE` (`tools/pull_intraday.py:54`, `intraday_data.md` §4, `bars.py:21`), so splits are live in the prices. `BarSeries.validate()` (bars.py:307-388) checks within-bar OHLC, session shape and intra-session 5-minute gaps; an 8x jump *between* sessions is invisible to every one of them, and `missing_sessions` passes too.

**Must say instead — add to §2 before the universe is frozen:**

> **Corporate actions.** The series is raw (`AuType.NONE`) and therefore carries split discontinuities. Before any d_s is computed, `get_rehab` is called for all 23 symbols over 2018-09-10..2026-09-11 and every populated `split_ratio` is listed; independently, every overnight raw return whose magnitude exceeds 20% is listed and reconciled against that record. This is a listing-and-adjudication step, not a hard assert — legitimate March/April 2020 moves will appear. Screen already run; the exceptions are:
> - **USO 2020-04-29, +745.5% (1-for-8 reverse split), inside the training segment.** Close 2.13 -> open 18.01; volume 146M -> 22M.
> - **XLB, XLE, XLK, XLU, XLY 2025-12-05, ~-50% each (2-for-1 forward split), inside the TEST segment.** XLF on the same date is unaffected.
> - USO 2020-03-09, -21.9%: genuine, no action.
>
> Disposition, recorded before the pull: each affected symbol is carried on a split-adjusted-but-not-dividend-adjusted series with the adjustment method recorded in the manifest, or the exclusion is recorded as a mechanical data fact. Whichever is chosen, it is chosen from the `get_rehab` record, never from what the returns turn out to show.

**Also amend A5 (L170-172)** to remove the three largest **absolute** per-symbol contributions, not the three largest positive ones. As written A5 passes a large *negative* single-symbol artefact straight through to A2.

**Do not adopt** the reviewer's proposal to drop USO on the ground that "its index methodology was rewritten repeatedly" in 2020. That is a judgement about instrument quality, and §2 L47-48 ("membership-defined, not performance-defined") exists to keep judgement out of the universe. Excluding on the verifiable split is legitimate and has direct precedent (`selection_criteria.md` §3, SPY/BIL revised on "a data fact discovered before any backtest was run"); excluding on methodology, after reading about April 2020, is the post-hoc universe selection §2 was written to prevent.

**Why the 2025-12-05 cluster is the more serious half.** USO is 1 of 23 in training and its worst-case effect on the headline is ~2.3pp. The sector splits are **5 of 23 on one shared date in the segment §7 opens exactly once**, all in the equity block — so A6 (equity vs non-equity sign reversal) cannot see it, A5 (three largest contributions) cannot see five, and A7 only *voids* a run after the fact, which with the budget at 24/24 leaves no legitimate re-run. Whatever else is decided, this screen must be run and its disposition committed **before** the test segment is ever opened, by V4 or by anything that replaces it.

### EDIT 4 — §6 L127-133, resampling object and block length. Finding 2. MATERIAL (downgraded from fatal; one skeptic refuted it, one upheld it at material).

**Currently:**
```
Primary test: stationary block bootstrap over TIME, resampling blocks simultaneously
across all symbols...
- Block length: 21 sessions (one month), frozen.
```

**Two sub-claims survive; two do not.** Sub-claim (a) has the bias backwards — drawing whole blocks widens the resample distribution relative to iid, it does not narrow it, and "the variance of averaging ~52 already-aligned blocks" *is* the target estimand. Sub-claim (b) (stitched price blocks, ~51 artificial joins firing barriers) attacks an implementation the text does not describe: L128-129's "preserves whatever cross-sectional correlation exists on each resampled date" and L137's "per-symbol daily rule returns" only make sense for a date-indexed return panel. Sub-claim (d) is a terminology nit — Politis-Romano's stationary bootstrap is parameterised by an *expected* block length, so "block length 21" reads naturally as mean 21.

**Sub-claim (c) is right, and I measured it.** Pooled OUT-episode dwell across the cross-section:

| X | episodes | median | p90 | max | episodes > 21 sessions | share of all OUT time they carry |
|---|---|---|---|---|---|---|
| 1% | 474 | 3 | 38 | **857** | 66 | **81%** |
| 2% | 263 | 6 | 66 | 856 | 63 | **85%** |
| 3% | 152 | 11 | 99 | 855 | 59 | **90%** |

d_t is approximately -1{OUT_t}·r_t: ~0 while IN, minus the market while OUT. Its dependence length is the OUT-episode length, and 81-90% of OUT time sits in episodes longer than the block. A 21-session block chops a single draw of the state process into a dozen or more exchangeable units, so replicate-to-replicate variation becomes Binomial block-count sampling rather than the in-or-out variation of one episode — anti-conservative, i.e. the direction that manufactures significance against a 0.00208 threshold.

**Must say instead:**

> - Blocks are drawn on the session axis of the date-aligned panel of realised per-symbol daily rule and hold returns. The state machine is run **once** on the true price series and is **not** re-run on resamples.
> - Moving-block with fixed L, or stationary with geometric mean L — state which.
> - **L = 63 sessions**, set from the p90 of the realised OUT-dwell distribution rather than from the trade horizon. Sensitivity grid L in {21, 42, 63, 126} frozen now, p reported at every L, with L = 63 the decision and the others diagnostics that can only abandon, never rescue.
> - **New abandon condition, temporal analogue of A5:** removing the single largest OUT episode per symbol, or excluding calendar 2022, must not turn the training-segment mean d_s negative. §9 currently has no temporal robustness check of any kind — A3/E3 are cross-sectional and A5 is per-symbol.

**Do not adopt the reviewer's headline fix.** "Resample whole STATE EPISODES" cannot be done "simultaneously across all symbols" because episode boundaries are asynchronous across 23 symbols; adopting it would draw 23 correlated crash episodes as 23 independent units, destroying the cross-sectional correlation control that is §6's entire stated purpose (L122-126) and biasing p downward. Both skeptics converged on this and they are right. Also do not set L from a data-dependent quantile *and* report p at every L with no combination rule — that is a fourfold researcher degree of freedom the frozen threshold does not price. Freeze the grid and name the decision value.

### EDIT 5 — §5 L114-116 vs `selection_criteria.md` §A.3. Tension that must be resolved in the freezing commit, not left to the result.

§5 says "Nothing else is a benchmark. Not cash..." A.3 L302-305 mandates four comparators including the static de-risked blend `w·asset + (1-w)·cash`. Both reviewers' skeptics correctly note that Appendix A is headed "NOT ACTIVATED" (L266-267) — **but that header is stale**: `power_gate_result.md` L3-5 records A.5(a) being applied the next day as binding, V1 L11 and V2 L23 honour it, V3 L18 had to argue an exemption from it. The project has activated Appendix A in practice for A.5(a) and cannot selectively treat A.3 as dormant.

This matters because the rule holds cash 65-85% of the time, so §3 L80-82's "cash earns zero... the bias runs against the hypothesis" is not the rounding error it reads as — at 15-36% time in market the foregone T-bill yield over 2018-2022 is most of the distance to an honest benchmark. **Resolve explicitly in the commit that freezes V4:** either activate A.3's fourth comparator and strike §5 L115's "Not cash", or state in §5 why a rule that is flat 65-85% of the time may be priced against a 100%-invested benchmark alone. Do not let the result decide which.

**Conflict note.** Finding 1's fix option (a) — change d_s to a risk-adjusted statistic and admit the de-risked comparator — collides with Findings 5/6's fix — change the OUT rule. **Neither wins, because both are out of scope under §4 L107-109 and §A.1.** Changing the primary statistic *now*, when the training answer has been computed and is negative, is precisely what §A.1 calls permanent rejection: "Changing parameters, benchmarks or the objective function after seeing a result permanently rejects that candidate. It may not be revived under the name 'robustness check'." The benchmark question above is a disclosure to resolve, not a statistic to swap.

---

## VERDICT

**V4 should not be run. It should be rejected without a backtest, under `selection_criteria.md` §A.5(a), and the remaining configurations should not be spent on it.**

Not because the patches above are hard, but because the two fatal defects point in opposite directions and there is no design that satisfies both inside this budget.

**The power arithmetic is the decisive one, and it is now measured rather than assumed.** The minimum detectable cross-sectional mean d_s is 37-39%/yr at §8's threshold, 28-29%/yr if you delete multiplicity control entirely. A 3%/yr effect needs ~600 years; there are 4.30. This is the same wall `power_gate_result.md` hit, worse in every term: a *shorter* calendar sample (4.30 training years against QQQ's 7.98), a *higher* tracking error (~25%/yr against 17%, because 15-36% exposure deviates further from a full-NAV benchmark than 50% does), and a cross-section that supplies a factor of **1.24** on the standard error rather than the 4.8 that independence would give. §0's stated reason for V4's existence — "the shortfall was in independent observations and the cross-section is where more of them live" — is the one claim in the document that was checkable with no configurations spent, and it is false by roughly a factor of four. The failure is not a property of the rule. `power_gate_result.md` L67-70 named the binding quantity three days ago and V4 did not read it: a long/flat overlay measured against buy-and-hold on a ~20-25% volatility universe carries a denominator no 4.3-year sample can resolve, and a skilful rule and a worthless one carry the same denominator.

**The OUT anchor is the second, and it is what makes patching pointless.** Repairing §3 so d_s can respond to H1 (shadow chain, or a timer) does not improve any term in the power calculation — it may raise exposure and cut TE somewhat, but TE stays in the high teens and N_eff stays near 1.5 because all 23 symbols step aside in the same drawdowns. You would be buying a statistic that is no longer arithmetically pinned, and still cannot be resolved. And per §4 L107-109 that repair is a new search needing a new budget, so it cannot be done under V4 in any case.

**Running it as written would put a false finding into the permanent record, which is the specific harm.** A2 fires — measured, at all three X. §9 A2 is phrased as an empirical result ("The rule loses to holding on average; no p-value can rescue that") and §11 L198-199 converts it into "H1 unsupported, search over." That sentence would record a rejection of short-horizon state dependence produced by ln(1+X) and a fee schedule, from a design that could not have registered the effect if it were real — the same failure mode as the daily-loss halt that made an entire experiment measure an artefact, and exactly what `power_gate_result.md` L98-101 says the gate exists to prevent.

**And the pass branch would be worse than the fail branch.** The only channel that can make d_s positive is the terminal open OUT episode, and it is not hypothetical: **21 of 21 symbols end the training segment sitting OUT with price below their last exit.** It is worth +5.4pp on the cross-sectional mean (-8.57% without it, -3.19% with it). It is one common event — where the calendar was cut, near a cyclical low — shared by every symbol, so its effective independence is 1, and §6's block bootstrap cannot generate a sampling distribution for where the window ends. A5 cannot see it because it is in all 23, not three. A6 cannot see it because 2022 hit both blocks. E3 cannot see it because §6's N_eff diagnostic reads 4.0-6.3 off rule returns that are mostly cash. A pass would be the 2022-12-31 boundary, reported as cross-sectional evidence for H1.

**What replaces it.** Three things, in order:

1. **Record the A.5(a) rejection as the result.** It is a real result, it cost no configurations, and it has precedent in this project — `power_gate_result.md` is exactly this and is filed "as a result in its own right, not as a setback." It preserves whatever remains of the budget, which patching V4 would not.
2. **If H1 is still worth measuring, measure H1 and stop dressing it as a strategy.** Per symbol, build the disjoint ±X chain, form the 2x2 previous-outcome × next-outcome table, and estimate Δ = P(+X | prev +X) − P(+X | prev −X) with the block bootstrap resampled simultaneously across symbols. That statistic *is* §1's H1. It needs no fee model, no state machine, no exposure adjustment and — critically — **no buy-and-hold denominator, so the tracking-error wall does not apply to it.** Two cautions. First, `tools/reentry_chain.py` as it stands computes `lift = cond − base` (line 99), i.e. P(win|prev win) − P(win), not H1's contrast; it needs the two-sided conditional and its own SE. Second, this is a new measurement and owes its own §A.5(a) submission before it runs — swing_verdict §2's 32-3,412 years against a cross-section worth 2-4x may well fail it too, and if it does, that is the answer.
3. **Run the corporate-action screen regardless of what happens to V4**, and commit its disposition before the test segment is opened by anything. The 2025-12-05 2-for-1 split across XLB/XLE/XLK/XLU/XLY sits in the one segment the project gets to open once, on five of its 23 symbols, and no abandon condition in §9 can see it.

The honest summary for the log: V4 asked whether the cross-section could supply the independent observations QQQ lacked. It can be answered without spending a configuration, and the answer is no — 23 co-moving ETFs measured as long/flat overlays against their own buy-and-hold supply about 1.5 independent units, not 23. The rule's re-entry anchor is a separate and equally disqualifying defect, but it is the second reason, not the first. `power_gate_result.md` L111 already named the only unexplored direction: abandon the timing-overlay framing, and test something whose signal is not competing against a 20-25% volatility benchmark. V4 changed the instrument count and kept the framing.