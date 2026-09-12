"""
Loaders for Irene's actual Navachab / Byrnecut export files.

These files have a fixed, idiosyncratic shape specific to this mine's own
systems (a wide monthly store-issue workbook, EOM development payment
reports, PLOD exports, stocktake sheets with section headers, etc). This
module turns each of those real shapes into a small set of tidy long-format
tables. It is deliberately separate from the generic "upload any workbook,
map any column" mechanism in mining_core.py / app.py, which stays available
so a different mine's differently-shaped data can still be used.

Zero-hallucination rule applies here too: a loader either returns real rows
parsed from the file, or an empty frame / None with the gap explained. It
never invents a figure to fill a hole.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

REAL_DATA_DIR = Path(__file__).parent / "real_data"

# ---------------------------------------------------------------------------
# Category keywords, tuned to the real item descriptions actually seen in
# Irene's data (extends the generic keyword list in mining_core.py). Order
# matters: accessory/tool exceptions are checked before the generic bolt/rod
# keywords they would otherwise be swept up by.
# ---------------------------------------------------------------------------

DRILLING_ACCESSORY_EXCEPTIONS = [
    "bolt driver", "centraliser", "centralizer", "dolly",
]
DRILLING_KEYWORDS_REAL = [
    "bit", "rod", "shank", "coupling", "drifter", "reamer", "reaming",
    "drill tube", "fishing", "fish sleeve", "bit adaptor", "bit adapter",
]
GROUND_SUPPORT_KEYWORDS_REAL = [
    "split set", "galv ss", "friction bolt", "friction stabiliser", "md bolt",
    "m/d bolt", "resin bolt", "cable bolt", "cbolt", "rock bolt", "rockbolt",
    "bolt", "mesh", "plate", "combi plate", "d/fly", "dome", "pull ring",
    "pull test ring", "barrel", "wedge anchor", "expansion shell", "spiling",
    "resin", "grout", "cement", "shotcrete", "cable cement", "re-bar", "rebar",
]
# Shotcrete admixtures/accessories: chemically part of the "shotcrete" line
# item in the ground support cost equation (accelerant, plasticiser, fibre
# reinforcement all go into a shotcrete mix), just described by trade/brand
# name rather than the word "shotcrete" itself in the stores register.
SHOTCRETE_ADMIXTURE_KEYWORDS = [
    "chryso", "masterroc", "master glenium", "glenium", "poly fibre", "polyfibre",
]
OUT_OF_SCOPE_VENTILATION_KEYWORDS = [
    "typhoon", "duct", "vent needle", "vent bag", "vent trans",
]
OUT_OF_SCOPE_OTHER_KEYWORDS = [
    "sign", "danger", "cap lamp", "scaling bar", "chain", "shackle", "rope",
    "hose", "paintstick", "paint mine mark", "poly agro", "poly pn",
]


def classify_real_item(description: str) -> str:
    """Classify one item description into Drilling / Ground Support /
    Uncategorized, using the real vocabulary found in Irene's data. This is
    intentionally more specific than mining_core.classify_item_category
    (which stays as the generic fallback for other mines' data) because a
    generic "bolt" keyword match would wrongly sweep drilling accessories
    like "MD BOLT DRIVER" or "BOLTING CENTRALISER" into ground support.

    Nothing here is a numeric guess -- it only decides which of the study's
    two consumable buckets (drilling / ground support) an item's own words
    describe, or that it is genuinely neither (a reusable tool, ventilation
    ducting, paint, piping -- all explicitly out of the study's scope per
    its own delimitations). See classify_uncategorized_reason for *why* any
    given uncategorized item was excluded, so "uncategorized" never reads as
    an unresolved gap.
    """
    if not isinstance(description, str) or not description.strip():
        return "uncategorized"
    text = description.lower()
    for kw in DRILLING_ACCESSORY_EXCEPTIONS:
        if kw in text:
            return "uncategorized"  # drilling tool/accessory, not a consumable per her definitions
    for kw in OUT_OF_SCOPE_VENTILATION_KEYWORDS + OUT_OF_SCOPE_OTHER_KEYWORDS:
        if kw in text:
            return "uncategorized"
    for kw in DRILLING_KEYWORDS_REAL:
        if kw in text:
            return "drilling"
    for kw in GROUND_SUPPORT_KEYWORDS_REAL + SHOTCRETE_ADMIXTURE_KEYWORDS:
        if kw in text:
            return "ground_support"
    return "uncategorized"


def classify_uncategorized_reason(description: str) -> str | None:
    """For an item classify_real_item put in 'uncategorized', state which of
    the three genuine reasons applies, so the app can show *why* rather than
    leaving 'uncategorized' looking like an unresolved data gap. Returns None
    for anything not actually uncategorized (including drilling/ground
    support items)."""
    if classify_real_item(description) != "uncategorized":
        return None
    text = str(description).lower()
    for kw in DRILLING_ACCESSORY_EXCEPTIONS:
        if kw in text:
            return "Reusable drilling tool/accessory (e.g. a bolt driver, centraliser, dolly) -- not a per-metre consumable, per the study's own item definitions."
    for kw in OUT_OF_SCOPE_VENTILATION_KEYWORDS:
        if kw in text:
            return "Ventilation ducting/accessory -- explicitly out of scope (the study covers drilling and ground support consumables only)."
    for kw in OUT_OF_SCOPE_OTHER_KEYWORDS:
        if kw in text:
            return "Other out-of-scope store item (signage, piping, paint, rigging hardware, etc.) -- not a drilling or ground support consumable."
    return "Not recognised by either keyword list -- genuinely unclassified; check this item's description manually."


def classify_gs_design_item(item_text: str):
    """Map a ground support usage item name to one of the four categories
    tracked on the GSS01/GSS02 design-standard drawings (see
    load_gss_design_standard), or None if it isn't one of those four (e.g. a
    cable bolt, pull ring or plate -- real items, just not part of this
    specific design comparison). Keyword rules only, built from the actual
    item vocabulary in the live and offsider usage logs; never a numeric
    guess."""
    if not isinstance(item_text, str) or not item_text.strip():
        return None
    t = item_text.upper()
    if "MESH" in t:
        return "mesh_sheet"
    if "M/D" in t or "MD BOLT" in t or re.search(r"\bMD\b", t):
        return "md_bolt_2_4m"
    if "900" in t or "0.9M" in t:
        return "stubby_split_set_0_9m"
    if ("2400" in t or "2.4M" in t) and ("SS" in t or "SPLIT SET" in t or "FRICTION BOLT" in t):
        return "split_set_2_4m"
    return None


# ---------------------------------------------------------------------------
# Ground support item -> price-list alias map. The live jumbo-linked log and
# the offsider store-issue log describe the same physical items in very
# different words from the flat Consumables_Unit_Costs.xlsx price list (e.g.
# "2.4m M/D bolts" vs "MD Bolt - 47mm - 2.4m"), so exact-text price lookup
# fails for almost everything. This alias map is a manual, reviewed mapping
# built from the actual item vocabulary found in the data -- every mapping
# is a same-product identification (a split set is the generic name for a
# friction bolt of that spec), never a numeric guess. Items with no
# equivalent in the price list are left unmapped (None) rather than
# assigned an approximate price, and are surfaced as "unpriced" in the app
# rather than silently dropped.
GS_ITEM_PRICE_ALIASES = {
    "2.4m m/d bolts": "MD Bolt - 47mm - 2.4m",
    "md bolt 2.4m long galvanized": "MD Bolt - 47mm - 2.4m",
    "2.4m galv ss - 47mm": "Split Set - 47mm Galvanised - 2.4m",
    "0.9m galv ss - 47mm fat": "Split Set - 47mm Galvanised - 0.9m",
    "0.9m galv ss - 39mm": "Split Set - 39mm Galvanised - 0.9m",
    "friction bolt 47 x 2400 galv": "Split Set - 47mm Galvanised - 2.4m",
    "friction bolt 47 x 900 galv wa": "Split Set - 47mm Galvanised - 0.9m",
    "friction bolt 39 x 900 gal wa": "Split Set - 39mm Galvanised - 0.9m",
    "friction bolt 39 x 900 gal wa   sandvik:fbj39090gwa": "Split Set - 39mm Galvanised - 0.9m",
    "friction bolt 47 x 900 galv wa  sandvik:fbj47090gwa": "Split Set - 47mm Galvanised - 0.9m",
    "friction stabiliser bolt 47x2400m hdg fs47-2400g galv": "Split Set - 47mm Galvanised - 2.4m",
    "2.4m gewi - resin": "Resin Bolts - 24mm Black - 2.4m",
    "6m cablebolt grouted - twin strand": "Cable Bolt (Twin Strand Bulbed) - 15.2mm - 6m  Length",
    "6m cablebolt install - twin strand": "Cable Bolt (Twin Strand Bulbed) - 15.2mm - 6m  Length",
    "cable bolt installed - twin strand": "Cable Bolt (Twin Strand Bulbed) - 15.2mm - 6m  Length",
    "cbolt (ts bulb) - 15.2mm - 6m": "Cable Bolt (Twin Strand Bulbed) - 15.2mm - 6m  Length",
}
# Mesh items are priced per m2 in the price list but logged per sheet
# ("EACH") in the usage data -- the sheet's own area must be multiplied in.
# Maps normalized item text -> (price-list item name, sheet area in m2).
GS_MESH_ITEM_AREA_ALIASES = {
    "galv mesh 4.5m x 2.4m": ("Mesh Galvanised  - 100mm x 100mm x 5.6mmm", 4.5 * 2.4),
    "mesh - 2.40 x 4.50 m - galv": ("Mesh Galvanised  - 100mm x 100mm x 5.6mmm", 2.4 * 4.5),
}


def resolve_gs_price(item_text: str, gs_price_map: pd.Series):
    """Return (unit_price_or_None, qty_multiplier) for one ground support
    item description, using the alias maps above. qty_multiplier is 1 for
    plain per-each items and a sheet area (m2) for mesh, so cost = qty *
    qty_multiplier * unit_price."""
    if not isinstance(item_text, str):
        return None, 1.0
    key = item_text.strip().lower()
    if key in GS_MESH_ITEM_AREA_ALIASES:
        price_item, area = GS_MESH_ITEM_AREA_ALIASES[key]
        return gs_price_map.get(price_item), area
    alias = GS_ITEM_PRICE_ALIASES.get(key)
    if alias is not None:
        return gs_price_map.get(alias), 1.0
    # some registers (the physical stocktake sheets) append a supplier part
    # number after the item's own description, e.g. "D/FLY 300X280 GALV
    # Sandvik P/no: DF3STDD15449GWA" -- strip that tail and retry the same
    # alias/exact lookups on the bare description before giving up.
    stripped = re.split(r"\s{2,}sandvik|\s+sandvik\b", key, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if stripped and stripped != key:
        if stripped in GS_MESH_ITEM_AREA_ALIASES:
            price_item, area = GS_MESH_ITEM_AREA_ALIASES[stripped]
            return gs_price_map.get(price_item), area
        alias = GS_ITEM_PRICE_ALIASES.get(stripped)
        if alias is not None:
            return gs_price_map.get(alias), 1.0
        hit = gs_price_map.get(stripped)
        if hit is not None:
            return hit, 1.0
    # last resort: an exact match against the price list itself
    return gs_price_map.get(item_text.strip()), 1.0


def normalize_portal(value) -> str:
    """Classify a location/heading string to North or South.

    An earlier version of this guessed that an "MS" prefix meant a shared
    "Main" area and "NS" meant a "connecting" area distinct from North/South.
    That guess was wrong, and it silently erased the South portal from the
    live jumbo-linked and GS inventory logs (every South record was bucketed
    as "MS (shared)"). Irene's own CostModel_to_date.xlsx (Portal_Analysis
    and Anomalies sheets) resolves every heading in her four months of data
    to a portal and states the real rule for this mine: "MS" headings are
    Southern Portal, "NS" headings are Northern Portal (NS = North Shoot),
    and -- more reliably still -- "the Southern Portal occupies levels 840
    to 940 and the Northern Portal levels 1020 and 1040, with no overlap, so
    a location can be assigned from its level number." Her own analysis
    found one exception to the prefix rule (an "MS_"-prefixed heading with a
    Northern level number) and excluded it rather than force a guess, which
    is why the level number is checked first here and the prefix is only a
    fallback for text with no level number in it (e.g. "MS Decline").
    """
    if not isinstance(value, str) or not value.strip():
        return "Unspecified"
    text = value.strip().upper()
    if "NORTH" in text:
        return "North"
    if "SOUTH" in text:
        return "South"
    level_match = re.search(r"(\d{3,4})", text)
    if level_match:
        level = int(level_match.group(1))
        if 800 <= level <= 999:
            return "South"
        if 1000 <= level <= 1099:
            return "North"
    if text.startswith("NS"):
        return "North"
    if text.startswith("MS"):
        return "South"
    if text.startswith("N_"):
        return "North"
    if text.startswith("S_"):
        return "South"
    return "Unspecified"


def normalize_portal_best(location, parent_location=None) -> str:
    """Prefer the higher-level parent_location/heading field for portal
    classification when it resolves to something specific; the raw
    location field is often a granular sub-point (a stope, a sump, an
    access bay) whose own text rarely says North/South even though its
    parent heading does."""
    if parent_location is not None:
        p = normalize_portal(parent_location)
        if p != "Unspecified":
            return p
    return normalize_portal(location)


# ---------------------------------------------------------------------------
# 1. Drilling consumable unit prices (file is named GS_UNIT_costs.xlsx but
#    actually contains drilling consumables/accessories pricing) and
#    ground support unit prices (file named Consumables_Unit_Costs.xlsx but
#    actually contains ground support pricing). Names are swapped from what
#    they suggest -- classify by content, never by filename.
# ---------------------------------------------------------------------------

def load_price_table_generic(path: Path, description_col_hint="Descri", price_col_hint="Unit") -> pd.DataFrame:
    """Read one of the two flat unit-price workbooks (single sheet, a
    Description-like column and a Unit Price-like column, floating a few
    blank rows down)."""
    raw = pd.read_excel(path, sheet_name=0, header=None)
    header_row_idx = None
    for i in range(min(10, len(raw))):
        row_vals = raw.iloc[i].astype(str)
        if row_vals.str.contains(description_col_hint, case=False, na=False).any():
            header_row_idx = i
            break
    if header_row_idx is None:
        return pd.DataFrame(columns=["item", "unit_price", "unit_of_measure"])
    header = raw.iloc[header_row_idx]
    desc_col = next((c for c in raw.columns if description_col_hint.lower() in str(header[c]).lower()), None)
    price_col = None
    uom_col = None
    for c in raw.columns:
        h = str(header[c]).lower()
        if "unit of measure" in h or h.strip() == "unit":
            uom_col = c
    # The price column's header text can be split across several merged
    # rows just below the description header (e.g. "Unit" / "Cost" / "USD"
    # stacked in three separate physical rows of the same column) -- scan a
    # small window below the description row rather than only the row that
    # matched the description keyword.
    for offset in range(0, 4):
        ridx = header_row_idx + offset
        if ridx >= len(raw):
            break
        row = raw.iloc[ridx]
        for c in raw.columns:
            h = str(row[c]).lower()
            if "price" in h or "cost" in h:
                price_col = c
        if price_col is not None:
            break
    if price_col is None:
        # last resort: the rightmost numeric-typed column below the header
        numeric_cols = [c for c in raw.columns if pd.to_numeric(raw.iloc[header_row_idx + 1:, c], errors="coerce").notna().sum() > 0]
        if numeric_cols:
            price_col = numeric_cols[-1]
    if desc_col is None:
        return pd.DataFrame(columns=["item", "unit_price", "unit_of_measure"])
    # price value may be one or two header rows below the label (merged cells)
    data = raw.iloc[header_row_idx + 1:].copy()
    out = pd.DataFrame({
        "item": data[desc_col],
        "unit_price": pd.to_numeric(data[price_col], errors="coerce") if price_col is not None else np.nan,
        "unit_of_measure": data[uom_col] if uom_col is not None else np.nan,
    })
    out = out.dropna(subset=["item"])
    out["item"] = out["item"].astype(str).str.strip()
    out = out[out["item"] != "nan"]
    return out.reset_index(drop=True)


def build_embedded_drilling_price_table(monthly_totals: dict) -> pd.DataFrame:
    """The wide usage-master workbook embeds its own per-month unit cost for
    every drilling item (row 0 of each monthly tab). These are the prices
    actually applied to real transactions -- stable across all 8 months for
    every item in practice -- and take precedence over the separate flat
    GS_UNIT_costs.xlsx reference sheet, which was found to disagree by a
    consistent ~11.4x factor for two items (see compare_price_sources)."""
    rows = []
    for sheet, info in monthly_totals.items():
        for item, cost in info["item_unit_cost"].items():
            if pd.notna(cost):
                rows.append((item, cost))
    if not rows:
        return pd.DataFrame(columns=["item", "unit_price"])
    df = pd.DataFrame(rows, columns=["item", "unit_price"])
    # every item's embedded cost is consistent across months in practice;
    # take the median defensively in case a genuine mid-year price change
    # ever appears.
    out = df.groupby("item", as_index=False)["unit_price"].median()
    out["price_source_file"] = "01_Stock_Usage_Data_Entry_August_26.xlsx (embedded, operational)"
    return out


def flat_only_items_with_no_embedded_price(monthly_totals: dict, flat_prices: pd.DataFrame) -> pd.DataFrame:
    """Items that were actually issued (they appear in the usage records)
    but never carried a valid embedded unit cost in any month's own
    workbook, so the only price available for them comes from the flat
    reference sheet. Flagged separately because two sibling T45-family
    items (SHANK T45, COUPLING SLEEVE T45/T38) were found to have a flat
    reference price ~11.4x the price actually applied operationally -- so
    a flat-only price for another T45-family item is not assumed reliable
    just because it's the only number available."""
    embedded = build_embedded_drilling_price_table(monthly_totals)
    embedded_items = set(embedded["item"])
    flat = flat_prices.dropna(subset=["unit_price"]).drop_duplicates(subset=["item"])
    flat_only = flat[~flat["item"].isin(embedded_items)].copy()
    flat_only["shares_t45_anomaly_pattern"] = flat_only["item"].str.contains("T45", case=False, na=False)
    return flat_only[["item", "unit_price", "shares_t45_anomaly_pattern"]].reset_index(drop=True)


