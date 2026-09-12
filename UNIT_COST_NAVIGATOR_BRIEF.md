# Unit Cost Navigator — Master Brief

*Paste this whole document into a fresh AI chat (or hand it to a developer) any time you want help continuing this project without re-explaining everything. It is written so an AI reading it cold has full context.*

---

## 1. What this is

**Unit Cost Navigator** is a web-based tool that calculates the unit cost (N$ per metre) of underground development, split into drilling consumables and ground support consumables, relates that cost to development productivity (metres advanced per shift), and models how productivity improvements dilute fixed labour/machine cost. It was built for a specific case study — Irene Kavhura's UNAM Honours research at Navachab Gold Mine — but it must work for **any** underground mechanised mine, because the goal is for other mining companies to eventually use it with their own data and their own cost figures.

Two audiences must both be satisfied by the same tool:
- **Academic**: it must visibly and completely answer the four research objectives/questions below, with a defensible methodology, in a way a supervisor can review.
- **Operational**: a mine manager must be able to open it on any random day and immediately see what has been spent so far, without waiting for month-end — and must get cost per drilled metre in addition to cost per metre advanced.

## 2. The research this must answer

Source: Irene Kavhura's UNAM research proposal, *"Assessment of Drilling and Ground Support Operational Cost for Underground Development Advancement at Navachab Gold Mine."*

**Main objective:** assess the operational costs of drilling and ground support consumables for underground development advancement, and determine how productivity affects development unit cost.

**Specific objectives / research questions (quoted, these are the contract — every one must have a visible, numbered answer in the tool):**
1. What is the current unit cost (N$/m) of drilling consumables (drill bits, rods, shanks, couplings) per metre of underground development advance?
2. What is the current unit cost (N$/m) of ground support consumables (rockbolts, mesh, bearing plates, resin/grout, shotcrete) per metre of underground development advance, and which items contribute most to this cost?
3. What is the current average development advance rate (metres per shift) at the underground development headings?
4. What is the quantified impact on total development unit cost of defined advance-rate improvement scenarios, given fixed labour and machine rates?

**Supervisor's feedback (Mrs. Nekwaya, received after reviewing progress):** direction is confirmed correct. Next stage: complete and verify the cost/consumption data, calculate cost per metre for each consumable category, establish metres advanced per shift, then analyse the relationship between productivity and total development unit cost with labour and machine costs treated as fixed inputs — **and investigate and explain any discrepancies between the different records before finalising the calculations.** That last instruction is not optional decoration: the discrepancy explanation (physical stock vs. logged usage vs. theoretical/design requirement, and *why* they differ) is itself a required, graded piece of the analysis, not a footnote.

**The three formal equations from the proposal (use these exact forms):**

```
UC_drill   = (C_bits + C_rods + C_shanks + C_couplings) / m
UC_support = (C_bolts + C_mesh + C_plates + C_resin/grout + C_shotcrete) / m_supported
UC_total   = (C_labour + C_machine) / A  +  (UC_drill + UC_support)
```
where C_x are total issue/installed costs (N$) of each item over a period, m is metres advanced, m_supported is metres of development supported, A is advance rate (m/shift), and C_labour / C_machine are fixed cost per shift.

