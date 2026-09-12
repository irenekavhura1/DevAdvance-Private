"""
mining_core.py

Pure data-reconciliation and cost-modelling logic for the Navachab
Development Unit Cost Analyzer.

Deliberately framework-free (no Streamlit imports) so every function here
can be unit tested with plain pandas DataFrames. app.py imports this module
and is responsible only for the upload / column-mapping UI and rendering.

DATA INTEGRITY POLICY
----------------------
Nothing in this module invents, estimates, or backfills a missing value.
Every function accepts optional inputs (None when a data source was not
mapped) and returns NaN / None for any metric it cannot compute from what
was actually supplied. The UI layer is responsible for rendering those as
"Data not available in uploaded dataset" rather than a blank or a zero,
because a zero would misrepresent an unmeasured quantity as a measured one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NOT_AVAILABLE = "Data not available in uploaded dataset"

# ---------------------------------------------------------------------------
# Column auto-detection (best-effort UI convenience only -- every guess is
# shown to the user in an editable selectbox, never applied silently).
# ---------------------------------------------------------------------------
AUTO_DETECT_KEYWORDS = {
    "item": ["item", "consumable", "description", "material", "stock code", "product"],
    "category": ["category", "type", "class"],
    "quantity": ["qty", "quantity", "issued", "consumed", "usage"],
    "unit_price": ["unit price", "price", "rate", "unit cost"],
    "date": ["date", "period", "month"],
    "location": ["heading", "portal", "location", "area", "panel"],
    "shift": ["shift"],
    "ground_class": ["gss", "ground class", "ground support standard", "ground condition"],
    "metres_advanced": ["advance", "metres advanced", "m advanced", "survey"],
    "metres_drilled": ["drilled", "metres drilled", "drm"],
    "theoretical_qty": ["theoretical", "design qty", "design consumption", "design quantity"],
}


def auto_detect_column(field_key: str, columns) -> str | None:
    """Best-effort keyword match from a column's header text to a logical
    field. Returns the first column whose header contains one of the
    field's keywords, or None. Longer, more specific keywords are checked
    first within each field so e.g. 'unit price' wins over a bare 'price'
    style false match, and this is purely a UI default -- never applied
    without being shown in an editable selectbox.
    """
    keywords = sorted(AUTO_DETECT_KEYWORDS.get(field_key, []), key=len, reverse=True)
    for col in columns:
        cl = str(col).strip().lower()
        for kw in keywords:
            if kw in cl:
                return str(col)
    return None

# ---------------------------------------------------------------------------
# Item classification (drilling vs ground support), only used as a fallback
# when the uploaded data has no explicit category column. This is a text
# classifier over the item description, not a source of any numeric value.
# ---------------------------------------------------------------------------
DRILLING_KEYWORDS = ["bit", "rod", "shank", "coupling"]
GROUND_SUPPORT_KEYWORDS = [
    "bolt", "mesh", "plate", "resin", "grout", "shotcrete", "capsule",
]

CATEGORY_DRILLING = "Drilling"
CATEGORY_GROUND_SUPPORT = "Ground Support"
CATEGORY_UNCATEGORIZED = "Uncategorized"


def classify_item_category(item_name) -> str:
    """Classify a consumable item name as Drilling / Ground Support /
    Uncategorized using the item lists named in the research brief. Returns
    Uncategorized (never a guess) when nothing matches, so uncategorized
    spend is surfaced rather than silently folded into either total.
    """
    if item_name is None or (isinstance(item_name, float) and np.isnan(item_name)):
        return CATEGORY_UNCATEGORIZED
    s = str(item_name).strip().lower()
    if any(k in s for k in DRILLING_KEYWORDS):
        return CATEGORY_DRILLING
    if any(k in s for k in GROUND_SUPPORT_KEYWORDS):
        return CATEGORY_GROUND_SUPPORT
    return CATEGORY_UNCATEGORIZED


def add_category_column(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Return a copy of df with a 'category' column guaranteed present.
    Uses the user-supplied category column when it exists and is populated;
    otherwise derives it from the item name via classify_item_category.
    """
    if df is None:
        return None
    d = df.copy()
    if "category" in d.columns and d["category"].notna().any():
        d["category"] = d["category"].fillna(CATEGORY_UNCATEGORIZED)
    elif "item" in d.columns:
        d["category"] = d["item"].apply(classify_item_category)
    else:
        d["category"] = CATEGORY_UNCATEGORIZED
    return d