def compare_price_sources(monthly_totals: dict, flat_prices: pd.DataFrame, ratio_threshold: float = 1.5) -> pd.DataFrame:
    """Items where the flat reference price list disagrees with the
    embedded operational price by more than ratio_threshold -- a genuine
    data-quality finding worth investigating and explaining, not something
    to silently resolve."""
    embedded = build_embedded_drilling_price_table(monthly_totals).set_index("item")["unit_price"]
    flat = flat_prices.dropna(subset=["unit_price"]).drop_duplicates(subset=["item"]).set_index("item")["unit_price"]
    joined = pd.DataFrame({"embedded_operational_price": embedded, "flat_reference_price": flat}).dropna()
    if joined.empty:
        return joined
    joined["ratio"] = joined["flat_reference_price"] / joined["embedded_operational_price"]
    return joined[(joined["ratio"] > ratio_threshold) | (joined["ratio"] < 1 / ratio_threshold)].reset_index().rename(columns={"index": "item"})


def load_all_price_tables(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    frames = []
    p1 = data_dir / "GS_UNIT_costs.xlsx"  # actually drilling consumables/accessories
    if p1.exists():
        df = load_price_table_generic(p1, description_col_hint="Descri")
        df["price_source_file"] = p1.name
        frames.append(df)
    p2 = data_dir / "Consumables_Unit_Costs.xlsx"  # actually ground support consumables
    if p2.exists():
        df = load_price_table_generic(p2, description_col_hint="Ground Support Descri")
        df["price_source_file"] = p2.name
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["item", "unit_price", "unit_of_measure", "price_source_file"])
    combined = pd.concat(frames, ignore_index=True)
    # currency note: source price files are denominated in USD, not N$ --
    # surfaced explicitly in the app rather than silently converted.
    return combined


