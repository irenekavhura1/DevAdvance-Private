UNIT COST NAVIGATOR — real-data build (September 2026)
========================================================

HOW TO RUN
----------
1. Keep every file in this folder together, including the "real_data"
   subfolder — the app expects real_data\ to sit right next to app.py.
2. Double-click Start_Cost_Analyzer.bat. It will set up Python packages
   the first time (needs an internet connection once), then open the
   app in your browser at http://localhost:8501.
3. Leave the black window open while you use the app. Closing it, or
   pressing Ctrl+C inside it, stops the app.

WHAT'S IN THIS BUILD
--------------------
This version runs on your actual Navachab/Byrnecut records, not sample
data: the drilling stock-usage master, the live jumbo-linked and
offsider ground support logs, the physical stocktake sheets, the
monthly EOM development reports, the Jumbo PLOD log, and your own
CostModel_to_date.xlsx — all 17 files are bundled in real_data\ and
load automatically. The GSS01/GSS02 drawing PDFs aren't read by the
app directly, but their minimum-quantity-per-cut figures (read from
your CostModel_to_date.xlsx Inputs sheet) were checked cell-for-cell
against the drawings themselves.

Go to Setup first — it lists exactly what loaded, and flags every data
quality issue found along the way (mislabeled price files, a pricing
error worth raising with the stores team, items excluded until their
price is verified). Nothing is hidden or silently fixed; every finding
is shown so you can quote it directly in your report.

A PORTAL CLASSIFICATION BUG WAS FOUND AND FIXED
------------------------------------------------
An earlier version of this app misread the live inventory and Jumbo
PLOD location codes: it treated an "MS" prefix as a shared/main area
and "NS" as a connecting area, which silently erased the South portal
from those two logs entirely. Your own CostModel_to_date.xlsx
(Portal_Analysis and Anomalies sheets) resolves every heading to a
portal and states the real rule for this mine: "MS" headings are
Southern Portal, "NS" headings are Northern Portal (NS = North Shoot),
and more reliably, levels 840-940 are Southern and levels 1020/1040
are Northern. That's now built into the app, and the South portal
shows properly everywhere (Ground Support, Productivity, Drilling).

The ground support design benchmark was also rebuilt on your real,
drawing-confirmed figures (33 MD bolts / 0 split sets / 11 stubby
split sets / 6 mesh sheets per cut for GSS_01; 15 / 18 / 11 / 6 for
GSS_02, with GSS_03 using the GSS_02 figures per your own workbook) —
replacing the earlier placeholder numbers, which were wrong.

WORTH YOUR ATTENTION
---------------------
A few things came out of the real data that are worth a closer look
before you write them up (all flagged in-app, with a pre-loaded row
each on screen 6, Discrepancies & Recommendations):

- MD bolts in the North portal run about 163% above the GSS_02 design
  minimum. The drawing states a MINIMUM, so this is compliance rather
  than automatic over-consumption, but worth confirming with ground
  control — this direction matches your own CostModel Anomalies #4.
- Stubby split sets (0.9m x 39mm) run 75-80% below the design minimum
  in BOTH portals, while MD bolts and 2.4m split sets meet or exceed
  design. This independently reproduces your own CostModel Anomalies
  #3 finding, from a completely different usage stream — worth asking
  whether the 0.9m x 47mm bolt (not on either drawing) is covering the
  gap at the face.
- The live jumbo-linked log, the offsider log, and your own
  CostModel_to_date.xlsx all give a different total ground support
  cost for the same May-Aug window (USD 1.10M, USD 0.35M, and USD
  1.39M respectively) — all three are now shown side by side on the
  Ground Support page for you to reconcile in your report.
- Your own CostModel workbook already flags its whole-mine drilling
  cost total as "Blocking" pending confirmation of the same T45-family
  pricing anomaly this app excludes — likely the main driver of the
  gap between its drilling total (USD 985,916) and this app's
  (USD 213,457), not a new problem.

Full detail on the underlying data (research questions, the cost
model, page-by-page layout) is in UNIT_COST_NAVIGATOR_BRIEF.md in
this folder.