# ---------------------------------------------------------------------------
# Price resolution
# ---------------------------------------------------------------------------

def build_price_table(cost_inputs_df: pd.DataFrame | None) -> pd.Series | None:
    """Build an item -> unit_price (N$) lookup from the mapped cost-inputs
    sheet. Returns None if no usable price table was supplied.
    """
    if cost_inputs_df is None:
        return None
    if "item" not in cost_inputs_df.columns or "unit_price" not in cost_inputs_df.columns:
        return None
    d = cost_inputs_df.dropna(subset=["item"]).copy()
    d["item"] = d["item"].astype(str).str.strip()
    d = d.drop_duplicates(subset=["item"], keep="last")
    prices = pd.to_numeric(d["unit_price"], errors="coerce")
    return pd.Series(prices.values, index=d["item"].values)


def attach_cost(df: pd.DataFrame | None, price_table: pd.Series | None) -> pd.DataFrame | None:
    """Attach a numeric 'unit_price' and 'cost' (= quantity * unit_price)
    column to a consumption DataFrame (physical stock or offsider usage).

    Resolution order: an existing populated unit_price column in the source
    data wins (some registers price every line item); otherwise price is
    looked up per item from price_table. If neither is available the cost
    column is left as NaN rather than assumed to be zero.
    """
    if df is None:
        return None
    d = df.copy()
    if "quantity" in d.columns:
        d["quantity"] = pd.to_numeric(d["quantity"], errors="coerce")

    has_row_price = "unit_price" in d.columns and pd.to_numeric(
        d["unit_price"], errors="coerce"
    ).notna().any()

    if has_row_price:
        d["unit_price"] = pd.to_numeric(d["unit_price"], errors="coerce")
        if price_table is not None and "item" in d.columns:
            missing = d["unit_price"].isna()
            if missing.any():
                d.loc[missing, "unit_price"] = d.loc[missing, "item"].astype(str).str.strip().map(price_table)
    elif price_table is not None and "item" in d.columns:
        d["unit_price"] = d["item"].astype(str).str.strip().map(price_table)
    else:
        d["unit_price"] = np.nan

    if "quantity" in d.columns:
        d["cost"] = d["quantity"] * d["unit_price"]
    else:
        d["cost"] = np.nan
    return d


# ---------------------------------------------------------------------------
# Section 1 & 2: consumable cost analysis (drilling / ground support share
# the same logic, parameterised by category)
# ---------------------------------------------------------------------------

def filter_category(df: pd.DataFrame | None, category: str) -> pd.DataFrame | None:
    if df is None or "category" not in df.columns:
        return None
    out = df[df["category"] == category]
    return out if len(out) else None