# ---------------------------------------------------------------------------
# 1b. Ground support design standard: CostModel_to_date.xlsx, Inputs sheet.
#     This is Irene's own reconciled workbook, built from the actual GSS01
#     and GSS02 approved drawings (confirmed against the drawing PDFs
#     directly) -- minimum quantity per cut, by bolt/mesh type, for each
#     ground support standard. GSS_03 has no drawing of its own; her own
#     analysis resolved this by applying the GSS_02 standard to it, which is
#     carried through here rather than left blank.
# ---------------------------------------------------------------------------

def load_gss_design_standard(data_dir: Path = REAL_DATA_DIR):
    """Returns (design_df, cut_length_m). design_df has one row per GSS
    standard with columns: standard, ground_condition, md_bolt_2_4m,
    split_set_2_4m, stubby_split_set_0_9m, mesh_sheet, source. Quantities
    are per cut (per blast round), not per metre -- divide by cut_length_m
    for a per-metre rate. Returns (empty df, None) if the file or the
    expected section isn't found, rather than guessing standard figures."""
    path = data_dir / "CostModel_to_date.xlsx"
    empty = pd.DataFrame(columns=["standard", "ground_condition", "md_bolt_2_4m",
                                   "split_set_2_4m", "stubby_split_set_0_9m",
                                   "mesh_sheet", "source"])
    if not path.exists():
        return empty, None
    try:
        raw = pd.read_excel(path, sheet_name="Inputs", header=None)
    except Exception:
        return empty, None

    header_row = None
    for i in range(len(raw)):
        row_vals = raw.iloc[i].astype(str)
        if row_vals.str.contains("Standard", case=False, na=False).any() and \
           row_vals.str.contains("Ground condition", case=False, na=False).any():
            header_row = i
            break
    rows = []
    if header_row is not None:
        r = header_row + 1
        while r < len(raw):
            standard = raw.iloc[r, 1]
            if not isinstance(standard, str) or not standard.strip():
                break
            rows.append({
                "standard": standard.strip(),
                "ground_condition": raw.iloc[r, 2],
                "md_bolt_2_4m": pd.to_numeric(raw.iloc[r, 3], errors="coerce"),
                "split_set_2_4m": pd.to_numeric(raw.iloc[r, 4], errors="coerce"),
                "stubby_split_set_0_9m": pd.to_numeric(raw.iloc[r, 5], errors="coerce"),
                "mesh_sheet": pd.to_numeric(raw.iloc[r, 6], errors="coerce"),
                "source": raw.iloc[r, 8] if raw.shape[1] > 8 else None,
            })
            r += 1
    design_df = pd.DataFrame(rows) if rows else empty

    cut_length_m = None
    for i in range(len(raw)):
        row_vals = raw.iloc[i].astype(str)
        if row_vals.str.contains("Cut length", case=False, na=False).any():
            val_row = raw.iloc[i]
            for c in range(len(val_row)):
                v = pd.to_numeric(val_row[c], errors="coerce")
                if pd.notna(v) and 0 < v < 20:
                    cut_length_m = float(v)
                    break
            break
    return design_df, cut_length_m


