"""End-to-end sanity check chaining mining_core functions the same way
app.py does, using synthetic data shaped like the mapped role DataFrames
render_role_mapper would produce. This is not real mine data -- it only
exercises the computation path app.py wires together."""

import pandas as pd

import mining_core as mc

# --- synthetic "mapped" inputs -------------------------------------------------
physical_raw = pd.DataFrame({
    "item": ["Drill Bit 38mm", "Extension Rod", "Rock Bolt 2.4m", "Weld Mesh", "Shotcrete"],
    "quantity": [40, 60, 500, 120, 80],
    "date": ["2026-05-01"] * 5,
})

offsider_raw = pd.DataFrame({
    "item": ["Drill Bit 38mm", "Extension Rod", "Rock Bolt 2.4m", "Weld Mesh", "Shotcrete"],
    "quantity": [36, 55, 420, 118, 75],
    "date": ["2026-05-01"] * 5,
})

production_raw = pd.DataFrame({
    "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
    "location": ["Heading A", "Heading B", "Heading A", "Heading B"],
    "shift": ["Day", "Day", "Night", "Night"],
    "metres_advanced": [3.2, 2.8, 3.6, 3.0],
    "metres_drilled": [3.2, 2.8, 3.6, 3.0],
})

unit_prices_raw = pd.DataFrame({
    "item": ["Drill Bit 38mm", "Extension Rod", "Rock Bolt 2.4m", "Weld Mesh", "Shotcrete"],
    "unit_price": [850.0, 620.0, 145.0, 980.0, 2100.0],
})

# theoretical/design quantities (would come from the production sheet, item + theoretical_qty)
theoretical_raw = pd.DataFrame({
    "item": ["Drill Bit 38mm", "Extension Rod", "Rock Bolt 2.4m", "Weld Mesh", "Shotcrete"],
    "theoretical_qty": [38, 58, 380, 110, 70],
})

# --- replicate app.py's wiring -------------------------------------------------
price_table = mc.build_price_table(unit_prices_raw)
physical = mc.add_category_column(mc.attach_cost(physical_raw, price_table))
offsider = mc.add_category_column(mc.attach_cost(offsider_raw, price_table))
theoretical = mc.add_category_column(theoretical_raw)

prod = mc.productivity_baseline(production_raw)
print("Productivity baseline:", prod)
assert prod["total_metres_advanced"] == 3.2 + 2.8 + 3.6 + 3.0
assert prod["shift_count"] == 4
assert abs(prod["avg_advance_rate"] - prod["total_metres_advanced"] / 4) < 1e-9

drill_physical = mc.filter_category(physical, mc.CATEGORY_DRILLING)
drill_offsider = mc.filter_category(offsider, mc.CATEGORY_DRILLING)
drill_theoretical = mc.filter_category(theoretical, mc.CATEGORY_DRILLING)

expected_drill_cost = 40 * 850.0 + 60 * 620.0
total_drilling_cost = mc.total_cost(drill_physical)
print("Total drilling cost:", total_drilling_cost, "expected:", expected_drill_cost)
assert abs(total_drilling_cost - expected_drill_cost) < 1e-6

drilling_unit_cost = total_drilling_cost / prod["total_metres_advanced"]
print("Drilling unit cost (N$/m):", drilling_unit_cost)

gs_physical = mc.filter_category(physical, mc.CATEGORY_GROUND_SUPPORT)
gs_offsider = mc.filter_category(offsider, mc.CATEGORY_GROUND_SUPPORT)
gs_theoretical = mc.filter_category(theoretical, mc.CATEGORY_GROUND_SUPPORT)

expected_gs_cost = 500 * 145.0 + 120 * 980.0 + 80 * 2100.0
total_gs_cost = mc.total_cost(gs_physical)
print("Total ground support cost:", total_gs_cost, "expected:", expected_gs_cost)
assert abs(total_gs_cost - expected_gs_cost) < 1e-6

gs_breakdown = mc.item_breakdown(gs_physical)
print("Ground support breakdown:\n", gs_breakdown)
top_item = gs_breakdown.sort_values("cost", ascending=False).iloc[0]["item"]
assert top_item == "Shotcrete"  # 80*2100=168000 is the largest single line

drill_merged = mc.reconcile_three_streams(drill_physical, drill_offsider, drill_theoretical)
print("Drilling reconciliation:\n", drill_merged)
assert set(["physical_qty", "offsider_qty", "theoretical_qty", "unlogged_variance_qty", "over_consumption_qty"]) <= set(drill_merged.columns)

gs_merged = mc.reconcile_three_streams(gs_physical, gs_offsider, gs_theoretical)
print("Ground support reconciliation:\n", gs_merged)

# catch-up spike flagging should not false-positive on this smooth synthetic data
flagged = mc.flag_catchup_spikes(gs_physical)
assert flagged["possible_catchup_spike"].sum() == 0
print("Catch-up spike flag on smooth data: 0 flagged (expected)")

# now build a small per-shift history for one item with a clear catch-up
# spike (bolting fell behind for a few shifts, then two cycles' worth went
# in at once) and confirm the spike -- not the whole run -- gets flagged
history = pd.DataFrame({
    "item": ["Rock Bolt 2.4m"] * 6,
    "quantity": [48, 52, 50, 49, 300, 51],  # one shift spikes ~6x typical
    "category": ["Ground Support"] * 6,
})
flagged_spiky = mc.flag_catchup_spikes(history)
assert flagged_spiky["possible_catchup_spike"].tolist() == [False, False, False, False, True, False]
print("Catch-up spike flag correctly caught the injected spike and nothing else")

variable_cost_per_metre = (total_drilling_cost + total_gs_cost) / prod["total_metres_advanced"]
fixed_cost_per_shift = 25000.0 + 15000.0
model = mc.sensitivity_model(
    variable_cost_per_metre=variable_cost_per_metre,
    fixed_cost_per_shift=fixed_cost_per_shift,
    baseline_advance_rate=prod["avg_advance_rate"],
    scenario_pct_changes=[0.0, 0.10, 0.25],
)
print("Sensitivity model:\n", model)
assert model.iloc[0]["scenario"] == "Baseline"
assert model["total_unit_cost_n_per_m"].is_monotonic_decreasing  # higher advance rate -> lower total unit cost
assert model.iloc[-1]["reduction_vs_baseline_pct"] > 0

print("\nAll integration checks passed.")
