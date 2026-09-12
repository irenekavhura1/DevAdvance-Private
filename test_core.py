"""Sanity tests for mining_core.py using synthetic data (no real mine data
is used or required — this only checks the arithmetic and NaN handling)."""

import numpy as np
import pandas as pd

import mining_core as mc


def test_classify_item_category():
    assert mc.classify_item_category("38mm Drill Bit") == mc.CATEGORY_DRILLING
    assert mc.classify_item_category("Extension Rod 4ft") == mc.CATEGORY_DRILLING
    assert mc.classify_item_category("Rock Bolt 2.4m") == mc.CATEGORY_GROUND_SUPPORT
    assert mc.classify_item_category("Weld Mesh 100x100") == mc.CATEGORY_GROUND_SUPPORT
    assert mc.classify_item_category("Diesel filter") == mc.CATEGORY_UNCATEGORIZED
    assert mc.classify_item_category(None) == mc.CATEGORY_UNCATEGORIZED
    print("OK classify_item_category")


def test_add_category_column_fallback():
    df = pd.DataFrame({"item": ["Drill Bit 38mm", "Rock Bolt", "Unknown Widget"], "quantity": [10, 5, 2]})
    out = mc.add_category_column(df)
    assert list(out["category"]) == [mc.CATEGORY_DRILLING, mc.CATEGORY_GROUND_SUPPORT, mc.CATEGORY_UNCATEGORIZED]
    print("OK add_category_column fallback")


def test_price_resolution_and_cost():
    cost_inputs = pd.DataFrame({"item": ["Drill Bit 38mm", "Rock Bolt"], "unit_price": [850.0, 120.0]})
    price_table = mc.build_price_table(cost_inputs)
    assert price_table["Drill Bit 38mm"] == 850.0

    usage = pd.DataFrame({"item": ["Drill Bit 38mm", "Rock Bolt", "Mystery Item"], "quantity": [10, 40, 3]})
    priced = mc.attach_cost(usage, price_table)
    assert priced.loc[priced.item == "Drill Bit 38mm", "cost"].iloc[0] == 8500.0
    assert priced.loc[priced.item == "Rock Bolt", "cost"].iloc[0] == 4800.0
    assert np.isnan(priced.loc[priced.item == "Mystery Item", "cost"].iloc[0])  # no price -> NaN, not 0
    print("OK price resolution + cost attach")


def test_attach_cost_row_level_price_wins():
    price_table = pd.Series({"Rock Bolt": 999.0})  # should be ignored where a row price exists
    usage = pd.DataFrame({"item": ["Rock Bolt"], "quantity": [10], "unit_price": [120.0]})
    priced = mc.attach_cost(usage, price_table)
    assert priced["cost"].iloc[0] == 1200.0
    print("OK row-level price precedence")


def test_total_cost_none_when_all_nan():
    df = pd.DataFrame({"item": ["X"], "quantity": [5], "cost": [np.nan]})
    assert mc.total_cost(df) is None
    df2 = pd.DataFrame({"item": ["X"], "quantity": [5], "cost": [500.0]})
    assert mc.total_cost(df2) == 500.0
    print("OK total_cost NaN handling")


def test_reconcile_three_streams():
    physical = pd.DataFrame({"item": ["Rock Bolt", "Mesh"], "quantity": [100, 40]})
    offsider = pd.DataFrame({"item": ["Rock Bolt", "Mesh"], "quantity": [90, 40]})
    theoretical = pd.DataFrame({"item": ["Rock Bolt", "Mesh"], "theoretical_qty": [80, 35]})
    merged = mc.reconcile_three_streams(physical, offsider, theoretical)
    row = merged[merged.item == "Rock Bolt"].iloc[0]
    assert row["unlogged_variance_qty"] == 10  # physical - offsider = under-logged usage
    assert row["over_consumption_qty"] == 20  # physical - theoretical = over-consumption
    print("OK reconcile_three_streams")

    # missing theoretical stream should not crash, just omit those columns
    merged2 = mc.reconcile_three_streams(physical, offsider, None)
    assert "over_consumption_qty" not in merged2.columns
    assert "unlogged_variance_qty" in merged2.columns
    print("OK reconcile_three_streams partial data")


def test_productivity_baseline():
    production = pd.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02"],
            "location": ["Heading A", "Heading B", "Heading A"],
            "shift": ["Day", "Day", "Night"],
            "metres_advanced": [3.5, 2.0, 4.0],
        }
    )
    result = mc.productivity_baseline(production)
    assert result["total_metres_advanced"] == 9.5
    assert result["shift_count"] == 3
    assert abs(result["avg_advance_rate"] - (9.5 / 3)) < 1e-9
    assert result["by_heading"] is not None
    print("OK productivity_baseline")


def test_productivity_baseline_missing_data():
    result = mc.productivity_baseline(None)
    assert result["total_metres_advanced"] is None
    assert result["avg_advance_rate"] is None
    print("OK productivity_baseline missing data -> None, not zero")


def test_sensitivity_model():
    out = mc.sensitivity_model(
        variable_cost_per_metre=2500.0,
        fixed_cost_per_shift=40000.0,
        baseline_advance_rate=4.0,
        scenario_pct_changes=[0.0, 0.10, 0.25],
    )
    baseline_row = out[out.scenario == "Baseline"].iloc[0]
    assert abs(baseline_row["total_unit_cost_n_per_m"] - (40000 / 4 + 2500)) < 1e-9
    plus10 = out[out.scenario == "+10% advance rate"].iloc[0]
    expected_rate = 4.4
    assert abs(plus10["advance_rate_m_per_shift"] - expected_rate) < 1e-9
    assert plus10["total_unit_cost_n_per_m"] < baseline_row["total_unit_cost_n_per_m"]
    assert plus10["reduction_vs_baseline_n_per_m"] > 0
    print("OK sensitivity_model")


def test_sensitivity_curve():
    curve = mc.sensitivity_curve(2500.0, 40000.0, 4.0, rate_multiplier_min=0.5, rate_multiplier_max=2.0, n_points=50)
    assert len(curve) == 50
    assert curve["total_unit_cost_n_per_m"].is_monotonic_decreasing  # higher rate -> strictly lower cost/m
    assert curve["advance_rate_m_per_shift"].min() == 2.0  # 4.0 * 0.5
    assert abs(curve["advance_rate_m_per_shift"].max() - 8.0) < 1e-9  # 4.0 * 2.0
    assert mc.sensitivity_curve(None, 40000.0, 4.0) is None
    print("OK sensitivity_curve")


def test_sensitivity_model_missing_inputs_returns_none():
    assert mc.sensitivity_model(None, 40000.0, 4.0, [0.0]) is None
    assert mc.sensitivity_model(2500.0, None, 4.0, [0.0]) is None
    assert mc.sensitivity_model(2500.0, 40000.0, None, [0.0]) is None
    assert mc.sensitivity_model(2500.0, 40000.0, 0.0, [0.0]) is None
    print("OK sensitivity_model missing-input guards")


if __name__ == "__main__":
    test_classify_item_category()
    test_add_category_column_fallback()
    test_price_resolution_and_cost()
    test_attach_cost_row_level_price_wins()
    test_total_cost_none_when_all_nan()
    test_reconcile_three_streams()
    test_productivity_baseline()
    test_productivity_baseline_missing_data()
    test_sensitivity_model()
    test_sensitivity_curve()
    test_sensitivity_model_missing_inputs_returns_none()
    print("\nAll mining_core tests passed.")