def load_costmodel_totals(data_dir: Path = REAL_DATA_DIR):
    """Reads Irene's own reconciled May-Aug 2026 whole-mine and by-portal
    headline totals from CostModel_to_date.xlsx's Portal_Analysis sheet (its
    own reconciliation checks all show "Reconciles"). Returns a dict with
    keys like 'gs_cost_may_aug', 'drilling_cost_may_aug',
    'advance_m_may_aug', each a dict {"North": x, "South": y, "Whole mine":
    z}, or an empty dict if the file/sheet isn't found. This is a third,
    independent measurement of the same totals this app computes from the
    live/offsider usage logs -- used only as a cross-check, never merged
    into this app's own calculations."""
    path = data_dir / "CostModel_to_date.xlsx"
    if not path.exists():
        return {}
    try:
        raw = pd.read_excel(path, sheet_name="Portal_Analysis", header=None)
    except Exception:
        return {}
    wanted = {
        "advance_m_may_aug": "Metres advanced, May to August",
        "gs_cost_may_aug": "Ground support consumable cost, May to August",
        "drilling_cost_may_aug": "Drilling consumable cost, May to August",
    }
    out = {}
    for key, label in wanted.items():
        for i in range(len(raw)):
            cell = raw.iloc[i, 1]
            if isinstance(cell, str) and cell.strip() == label:
                out[key] = {
                    "North": pd.to_numeric(raw.iloc[i, 4], errors="coerce"),
                    "South": pd.to_numeric(raw.iloc[i, 5], errors="coerce"),
                    "Whole mine": pd.to_numeric(raw.iloc[i, 6], errors="coerce"),
                }
                break
    return out