**Five-step data analysis method from the proposal (mirror this structure in the tool's flow):**
1. Drilling consumable unit cost (Equation 1), calculated monthly and per heading, plus per-item cost/metre to see which items drive cost.
2. Ground support consumable unit cost (Equation 2), actual consumption per metre compared against design consumption rates from the ground support design sheets.
3. Classification of over-consumption causes into exactly two categories: **geotechnical necessity** (poor/variable ground beyond design assumptions, evidenced by design sheets/observations/interviews) vs. **operator-related waste** (material wastage, incorrect installation, re-drilling/re-blasting). This is a required judgement call, not just a number — the tool must give the user a place to record which bucket each discrepancy falls into and why.
4. Productivity baseline (average advance rate m/shift with standard deviation) and the unit cost sensitivity model (Equation 3), run for at least three scenarios: current advance rate, +15%, +30% (the proposal's own stated scenario set — a later conversation with the mine manager also wants a freely adjustable version of this, so make the percentages user-editable but default to 0/15/30).
5. Pareto analysis ranking all individual consumable items by cost-per-metre contribution, to identify the 3–4 items driving most of the cost.

**Delimitations already agreed and must be respected:** the study (and therefore the tool) covers drilling consumables (DC) and ground support consumables (GSC) only — blasting, mucking, haulage, and support-installation labour are explicitly out of scope. Labour and machine costs are fixed inputs, not disaggregated. Findings are specific to the site's own data; the tool must not claim its Navachab-derived numbers generalise to another mine, even though the *tool itself* is meant to be reusable elsewhere with that mine's own numbers.

## 3. What changed since the first build, and why

The first version of this tool (a Streamlit app called "Navachab Development Unit Cost Analyzer") was a generic upload-and-map tool: the user uploads a workbook, tells it which column means what, and it computes the four sections above. It worked correctly, but it failed the actual assignment in two ways worth stating plainly so they don't happen again:

- **It never had real data in it**, so every screen showed "Data not available" and looked like nothing had been achieved — four months of fieldwork produced no visible analysis. A tool that only ever demos empty state is not a deliverable.
- **It was one long scrolling page of tabs and forms**, which reads as cluttered and unfinished rather than as a polished result a mine manager or a supervisor would want to look at.

Two new hard constraints also emerged from a conversation with the mine and the mine manager:

- **Navachab will not share its fixed labour and machine cost figures.** This directly touches Objective 4 and Equation 3, which need C_labour and C_machine. The resolution: fixed costs are a **user-entered input**, never something the tool tries to source, scrape, or assume from the mine's own systems. This is not a workaround, it's now a design principle — it is also exactly what makes the tool sellable to a second, third, and fourth mine: each one plugs in its own consumable list, its own prices, and its own fixed costs, and gets its own unit cost model out.
- **The mine manager wants to check spend on demand ("a random Tuesday"), not just at month-end.** This does not require a database or a live system rebuild: it requires that whenever fresh stores-issue and production data is dropped into the tool (a five-minute export from whatever system the mine already uses), every number on every screen recalculates immediately from that data, with no month-end batch step and no re-deriving anything by hand. The tool must make this feel instant, and should visibly show *what date range the currently-loaded data covers* so nobody mistakes a stale figure for today's. If a future version should watch a shared folder for the latest export automatically, that's a reasonable stretch goal but is not required for v1.

Also raised, and both must be built in:

- **Cost per drilled metre, in addition to cost per metre advanced.** These are different things and both matter. *Metres advanced* is the net tunnel progress after blasting (what the mine manager ultimately pays for). *Metres drilled* is holes × hole depth — the actual drilling activity, before blast efficiency, overbreak/underbreak, or re-drilling change how much of that becomes real advance. Drilling consumables (bits especially) wear as a function of metres *drilled*, not metres *advanced*, so cost-per-drilled-metre is the more mechanically honest way to judge bit/rod economics, while cost-per-metre-advanced is what the mine manager needs for budgeting. Report both, and don't quietly conflate them.
- **A drill bit (and, in principle, other consumable) life and resharpening economics module.** See the worked example below — this became a real, needed piece of the model, not a side note.

## 4. The button-bit resharpening study — what it means and how to build it in

Data collected on site, 45 mm button bits, 4.2 m hole depth:

| Portal | Holes before resharpening | Holes after resharpening | Total holes | Total metres drilled |
|---|---|---|---|---|
| North | 30 (126.0 m) | 20 (84.0 m) | 50 | 210.0 m |
| South | 30 (126.0 m) | 25 (105.0 m) | 55 | 231.0 m |

**What this tells you:**

- The **fresh-bit life before any resharpening was identical in both portals (30 holes / 126 m)**. That's a useful baseline: a new bit's initial life doesn't yet show a portal difference.
- The **resharpening yield differs**: north recovered 20/30 = **66.7%** of its original hole count after resharpening; south recovered 25/30 = **83.3%**. South's resharpened bit clearly outlasted north's.
- This is a plausible, reportable *mechanism* behind the ground-support and drilling over-consumption differences you already track by portal (north being predominantly GSS_02/GSS_03 — fair-to-poor ground — versus south's largely GSS_01 good ground): harder or more fractured rock may be wearing down a *re-ground* edge faster than it wears down a *factory-fresh* edge, which would explain why the difference only shows up after resharpening, not before.
- **Be honest about the sample size in the report**: this is one bit-life cycle per portal (n = 1 each). It is a real, useful, reportable observation and a good example of exactly the kind of discrepancy-explanation your supervisor asked for — but it is not yet statistically established. Recommend collecting several more paired bit-life records (ideally 5–10 bits per portal) before stating "resharpened bits last longer in the south" as a finding rather than a preliminary indication. The tool should support recording many such bit-life records over time and will get more confident automatically as more come in — don't hardcode "n=1" assumptions into the module.

**Illustrative economics this unlocks** (using a placeholder bit price of N$850 and a placeholder resharpening service cost of N$150 — replace with real site figures, never ship the placeholders as if they were real):

- Without resharpening, cost per drilled metre from bit spend alone ≈ N$6.75/m in both portals (bit price ÷ pre-resharpen metres — identical because pre-resharpen life was identical).
- With resharpening: north ≈ N$4.76/m (a 29% saving over not resharpening), south ≈ N$4.33/m (a 36% saving).
- This is a genuine, quantified case for resharpening as a cost-reduction lever, and it is portal-specific, which is exactly the kind of "which lever matters where" insight the Pareto/discrepancy sections are supposed to produce.

**Build this in as its own module** ("Drill Bit Life & Resharpening"), separate from the main four objective pages, with:
- Input fields per bit record: portal/heading, bit spec (e.g. diameter), hole depth, holes drilled before resharpening, holes drilled after resharpening (repeatable — a resharpened bit could in principle be resharpened again), bit purchase price, resharpening service cost.
- Computed per record: total lifetime holes/metres, resharpen yield %, cost per drilled metre with vs. without resharpening, % saving.
- Aggregated across all recorded bits: average resharpen yield by portal/ground class, with a visible sample-size count so nobody mistakes 2 data points for a trend.
- This module's output (cost per drilled metre) should feed into, and be shown alongside, the Objective 1 drilling unit cost page — not live in total isolation.

## 5. Raw data vs. the cost model — what to actually hand over

Your own proposal already answers this in Section 3.5 (Validity, Reliability and Ethics) and Section 1.6 (Limitations): *"All raw data and Excel workbooks will be retained and made available for verification by the supervisor,"* and *"Commercially sensitive financial data provided by the mine will be subject to confidentiality restrictions, which may limit the level of cost detail published in the final report."*

Practically, that means:
- **To your supervisor**: keep the raw stores/production records and full Excel workbook available and offer them for verification, but the graded deliverable is the analysis (report + tool + summarised Excel model), not a data dump. Reference the raw data as retained evidence, don't bury the findings in it.
- **To the mine manager**: the same principle, doubled — mine managers do not want to sift stores ledgers, and Navachab's own confidentiality stance means granular commercially-sensitive figures (exact unit prices, exact quantities by supplier) probably shouldn't circulate broadly anyway. Give them the tool (live numbers, trends, Pareto, recommendations) and, if asked, a separate confidential appendix.
- **Never publish raw commercially-sensitive data inside the tool's shareable/demo view** — if the tool is ever shown to a second mining company, their competitors must not be able to infer Navachab's actual prices from a leftover demo dataset.

## 6. Design requirements for the rebuild

**Multi-tenant / configurable, always:**
- Never hardcode a consumable list, a price, or a fixed cost. Every mine that uses this brings its own item list (still bucketed into Drilling vs. Ground Support), its own unit prices, and its own labour/machine cost per shift, entered directly.
- The existing "map your uploaded sheet's columns to a role" approach from v1 is the right underlying mechanism for this — keep it — but it should live inside a clearly separate **Setup** step, not be interleaved with the results.

**Navigation: paginated, not one long scroll.**
- Structure it as a guided sequence of focused screens, e.g.: Overview → Setup (data + fixed costs) → Objective 1: Drilling Unit Cost → Objective 2: Ground Support Unit Cost → Drill Bit Life & Resharpening → Objective 3: Productivity Baseline → Objective 4: Sensitivity Model → Discrepancies & Recommendations.
- Only one screen's content is visible at a time, with clear Next/Back or a persistent side-nav to jump between them — never all of it stacked and scrolling on one page.
- Each screen should read like a finished result (headline numbers, one focused chart, a short plain-English takeaway), not a form waiting to be filled in, once data is loaded.

**Discrepancy explanation is a first-class feature, not an afterthought.**
- Every reconciliation (physical stock vs. logged usage vs. theoretical/design requirement) needs a visible, editable classification: geotechnical necessity vs. operator-related waste, per your methodology's Step 3 — with a short text note field so you can record *why*, ready to quote in the report.

**Zero-hallucination, unchanged from v1:** nothing is estimated; a metric with no backing data shows "Data not available," never a blank, a dash, or an invented zero.

**Report both cost bases, clearly labelled:** cost per metre advanced (for every objective, matching the proposal's equations) and cost per drilled metre (drilling consumables specifically, and the bit-life module).

**On-demand/live framing:** show a visible "data as of [date range of loaded records]" indicator on every page, so a mine manager checking on a random Tuesday can see immediately how current the numbers are, and reloading with a fresh export should be a single obvious action, not a multi-step re-configuration.

**Name:** *Unit Cost Navigator*.

## 7. What "done" looks like

Every one of the four research questions in Section 2 has a page with a real, numbered answer (not "Data not available") once real data is loaded, plus: a Pareto ranking of cost drivers, a discrepancy log with geotechnical-vs-waste classification and notes, a drill bit life & resharpening module producing cost-per-drilled-metre, a sensitivity model with editable advance-rate scenarios, and a setup step where fixed costs and consumable prices are entered directly rather than assumed — all navigable as separate, uncluttered screens, all reusable by a different mine with different numbers.