def item_breakdown(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Group a consumption DataFrame by item -> total quantity, total cost."""
    if df is None or "item" not in df.columns:
        return None
    agg = {}
    if "quantity" in df.columns:
        agg["quantity"] = ("quantity", "sum")
    if "cost" in df.columns:
        agg["cost"] = ("cost", "sum")
    if not agg:
        return None
    out = df.groupby("item", dropna=False).agg(**agg).reset_index()
    return out.sort_values("cost", ascending=False, na_position="last") if "cost" in out.columns else out


def total_cost(df: pd.DataFrame | None) -> float | None:
    if df is None or "cost" not in df.columns:
        return None
    v = df["cost"].sum(skipna=True)
    if df["cost"].isna().all():
        return None
    return float(v)


def flag_catchup_spikes(df: pd.DataFrame | None, threshold_multiplier: float = 1.8) -> pd.DataFrame | None:
    """Flag rows whose quantity is far above that item's own typical
    (median) line quantity, as a possible catch-up install (two cycles'
    worth of mesh/bolts issued in a single pass when bolting has fallen
    behind the jumbo's advance) rather than genuine over-consumption.

    Purely descriptive: adds a boolean 'possible_catchup_spike' column and
    changes no other value. threshold_multiplier is a heuristic, not a
    measured constant, and is surfaced as such by the caller.
    """
    if df is None or "item" not in df.columns or "quantity" not in df.columns:
        return df
    d = df.copy()
    qty = pd.to_numeric(d["quantity"], errors="coerce")
    median_by_item = qty.groupby(d["item"]).transform("median")
    d["possible_catchup_spike"] = (median_by_item > 0) & (qty >= threshold_multiplier * median_by_item)
    return d


def reconcile_three_streams(
    physical_df: pd.DataFrame | None,
    offsider_df: pd.DataFrame | None,
    theoretical_df: pd.DataFrame | None,
) -> pd.DataFrame | None:
    """Build a per-item table comparing physical stock depletion, offsider
    logged usage, and live-mine (theoretical/design) requirement, each
    already filtered to one category by the caller.

    theoretical_df is expected to carry 'item' and 'theoretical_qty'
    columns (from the live-production mapping); it is optional. Any stream
    not supplied contributes NaN columns rather than being assumed zero, so
    a genuinely absent stream is never mistaken for "no consumption".
    """
    frames = []

    def _prep(df, qty_col, label):
        if df is None or "item" not in df.columns or qty_col not in df.columns:
            return None
        g = df.groupby("item", dropna=False)[qty_col].sum().rename(f"{label}_qty")
        return g

    phys = _prep(physical_df, "quantity", "physical")
    off = _prep(offsider_df, "quantity", "offsider")
    theo = _prep(theoretical_df, "theoretical_qty", "theoretical") if theoretical_df is not None else None

    series_list = [s for s in (phys, off, theo) if s is not None]
    if not series_list:
        return None

    merged = pd.concat(series_list, axis=1).reset_index().rename(columns={"index": "item"})

    if "physical_qty" in merged.columns and "offsider_qty" in merged.columns:
        merged["unlogged_variance_qty"] = merged["physical_qty"] - merged["offsider_qty"]
    if "physical_qty" in merged.columns and "theoretical_qty" in merged.columns:
        merged["over_consumption_qty"] = merged["physical_qty"] - merged["theoretical_qty"]

    return merged


# ---------------------------------------------------------------------------
# Section 3: development productivity baseline
# ---------------------------------------------------------------------------

def productivity_baseline(production_df: pd.DataFrame | None) -> dict:
    """Compute total metres advanced and average advance rate (m/shift).

    A 'shift' is counted as one row unless the mapped data provides a
    dedicated shift identifier column, in which case distinct
    (date, location, shift) combinations are counted so a heading reported
    more than once in the same shift is not double counted.
    """
    result = {
        "total_metres_advanced": None,
        "shift_count": None,
        "avg_advance_rate": None,
        "by_heading": None,
    }
    if production_df is None or "metres_advanced" not in production_df.columns:
        return result

    d = production_df.copy()
    d["metres_advanced"] = pd.to_numeric(d["metres_advanced"], errors="coerce")

    total_metres = d["metres_advanced"].sum(skipna=True)
    result["total_metres_advanced"] = float(total_metres) if d["metres_advanced"].notna().any() else None

    shift_key_cols = [c for c in ("date", "location", "shift") if c in d.columns]
    if shift_key_cols:
        shift_count = d[shift_key_cols].drop_duplicates().shape[0]
    else:
        shift_count = len(d)
    result["shift_count"] = int(shift_count) if shift_count else None

    if result["total_metres_advanced"] is not None and result["shift_count"]:
        result["avg_advance_rate"] = result["total_metres_advanced"] / result["shift_count"]

    if "location" in d.columns:
        by_heading = (
            d.groupby("location", dropna=False)["metres_advanced"]
            .sum()
            .reset_index()
            .rename(columns={"location": "heading", "metres_advanced": "total_metres_advanced"})
            .sort_values("total_metres_advanced", ascending=False)
        )
        result["by_heading"] = by_heading

    return result


# ---------------------------------------------------------------------------
# Section 4: sensitivity / cost-advance modelling
# ---------------------------------------------------------------------------

def sensitivity_model(
    variable_cost_per_metre: float | None,
    fixed_cost_per_shift: float | None,
    baseline_advance_rate: float | None,
    scenario_pct_changes: list[float],
) -> pd.DataFrame | None:
    """Model total development unit cost (N$/m) under advance-rate
    improvement scenarios, holding labour + machine cost fixed PER SHIFT.

    DUC(scenario) = fixed_cost_per_shift / advance_rate(scenario)
                    + variable_cost_per_metre

    scenario_pct_changes: e.g. [0.0, 0.10, 0.25] for baseline / +10% / +25%.
    Returns None if any required input is missing (never fabricates a
    baseline to fill the gap).
    """
    if (
        variable_cost_per_metre is None
        or fixed_cost_per_shift is None
        or baseline_advance_rate is None
        or not baseline_advance_rate
    ):
        return None

    rows = []
    baseline_duc = None
    for pct in scenario_pct_changes:
        advance_rate = baseline_advance_rate * (1 + pct)
        if advance_rate <= 0:
            continue
        fixed_component = fixed_cost_per_shift / advance_rate
        duc = fixed_component + variable_cost_per_metre
        if pct == 0.0:
            baseline_duc = duc
        rows.append(
            {
                "scenario": "Baseline" if pct == 0.0 else f"{pct:+.0%} advance rate",
                "advance_rate_m_per_shift": advance_rate,
                "fixed_cost_component_n_per_m": fixed_component,
                "variable_cost_component_n_per_m": variable_cost_per_metre,
                "total_unit_cost_n_per_m": duc,
            }
        )

    out = pd.DataFrame(rows)
    if baseline_duc is not None and len(out):
        out["reduction_vs_baseline_n_per_m"] = baseline_duc - out["total_unit_cost_n_per_m"]
        out["reduction_vs_baseline_pct"] = out["reduction_vs_baseline_n_per_m"] / baseline_duc
    return out


def sensitivity_curve(
    variable_cost_per_metre: float | None,
    fixed_cost_per_shift: float | None,
    baseline_advance_rate: float | None,
    rate_multiplier_min: float = 0.5,
    rate_multiplier_max: float = 2.0,
    n_points: int = 60,
) -> pd.DataFrame | None:
    """Continuous version of sensitivity_model: total unit cost evaluated at
    n_points advance rates spanning [baseline * rate_multiplier_min,
    baseline * rate_multiplier_max], to show the shape of the fixed-cost-
    dilution curve (a hyperbola, DUC = fixed/rate + variable) rather than
    only the handful of discrete scenario points sensitivity_model returns.
    This is the same equation, just sampled finely enough to plot -- it
    exists to make the inverse advance-rate/unit-cost relationship visibly
    obvious, not to introduce a different model. Returns None if any
    required input is missing.
    """
    if (
        variable_cost_per_metre is None
        or fixed_cost_per_shift is None
        or baseline_advance_rate is None
        or not baseline_advance_rate
        or n_points < 2
    ):
        return None
    rate_min = baseline_advance_rate * rate_multiplier_min
    rate_max = baseline_advance_rate * rate_multiplier_max
    if rate_min <= 0 or rate_max <= rate_min:
        return None
    rates = np.linspace(rate_min, rate_max, n_points)
    fixed_component = fixed_cost_per_shift / rates
    total = fixed_component + variable_cost_per_metre
    return pd.DataFrame({
        "advance_rate_m_per_shift": rates,
        "fixed_cost_component_n_per_m": fixed_component,
        "variable_cost_component_n_per_m": variable_cost_per_metre,
        "total_unit_cost_n_per_m": total,
    })