# ---------------------------------------------------------------------------
# 2. Drilling consumable usage master: 01_Stock_Usage_Data_Entry_August_26.xlsx
#    Wide format, one monthly tab per month (Jan-Aug 2026), one row per
#    shift/requester record, one column per item. Rows 0-3 are cost/qty/
#    category summaries; the real per-record header is row 4 (0-indexed);
#    data starts row 5. Meta columns are always at positions 1-8; item
#    columns start at position 9 and vary in name/order by month.
# ---------------------------------------------------------------------------

def load_drilling_usage_master(data_dir: Path = REAL_DATA_DIR):
    path = data_dir / "01_Stock_Usage_Data_Entry_August_26.xlsx"
    if not path.exists():
        return pd.DataFrame(), {}
    xls = pd.ExcelFile(path)
    month_tabs = [s for s in xls.sheet_names if s not in ("Sheet4", "LOOKUP")]
    usage_frames = []
    monthly_totals = {}
    for sheet in month_tabs:
        raw = pd.read_excel(path, sheet_name=sheet, header=None)
        if raw.shape[0] < 6:
            continue
        header = raw.iloc[4]
        item_cols = [c for c in raw.columns if c >= 9 and pd.notna(header[c])]
        item_names = {c: str(header[c]).strip() for c in item_cols}
        unit_cost_row = raw.iloc[0]
        qty_total_row = raw.iloc[2]
        reported_monthly_cost = raw.iloc[1, 7] if raw.shape[1] > 7 else np.nan
        monthly_totals[sheet] = {
            "reported_monthly_cost": reported_monthly_cost,
            "item_unit_cost": {item_names[c]: unit_cost_row[c] for c in item_cols},
            "item_reported_qty": {item_names[c]: qty_total_row[c] for c in item_cols},
        }
        data = raw.iloc[5:].copy()
        if data.empty:
            continue
        meta = data.iloc[:, 1:9].copy()
        meta.columns = ["date", "month", "rig_type", "shift", "rig", "requester", "approved_by", "level"]
        meta = meta.reset_index(drop=True)
        items = data[item_cols].reset_index(drop=True)
        items.columns = [item_names[c] for c in item_cols]
        combined = pd.concat([meta, items], axis=1)
        long = combined.melt(id_vars=meta.columns.tolist(), var_name="item", value_name="qty")
        long["qty"] = pd.to_numeric(long["qty"], errors="coerce")
        long = long.dropna(subset=["qty"])
        long = long[long["qty"] != 0]
        long["source_sheet"] = sheet
        usage_frames.append(long)
    usage = pd.concat(usage_frames, ignore_index=True) if usage_frames else pd.DataFrame()
    if not usage.empty:
        usage["date"] = pd.to_datetime(usage["date"], errors="coerce", dayfirst=True)
        # Known data-entry quality issue: a scattered handful of rows in the
        # source workbook carry a mistyped year (e.g. "07.03.2028" typed on a
        # tab named "MAR 26" whose own MONTH column says "MARCH"). The tab
        # name and the row's own month label agree it is 2026; only the year
        # digits are wrong. We correct the year to 2026 and flag every row
        # this touches, rather than silently keeping an impossible date or
        # silently discarding real transactions -- surfaced in the app as an
        # explicit, counted data-quality note.
        year_wrong = usage["date"].dt.year.notna() & (usage["date"].dt.year != 2026)
        usage["date_year_corrected"] = False
        if year_wrong.any():
            corrected = usage.loc[year_wrong, "date"].apply(
                lambda d: d.replace(year=2026) if pd.notna(d) else d
            )
            usage.loc[year_wrong, "date"] = corrected
            usage.loc[year_wrong, "date_year_corrected"] = True
        usage["portal"] = usage["level"].apply(normalize_portal)
        usage["category"] = usage["item"].apply(classify_real_item)
        usage["stream"] = "offsider_store_issue"
    return usage, monthly_totals


# ---------------------------------------------------------------------------
# 3. Ground support "live" usage (jumbo-linked, digital): LiveMine_Data.xlsx
#    Inventory tab. Clean long format already: one row per item consumed
#    per shift. Rock Bolts / Mesh / Cable Bolts only (no resin/shotcrete
#    tracked digitally as of this export).
# ---------------------------------------------------------------------------

def load_gs_usage_live(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    path = data_dir / "LiveMine_Data.xlsx"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Inventory", header=0)
    except Exception:
        return pd.DataFrame()
    df = df.rename(columns={
        "Shift Date": "date", "Shift Type": "shift_type", "Equipment ID": "equipment",
        "Location": "location", "Inventory": "item", "Inventory Group": "group",
        "Quantity": "qty", "Parent Location": "parent_location",
    })
    keep = [c for c in ["date", "shift_type", "equipment", "location", "item", "group", "qty",
                        "parent_location", "Employee", "Activity", "Usage Type"] if c in df.columns]
    out = df[keep].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["qty"] = pd.to_numeric(out["qty"], errors="coerce")
    out = out.dropna(subset=["qty"])
    if "location" in out.columns:
        out["portal"] = out.apply(
            lambda r: normalize_portal_best(r.get("location"), r.get("parent_location")), axis=1
        )
    else:
        out["portal"] = "Unspecified"
    out["category"] = out["item"].apply(classify_real_item)
    out["stream"] = "live_jumbo_linked"
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Offsider store-issue logs from the monthly STOCK_USAGE_SHEETS workbooks:
#    "GS & VENT ISS UPDAE" tab (ground support + ventilation mixed, columns
#    4-8 = Date/Requester/Qty issued/Description/Area) and "Drill Cons Iss
#    Update" tab (columns 9-15 = Date/Requester/Machine/Shift/Qty issued/
#    Description/Area). Only May/June/July exist as separate monthly files;
#    August's equivalent, if it exists, was not part of this upload.
# ---------------------------------------------------------------------------

MONTHLY_STOCK_USAGE_FILES = {
    "May": "STOCK_USAGE_SHEETS_UPDATE_MAY.xlsx",
    "June": "STOCK_USAGE_SHEETS_UPDATE_JUNE.xlsx",
    "July": "STOCK_USAGE_SHEETS_UPDATE_JULY.xlsx",
}


def load_gs_usage_offsider(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    frames = []
    for month, fname in MONTHLY_STOCK_USAGE_FILES.items():
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            raw = pd.read_excel(path, sheet_name="GS & VENT ISS UPDAE", header=None)
        except Exception:
            continue
        sub = raw.iloc[1:, 4:9].copy()
        sub.columns = ["date", "requester", "qty", "item", "area"]
        sub = sub.dropna(subset=["date", "qty"])
        sub["month_tab"] = month
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["qty"] = pd.to_numeric(out["qty"], errors="coerce")
    out = out.dropna(subset=["qty"])
    out["item"] = out["item"].astype(str).str.strip()
    out["portal"] = out["area"].apply(normalize_portal)
    out["category"] = out["item"].apply(classify_real_item)
    out["stream"] = "offsider_store_issue"
    return out.reset_index(drop=True)


def load_drilling_usage_offsider_crosscheck(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    """Independent long-format drilling issue log (pre-consolidation), used
    only as a cross-check against the wide master workbook, not as the
    primary source, since it appears to be an earlier capture of the same
    underlying store requests."""
    frames = []
    for month, fname in MONTHLY_STOCK_USAGE_FILES.items():
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            raw = pd.read_excel(path, sheet_name="Drill Cons Iss Update", header=None)
        except Exception:
            continue
        sub = raw.iloc[1:, 9:16].copy()
        sub.columns = ["date", "requester", "machine", "shift", "qty", "item", "area"]
        sub = sub.dropna(subset=["date", "qty"])
        sub["month_tab"] = month
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["qty"] = pd.to_numeric(out["qty"], errors="coerce")
    out = out.dropna(subset=["qty"])
    out["item"] = out["item"].astype(str).str.strip()
    out["portal"] = out["area"].apply(normalize_portal)
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5. Physical stocktake sheets: section-tagged (Drilling Consumables - Jumbo
#    / - Production, Ground Support - Bolts / - Mesh / - Cable Bolts,
#    Ventilation). Column layout differs slightly month to month (labels
#    like "Start of Month Count" vs "End of July Count") so we match by
#    keyword rather than fixed name.
# ---------------------------------------------------------------------------

STOCKTAKE_SOURCES = [
    ("May", "EOM_PL_COUNT_SHEET_MAY_2026.xlsx", None),   # month tab picked dynamically
    ("June", "EOM_PL_COUNT_SHEET_JUNE_2026.xlsx", None),
    ("July", "NEW_End_July_EOM_Stocktake_Sheet.xlsx", "Stoktake Sheet"),
    ("August (mid-month)", "END_OF_AUGUST_EOM_PL_Stocktake_Sheet.xlsx", "Stocktake August MidMonth"),
]


def _section_tagged_stocktake(path: Path, sheet: str) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header_row_idx = None
    for i in range(min(6, len(raw))):
        row_vals = raw.iloc[i].astype(str)
        if row_vals.str.contains("count|received|used|usage", case=False, na=False).any():
            header_row_idx = i
            break
    if header_row_idx is None:
        return pd.DataFrame()
    header = raw.iloc[header_row_idx]
    section = None
    rows = []
    for i in range(header_row_idx + 1, len(raw)):
        row = raw.iloc[i]
        first_cell = row.iloc[0]
        # a section header row has text in col0 but nothing item-like in the rest
        if isinstance(first_cell, str) and row.iloc[2:5].isna().all():
            section = first_cell.strip()
            continue
        if row.iloc[2:5].isna().all():
            continue
        rows.append((section, i))
    if not rows:
        return pd.DataFrame()
    idxs = [i for _, i in rows]
    sections = [s for s, _ in rows]
    data = raw.loc[idxs].copy()
    data["section"] = sections
    # map generic column roles by header keyword
    colmap = {}
    for c in raw.columns:
        h = str(header[c]).lower()
        if "supplier code" in h:
            colmap["supplier_code"] = c
        elif h.strip() == "supplier":
            colmap["supplier"] = c
        elif "descri" in h:
            colmap["item"] = c
        elif h.strip() == "uom":
            colmap["uom"] = c
        elif "received" in h:
            colmap["received_qty"] = c
        elif "start" in h or "end of july" in h or "31-05" in h or "05-31" in h:
            colmap["start_qty"] = c
        elif "end" in h and "count" in h:
            colmap["end_qty"] = c
        elif "used" in h or "usage" in h:
            colmap["used_qty"] = c
    if "item" not in colmap:
        # Some stocktake tabs (e.g. the July/August sheets) never repeat a
        # "Description" header in the row we detected -- the item text is
        # still there, just unlabelled. Fall back to whichever of the first
        # few columns holds the longest average text: that's always the
        # item description column in every variant of this sheet seen.
        candidate_cols = [c for c in raw.columns if c <= 4 and c not in colmap.values()]
        best_col, best_len = None, 0
        for c in candidate_cols:
            vals = data[c].dropna().astype(str)
            if vals.empty:
                continue
            avg_len = vals.str.len().mean()
            if avg_len > best_len:
                best_len, best_col = avg_len, c
        if best_col is not None:
            colmap["item"] = best_col
    out = pd.DataFrame({k: data[c].values for k, c in colmap.items() if c in data.columns})
    out["section"] = data["section"].values
    for col in ["received_qty", "start_qty", "end_qty", "used_qty"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "item" in out.columns:
        out["item"] = out["item"].astype(str).str.strip()
        out = out[out["item"].notna() & (out["item"] != "nan")]
    out["category"] = out["item"].apply(classify_real_item) if "item" in out.columns else "uncategorized"
    return out.reset_index(drop=True)


def load_stocktake_all(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    frames = []
    for period, fname, sheet in STOCKTAKE_SOURCES:
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            xls = pd.ExcelFile(path)
        except Exception:
            continue
        target_sheet = sheet
        if target_sheet is None:
            # pick the sheet that looks like a dated count tab (contains an apostrophe/year)
            candidates = [s for s in xls.sheet_names if re.search(r"26|25", s)]
            target_sheet = candidates[-1] if candidates else xls.sheet_names[0]
        df = _section_tagged_stocktake(path, target_sheet)
        if df.empty:
            continue
        df["period_label"] = period
        df["source_file"] = fname
        df["source_sheet"] = target_sheet
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 6. Monthly EOM underground development (production/advance) reports:
#    one row per heading, with EOM Advance (m), Design Meters, GS Type, etc.
# ---------------------------------------------------------------------------

PRODUCTION_REPORT_FILES = {
    "May": ("May_2026_eom_ug_development_report.xlsx", "May_2026 eom ug dev"),
    "June": ("June_2026_eom_ug_development_report.xlsx", "June_2026 eom ug dev"),
    "July": ("July_2026_eom_ug_development_report.xlsx", "July_2026 eom ug dev"),
    "August": ("August_2026_eom_ug_development_report.xlsx", "August_2026 eom ug dev"),
}


def load_production_reports(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    frames = []
    for month, (fname, sheet) in PRODUCTION_REPORT_FILES.items():
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            raw = pd.read_excel(path, sheet_name=sheet, header=None)
        except Exception:
            continue
        header_row_idx = None
        for i in range(min(12, len(raw))):
            row_vals = raw.iloc[i].astype(str)
            if row_vals.str.contains("Heading name", case=False, na=False).any():
                header_row_idx = i
                break
        if header_row_idx is None:
            continue
        header = raw.iloc[header_row_idx]
        data = raw.iloc[header_row_idx + 2:].copy()  # skip the "(%)" units row right after header
        data.columns = [str(h).replace("\n", " ").strip() if pd.notna(h) else f"col{i}" for i, h in enumerate(header)]
        data = data.dropna(subset=[data.columns[2]])  # Heading name column
        # The sheet appends "Waste" / "Ore" grand-total rows (and further
        # down, signature/position rows) below the real per-heading rows.
        # A real heading row always carries a Cap/Op and GS Type value;
        # the total/signature rows do not -- use that to drop them so they
        # are never summed on top of the individual headings they total.
        if "Cap/Op" in data.columns:
            data = data[data["Cap/Op"].notna()]
        keep_cols = {c: c for c in data.columns}
        data = data.rename(columns=keep_cols)
        data["month_tab"] = month
        data["source_file"] = fname
        frames.append(data)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


# ---------------------------------------------------------------------------
# 7. Jumbo PLOD (per-shift drilling activity: holes drilled, hole length,
#    advance metres). Two files together span 1 May - 30 Aug 2026; the tail
#    of LiveMine_Data.xlsx (up to 22 Aug) overlaps the head of
#    Live_mine_data_August.xlsx (1-30 Aug), so duplicates are dropped.
# ---------------------------------------------------------------------------

def load_jumbo_plod_all(data_dir: Path = REAL_DATA_DIR) -> pd.DataFrame:
    frames = []
    for fname in ["LiveMine_Data.xlsx", "Live_mine_data_August.xlsx"]:
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            df = pd.read_excel(path, sheet_name="Jumbo PLOD", header=0)
        except Exception:
            continue
        df["source_file"] = fname
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    out = out.rename(columns={
        "Shift Date": "date", "Shift Type": "shift_type", "Equipment ID": "equipment",
        "Employee": "employee", "Source Locations": "location", "Parent Location": "parent_location",
        "Face Hole Drilled": "face_holes", "Ream Hole Drilled": "ream_holes",
        "Hole Length": "hole_length_m", "Charged Holes": "charged_holes",
        "Advance": "advance_m", "Wet Holes": "wet_holes", "Activity": "activity",
    })
    dedupe_cols = [c for c in ["date", "shift_type", "equipment", "employee", "location",
                                "face_holes", "ream_holes", "hole_length_m", "advance_m", "activity"]
                   if c in out.columns]
    out = out.drop_duplicates(subset=dedupe_cols).reset_index(drop=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["face_holes", "ream_holes", "hole_length_m", "charged_holes", "advance_m"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["metres_drilled"] = (out.get("face_holes", 0).fillna(0) + out.get("ream_holes", 0).fillna(0)) * out.get("hole_length_m", np.nan)
    if "location" in out.columns:
        out["portal"] = out.apply(
            lambda r: normalize_portal_best(r.get("location"), r.get("parent_location")), axis=1
        )
    else:
        out["portal"] = "Unspecified"
    is_ground_support_activity = out["activity"].astype(str).str.contains("GS", case=False, na=False) if "activity" in out.columns else False
    out["activity_class"] = np.where(is_ground_support_activity, "Ground support related", "Face/production drilling")
    return out
