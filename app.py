"""
DevAdvance Analytics
--------------------
Underground development cost and productivity intelligence: drilling and
ground support consumable unit cost, productivity baseline, and an
advance-rate sensitivity model, built so any underground mechanised mine can
load its own data and its own fixed costs.

DATA INTEGRITY POLICY
Every number on this page is derived only from data actually loaded, or an
input explicitly entered in the control panel. Nothing is estimated,
interpolated, or invented: a metric that cannot be computed from what is
available is shown as "Data not available" rather than a blank, a dash, or
an invented zero.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

import mining_core as mc
import navachab_loaders as nl

APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "logo.png"
NA = mc.NOT_AVAILABLE
MONTH_NUM = {"May": 5, "June": 6, "July": 7, "August": 8}
MONTH_ORDER = ["May", "June", "July", "August"]
ANALYSIS_START = pd.Timestamp(2026, 5, 1)
MESH_PRICE_ITEM, MESH_AREA_M2 = next(iter(nl.GS_MESH_ITEM_AREA_ALIASES.values()))

# ---------------------------------------------------------------------------
# Theme system: two absolute palettes, injected as CSS each rerun. Streamlit
# does not support a runtime theme switch natively (its theme is fixed at
# launch via config.toml), so this overrides the relevant containers
# directly -- the standard approach for an in-app light/dark toggle.
# ---------------------------------------------------------------------------
THEMES = {
    "dark": dict(
        bg="#0E1117", card_bg="#161B22", card_border="#2A313C", text="#FFFFFF", subtext="#9CA3AF",
        grid="#2A313C", green="#00D26A", amber="#FF9900", red="#FF4B4B", accent="#00D26A",
        plot_template="plotly_dark", surface="#0E1117",
    ),
    "light": dict(
        bg="#F5F6F8", card_bg="#FFFFFF", card_border="#E1E4E8", text="#0B0B0B", subtext="#52514E",
        grid="#E1E4E8", green="#0CA30C", amber="#B06F00", red="#D03B3B", accent="#186B4A",
        plot_template="plotly_white", surface="#FFFFFF",
    ),
}


def get_theme() -> dict:
    return THEMES[st.session_state.get("theme", "dark")]


def chart_layout(T: dict) -> dict:
    return dict(
        paper_bgcolor=T["card_bg"],
        plot_bgcolor=T["card_bg"],
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=T["text"], size=13),
        margin=dict(l=10, r=10, t=36, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )


CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

st.set_page_config(page_title="DevAdvance Analytics", page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📊", layout="wide")


def inject_css(T: dict):
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {T['bg']}; }}
        .stApp, .stApp p, .stApp span, .stApp label, .stApp div {{ color: {T['text']}; }}
        section[data-testid="stSidebar"] {{ background-color: {T['card_bg']}; border-right: 1px solid {T['card_border']}; }}
        section[data-testid="stSidebar"] * {{ color: {T['text']}; }}
        h1, h2, h3, h4, h5, h6 {{ color: {T['text']}; }}
        div[data-testid="stExpander"] {{ background-color: {T['card_bg']}; border: 1px solid {T['card_border']}; border-radius: 10px; }}
        .stTabs [data-baseweb="tab-list"] {{ background-color: {T['card_bg']}; border-radius: 10px; padding: 4px; gap: 2px; border: 1px solid {T['card_border']}; }}
        .stTabs [data-baseweb="tab"] {{ color: {T['subtext']}; border-radius: 8px; }}
        .stTabs [aria-selected="true"] {{ background-color: {T['accent']}26; color: {T['accent']} !important; }}
        div[data-testid="stMetric"] {{ background: {T['card_bg']}; border: 1px solid {T['card_border']}; border-radius: 10px; padding: 12px 14px; }}
        [data-testid="stMetricValue"] {{ color: {T['text']}; }}
        [data-testid="stMetricLabel"] {{ color: {T['subtext']}; }}
        div[data-testid="stDataFrame"] {{ border: 1px solid {T['card_border']}; border-radius: 8px; }}
        .stButton button, .stDownloadButton button, [data-testid="stFileUploader"] button {{
            border-radius: 8px; background-color: {T['card_bg']}; color: {T['text']} !important;
            border: 1px solid {T['card_border']};
        }}
        .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFileUploader"] button:hover {{
            border-color: {T['accent']}; color: {T['accent']} !important;
        }}
        [data-testid="stFileUploaderDropzone"] {{ background-color: {T['card_bg']}; border: 1px dashed {T['card_border']}; }}
        .stButton button[kind="primary"] {{ background-color: {T['accent']}; color: {T['bg']} !important; border: none; }}
        .stButton button[kind="primary"]:hover {{ background-color: {T['accent']}; color: {T['bg']} !important; opacity: 0.85; }}
        section[data-testid="stSidebar"] div[data-testid="stImage"] {{
            background:#0E1117; border-radius: 12px; padding: 14px; margin-bottom: 6px;
        }}
        .devadv-kpi {{ background:{T['card_bg']}; border:1px solid {T['card_border']}; border-radius:12px;
                       padding:14px 16px; height:100%; }}
        .devadv-kpi-label {{ font-size:0.76rem; color:{T['subtext']}; text-transform:uppercase; letter-spacing:0.03em; }}
        .devadv-kpi-value {{ font-size:1.6rem; font-weight:700; color:{T['text']}; margin-top:4px; }}
        .devadv-kpi-sub {{ font-size:0.78rem; color:{T['subtext']}; margin-top:3px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value_str: str, status: str = "neutral", sub: str | None = None, T: dict | None = None):
    T = T or get_theme()
    colors = {"good": T["green"], "warning": T["amber"], "critical": T["red"], "neutral": T["accent"]}
    color = colors.get(status, T["accent"])
    sub_html = f'<div class="devadv-kpi-sub">{sub}</div>' if sub else ""
    # Built as one unindented line: st.markdown runs its content through a
    # Markdown parser before HTML, and any line with >=4 leading spaces is
    # read as an indented code block -- a multi-line, indented f-string here
    # previously made the closing </div> render as literal visible text.
    html = (
        f'<div class="devadv-kpi" style="border-left:4px solid {color};">'
        f'<div class="devadv-kpi-label">{label}</div>'
        f'<div class="devadv-kpi-value">{value_str}</div>'
        f'{sub_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def notes_expander(title: str, expanded: bool = False):
    return st.expander(title, expanded=expanded)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and np.isnan(value))


def fmt_money(value, currency, decimals=2) -> str:
    if is_missing(value):
        return NA
    return f"{currency} {value:,.{decimals}f}"


def fmt_number(value, decimals=1, suffix="") -> str:
    if is_missing(value):
        return NA
    return f"{value:,.{decimals}f}{suffix}"


def safe_div(numerator, denominator):
    if is_missing(numerator) or is_missing(denominator) or denominator == 0:
        return None
    return numerator / denominator


def currency() -> str:
    return "N$" if st.session_state.get("fx_rate") else "USD"


def to_reporting_currency(usd_value):
    if is_missing(usd_value):
        return None
    rate = st.session_state.get("fx_rate")
    return usd_value * rate if rate else usd_value


def wrapped_table(df: pd.DataFrame, height=340, editable=False, select_columns=None, key=None, T=None):
    if df.empty:
        st.info(NA)
        return df
    T = T or get_theme()
    gob = GridOptionsBuilder.from_dataframe(df)
    gob.configure_default_column(wrapText=True, autoHeight=True, resizable=True, editable=editable, filter=False)
    if select_columns:
        for col, options in select_columns.items():
            gob.configure_column(col, editable=True, cellEditor="agSelectCellEditor", cellEditorParams={"values": options})
    grid_options = gob.build()
    response = AgGrid(
        df, gridOptions=grid_options, height=height,
        theme="alpine-dark" if st.session_state.get("theme") == "dark" else "alpine",
        update_mode=GridUpdateMode.VALUE_CHANGED if editable else GridUpdateMode.NO_UPDATE,
        data_return_mode=DataReturnMode.AS_INPUT,
        allow_unsafe_jscode=False, show_toolbar=False, show_search=False, show_download_button=False, key=key,
    )
    out = response.data
    return out if out is not None else df


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_state():
    defaults = {
        "theme": "dark",
        "page": "Overview",
        "fixed_costs_enabled": False,
        "fixed_labour_cost_per_shift": None,
        "fixed_machine_cost_per_shift": None,
        "fx_rate": None,
        "optimistic_pct": 15,
        "max_capacity_pct": 30,
        "monthly_report_month": "August",
        "bit_life_records": [
            {"portal": "North", "bit_spec": "45mm button bit", "hole_depth_m": 4.2,
             "holes_before_resharpen": 30, "holes_after_resharpen": 20,
             "bits_averaged": 3, "bit_price": None, "resharpen_cost": None},
            {"portal": "South", "bit_spec": "45mm button bit", "hole_depth_m": 4.2,
             "holes_before_resharpen": 30, "holes_after_resharpen": 25,
             "bits_averaged": 3, "bit_price": None, "resharpen_cost": None},
        ],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()
T = get_theme()
inject_css(T)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading development data...")
def load_everything():
    usage, monthly_totals = nl.load_drilling_usage_master()
    prices = nl.load_all_price_tables()
    gs_live = nl.load_gs_usage_live()
    gs_offsider = nl.load_gs_usage_offsider()
    drill_offsider_cc = nl.load_drilling_usage_offsider_crosscheck()
    stocktake = nl.load_stocktake_all()
    production = nl.load_production_reports()
    plod = nl.load_jumbo_plod_all()
    gss_design, cut_length_m = nl.load_gss_design_standard()
    costmodel_totals = nl.load_costmodel_totals()
    return dict(
        usage=usage, monthly_totals=monthly_totals, prices=prices, gs_live=gs_live,
        gs_offsider=gs_offsider, drill_offsider_cc=drill_offsider_cc,
        stocktake=stocktake, production=production, plod=plod,
        gss_design=gss_design, cut_length_m=cut_length_m,
        costmodel_totals=costmodel_totals,
    )


DATA = load_everything()


def _clip_to_analysis_window(df: pd.DataFrame) -> pd.DataFrame:
    """The analysis period for this study is May-August 2026, matching the
    physical stocktake sheets, the EOM development survey reports and the
    live ground-support log. The drilling stock-usage master happens to
    contain earlier months (Jan-Apr) from the mine's own systems, but those
    are outside the analysed period and are excluded here at the source so
    nothing downstream can accidentally surface a pre-May figure."""
    if df.empty or "date" not in df.columns:
        return df
    return df[df["date"] >= ANALYSIS_START].reset_index(drop=True)


DATA["usage"] = _clip_to_analysis_window(DATA["usage"])
DATA["gs_live"] = _clip_to_analysis_window(DATA["gs_live"])
DATA["plod"] = _clip_to_analysis_window(DATA["plod"])


@st.cache_data
def price_source_comparison():
    """Diagnostic only, never used to price anything: shows where the price
    baked into the monthly stock-usage workbook (what a shift record happens
    to say it cost) disagrees with the official static price list. Per
    direct confirmation, the static list is the mine's real, authoritative
    price -- any disagreement here means the *operational workbook* has a
    stale or mistyped unit cost for that item, not the other way round."""
    _, monthly_totals = nl.load_drilling_usage_master()
    embedded = nl.build_embedded_drilling_price_table(monthly_totals)
    flat = DATA["prices"]
    embedded_map = embedded.set_index("item")["unit_price"]
    flat_map = flat.dropna(subset=["unit_price"]).drop_duplicates(subset=["item"]).set_index("item")["unit_price"]
    joined = pd.DataFrame({"operational_workbook_price": embedded_map, "official_price_list": flat_map}).dropna()
    if joined.empty:
        return joined
    joined["ratio"] = joined["official_price_list"] / joined["operational_workbook_price"]
    mismatched = joined[(joined["ratio"] > 1.5) | (joined["ratio"] < 1 / 1.5)]
    return mismatched.reset_index().rename(columns={"index": "item"})


def price_map() -> pd.Series:
    """Ground truth for every cost computation in this app: the official
    static unit price list only (GS_UNIT_costs.xlsx for drilling,
    Consumables_Unit_Costs.xlsx for ground support). No other price source
    is blended in, per direct confirmation that this list is authoritative
    -- an item with no entry here shows as unpriced rather than falling
    back to a number from a different, unconfirmed source."""
    flat = DATA["prices"]
    return flat.dropna(subset=["unit_price"]).drop_duplicates(subset=["item"], keep="first").set_index("item")["unit_price"]


def attach_cost(df: pd.DataFrame, item_col="item", qty_col="qty") -> pd.DataFrame:
    if df.empty:
        return df.assign(unit_price=np.nan, cost=np.nan)
    pm = price_map()
    out = df.copy()
    out["unit_price"] = out[item_col].map(pm)
    out["cost"] = out["unit_price"] * out[qty_col]
    return out


def gs_price_series() -> pd.Series:
    p = DATA["prices"]
    p = p[p["price_source_file"] == "Consumables_Unit_Costs.xlsx"]
    return p.dropna(subset=["unit_price"]).drop_duplicates(subset=["item"]).set_index("item")["unit_price"]


def attach_gs_cost(df: pd.DataFrame, item_col="item", qty_col="qty") -> pd.DataFrame:
    if df.empty:
        return df.assign(unit_price=np.nan, cost=np.nan)
    gpm = gs_price_series()
    out = df.copy()
    resolved = out[item_col].apply(lambda it: nl.resolve_gs_price(it, gpm))
    out["unit_price"] = [r[0] for r in resolved]
    out["qty_multiplier"] = [r[1] for r in resolved]
    out["cost"] = out["unit_price"] * out[qty_col] * out["qty_multiplier"]
    return out


def overall_date_bounds():
    frames = [DATA["usage"], DATA["gs_live"], DATA["plod"]]
    mins, maxs = [], []
    for f in frames:
        if not f.empty and "date" in f.columns:
            d = f["date"].dropna()
            if not d.empty:
                mins.append(d.min())
                maxs.append(d.max())
    if not mins:
        return None, None
    return min(mins).date(), max(maxs).date()


DATA_MIN, DATA_MAX = overall_date_bounds()
st.session_state["date_range"] = (DATA_MIN, DATA_MAX) if DATA_MIN is not None else None

if not st.session_state.get("_bit_price_backfilled"):
    _pm = price_map()
    _verified_bit_price = _pm.get("A340X45MM BUTTON BIT")
    if _verified_bit_price is not None:
        for _rec in st.session_state["bit_life_records"]:
            if _rec.get("bit_spec") == "45mm button bit" and _rec.get("bit_price") is None:
                _rec["bit_price"] = float(_verified_bit_price)
    st.session_state["_bit_price_backfilled"] = True


def selected_range():
    rng = st.session_state.get("date_range")
    if not rng:
        return None, None
    start, end = rng
    return pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)


def filter_dates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    start, end = selected_range()
    if start is None:
        return df
    return df[(df["date"] >= start) & (df["date"] <= end)]


def months_in_range() -> set[str]:
    return set(MONTH_ORDER)


def month_bounds(month_label: str):
    num = MONTH_NUM[month_label]
    start = pd.Timestamp(2026, num, 1)
    end = start + pd.offsets.MonthEnd(1) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return start, end


def restrict_to_portals(df: pd.DataFrame, portal_col="portal"):
    if df.empty or portal_col not in df.columns:
        return df, 0
    mask = df[portal_col].isin(["North", "South"])
    return df[mask], int((~mask).sum())


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def pareto_chart(item_costs: pd.Series, top_n=12):
    s = item_costs.dropna().sort_values(ascending=False)
    if s.empty or s.sum() == 0:
        return None
    s = s.head(top_n)
    total = item_costs.dropna().sum()
    pct = (s / total * 100)
    cum_pct = pct.cumsum()
    fig = go.Figure()
    fig.add_bar(x=s.index, y=pct.values, marker_color=T["accent"], name="Share of total cost (%)",
                customdata=s.values, hovertemplate="%{x}<br>%{y:.1f}% of cost<extra></extra>")
    fig.add_scatter(x=s.index, y=cum_pct.values, mode="lines+markers", name="Cumulative %",
                     line=dict(color=T["amber"], width=2))
    fig.update_layout(**chart_layout(T), yaxis=dict(title="% of total cost", gridcolor=T["grid"], range=[0, max(105, cum_pct.max() * 1.05)]),
                       xaxis=dict(tickangle=-30))
    return fig


def trend_chart(monthly: pd.Series, y_title: str):
    if monthly.dropna().empty:
        return None
    fig = go.Figure()
    fig.add_bar(x=[str(i) for i in monthly.index], y=monthly.values, marker_color=T["accent"])
    fig.update_layout(**chart_layout(T), yaxis=dict(title=y_title, gridcolor=T["grid"]))
    return fig


def dual_trace_chart(categories, series_a, name_a, series_b, name_b, y_title):
    fig = go.Figure()
    fig.add_bar(x=categories, y=series_a, name=name_a, marker_color=T["accent"])
    fig.add_scatter(x=categories, y=series_b, name=name_b, mode="lines+markers", line=dict(color=T["amber"], width=3))
    fig.update_layout(**chart_layout(T), yaxis=dict(title=y_title, gridcolor=T["grid"]))
    return fig


def variance_gauge(pct_value: float, title: str, good=8, warn=20):
    color = T["green"] if pct_value <= good else (T["amber"] if pct_value <= warn else T["red"])
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=pct_value, number={"suffix": "%"},
        title={"text": title, "font": {"size": 13, "color": T["text"]}},
        gauge={
            "axis": {"range": [0, max(40, pct_value * 1.2)], "tickcolor": T["subtext"]},
            "bar": {"color": color},
            "bgcolor": T["card_bg"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, good], "color": T["green"] + "33"},
                {"range": [good, warn], "color": T["amber"] + "33"},
                {"range": [warn, max(40, pct_value * 1.2)], "color": T["red"] + "33"},
            ],
        },
    ))
    fig.update_layout(paper_bgcolor=T["card_bg"], font=dict(color=T["text"]), height=220, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def yield_gauge(pct_value: float, title: str):
    color = T["red"] if pct_value < 60 else (T["amber"] if pct_value < 80 else T["green"])
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=pct_value, number={"suffix": "%"},
        title={"text": title, "font": {"size": 13, "color": T["text"]}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": T["subtext"]},
            "bar": {"color": color},
            "bgcolor": T["card_bg"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, 60], "color": T["red"] + "33"},
                {"range": [60, 80], "color": T["amber"] + "33"},
                {"range": [80, 100], "color": T["green"] + "33"},
            ],
        },
    ))
    fig.update_layout(paper_bgcolor=T["card_bg"], font=dict(color=T["text"]), height=220, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def cost_treemap(item_costs: pd.Series, top_n=14):
    s = item_costs.dropna()
    s = s[s > 0].sort_values(ascending=False).head(top_n)
    if s.empty:
        return None
    fig = go.Figure(go.Treemap(
        labels=[str(i) for i in s.index], parents=[""] * len(s), values=s.values,
        marker=dict(colors=s.values, colorscale=[[0, T["accent"] + "55"], [1, T["accent"]]], line=dict(color=T["card_bg"], width=2)),
        textinfo="label+value+percent root", texttemplate="%{label}<br>%{value:,.0f}",
    ))
    layout = chart_layout(T)
    layout["margin"] = dict(l=4, r=4, t=4, b=4)
    fig.update_layout(**layout)
    return fig


def sensitivity_chart(df: pd.DataFrame, cur: str):
    fig = go.Figure()
    fig.add_bar(x=df["scenario"], y=df["fixed_cost_component_n_per_m"], name=f"Fixed cost component ({cur}/m)", marker_color=T["accent"])
    fig.add_bar(x=df["scenario"], y=df["variable_cost_component_n_per_m"], name=f"Variable cost component ({cur}/m)", marker_color=T["amber"])
    fig.add_scatter(x=df["scenario"], y=df["total_unit_cost_n_per_m"], mode="lines+markers", name=f"Total unit cost ({cur}/m)",
                     line=dict(color=T["red"], width=2))
    fig.update_layout(**chart_layout(T), barmode="stack", yaxis=dict(title=f"{cur} / metre", gridcolor=T["grid"]))
    return fig


def sensitivity_curve_chart(curve: pd.DataFrame, cur: str, baseline_rate: float, markers: dict):
    fig = go.Figure()
    fig.add_scatter(x=curve["advance_rate_m_per_shift"], y=curve["total_unit_cost_n_per_m"], mode="lines",
                     line=dict(color=T["accent"], width=3), name=f"Total unit cost ({cur}/m)", fill="tozeroy",
                     fillcolor=T["accent"] + "18")
    for label, (rate, cost) in markers.items():
        if rate is None or cost is None:
            continue
        fig.add_scatter(x=[rate], y=[cost], mode="markers+text", text=[label], textposition="top center",
                         marker=dict(size=10, color=T["amber"]), textfont=dict(color=T["text"], size=11), showlegend=False)
    fig.update_layout(**chart_layout(T), xaxis=dict(title="Advance rate (m/shift)", gridcolor=T["grid"]),
                       yaxis=dict(title=f"Total unit cost ({cur}/m)", gridcolor=T["grid"]))
    return fig


def round_efficiency_chart(months, advance_per_round, support_n_per_m, cur):
    """Dual-axis by design: advance-per-round (metres) and support unit cost
    (currency/m) are different units, and the entire point of this chart is
    to show them moving in opposite directions on the same month axis --
    a single shared axis would misrepresent one of the two series."""
    fig = go.Figure()
    fig.add_bar(x=months, y=advance_per_round, name="Advance per round (m)", marker_color=T["accent"], yaxis="y1")
    fig.add_scatter(x=months, y=support_n_per_m, name=f"Support unit cost ({cur}/m)", mode="lines+markers",
                     line=dict(color=T["amber"], width=3), yaxis="y2")
    layout = chart_layout(T)
    layout["yaxis"] = dict(title="Advance per round (m)", gridcolor=T["grid"])
    layout["yaxis2"] = dict(title=f"Support unit cost ({cur}/m)", overlaying="y", side="right", showgrid=False)
    fig.update_layout(**layout)
    return fig


def gs_waterfall_chart(design_cost, offsider_cost, stocktake_cost, live_cost, cur):
    """Design Required -> Offsider Issue Log -> Physical Stocktake is the
    primary escalation (each step a genuinely more complete measurement of
    the same consumption); Live Jumbo Log is appended as a fourth stage
    since it's valuable corroborating data, not because it sits logically
    between the other three. Every step/segment carries both its dollar
    delta and the % change from the previous stage."""
    stages = [("Design requirement", design_cost), ("Offsider issue log", offsider_cost),
              ("Physical stocktake", stocktake_cost), ("Live jumbo log", live_cost)]
    stages = [(label, val) for label, val in stages if val is not None]
    if len(stages) < 2:
        return None
    x, measure, y, text = [stages[0][0]], ["absolute"], [stages[0][1]], [fmt_money(stages[0][1], cur, 0)]
    base = stages[0][1]
    for label, val in stages[1:]:
        delta = val - base
        pct = safe_div(delta, base)
        pct_txt = f" ({pct*100:+.0f}%)" if pct is not None else ""
        x.append(f"Δ to {label.lower()}"); measure.append("relative"); y.append(delta); text.append(f"{fmt_money(delta, cur, 0)}{pct_txt}")
        x.append(label); measure.append("total"); y.append(val); text.append(fmt_money(val, cur, 0))
        base = val
    fig = go.Figure(go.Waterfall(
        x=x, measure=measure, y=y, text=text, textposition="outside",
        increasing=dict(marker=dict(color=T["red"])), decreasing=dict(marker=dict(color=T["green"])),
        totals=dict(marker=dict(color=T["accent"])), connector=dict(line=dict(color=T["grid"])),
    ))
    fig.update_layout(**chart_layout(T), yaxis=dict(title=f"Ground support cost ({cur})", gridcolor=T["grid"]), showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# Shared computations
# ---------------------------------------------------------------------------

def drilling_slice():
    u = filter_dates(DATA["usage"])
    if u.empty or "category" not in u.columns:
        u = pd.DataFrame()
    else:
        u = u[u["category"] == "drilling"]
    return attach_cost(u)


def gs_live_slice():
    g = filter_dates(DATA["gs_live"])
    if g.empty or "category" not in g.columns:
        g = pd.DataFrame()
    else:
        g = g[g["category"] == "ground_support"]
    return attach_gs_cost(g)


def gs_offsider_slice():
    g = filter_dates(DATA["gs_offsider"])
    if g.empty or "category" not in g.columns:
        g = pd.DataFrame()
    else:
        g = g[g["category"] == "ground_support"]
    return attach_gs_cost(g)


def drilling_offsider_slice():
    """The offsider store-issue log's drilling-side crosscheck (May-July
    only). Used only for discrepancy-checking against the physical
    stocktake, never as a headline number -- see the leakage KPI."""
    d = filter_dates(DATA["drill_offsider_cc"])
    if d.empty:
        return d
    return attach_cost(d)


def stocktake_category_slice(category: str, period_label: str | None = None) -> pd.DataFrame:
    """The physical stocktake sheets (start count + received - end count =
    used_qty) are the primary source for whole-mine unit cost. A used_qty
    below zero is physically impossible (material cannot be un-consumed) --
    it means a stock receipt landed between counts without being logged in
    the 'received' column. Those rows are flagged and excluded from cost
    totals rather than allowed to silently understate spend; see
    stocktake_flagged_negative for the excluded rows."""
    d = DATA["stocktake"]
    if d.empty:
        return d
    d = d[d["category"] == category].copy()
    if period_label is not None:
        d = d[d["period_label"] == period_label]
    if d.empty:
        return d
    if category == "drilling":
        pm = price_map()
        d["unit_price"] = d["item"].map(pm)
        d["qty_multiplier"] = 1.0
    elif category == "ground_support":
        gpm = gs_price_series()
        resolved = d["item"].apply(lambda it: nl.resolve_gs_price(it, gpm))
        d["unit_price"] = [r[0] for r in resolved]
        d["qty_multiplier"] = [r[1] for r in resolved]
    else:
        d["unit_price"] = np.nan
        d["qty_multiplier"] = 1.0
    d["negative_usage_flag"] = d["used_qty"] < 0
    d["cost"] = np.where(d["negative_usage_flag"], np.nan, d["unit_price"] * d["used_qty"] * d["qty_multiplier"])
    return d


def itemized_breakdown(stk_df: pd.DataFrame, qty_col="used_qty") -> pd.DataFrame:
    """Item, quantity, unit price, cost, and % of category total -- the same
    shape for drilling and ground support so both categories get identical
    detail and layout."""
    if stk_df.empty or "cost" not in stk_df.columns:
        return pd.DataFrame()
    agg = stk_df.groupby("item", dropna=False).agg(
        quantity=(qty_col, "sum"), unit_price=("unit_price", "first"), cost=("cost", "sum"),
    ).reset_index()
    agg = agg.sort_values("cost", ascending=False, na_position="last")
    total = agg["cost"].sum(skipna=True)
    agg["pct_of_category"] = agg["cost"] / total * 100 if total else np.nan
    return agg


def stocktake_flagged_negative() -> pd.DataFrame:
    frames = []
    for cat in ("drilling", "ground_support"):
        d = stocktake_category_slice(cat)
        if not d.empty:
            frames.append(d[d["negative_usage_flag"]])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def priced_coverage_note(df: pd.DataFrame, qty_col="qty") -> str | None:
    if df.empty or "unit_price" not in df.columns or qty_col not in df.columns:
        return None
    unpriced = df[df["unit_price"].isna()]
    if unpriced.empty:
        return None
    unpriced_qty = unpriced[qty_col].sum()
    total_qty = df[qty_col].sum()
    items = sorted(unpriced["item"].dropna().unique().tolist())
    pct = safe_div(unpriced_qty, total_qty)
    pct_txt = f"{pct * 100:.0f}%" if pct is not None else "an unknown share of"
    return f"{pct_txt} of usage volume has no matching price ({', '.join(items[:6])}{'...' if len(items) > 6 else ''}) and is excluded from the cost totals above."


def plod_slice():
    return filter_dates(DATA["plod"])


def total_or_none(series: pd.Series):
    s = series.dropna()
    return float(s.sum()) if not s.empty else None


def production_in_range(month_label: str | None = None) -> pd.DataFrame:
    pr = DATA["production"]
    if pr.empty:
        return pr
    if month_label is not None:
        return pr[pr["month_tab"] == month_label]
    return pr[pr["month_tab"].isin(MONTH_ORDER)]


def production_advance_by_portal(month_label: str | None = None):
    pr = production_in_range(month_label)
    empty = pd.DataFrame(columns=["advance_m"])
    if pr.empty or "Heading name" not in pr.columns or "EOM Advance" not in pr.columns:
        return empty, 0
    d = pr.copy()
    d["EOM Advance"] = pd.to_numeric(d["EOM Advance"], errors="coerce")
    d["portal"] = d["Heading name"].apply(nl.normalize_portal)
    restricted, n_excluded = restrict_to_portals(d)
    if restricted.empty:
        return empty, n_excluded
    by_portal = restricted.groupby("portal")["EOM Advance"].sum(min_count=1).rename("advance_m").to_frame()
    return by_portal, n_excluded


def production_report_advance_by_month():
    pr = production_in_range()
    if pr.empty or "EOM Advance" not in pr.columns:
        return pd.Series(dtype=float)
    pr = pr.copy()
    pr["EOM Advance"] = pd.to_numeric(pr["EOM Advance"], errors="coerce")
    s = pr.groupby("month_tab")["EOM Advance"].sum(min_count=1)
    return s.reindex([m for m in MONTH_ORDER if m in s.index])


def productivity_summary():
    pr = production_in_range()
    plod = plod_slice()
    if pr.empty and plod.empty:
        return None

    total_advance = None
    n_heading_months = None
    if not pr.empty and "EOM Advance" in pr.columns:
        adv = pd.to_numeric(pr["EOM Advance"], errors="coerce")
        if adv.notna().any():
            total_advance = float(adv.sum(skipna=True))
            n_heading_months = int(adv.notna().sum())

    total_drilled = total_or_none(plod["metres_drilled"]) if not plod.empty else None

    shift_count = None
    if not plod.empty:
        shift_groups = plod.groupby(["date", "shift_type", "equipment"], dropna=False)
        shift_count = shift_groups.ngroups if shift_groups.ngroups else None

    avg_rate_per_shift = safe_div(total_advance, shift_count)
    avg_advance_per_heading_month = safe_div(total_advance, n_heading_months)

    by_portal_survey, n_excluded_survey = production_advance_by_portal()

    plod_restricted, n_excluded_plod = restrict_to_portals(plod) if not plod.empty else (plod, 0)
    by_portal_plod = (
        plod_restricted.groupby("portal", dropna=False).agg(
            advance_m=("advance_m", "sum"), metres_drilled=("metres_drilled", "sum")
        )
        if not plod_restricted.empty else pd.DataFrame(columns=["advance_m", "metres_drilled"])
    )

    return dict(
        total_advance=total_advance, total_drilled=total_drilled, shift_count=shift_count,
        avg_rate_per_shift=avg_rate_per_shift, avg_advance_per_heading_month=avg_advance_per_heading_month,
        n_heading_months=n_heading_months,
        by_portal=by_portal_survey, n_excluded_survey_portal=n_excluded_survey,
        by_portal_plod=by_portal_plod, n_excluded_plod_portal=n_excluded_plod,
    )


def bit_life_calc() -> pd.DataFrame | None:
    records = st.session_state.get("bit_life_records", [])
    if not records:
        return None
    calc = pd.DataFrame(records)
    if calc.empty:
        return None
    calc["metres_before"] = calc["hole_depth_m"] * calc["holes_before_resharpen"]
    calc["metres_after"] = calc["hole_depth_m"] * calc["holes_after_resharpen"]
    calc["total_holes"] = calc["holes_before_resharpen"] + calc["holes_after_resharpen"]
    calc["total_metres"] = calc["metres_before"] + calc["metres_after"]
    calc["resharpen_yield_pct"] = calc["holes_after_resharpen"] / calc["holes_before_resharpen"] * 100
    calc["cost_per_m_no_resharpen"] = calc.apply(lambda r: safe_div(r["bit_price"], r["metres_before"]), axis=1)
    calc["cost_per_m_with_resharpen"] = calc.apply(
        lambda r: safe_div(r["bit_price"] + r["resharpen_cost"], r["total_metres"])
        if r["bit_price"] is not None and r["resharpen_cost"] is not None else None, axis=1)
    calc["pct_saving"] = calc.apply(
        lambda r: safe_div(r["cost_per_m_no_resharpen"] - r["cost_per_m_with_resharpen"], r["cost_per_m_no_resharpen"]) * 100
        if r["cost_per_m_no_resharpen"] not in (None, 0) and r["cost_per_m_with_resharpen"] is not None else None, axis=1)
    return calc


def design_required_cost(months: list[str] | None = None):
    """Whole-mine theoretical ground support spend implied by the approved
    design standard (minimum quantity per cut) applied to each portal's
    actual metres advanced. This is the closest thing to a 'budget' this
    dataset supports -- there is no independent drilling design/theoretical
    benchmark loaded, so this figure is ground-support only.

    months restricts the portal-advance input to specific months (e.g. to
    match a comparison stream, like the offsider log, that doesn't cover
    the full analysed period) -- default is the whole analysed period."""
    gss_design = DATA["gss_design"]
    cut_length_m = DATA["cut_length_m"]
    if gss_design.empty or cut_length_m is None:
        return None
    if months is None:
        _prod = productivity_summary()
        by_portal = _prod["by_portal"] if _prod else pd.DataFrame()
    else:
        pr_all = DATA["production"]
        by_portal = pd.DataFrame(columns=["advance_m"])
        if pr_all.empty or "month_tab" not in pr_all.columns:
            pr = pd.DataFrame()
        else:
            pr = pr_all[pr_all["month_tab"].isin(months)]
        if not pr.empty and "Heading name" in pr.columns and "EOM Advance" in pr.columns:
            d = pr.copy()
            d["EOM Advance"] = pd.to_numeric(d["EOM Advance"], errors="coerce")
            d["portal"] = d["Heading name"].apply(nl.normalize_portal)
            d, _ = restrict_to_portals(d)
            if not d.empty:
                by_portal = d.groupby("portal")["EOM Advance"].sum(min_count=1).rename("advance_m").to_frame()
    prod = {"by_portal": by_portal}
    if prod["by_portal"].empty:
        return None
    item_cols = [
        ("md_bolt_2_4m", "MD Bolt - 47mm - 2.4m", 1.0),
        ("split_set_2_4m", "Split Set - 47mm Galvanised - 2.4m", 1.0),
        ("stubby_split_set_0_9m", "Split Set - 39mm Galvanised - 0.9m", 1.0),
        ("mesh_sheet", MESH_PRICE_ITEM, MESH_AREA_M2),
    ]
    portal_to_gss = {"South": "GSS_01", "North": "GSS_02"}
    design_by_standard = gss_design.set_index("standard")
    gpm = gs_price_series()
    total = 0.0
    found_any = False
    for portal, gss_key in portal_to_gss.items():
        if gss_key not in design_by_standard.index or portal not in prod["by_portal"].index:
            continue
        portal_advance = prod["by_portal"].loc[portal, "advance_m"]
        design_row = design_by_standard.loc[gss_key]
        for col, price_item, area in item_cols:
            design_per_cut = design_row[col]
            if pd.isna(design_per_cut) or portal_advance is None:
                continue
            expected_qty = (design_per_cut / cut_length_m) * portal_advance
            price = gpm.get(price_item)
            if price is None:
                continue
            total += expected_qty * area * price
            found_any = True
    return total if found_any else None


# ---------------------------------------------------------------------------
# Monthly breakdown, peak-driver detection, variance/causal analysis
# ---------------------------------------------------------------------------

def monthly_cost_table():
    """Whole-mine drilling and ground support cost by month, from the
    physical stocktake sheets (August is a mid-month count, so its figure
    covers roughly half a month, not a full one -- shown as-is, not scaled,
    since scaling would be an estimate)."""
    rows = []
    for month in MONTH_ORDER:
        period_label = "August (mid-month)" if month == "August" else month
        d_cost = total_or_none(stocktake_category_slice("drilling", period_label)["cost"]) if not DATA["stocktake"].empty else None
        g_cost = total_or_none(stocktake_category_slice("ground_support", period_label)["cost"]) if not DATA["stocktake"].empty else None
        rows.append({"month": month, "drilling_cost": d_cost, "ground_support_cost": g_cost,
                     "total_cost": (d_cost or 0) + (g_cost or 0) if (d_cost is not None or g_cost is not None) else None})
    return pd.DataFrame(rows)


def peak_month_info():
    tbl = monthly_cost_table()
    if tbl["total_cost"].dropna().empty:
        return None
    idx = tbl["total_cost"].idxmax()
    peak_month = tbl.loc[idx, "month"]
    period_label = "August (mid-month)" if peak_month == "August" else peak_month
    drivers = []
    for cat in ("drilling", "ground_support"):
        d = stocktake_category_slice(cat, period_label)
        if d.empty:
            continue
        top = d.groupby("item")["cost"].sum(min_count=1).dropna().sort_values(ascending=False).head(3)
        for item, cost in top.items():
            drivers.append({"category": cat, "item": item, "cost": cost})
    drivers_df = pd.DataFrame(drivers).sort_values("cost", ascending=False) if drivers else pd.DataFrame()
    return dict(month=peak_month, total_cost=tbl.loc[idx, "total_cost"], drivers=drivers_df, table=tbl)


def abnormal_items_for_month(month_label: str, threshold_multiplier: float = 1.8):
    """Items whose stocktake quantity in one month runs far above that
    item's own typical monthly quantity across the analysed period --
    reuses the same median-multiplier heuristic as the shift-level catch-up
    flag, applied at month grain instead of shift grain."""
    rows = []
    for cat in ("drilling", "ground_support"):
        frames = []
        for month in MONTH_ORDER:
            period_label = "August (mid-month)" if month == "August" else month
            d = stocktake_category_slice(cat, period_label)
            if d.empty:
                continue
            agg = d.groupby("item", dropna=False)["used_qty"].sum().reset_index()
            agg["month"] = month
            frames.append(agg)
        if not frames:
            continue
        long = pd.concat(frames, ignore_index=True).rename(columns={"used_qty": "quantity"})
        flagged = mc.flag_catchup_spikes(long, threshold_multiplier=threshold_multiplier)
        if flagged is None:
            continue
        hits = flagged[(flagged["month"] == month_label) & (flagged["possible_catchup_spike"])]
        for _, r in hits.iterrows():
            rows.append({"category": cat, "item": r["item"], "month_quantity": r["quantity"]})
    return pd.DataFrame(rows)


def portal_overbreak_summary(month_label: str | None = None):
    pr = production_in_range(month_label)
    if pr.empty or "OverBreak" not in pr.columns:
        return pd.DataFrame()
    d = pr.copy()
    d["OverBreak"] = pd.to_numeric(d["OverBreak"], errors="coerce")
    d["UnderBreak"] = pd.to_numeric(d["UnderBreak"], errors="coerce")
    d["portal"] = d["Heading name"].apply(nl.normalize_portal)
    d, _ = restrict_to_portals(d)
    if d.empty:
        return pd.DataFrame()
    return d.groupby("portal")[["OverBreak", "UnderBreak"]].mean()


def round_efficiency_table():
    """Dynamic, non-hardcoded scan of every month actually present in the
    dataset (MONTH_ORDER, never a fixed pair of months). A 'round' is
    approximated by one production-report row (one heading reported in one
    month = one fired cut/cycle) -- the only proxy for round count this
    data supports. Ground support is applied per round, roughly independent
    of how far that round advanced, so a month with unusually short rounds
    carries the same support overhead spread over fewer metres, inflating
    N$/m even when nothing about per-item consumption rates changed."""
    rows = []
    for month in MONTH_ORDER:
        period_label = "August (mid-month)" if month == "August" else month
        pr = production_in_range(month)
        n_rounds = len(pr) if not pr.empty else None
        adv = None
        if not pr.empty and "EOM Advance" in pr.columns:
            adv_series = pd.to_numeric(pr["EOM Advance"], errors="coerce")
            if adv_series.notna().any():
                adv = float(adv_series.sum(skipna=True))
        avg_advance_per_round = safe_div(adv, n_rounds)

        gs_stk = stocktake_category_slice("ground_support", period_label)
        drill_stk = stocktake_category_slice("drilling", period_label)
        gs_cost = total_or_none(gs_stk["cost"]) if not gs_stk.empty else None
        drill_cost = total_or_none(drill_stk["cost"]) if not drill_stk.empty else None
        gs_cost_per_round = safe_div(gs_cost, n_rounds)
        gs_n_per_m = safe_div(gs_cost, adv)
        drilling_n_per_m = safe_div(drill_cost, adv)
        total_n_per_m = None
        if gs_n_per_m is not None or drilling_n_per_m is not None:
            total_n_per_m = (gs_n_per_m or 0) + (drilling_n_per_m or 0)

        rows.append(dict(
            month=month, n_rounds=n_rounds, total_advance=adv, avg_advance_per_round=avg_advance_per_round,
            gs_cost=gs_cost, gs_cost_per_round=gs_cost_per_round, gs_n_per_m=gs_n_per_m,
            drilling_n_per_m=drilling_n_per_m, total_n_per_m=total_n_per_m,
        ))
    tbl = pd.DataFrame(rows)

    baseline_advance_per_round = tbl["avg_advance_per_round"].mean(skipna=True)
    baseline_gs_cost_per_round = tbl["gs_cost_per_round"].mean(skipna=True)
    tbl["pct_below_baseline_advance"] = tbl["avg_advance_per_round"].apply(
        lambda v: safe_div(baseline_advance_per_round - v, baseline_advance_per_round) if pd.notna(v) and baseline_advance_per_round else None
    )
    flagged_months = tbl[tbl["pct_below_baseline_advance"].apply(lambda v: v is not None and v > 0.15)]["month"].tolist()

    return dict(
        table=tbl, baseline_advance_per_round=baseline_advance_per_round,
        baseline_gs_cost_per_round=baseline_gs_cost_per_round, flagged_months=flagged_months,
    )


def generate_monthly_report(month_label: str) -> dict:
    period_label = "August (mid-month)" if month_label == "August" else month_label
    prod_m = production_in_range(month_label)
    plod_m = DATA["plod"]
    if not plod_m.empty:
        start, end = month_bounds(month_label)
        plod_m = plod_m[(plod_m["date"] >= start) & (plod_m["date"] <= end)]

    adv_m = None
    n_headings = None
    if not prod_m.empty and "EOM Advance" in prod_m.columns:
        adv_series = pd.to_numeric(prod_m["EOM Advance"], errors="coerce")
        if adv_series.notna().any():
            adv_m = float(adv_series.sum(skipna=True))
            n_headings = int(adv_series.notna().sum())
    avg_advance_per_heading = safe_div(adv_m, n_headings)

    shift_count_m = None
    if not plod_m.empty:
        shift_count_m = plod_m.groupby(["date", "shift_type", "equipment"], dropna=False).ngroups or None
    avg_rate_m = safe_div(adv_m, shift_count_m)

    drill_stk_m = stocktake_category_slice("drilling", period_label)
    gs_stk_m = stocktake_category_slice("ground_support", period_label)
    drilling_cost_m = total_or_none(drill_stk_m["cost"]) if not drill_stk_m.empty else None
    gs_cost_m = total_or_none(gs_stk_m["cost"]) if not gs_stk_m.empty else None
    drilling_n_per_m = safe_div(drilling_cost_m, adv_m)
    gs_n_per_m = safe_div(gs_cost_m, adv_m)
    total_cost_m = (drilling_cost_m or 0) + (gs_cost_m or 0) if (drilling_cost_m is not None or gs_cost_m is not None) else None
    total_n_per_m = safe_div(total_cost_m, adv_m)

    by_portal_adv, n_excl = production_advance_by_portal(month_label)

    heading_tbl = pd.DataFrame()
    if not prod_m.empty:
        cols = [c for c in ["Heading name", "GS Type", "Cap/Op", "EOM Advance", "OverBreak", "UnderBreak"] if c in prod_m.columns]
        heading_tbl = prod_m[cols].copy()
        if "OverBreak" in heading_tbl.columns:
            heading_tbl["OverBreak"] = pd.to_numeric(heading_tbl["OverBreak"], errors="coerce") * 100
        if "UnderBreak" in heading_tbl.columns:
            heading_tbl["UnderBreak"] = pd.to_numeric(heading_tbl["UnderBreak"], errors="coerce") * 100

    monthly_tbl = monthly_cost_table()
    other_months = monthly_tbl[monthly_tbl["month"] != month_label]
    this_row = monthly_tbl[monthly_tbl["month"] == month_label]
    variance = {}
    if not this_row.empty and other_months["total_cost"].notna().any():
        avg_other = other_months["total_cost"].mean(skipna=True)
        this_total = this_row.iloc[0]["total_cost"]
        if this_total is not None and avg_other:
            variance["total_cost_vs_avg_pct"] = (this_total - avg_other) / avg_other * 100
    idx_this = MONTH_ORDER.index(month_label)
    if idx_this > 0:
        prev_month = MONTH_ORDER[idx_this - 1]
        prev_row = monthly_tbl[monthly_tbl["month"] == prev_month]
        if not prev_row.empty and not this_row.empty:
            prev_total = prev_row.iloc[0]["total_cost"]
            this_total = this_row.iloc[0]["total_cost"]
            if prev_total:
                variance["total_cost_vs_prev_month_pct"] = (this_total - prev_total) / prev_total * 100
                variance["prev_month"] = prev_month

    pareto_items = []
    for cat, d in (("drilling", drill_stk_m), ("ground_support", gs_stk_m)):
        if d.empty:
            continue
        top = d.groupby("item")["cost"].sum(min_count=1).dropna().sort_values(ascending=False).head(5)
        for item, cost in top.items():
            pareto_items.append({"category": cat, "item": item, "cost": cost})
    pareto_df = pd.DataFrame(pareto_items).sort_values("cost", ascending=False) if pareto_items else pd.DataFrame()

    abnormal = abnormal_items_for_month(month_label)
    overbreak_by_portal = portal_overbreak_summary(month_label)

    observations = []
    rank = monthly_tbl["total_cost"].rank(ascending=False, method="min")
    this_rank = rank[monthly_tbl["month"] == month_label]
    if not this_rank.empty and pd.notna(this_rank.iloc[0]):
        r = int(this_rank.iloc[0])
        ordinal = {1: "highest", 2: "second-highest", 3: "third-highest", 4: "lowest"}.get(r, f"#{r}")
        observations.append(f"{month_label} recorded the {ordinal} combined consumable spend of the four months in the analysed period.")
    if "total_cost_vs_prev_month_pct" in variance:
        direction = "up" if variance["total_cost_vs_prev_month_pct"] >= 0 else "down"
        observations.append(f"Combined consumable spend is {direction} {abs(variance['total_cost_vs_prev_month_pct']):.1f}% versus {variance.get('prev_month')}.")
    if not pareto_df.empty:
        top_row = pareto_df.iloc[0]
        cat_total = drilling_cost_m if top_row["category"] == "drilling" else gs_cost_m
        share = safe_div(top_row["cost"], cat_total)
        share_txt = f" ({share*100:.0f}% of {top_row['category'].replace('_', ' ')} spend)" if share is not None else ""
        observations.append(f"{top_row['item']} was the largest single cost driver this month{share_txt}.")
    if not by_portal_adv.empty and set(["North", "South"]).issubset(by_portal_adv.index):
        n_adv, s_adv = by_portal_adv.loc["North", "advance_m"], by_portal_adv.loc["South", "advance_m"]
        observations.append(f"North portal advanced {n_adv:.1f} m against {s_adv:.1f} m in the South this month.")
    if not overbreak_by_portal.empty and set(["North", "South"]).issubset(overbreak_by_portal.index):
        ob_n = overbreak_by_portal.loc["North", "OverBreak"] * 100
        ob_s = overbreak_by_portal.loc["South", "OverBreak"] * 100
        if abs(ob_n - ob_s) > 1.5:
            higher = "North" if ob_n > ob_s else "South"
            observations.append(
                f"Average overbreak this month is higher in the {higher} portal ({max(ob_n, ob_s):.1f}% vs {min(ob_n, ob_s):.1f}%), "
                f"a plausible contributor if that portal's ground support consumption also runs above design."
            )
    if not abnormal.empty:
        items_txt = ", ".join(abnormal["item"].head(4).tolist())
        observations.append(f"{len(abnormal)} item(s) this month deviate sharply from their typical monthly quantity: {items_txt}. Cross-check against the shift schedule for a legitimate catch-up pass versus genuine over-consumption.")

    return dict(
        month=month_label, adv_m=adv_m, n_headings=n_headings, avg_advance_per_heading=avg_advance_per_heading,
        shift_count_m=shift_count_m, avg_rate_m=avg_rate_m, drilling_cost_m=drilling_cost_m, gs_cost_m=gs_cost_m,
        drilling_n_per_m=drilling_n_per_m, gs_n_per_m=gs_n_per_m, total_cost_m=total_cost_m, total_n_per_m=total_n_per_m,
        by_portal_adv=by_portal_adv, heading_tbl=heading_tbl, monthly_tbl=monthly_tbl, variance=variance,
        pareto_df=pareto_df, abnormal=abnormal, overbreak_by_portal=overbreak_by_portal, observations=observations,
    )


# ---------------------------------------------------------------------------
# Sidebar / control panel
# ---------------------------------------------------------------------------

def render_sidebar(prod):
    if LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), width="stretch")

    theme_choice = st.sidebar.radio("Theme", ["Dark", "Light"], index=0 if st.session_state["theme"] == "dark" else 1, horizontal=True)
    new_theme = theme_choice.lower()
    if new_theme != st.session_state["theme"]:
        st.session_state["theme"] = new_theme
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption(f"Analysis period: **May – August 2026**" + (f" (through {DATA_MAX})" if DATA_MAX else ""))

    st.sidebar.markdown("##### Currency")
    fx_raw = st.sidebar.text_input("USD → N$ rate (blank = report in USD)", value="" if not st.session_state.get("fx_rate") else str(st.session_state["fx_rate"]))
    if fx_raw.strip():
        try:
            st.session_state["fx_rate"] = float(fx_raw.strip())
        except ValueError:
            st.sidebar.error("Enter a plain number, e.g. 18.5")
    else:
        st.session_state["fx_rate"] = None

    st.sidebar.markdown("##### Fixed cost overhead")
    st.session_state["fixed_costs_enabled"] = st.sidebar.toggle("Set fixed labour & machine cost", value=st.session_state["fixed_costs_enabled"])
    if st.session_state["fixed_costs_enabled"]:
        st.session_state["fixed_labour_cost_per_shift"] = st.sidebar.slider(
            "Labour cost per shift", 0, 50000, value=int(st.session_state["fixed_labour_cost_per_shift"] or 10000), step=250)
        st.session_state["fixed_machine_cost_per_shift"] = st.sidebar.slider(
            "Machine/jumbo cost per shift", 0, 50000, value=int(st.session_state["fixed_machine_cost_per_shift"] or 8000), step=250)
    else:
        st.session_state["fixed_labour_cost_per_shift"] = None
        st.session_state["fixed_machine_cost_per_shift"] = None

    st.sidebar.markdown("##### Sensitivity scenarios")
    st.session_state["optimistic_pct"] = st.sidebar.slider("Optimistic advance-rate improvement", 0, 100, value=st.session_state["optimistic_pct"], step=5, format="%d%%")
    st.session_state["max_capacity_pct"] = st.sidebar.slider("Maximum-capacity advance-rate improvement", 0, 150, value=st.session_state["max_capacity_pct"], step=5, format="%d%%")

    baseline_rate = prod["avg_rate_per_shift"] if prod else None
    if baseline_rate:
        st.sidebar.markdown("##### Target advance rate (what-if)")
        st.session_state["target_rate"] = st.sidebar.slider(
            "Target rate (m/shift)", float(round(baseline_rate * 0.5, 2)), float(round(baseline_rate * 2.0, 2)),
            value=float(st.session_state.get("target_rate") or baseline_rate), step=0.05)
    else:
        st.session_state["target_rate"] = None


# ---------------------------------------------------------------------------
# TAB: Control Room
# ---------------------------------------------------------------------------

def render_control_room(prod):
    drill_stk = stocktake_category_slice("drilling")
    gs_stk = stocktake_category_slice("ground_support")
    usage = drilling_slice()
    live = gs_live_slice()
    cur = currency()
    adv = prod["total_advance"] if prod else None

    drill_cost = total_or_none(drill_stk["cost"]) if not drill_stk.empty else None
    gs_cost = total_or_none(gs_stk["cost"]) if not gs_stk.empty else None
    drill_cost_rep = to_reporting_currency(drill_cost)
    gs_cost_rep = to_reporting_currency(gs_cost)
    drill_per_m = safe_div(drill_cost_rep, adv)
    gs_per_m = safe_div(gs_cost_rep, adv)
    total_per_m = None
    if drill_per_m is not None and gs_per_m is not None:
        total_per_m = drill_per_m + gs_per_m

    # The offsider log only covers May-July, so it's compared against the
    # SAME three stocktake periods -- comparing it against the full May-Aug
    # stocktake total would overstate leakage purely from August's extra
    # spend, which the offsider log never had a chance to record.
    drill_stk_may_jul = pd.concat([stocktake_category_slice("drilling", m) for m in ["May", "June", "July"]], ignore_index=True)
    gs_stk_may_jul = pd.concat([stocktake_category_slice("ground_support", m) for m in ["May", "June", "July"]], ignore_index=True)
    drill_cost_may_jul = total_or_none(drill_stk_may_jul["cost"]) if not drill_stk_may_jul.empty else None
    gs_cost_may_jul = total_or_none(gs_stk_may_jul["cost"]) if not gs_stk_may_jul.empty else None

    drill_off = drilling_offsider_slice()
    gs_off = gs_offsider_slice()
    drill_off_cost = total_or_none(drill_off["cost"]) if not drill_off.empty else None
    gs_off_cost = total_or_none(gs_off["cost"]) if not gs_off.empty else None
    leak_drill = (drill_cost_may_jul - drill_off_cost) if (drill_cost_may_jul is not None and drill_off_cost is not None) else None
    leak_gs = (gs_cost_may_jul - gs_off_cost) if (gs_cost_may_jul is not None and gs_off_cost is not None) else None
    total_leak = None
    if leak_drill is not None or leak_gs is not None:
        total_leak = (leak_drill or 0) + (leak_gs or 0)
    stock_cost_for_leak = 0.0
    if leak_drill is not None:
        stock_cost_for_leak += drill_cost_may_jul
    if leak_gs is not None:
        stock_cost_for_leak += gs_cost_may_jul
    leak_pct = safe_div(total_leak, stock_cost_for_leak) if (leak_drill is not None or leak_gs is not None) else None
    leak_status = "neutral"
    if leak_pct is not None:
        leak_status = "good" if abs(leak_pct) < 0.05 else ("warning" if abs(leak_pct) < 0.15 else "critical")

    design_cost = design_required_cost()
    over_pct = safe_div(gs_cost - design_cost, design_cost) if (design_cost is not None and gs_cost is not None) else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Advance rate", fmt_number(prod["avg_rate_per_shift"] if prod else None, 2, " m/shift"), "neutral", "Research question 3", T)
    with c2:
        kpi_card("Drilling cost intensity", fmt_money(drill_per_m, cur, 2) + "/m", "neutral", "Research question 1", T)
    with c3:
        kpi_card("Ground support cost intensity", fmt_money(gs_per_m, cur, 2) + "/m", "neutral", "Research question 2", T)
    with c4:
        kpi_card("Total consumable cost intensity", fmt_money(total_per_m, cur, 2) + "/m", "neutral", "Drilling + ground support, per metre advanced", T)

    st.markdown("#### Unlogged inventory leakage — physical stocktake vs. offsider issue log")
    lc1, lc2 = st.columns([1, 1])
    with lc1:
        kpi_card("Unlogged inventory leakage", fmt_money(to_reporting_currency(total_leak), cur, 0),
                  leak_status, f"{leak_pct*100:.1f}% of stocktake spend (drilling + ground support)" if leak_pct is not None else NA, T)
        st.caption("Physical stocktake cost minus what the offsider issue log recorded. A positive value means stock left the store with no matching paperwork; the offsider log covers May-July only, so August is excluded from this specific comparison.")
    with lc2:
        if leak_pct is not None:
            st.plotly_chart(variance_gauge(abs(leak_pct) * 100, "Leakage %", good=5, warn=15), width="stretch", key="leakage_gauge")
        else:
            st.info(NA)

    st.markdown("#### Ground support over-consumption vs. design-required")
    gc1, gc2 = st.columns([1, 1])
    with gc1:
        if design_cost is not None and gs_cost is not None:
            status = "good" if over_pct is not None and over_pct <= 0 else ("warning" if over_pct is not None and over_pct < 0.5 else "critical")
            kpi_card("Ground support: actual vs. design-required", fmt_money(to_reporting_currency(gs_cost), cur, 0),
                      status, f"Design-required: {fmt_money(to_reporting_currency(design_cost), cur, 0)} ({over_pct*100:+.0f}%)", T)
        else:
            kpi_card("Ground support: actual vs. design-required", NA, "neutral", None, T)
    with gc2:
        if over_pct is not None:
            st.plotly_chart(variance_gauge(over_pct * 100, "Over-consumption vs. design %", good=20, warn=50), width="stretch", key="overconsumption_gauge")
    if over_pct is not None:
        overbreak = portal_overbreak_summary()
        overbreak_txt = ""
        if not overbreak.empty and set(["North", "South"]).issubset(overbreak.index):
            overbreak_txt = (
                f" Average overbreak across the period is {overbreak.loc['North','OverBreak']*100:.1f}% (North) and "
                f"{overbreak.loc['South','OverBreak']*100:.1f}% (South) -- localized overbreak is one plausible, "
                f"data-consistent driver of support beyond the design minimum."
            )
        st.info(
            f"Actual ground support spend runs {over_pct*100:.0f}% above the design-standard minimum. The design "
            f"figure is a *minimum*, so this gap is not automatically waste -- plausible drivers include ground "
            f"degradation beyond the design assumption, safety re-bolting (support added after the fact where "
            f"initial support was judged insufficient), and localized overbreak requiring extra bolts/mesh to "
            f"stabilise a wider-than-designed opening.{overbreak_txt} Confirming which driver applies is a "
            f"geotechnical judgement call -- record it in the Discrepancy Log."
        )

    st.markdown("#### Portal performance — totals and per-round averages")
    pc1, pc2 = st.columns(2)
    by_portal = prod["by_portal"] if prod else pd.DataFrame()
    pr_all = production_in_range()
    pr_by_portal = pd.DataFrame()
    if not pr_all.empty and "Heading name" in pr_all.columns:
        d = pr_all.copy()
        d["portal"] = d["Heading name"].apply(nl.normalize_portal)
        pr_by_portal, _ = restrict_to_portals(d)
    for col, portal in zip((pc1, pc2), ("North", "South")):
        with col:
            adv_p = by_portal.loc[portal, "advance_m"] if portal in by_portal.index else None
            drill_p = restrict_to_portals(usage)[0]
            drill_p_cost = total_or_none(drill_p[drill_p["portal"] == portal]["cost"]) if not drill_p.empty else None
            live_p = restrict_to_portals(live)[0]
            live_p_cost = total_or_none(live_p[live_p["portal"] == portal]["cost"]) if not live_p.empty else None
            total_p_cost = (drill_p_cost or 0) + (live_p_cost or 0)
            n_rounds_p = len(pr_by_portal[pr_by_portal["portal"] == portal]) if not pr_by_portal.empty else None
            avg_advance_per_round_p = safe_div(adv_p, n_rounds_p)
            avg_cost_per_round_p = safe_div(total_p_cost, n_rounds_p) if (drill_p_cost is not None or live_p_cost is not None) else None
            st.markdown(f"**{portal} portal**")
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                kpi_card("Total advance", fmt_number(adv_p, 1, " m"), "neutral", "Total", T)
            with r1c2:
                kpi_card("Total drilling + GS cost", fmt_money(to_reporting_currency(total_p_cost), cur, 0), "neutral", "Total (store-issue logs)", T)
            r2c1, r2c2 = st.columns(2)
            with r2c1:
                kpi_card("Advance per round", fmt_number(avg_advance_per_round_p, 2, " m"), "neutral", f"{n_rounds_p or 0} rounds fired" if n_rounds_p else None, T)
            with r2c2:
                kpi_card("Cost per round", fmt_money(to_reporting_currency(avg_cost_per_round_p), cur, 0), "neutral", "Shift/round average", T)

    st.markdown("#### Cost breakdown by item")
    dcol, gcol = st.columns(2)
    for col, label, stk in ((dcol, "Drilling consumables", drill_stk), (gcol, "Ground support consumables", gs_stk)):
        with col:
            st.markdown(f"**{label}**")
            item_costs = stk.groupby("item")["cost"].sum(min_count=1).apply(to_reporting_currency) if not stk.empty else pd.Series(dtype=float)
            fig = cost_treemap(item_costs)
            if fig:
                st.plotly_chart(fig, width="stretch", key=f"treemap_{label}")
            else:
                st.info(NA)
            table = itemized_breakdown(stk)
            if not table.empty:
                table_show = table.copy()
                table_show["unit_price"] = table_show["unit_price"].apply(lambda v: to_reporting_currency(v))
                table_show["cost"] = table_show["cost"].apply(lambda v: to_reporting_currency(v))
                table_show = table_show.rename(columns={
                    "item": "Item", "quantity": "Quantity", "unit_price": f"Unit price ({cur})",
                    "cost": f"Cost ({cur})", "pct_of_category": "% of category",
                })
                st.dataframe(table_show, width="stretch", hide_index=True, height=280)

    with notes_expander("Data sources & methodology notes"):
        st.caption("Formulas: UC_drill = drilling consumable cost / metres advanced. UC_support = ground support consumable cost / metres advanced. UC_total = (labour + machine)/advance rate + UC_drill + UC_support.")
        rows = [
            ("Physical stocktake sheets (primary cost source)", len(DATA["stocktake"])),
            ("Drilling stock usage log (comparison/portal split)", len(DATA["usage"])),
            ("Unit prices", len(DATA["prices"])),
            ("Ground support live jumbo-linked log (portal split source)", len(DATA["gs_live"])),
            ("Ground support offsider log (discrepancy-checking only)", len(DATA["gs_offsider"])),
            ("EOM development survey reports", len(DATA["production"])),
            ("Jumbo PLOD (shift-level drilling activity)", len(DATA["plod"])),
        ]
        st.dataframe(pd.DataFrame(rows, columns=["Source", "Rows loaded"]), width="stretch", hide_index=True)

        mismatches = price_source_comparison()
        if not mismatches.empty:
            st.warning(f"{len(mismatches)} drilling item(s): the unit cost typed into the monthly stock-usage workbook disagrees with the official static price list by more than 1.5x. The official price list is used for every cost on this app; the workbook figure is shown here only as a data-quality flag worth raising with whoever maintains that workbook.")
            wrapped_table(mismatches, height=140, key="ag_price_mismatches", T=T)

        neg = stocktake_flagged_negative()
        if not neg.empty:
            st.warning(f"{len(neg)} stocktake line item(s) show a physical stock increase with no recorded delivery (negative implied usage) -- excluded from cost totals rather than treated as negative consumption.")
            st.dataframe(neg[["period_label", "item", "used_qty", "start_qty", "received_qty", "end_qty"]], width="stretch", hide_index=True)

        unc = DATA["stocktake"][DATA["stocktake"]["category"] == "uncategorized"]["item"].drop_duplicates() if not DATA["stocktake"].empty else pd.Series(dtype=str)
        if not unc.empty:
            reasons = pd.DataFrame({"Item": unc.values, "Reason excluded": [nl.classify_uncategorized_reason(it) for it in unc.values]})
            st.caption(f"{len(reasons)} stocktake line items are neither a drilling nor a ground support consumable (reusable tools, ventilation, other out-of-scope items).")
            wrapped_table(reasons, height=260, key="ag_uncategorized", T=T)

        gss_design = DATA["gss_design"]
        if not gss_design.empty:
            st.caption("Ground support design standard (minimum quantity per cut): South portal is developed to GSS_01; North portal spans GSS_02 and GSS_03, with GSS_03 represented by the GSS_02 figures (no independent GSS_03 drawing exists in the source design data).")
            show = gss_design.rename(columns={
                "standard": "Standard", "ground_condition": "Ground condition", "md_bolt_2_4m": "MD bolt 2.4m",
                "split_set_2_4m": "Split set 2.4m", "stubby_split_set_0_9m": "Stubby split set 0.9m",
                "mesh_sheet": "Mesh sheet", "source": "Source",
            })
            st.dataframe(show, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# TAB: Meter Reconciliation
# ---------------------------------------------------------------------------

def render_reconciliation(prod):
    st.markdown("#### EOM survey advance vs. Jumbo PLOD advance")
    monthly_survey = production_report_advance_by_month()
    plod = plod_slice()
    plod_by_month = plod.assign(month_tab=plod["date"].dt.strftime("%B")).groupby("month_tab")["advance_m"].sum(min_count=1) if not plod.empty else pd.Series(dtype=float)
    plod_by_month = plod_by_month.reindex([m for m in MONTH_ORDER if m in plod_by_month.index])

    months = [m for m in MONTH_ORDER if m in monthly_survey.index or m in plod_by_month.index]
    survey_vals = [monthly_survey.get(m) for m in months]
    plod_vals = [plod_by_month.get(m) for m in months]
    fig = dual_trace_chart(months, survey_vals, "EOM survey advance (m)", plod_vals, "Jumbo PLOD advance (m)", "Metres advanced")
    st.plotly_chart(fig, width="stretch")

    total_survey = total_or_none(pd.Series(survey_vals))
    total_plod = total_or_none(pd.Series(plod_vals))
    pct_variance = safe_div(abs((total_plod or 0) - (total_survey or 0)), total_survey) * 100 if total_survey else None

    c1, c2 = st.columns([1, 2])
    with c1:
        if pct_variance is not None:
            st.plotly_chart(variance_gauge(pct_variance, "Survey vs. Jumbo variance"), width="stretch")
        else:
            st.info(NA)
    with c2:
        rows = []
        for m in months:
            s, p = monthly_survey.get(m), plod_by_month.get(m)
            diff_pct = safe_div(abs((p or 0) - (s or 0)), s) * 100 if s else None
            rows.append((m, s, p, diff_pct))
        st.dataframe(pd.DataFrame(rows, columns=["Month", "EOM survey advance (m)", "Jumbo PLOD advance (m)", "% difference"]), width="stretch", hide_index=True)

    st.markdown("#### By portal")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.caption("EOM survey (North/South only)")
        if prod and not prod["by_portal"].empty:
            st.dataframe(prod["by_portal"].rename(columns={"advance_m": "Metres advanced"}), width="stretch")
    with pcol2:
        st.caption("Jumbo PLOD (North/South only)")
        if prod and not prod["by_portal_plod"].empty:
            st.dataframe(prod["by_portal_plod"].rename(columns={"advance_m": "Metres advanced", "metres_drilled": "Metres drilled"}), width="stretch")

    with notes_expander("Why two different meter counts exist"):
        st.caption(
            "The EOM development survey report is the official monthly production record, per heading, with no "
            "shift-level field. Jumbo PLOD is a per-shift drilling log and is the only source with genuine shift "
            "granularity, so it is used for the shift count wherever an m/shift figure is shown, and independently "
            "for metres drilled (holes x hole depth), which the survey report does not capture at all."
        )


# ---------------------------------------------------------------------------
# TAB: Consumable Leakage & Drill Yield
# ---------------------------------------------------------------------------

def render_leakage_bityield():
    cur = currency()
    st.markdown("#### Ground support: Design Required → Offsider Issue Log → Physical Stocktake")
    st.caption("All four stages are restricted to May-July 2026, the offsider log's only coverage window, so every step compares the same period.")
    may_jul_gs_stk = pd.concat([stocktake_category_slice("ground_support", m) for m in ["May", "June", "July"]], ignore_index=True)
    stk_gs_cost = total_or_none(may_jul_gs_stk["cost"]) if not may_jul_gs_stk.empty else None
    live_may_jul = filter_dates(DATA["gs_live"])
    if live_may_jul.empty or "category" not in live_may_jul.columns:
        live_may_jul = pd.DataFrame()
    else:
        live_may_jul = live_may_jul[(live_may_jul["category"] == "ground_support") & (live_may_jul["date"] < pd.Timestamp(2026, 8, 1))]
    live_cost = total_or_none(attach_gs_cost(live_may_jul)["cost"]) if not live_may_jul.empty else None
    offsider_cost = total_or_none(gs_offsider_slice()["cost"])
    design_cost = design_required_cost(months=["May", "June", "July"])
    fig = gs_waterfall_chart(
        to_reporting_currency(design_cost), to_reporting_currency(offsider_cost),
        to_reporting_currency(stk_gs_cost), to_reporting_currency(live_cost), cur,
    )
    if fig:
        st.plotly_chart(fig, width="stretch")
    else:
        st.info(NA)

    st.markdown("#### Drill bit yield vs. baseline")
    calc = bit_life_calc()
    if calc is not None and calc["resharpen_yield_pct"].notna().any():
        gcols = st.columns(len(calc))
        for col, (_, r) in zip(gcols, calc.iterrows()):
            with col:
                if pd.notna(r.get("resharpen_yield_pct")):
                    st.plotly_chart(yield_gauge(r["resharpen_yield_pct"], f"{r['portal']} resharpen yield"), width="stretch")
        n_total_bits = int(calc["bits_averaged"].fillna(1).sum())
        st.caption(f"Each gauge is the average of the bits recorded for that portal ({n_total_bits} bits total). Yield = holes recovered after resharpening / fresh-bit holes.")
    else:
        st.info(NA)

    with notes_expander("Bit life records (edit)"):
        records = st.session_state["bit_life_records"]
        df = pd.DataFrame(records)
        if "bits_averaged" not in df.columns:
            df["bits_averaged"] = 1
        edited = st.data_editor(
            df, num_rows="dynamic", width="stretch", key="bit_life_editor",
            column_config={
                "portal": st.column_config.TextColumn("Portal"),
                "bit_spec": st.column_config.TextColumn("Bit spec"),
                "hole_depth_m": st.column_config.NumberColumn("Hole depth (m)", format="%.2f"),
                "holes_before_resharpen": st.column_config.NumberColumn("Holes before resharpen (avg)", format="%.1f"),
                "holes_after_resharpen": st.column_config.NumberColumn("Holes after resharpen (avg)", format="%.1f"),
                "bits_averaged": st.column_config.NumberColumn("Bits averaged", format="%d"),
                "bit_price": st.column_config.NumberColumn("Bit price"),
                "resharpen_cost": st.column_config.NumberColumn("Resharpen service cost"),
            },
        )
        st.session_state["bit_life_records"] = edited.to_dict("records")
        calc2 = bit_life_calc()
        if calc2 is not None:
            show_cols = ["portal", "bits_averaged", "total_holes", "total_metres", "resharpen_yield_pct",
                         "cost_per_m_no_resharpen", "cost_per_m_with_resharpen", "pct_saving"]
            display_df = calc2[show_cols].rename(columns={
                "portal": "Portal", "bits_averaged": "Bits averaged", "total_holes": "Total holes",
                "total_metres": "Total metres drilled", "resharpen_yield_pct": "Resharpen yield %",
                "cost_per_m_no_resharpen": "Cost/drilled-m, no resharpen", "cost_per_m_with_resharpen": "Cost/drilled-m, with resharpen",
                "pct_saving": "% saving from resharpening",
            })
            st.dataframe(display_df, width="stretch", hide_index=True)
            if calc2["bit_price"].isna().all():
                st.caption("Enter a bit price to see cost-per-metre economics.")
            elif calc2["resharpen_cost"].isna().any():
                st.caption("Enter a resharpen service cost to see the with-resharpen cost and saving.")

    st.markdown("#### Discrepancy classification log")
    default_rows = [
        {"item_or_area": "Ground support -- MD bolts, North portal (GSS_02/GSS_03)", "period": "May-Aug 2026",
         "observation": "MD bolts installed in the North portal run approximately 163% above the GSS_02 design minimum, at roughly 3.75 bolts per metre over 705 metres advanced.",
         "classification": "Undetermined",
         "note": "The GSS_02 drawing states a MINIMUM quantity per cut, so installing above it is compliance, not automatically over-consumption. Ground-control confirmation of whether the extra support was required by ground conditions would settle the classification."},
        {"item_or_area": "Ground support -- stubby split sets (0.9m x 39mm), both portals", "period": "May-Aug 2026",
         "observation": "Stubby split sets (0.9m x 39mm) run 75-80% below the design minimum in both portals, while MD bolts and 2.4m split sets meet or exceed design in the same period.",
         "classification": "Undetermined",
         "note": "Worth checking whether the 0.9m x 47mm bolt (not on either drawing) is being substituted at the face."},
        {"item_or_area": "Drilling consumables -- physical stocktake vs. stock usage log", "period": "May-Aug 2026",
         "observation": "The stock usage log's drilling total differs from the physical stocktake's implied consumption over the same window -- see the Control Room leakage KPI for the current percentage.",
         "classification": "Undetermined",
         "note": "A gap here typically means unlogged issues, a timing lag between issue and the next physical count, or a data-entry gap in one of the two registers."},
        {"item_or_area": "Drilling consumables -- abnormal monthly quantities", "period": "May-Aug 2026",
         "observation": "A handful of items show a single month's quantity far above that item's typical monthly quantity -- see the Monthly Report tab for the current list.",
         "classification": "Operator-related waste (tentative)",
         "note": "Cross-check flagged months against the jumbo bolting schedule before finalising -- this can be a legitimate catch-up pass rather than waste."},
    ]
    if "discrepancy_table" not in st.session_state:
        df0 = pd.DataFrame(default_rows)
        df0["suggested_cause"] = "-- none selected --"
        st.session_state["discrepancy_table"] = df0

    EXPERT_CAUSES = [
        "-- none selected --", "Unrecorded scrap (item damaged/discarded, not written off)",
        "Shift-change handover omission (issued by one shift, not logged before handover)",
        "Unlogged off-site transfer (moved to another section/site without a transfer note)",
        "Timing lag (physically counted before the matching issue was recorded)",
        "Other (see note)",
    ]
    st.caption("Expert-suggested causes for unlogged movement are offered alongside your own site notes -- pick one as a starting point, or write your own in the note field below.")
    edited = wrapped_table(
        st.session_state["discrepancy_table"], height=420, editable=True,
        select_columns={
            "classification": ["Geotechnical necessity", "Operator-related waste", "Operator-related waste (tentative)", "Undetermined"],
            "suggested_cause": EXPERT_CAUSES,
        },
        key="ag_discrepancy_log", T=T,
    )
    st.session_state["discrepancy_table"] = edited

    with notes_expander("Add or edit a custom site note", expanded=False):
        if not edited.empty:
            row_labels = edited["item_or_area"].tolist()
            selected_label = st.selectbox("Discrepancy item", row_labels, key="discrepancy_note_selector")
            row_idx = edited.index[edited["item_or_area"] == selected_label][0]
            current_note = edited.loc[row_idx, "note"] if "note" in edited.columns else ""
            new_note = st.text_area("Your site note for this item", value=current_note or "", height=100, key=f"note_input_{row_idx}")
            if st.button("Save note", key="save_discrepancy_note"):
                st.session_state["discrepancy_table"].loc[row_idx, "note"] = new_note
                st.rerun()

    csv = edited.to_csv(index=False).encode("utf-8")
    st.download_button("Download discrepancy log as CSV", csv, file_name="discrepancy_log.csv", mime="text/csv")


# ---------------------------------------------------------------------------
# TAB: Sensitivity Simulator
# ---------------------------------------------------------------------------

def compute_sensitivity_inputs(prod):
    """Shared by the main sensitivity model, the continuous curve, and the
    fixed-increment export matrix, so all three always agree with each
    other on variable cost per metre, fixed cost per shift, and baseline
    rate."""
    drill_stk = stocktake_category_slice("drilling")
    gs_stk = stocktake_category_slice("ground_support")
    adv = prod["total_advance"] if prod else None
    baseline_rate = prod["avg_rate_per_shift"] if prod else None
    drill_cost = to_reporting_currency(total_or_none(drill_stk["cost"])) if not drill_stk.empty else None
    gs_cost = to_reporting_currency(total_or_none(gs_stk["cost"])) if not gs_stk.empty else None
    variable_cost_per_m = None
    if drill_cost is not None and gs_cost is not None and adv:
        variable_cost_per_m = (drill_cost + gs_cost) / adv
    labour = to_reporting_currency(st.session_state["fixed_labour_cost_per_shift"])
    machine = to_reporting_currency(st.session_state["fixed_machine_cost_per_shift"])
    fixed_cost_per_shift = None
    if labour is not None or machine is not None:
        fixed_cost_per_shift = (labour or 0) + (machine or 0)
    return variable_cost_per_m, fixed_cost_per_shift, baseline_rate


def sensitivity_matrix_fixed_increments(variable_cost_per_m, fixed_cost_per_shift, rate_min=1.5, rate_max=4.0, step=0.5):
    """Predicted total unit cost at fixed 0.5 m/shift increments, independent
    of today's actual baseline rate -- a reference matrix for 'what would it
    cost at exactly this rate', not tied to current performance."""
    if variable_cost_per_m is None or fixed_cost_per_shift is None:
        return None
    rates = np.arange(rate_min, rate_max + step / 2, step).round(2)
    rows = []
    for r in rates:
        fixed_component = fixed_cost_per_shift / r
        rows.append({
            "advance_rate_m_per_shift": float(r), "fixed_cost_component_n_per_m": fixed_component,
            "variable_cost_component_n_per_m": variable_cost_per_m, "total_unit_cost_n_per_m": fixed_component + variable_cost_per_m,
        })
    return pd.DataFrame(rows)


def df_to_xlsx_bytes(sheets: dict) -> bytes:
    """sheets: {sheet_name: DataFrame}."""
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def render_sensitivity_simulator(prod):
    cur = currency()
    variable_cost_per_m, fixed_cost_per_shift, baseline_rate = compute_sensitivity_inputs(prod)

    missing_bits = []
    if variable_cost_per_m is None:
        missing_bits.append("drilling + ground support cost per metre")
    if fixed_cost_per_shift is None:
        missing_bits.append("fixed labour/machine cost per shift (control panel)")
    if baseline_rate is None:
        missing_bits.append("baseline advance rate")
    if missing_bits:
        st.warning("Cannot run the sensitivity model yet -- missing: " + ", ".join(missing_bits) + ".")
        return

    pcts = [0.0, st.session_state["optimistic_pct"] / 100.0, st.session_state["max_capacity_pct"] / 100.0]
    result = mc.sensitivity_model(variable_cost_per_m, fixed_cost_per_shift, baseline_rate, pcts)
    if result is None:
        st.warning(NA)
        return

    st.markdown(f"#### Total unit cost = (labour + machine) / advance rate + variable cost per metre, in {cur}")
    curve = mc.sensitivity_curve(variable_cost_per_m, fixed_cost_per_shift, baseline_rate)
    baseline_cost = fixed_cost_per_shift / baseline_rate + variable_cost_per_m
    target_rate = st.session_state.get("target_rate")
    target_cost = (fixed_cost_per_shift / target_rate + variable_cost_per_m) if target_rate else None
    markers = {"Current": (baseline_rate, baseline_cost)}
    if target_rate and abs(target_rate - baseline_rate) > 1e-6:
        markers["Target"] = (target_rate, target_cost)
    if curve is not None:
        st.plotly_chart(sensitivity_curve_chart(curve, cur, baseline_rate, markers), width="stretch")

    faster_row = result.iloc[-1]
    proof = (
        f"At {baseline_rate:.2f} m/shift, the fixed labour + machine cost of {fmt_money(fixed_cost_per_shift, cur, 0)}/shift "
        f"spreads over fewer metres, adding {fmt_money(fixed_cost_per_shift/baseline_rate, cur, 2)}/m to total unit cost. "
        f"At {faster_row['advance_rate_m_per_shift']:.2f} m/shift ({st.session_state['max_capacity_pct']}% faster), the same fixed cost "
        f"spreads over more metres, adding only {fmt_money(faster_row['fixed_cost_component_n_per_m'], cur, 2)}/m -- confirming that a "
        f"higher advance rate dilutes fixed cost over more metres and lowers total unit cost, while a lower advance rate spreads the same "
        f"fixed cost over fewer metres and raises it."
    )
    st.info(proof.replace("$", "\\$"))

    if target_rate and abs(target_rate - baseline_rate) > 1e-6:
        delta = baseline_cost - target_cost
        direction = "reduces" if delta > 0 else "increases"
        st.success(f"At the target rate of {target_rate:.2f} m/shift, total unit cost is {fmt_money(target_cost, cur, 2)}/m, which {direction} cost by {fmt_money(abs(delta), cur, 2)}/m versus the current rate.".replace("$", "\\$"))

    st.markdown("#### Scenario matrix")
    display = result.rename(columns={
        "scenario": "Scenario", "advance_rate_m_per_shift": "Advance rate (m/shift)",
        "fixed_cost_component_n_per_m": f"Fixed cost ({cur}/m)", "variable_cost_component_n_per_m": f"Variable cost ({cur}/m)",
        "total_unit_cost_n_per_m": f"Total unit cost ({cur}/m)", "reduction_vs_baseline_n_per_m": f"Saving vs. baseline ({cur}/m)",
        "reduction_vs_baseline_pct": "Saving vs. baseline (%)",
    })
    display["Scenario"] = ["Baseline", f"Optimistic (+{st.session_state['optimistic_pct']}%)", f"Maximum capacity (+{st.session_state['max_capacity_pct']}%)"]
    st.dataframe(display, width="stretch", hide_index=True)
    fig2 = sensitivity_chart(result, cur)
    st.plotly_chart(fig2, width="stretch")

    st.markdown("#### Export matrix — predicted unit cost at fixed advance-rate increments")
    st.caption("1.5 to 4.0 m/shift in 0.5 m steps, independent of the current baseline rate above.")
    matrix = sensitivity_matrix_fixed_increments(variable_cost_per_m, fixed_cost_per_shift)
    if matrix is not None:
        matrix_show = matrix.rename(columns={
            "advance_rate_m_per_shift": "Advance rate (m/shift)", "fixed_cost_component_n_per_m": f"Fixed cost ({cur}/m)",
            "variable_cost_component_n_per_m": f"Variable cost ({cur}/m)", "total_unit_cost_n_per_m": f"Total unit cost ({cur}/m)",
        })
        st.dataframe(matrix_show, width="stretch", hide_index=True)
        xlsx_bytes = df_to_xlsx_bytes({"Sensitivity Matrix": matrix_show})
        st.download_button("Download Matrix (.xlsx)", xlsx_bytes, file_name="sensitivity_matrix.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info(NA)


# ---------------------------------------------------------------------------
# TAB: Monthly Report
# ---------------------------------------------------------------------------

def render_round_efficiency():
    cur = currency()
    st.markdown("#### Round efficiency across the analysed period")
    st.caption("Scanned dynamically across every month in the dataset -- not a fixed comparison of any two specific months.")
    eff = round_efficiency_table()
    tbl = eff["table"]

    b1, b2 = st.columns(2)
    with b1:
        kpi_card("Normal baseline — advance per round", fmt_number(eff["baseline_advance_per_round"], 2, " m"), "neutral", "Average across all months", T)
    with b2:
        kpi_card("Normal baseline — support cost per round", fmt_money(to_reporting_currency(eff["baseline_gs_cost_per_round"]), cur, 0), "neutral", "Average across all months", T)

    show = tbl.copy()
    show["gs_cost_per_round"] = show["gs_cost_per_round"].apply(lambda v: to_reporting_currency(v))
    show["gs_n_per_m"] = show["gs_n_per_m"].apply(lambda v: to_reporting_currency(v))
    show["drilling_n_per_m"] = show["drilling_n_per_m"].apply(lambda v: to_reporting_currency(v))
    show["total_n_per_m"] = show["total_n_per_m"].apply(lambda v: to_reporting_currency(v))
    show["pct_below_baseline_advance"] = show["pct_below_baseline_advance"].apply(lambda v: v * 100 if v is not None else None)
    show = show.rename(columns={
        "month": "Month", "n_rounds": "Rounds fired", "total_advance": "Total advance (m)",
        "avg_advance_per_round": "Advance/round (m)", "gs_cost_per_round": f"Support cost/round ({cur})",
        "gs_n_per_m": f"Support ({cur}/m)", "drilling_n_per_m": f"Drilling ({cur}/m)", "total_n_per_m": f"Total ({cur}/m)",
        "pct_below_baseline_advance": "% below baseline advance/round",
    })
    st.dataframe(show.drop(columns=["gs_cost"], errors="ignore"), width="stretch", hide_index=True)

    fig = round_efficiency_chart(tbl["month"].tolist(), tbl["avg_advance_per_round"].tolist(),
                                  [to_reporting_currency(v) for v in tbl["total_n_per_m"]], cur)
    st.plotly_chart(fig, width="stretch", key="round_efficiency_chart")

    if eff["flagged_months"]:
        months_txt = ", ".join(eff["flagged_months"])
        st.warning(
            f"**{months_txt}**: advance per round runs more than 15% below the {eff['baseline_advance_per_round']:.2f} m "
            f"baseline. Mechanism: ground support (bolts and mesh) is applied per round fired, largely independent "
            f"of how far that round advanced. A month with shorter rounds carries the same fixed support overhead "
            f"per round spread over fewer metres, inflating {cur}/m even if physical consumption per item remains "
            f"normal for every individual item. This is a round-efficiency effect, not necessarily over-consumption."
        )
    else:
        st.caption("No month runs more than 15% below the period baseline for advance per round.")


def render_monthly_report():
    render_round_efficiency()
    st.divider()
    cur = currency()
    c1, c2 = st.columns([1, 3])
    with c1:
        month = st.selectbox("Month", MONTH_ORDER, index=MONTH_ORDER.index(st.session_state["monthly_report_month"]))
        st.session_state["monthly_report_month"] = month
        generate = st.button("Generate Monthly Analysis", type="primary", width="stretch")
    if not generate and "last_monthly_report" not in st.session_state:
        st.info("Select a month and click Generate Monthly Analysis.")
        return
    if generate:
        st.session_state["last_monthly_report"] = generate_monthly_report(month)
    r = st.session_state["last_monthly_report"]

    st.markdown(f"### {r['month']} 2026 — Underground Development Performance")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Metres advanced", fmt_number(r["adv_m"], 1, " m"), "neutral", None, T)
    with c2:
        kpi_card("Average advance rate", fmt_number(r["avg_rate_m"], 2, " m/shift"), "neutral", None, T)
    with c3:
        kpi_card("Drilling N$/m", fmt_money(to_reporting_currency(r["drilling_n_per_m"]), cur, 2), "neutral", None, T)
    with c4:
        kpi_card("Support N$/m", fmt_money(to_reporting_currency(r["gs_n_per_m"]), cur, 2), "neutral", None, T)

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Drilling consumption", fmt_money(to_reporting_currency(r["drilling_cost_m"]), cur, 0), "neutral", None, T)
    with c2:
        kpi_card("Support consumption", fmt_money(to_reporting_currency(r["gs_cost_m"]), cur, 0), "neutral", None, T)
    with c3:
        kpi_card("Total consumable N$/m", fmt_money(to_reporting_currency(r["total_n_per_m"]), cur, 2), "neutral", None, T)

    st.markdown("#### North vs. South")
    if not r["by_portal_adv"].empty:
        st.dataframe(r["by_portal_adv"].rename(columns={"advance_m": "Metres advanced"}), width="stretch")
    else:
        st.info(NA)

    st.markdown("#### Heading comparison")
    if not r["heading_tbl"].empty:
        st.dataframe(r["heading_tbl"], width="stretch", hide_index=True)
    else:
        st.info(NA)

    st.markdown("#### Variance analysis")
    vcol1, vcol2 = st.columns(2)
    with vcol1:
        st.dataframe(r["monthly_tbl"].rename(columns={"month": "Month", "drilling_cost": "Drilling cost", "ground_support_cost": "Ground support cost", "total_cost": "Total cost"}), width="stretch", hide_index=True)
    with vcol2:
        if "total_cost_vs_prev_month_pct" in r["variance"]:
            st.metric(f"vs. {r['variance']['prev_month']}", f"{r['variance']['total_cost_vs_prev_month_pct']:+.1f}%")
        if "total_cost_vs_avg_pct" in r["variance"]:
            st.metric("vs. 4-month average", f"{r['variance']['total_cost_vs_avg_pct']:+.1f}%")

    st.markdown("#### Pareto — top cost drivers this month")
    if not r["pareto_df"].empty:
        fig = pareto_chart(r["pareto_df"].set_index("item")["cost"].apply(to_reporting_currency))
        if fig:
            st.plotly_chart(fig, width="stretch")
    else:
        st.info(NA)

    st.markdown("#### Abnormal consumption")
    if not r["abnormal"].empty:
        st.dataframe(r["abnormal"], width="stretch", hide_index=True)
    else:
        st.caption("No items this month deviate sharply from their typical monthly quantity.")

    st.markdown("#### Productivity vs. cost, across the analysed period")
    pc1, pc2 = st.columns(2)
    with pc1:
        monthly_survey = production_report_advance_by_month()
        fig = trend_chart(monthly_survey, "Metres advanced")
        if fig:
            st.plotly_chart(fig, width="stretch")
    with pc2:
        cost_per_m_by_month = {}
        for m in MONTH_ORDER:
            rep = generate_monthly_report(m) if m != r["month"] else r
            cost_per_m_by_month[m] = rep["total_n_per_m"]
        fig = trend_chart(pd.Series(cost_per_m_by_month), f"Total unit cost ({cur}/m)")
        if fig:
            st.plotly_chart(fig, width="stretch")

    st.markdown("#### Observations")
    if r["observations"]:
        for obs in r["observations"]:
            st.markdown(f"- {obs}")
    else:
        st.caption(NA)
    st.caption("Note: bolt breakage counts are not captured in any loaded data source, so breakage is not part of this automated analysis. Record breakage observations in the discrepancy log.")


# ---------------------------------------------------------------------------
# TAB: Research Findings + document exports
# ---------------------------------------------------------------------------

def compile_research_findings(prod) -> dict:
    cur = currency()
    drill_stk = stocktake_category_slice("drilling")
    gs_stk = stocktake_category_slice("ground_support")
    adv = prod["total_advance"] if prod else None
    drill_cost = total_or_none(drill_stk["cost"]) if not drill_stk.empty else None
    gs_cost = total_or_none(gs_stk["cost"]) if not gs_stk.empty else None
    drill_per_m = safe_div(to_reporting_currency(drill_cost), adv)
    gs_per_m = safe_div(to_reporting_currency(gs_cost), adv)

    gs_items = itemized_breakdown(gs_stk)
    top_gs_items = gs_items.head(3)["item"].tolist() if not gs_items.empty else []

    design_cost = design_required_cost()
    over_pct = safe_div(gs_cost - design_cost, design_cost) if (design_cost is not None and gs_cost is not None) else None

    variable_cost_per_m, fixed_cost_per_shift, baseline_rate = compute_sensitivity_inputs(prod)
    sensitivity_result = None
    if all(v is not None for v in (variable_cost_per_m, fixed_cost_per_shift, baseline_rate)):
        pcts = [0.0, st.session_state["optimistic_pct"] / 100.0, st.session_state["max_capacity_pct"] / 100.0]
        sensitivity_result = mc.sensitivity_model(variable_cost_per_m, fixed_cost_per_shift, baseline_rate, pcts)

    return dict(
        currency=cur,
        rq1_drilling_n_per_m=drill_per_m,
        rq2_gs_n_per_m=gs_per_m, rq2_top_items=top_gs_items, rq2_over_pct=over_pct,
        rq3_avg_rate=prod["avg_rate_per_shift"] if prod else None,
        rq3_total_advance=prod["total_advance"] if prod else None,
        rq4_sensitivity=sensitivity_result,
        rq4_optimistic_pct=st.session_state["optimistic_pct"], rq4_max_pct=st.session_state["max_capacity_pct"],
    )


def render_research_findings(prod):
    f = compile_research_findings(prod)
    cur = f["currency"]

    st.markdown("### Research findings")
    st.caption("Direct answers to the study's four research questions, computed live from the currently loaded data.")

    st.markdown("#### RQ1 — Drilling consumable unit cost")
    kpi_card("Drilling cost per metre advanced", fmt_money(f["rq1_drilling_n_per_m"], cur, 2) + "/m", "neutral",
              "Bits, rods, shanks, couplings — physical stocktake basis, official static price list", T)

    st.markdown("#### RQ2 — Ground support consumable unit cost and cost drivers")
    c1, c2 = st.columns(2)
    with c1:
        kpi_card("Ground support cost per metre advanced", fmt_money(f["rq2_gs_n_per_m"], cur, 2) + "/m", "neutral", None, T)
    with c2:
        over_txt = f"{f['rq2_over_pct']*100:+.0f}% vs. design-required" if f["rq2_over_pct"] is not None else NA
        kpi_card("Actual vs. design-required", over_txt, "neutral", None, T)
    if f["rq2_top_items"]:
        st.markdown("Top cost drivers: " + ", ".join(f["rq2_top_items"]))

    st.markdown("#### RQ3 — Productivity baseline")
    st.info(
        f"**Established productivity baseline: {fmt_number(f['rq3_avg_rate'], 2, ' m/shift')}**, from "
        f"{fmt_number(f['rq3_total_advance'], 1, ' m')} total advance across the analysed period (May-August 2026)."
    )

    st.markdown("#### RQ4 — Impact of advance-rate scenarios on total unit cost")
    if f["rq4_sensitivity"] is not None:
        res = f["rq4_sensitivity"]
        baseline_row, best_row = res.iloc[0], res.iloc[-1]
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Baseline total unit cost", fmt_money(baseline_row["total_unit_cost_n_per_m"], cur, 2) + "/m", "neutral", None, T)
        with c2:
            kpi_card(f"Optimistic (+{f['rq4_optimistic_pct']}%)", fmt_money(res.iloc[1]["total_unit_cost_n_per_m"], cur, 2) + "/m", "good", None, T)
        with c3:
            kpi_card(f"Maximum capacity (+{f['rq4_max_pct']}%)", fmt_money(best_row["total_unit_cost_n_per_m"], cur, 2) + "/m", "good", None, T)
    else:
        st.info(NA + " (set fixed labour/machine cost in the control panel to compute this)")

    st.divider()
    st.markdown("#### Export findings")
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        st.download_button("Download Findings (.xlsx)", generate_findings_xlsx(f), file_name="devadvance_research_findings.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with ec2:
        st.download_button("Download Findings (.pdf)", generate_findings_pdf(f), file_name="devadvance_research_findings.pdf", mime="application/pdf")
    with ec3:
        st.download_button("Download Findings (.docx)", generate_findings_docx(f), file_name="devadvance_research_findings.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def _findings_lines(f: dict) -> list[tuple[str, str]]:
    cur = f["currency"]
    lines = [
        ("RQ1 — Drilling consumable unit cost", fmt_money(f["rq1_drilling_n_per_m"], cur, 2) + "/m"),
        ("RQ2 — Ground support consumable unit cost", fmt_money(f["rq2_gs_n_per_m"], cur, 2) + "/m"),
        ("RQ2 — Top ground support cost drivers", ", ".join(f["rq2_top_items"]) if f["rq2_top_items"] else NA),
        ("RQ2 — Actual vs. design-required", f"{f['rq2_over_pct']*100:+.0f}%" if f["rq2_over_pct"] is not None else NA),
        ("RQ3 — Productivity baseline", fmt_number(f["rq3_avg_rate"], 2, " m/shift")),
        ("RQ3 — Total advance (May-Aug 2026)", fmt_number(f["rq3_total_advance"], 1, " m")),
    ]
    if f["rq4_sensitivity"] is not None:
        res = f["rq4_sensitivity"]
        lines.append(("RQ4 — Baseline total unit cost", fmt_money(res.iloc[0]["total_unit_cost_n_per_m"], cur, 2) + "/m"))
        lines.append((f"RQ4 — Optimistic (+{f['rq4_optimistic_pct']}%)", fmt_money(res.iloc[1]["total_unit_cost_n_per_m"], cur, 2) + "/m"))
        lines.append((f"RQ4 — Maximum capacity (+{f['rq4_max_pct']}%)", fmt_money(res.iloc[-1]["total_unit_cost_n_per_m"], cur, 2) + "/m"))
    else:
        lines.append(("RQ4 — Sensitivity model", NA))
    return lines


def generate_findings_xlsx(f: dict) -> bytes:
    lines = _findings_lines(f)
    df = pd.DataFrame(lines, columns=["Finding", "Value"])
    sheets = {"Research Findings": df}
    if f["rq4_sensitivity"] is not None:
        sheets["Sensitivity Model"] = f["rq4_sensitivity"]
    return df_to_xlsx_bytes(sheets)


def _pdf_safe(text: str) -> str:
    """fpdf2's built-in core fonts (Helvetica) are Latin-1 only -- em/en
    dashes and similar typographic characters raise FPDFUnicodeEncodingException.
    Downgrade to plain ASCII equivalents rather than bundling a Unicode font
    just for a summary export."""
    return (
        str(text).replace("—", "-").replace("–", "-").replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
    )


def generate_findings_pdf(f: dict) -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DevAdvance Analytics - Research Findings", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, "Underground development cost and productivity, May-August 2026", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    for label, value in _findings_lines(f):
        # w=0 ("auto-width to right margin") intermittently miscomputes
        # available width across a bold/regular font-style switch in this
        # fpdf2 version, raising FPDFException; an explicit width (epw,
        # the page's own effective printable width) sidesteps it reliably.
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(pdf.epw, 7, _pdf_safe(label))
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(pdf.epw, 7, _pdf_safe(value))
        pdf.ln(2)
    return bytes(pdf.output())


def generate_findings_docx(f: dict) -> bytes:
    import io
    from docx import Document
    doc = Document()
    doc.add_heading("DevAdvance Analytics — Research Findings", level=1)
    doc.add_paragraph("Underground development cost and productivity, May-August 2026")
    for label, value in _findings_lines(f):
        doc.add_heading(label, level=3)
        doc.add_paragraph(str(value))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# TAB: Bring Your Own Data (generic, reusable engine for a different mine)
# ---------------------------------------------------------------------------

BYOD_ROLE_FIELDS = {
    "item": "Item / consumable description",
    "category": "Category (Drilling / Ground Support) -- optional, auto-classified if left unmapped",
    "quantity": "Quantity",
    "unit_price": "Unit price -- optional if a separate price list is uploaded",
    "date": "Date -- optional",
    "location": "Heading / location -- optional",
    "shift": "Shift -- optional",
}


def _read_uploaded(file):
    if file is None:
        return None
    name = file.name.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(file)
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Could not read {file.name}: {e}")
        return None


def _column_mapper(df: pd.DataFrame, fields: dict, key_prefix: str) -> dict:
    mapping = {}
    cols = ["-- not in this file --"] + list(df.columns)
    for field_key, label in fields.items():
        guess = mc.auto_detect_column(field_key, df.columns)
        default_idx = cols.index(guess) if guess in cols else 0
        choice = st.selectbox(label, cols, index=default_idx, key=f"{key_prefix}_{field_key}")
        if choice != "-- not in this file --":
            mapping[field_key] = choice
    return mapping


def _apply_mapping(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    if df is None or not mapping:
        return None
    out = df.rename(columns={v: k for k, v in mapping.items()})
    return out[[c for c in mapping.keys()]]


def render_byod():
    st.caption(
        "This tab runs the same zero-hallucination cost-modelling engine on data uploaded here instead of the "
        "bundled dataset, so a different site can analyse its own consumables, prices and production data. "
        "Nothing entered here affects the other tabs."
    )

    with st.expander("How this works"):
        st.markdown(
            "1. Upload physical stock / stocktake data, logged usage data, theoretical/design consumption data, "
            "production (advance) data, and a unit price list.\n"
            "2. Map each file's columns to the fields the engine needs -- every guess is shown and editable.\n"
            "3. Results compute immediately below from only what was uploaded. A metric with no backing data "
            "shows 'Data not available', never an invented number."
        )

    st.markdown("#### 1. Upload data")
    c1, c2 = st.columns(2)
    with c1:
        physical_file = st.file_uploader("Physical stock / stocktake data", type=["xlsx", "xls", "csv"], key="byod_physical_file")
        theoretical_file = st.file_uploader("Theoretical / design consumption data (optional)", type=["xlsx", "xls", "csv"], key="byod_theo_file")
        prices_file = st.file_uploader("Unit price list (optional)", type=["xlsx", "xls", "csv"], key="byod_price_file")
    with c2:
        offsider_file = st.file_uploader("Logged / issued usage data", type=["xlsx", "xls", "csv"], key="byod_offsider_file")
        production_file = st.file_uploader("Production / advance data", type=["xlsx", "xls", "csv"], key="byod_production_file")

    physical_raw = _read_uploaded(physical_file)
    offsider_raw = _read_uploaded(offsider_file)
    theoretical_raw = _read_uploaded(theoretical_file)
    production_raw = _read_uploaded(production_file)
    prices_raw = _read_uploaded(prices_file)

    if not any([physical_raw is not None, offsider_raw is not None, production_raw is not None]):
        st.info("Upload at least physical stock data (or logged usage data) and production data to see results.")
        return

    st.markdown("#### 2. Map columns")
    price_table = None
    if prices_raw is not None:
        st.markdown("**Unit price list**")
        price_mapping = _column_mapper(prices_raw, {"item": "Item / consumable description", "unit_price": "Unit price"}, "byod_pricemap")
        price_inputs = _apply_mapping(prices_raw, price_mapping)
        price_table = mc.build_price_table(price_inputs)

    physical = offsider = theoretical = None
    if physical_raw is not None:
        st.markdown("**Physical stock / stocktake data**")
        mapping = _column_mapper(physical_raw, BYOD_ROLE_FIELDS, "byod_physical")
        mapped = _apply_mapping(physical_raw, mapping)
        physical = mc.add_category_column(mc.attach_cost(mapped, price_table)) if mapped is not None else None

    if offsider_raw is not None:
        st.markdown("**Logged / issued usage data**")
        mapping = _column_mapper(offsider_raw, BYOD_ROLE_FIELDS, "byod_offsider")
        mapped = _apply_mapping(offsider_raw, mapping)
        offsider = mc.add_category_column(mc.attach_cost(mapped, price_table)) if mapped is not None else None

    if theoretical_raw is not None:
        st.markdown("**Theoretical / design consumption data**")
        theo_fields = {"item": "Item / consumable description", "theoretical_qty": "Theoretical / design quantity"}
        mapping = _column_mapper(theoretical_raw, theo_fields, "byod_theo")
        mapped = _apply_mapping(theoretical_raw, mapping)
        theoretical = mc.add_category_column(mapped) if mapped is not None else None

    production = None
    if production_raw is not None:
        st.markdown("**Production / advance data**")
        prod_fields = {"date": "Date -- optional", "location": "Heading / location -- optional",
                        "shift": "Shift -- optional", "metres_advanced": "Metres advanced",
                        "metres_drilled": "Metres drilled -- optional"}
        mapping = _column_mapper(production_raw, prod_fields, "byod_prod")
        production = _apply_mapping(production_raw, mapping)

    st.markdown("#### 3. Fixed costs and currency")
    c1, c2, c3 = st.columns(3)
    with c1:
        byod_currency = st.text_input("Currency label", value=st.session_state.get("byod_currency", "USD"), key="byod_currency")
    with c2:
        raw = st.text_input("Labour cost per shift", value="", key="byod_labour_raw")
        byod_labour = float(raw) if raw.strip() else None
    with c3:
        raw = st.text_input("Machine cost per shift", value="", key="byod_machine_raw")
        byod_machine = float(raw) if raw.strip() else None
    byod_pcts_raw = st.text_input("Sensitivity scenarios (%), comma-separated", value="0, 15, 30", key="byod_pcts_raw")

    st.divider()
    st.markdown("### Results")

    prod_baseline = mc.productivity_baseline(production) if production is not None else mc.productivity_baseline(None)
    adv = prod_baseline["total_metres_advanced"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total metres advanced", NA if is_missing(adv) else fmt_number(adv, 1, " m"))
    with c2:
        st.metric("Average advance rate", NA if is_missing(prod_baseline["avg_advance_rate"]) else fmt_number(prod_baseline["avg_advance_rate"], 2, " m/shift"))
    with c3:
        st.metric("Shifts recorded", NA if is_missing(prod_baseline["shift_count"]) else fmt_number(prod_baseline["shift_count"], 0))

    drill_physical = mc.filter_category(physical, mc.CATEGORY_DRILLING) if physical is not None else None
    gs_physical = mc.filter_category(physical, mc.CATEGORY_GROUND_SUPPORT) if physical is not None else None
    drill_cost = mc.total_cost(drill_physical)
    gs_cost = mc.total_cost(gs_physical)

    st.markdown("#### Unit cost")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Drilling cost per metre advanced", NA if is_missing(safe_div(drill_cost, adv)) else fmt_money(safe_div(drill_cost, adv), byod_currency, 2))
    with c2:
        st.metric("Ground support cost per metre advanced", NA if is_missing(safe_div(gs_cost, adv)) else fmt_money(safe_div(gs_cost, adv), byod_currency, 2))

    if drill_physical is not None and not drill_physical.empty:
        st.markdown("##### Drilling — top cost drivers")
        breakdown = mc.item_breakdown(drill_physical)
        if breakdown is not None:
            fig = pareto_chart(breakdown.set_index("item")["cost"])
            if fig:
                st.plotly_chart(fig, width="stretch", key="byod_drill_pareto")

    if gs_physical is not None and not gs_physical.empty:
        st.markdown("##### Ground support — top cost drivers")
        breakdown = mc.item_breakdown(gs_physical)
        if breakdown is not None:
            fig = pareto_chart(breakdown.set_index("item")["cost"])
            if fig:
                st.plotly_chart(fig, width="stretch", key="byod_gs_pareto")

    if physical is not None or offsider is not None or theoretical is not None:
        st.markdown("#### Discrepancy reconciliation")
        for label, cat in [("Drilling", mc.CATEGORY_DRILLING), ("Ground Support", mc.CATEGORY_GROUND_SUPPORT)]:
            p = mc.filter_category(physical, cat) if physical is not None else None
            o = mc.filter_category(offsider, cat) if offsider is not None else None
            t = mc.filter_category(theoretical, cat) if theoretical is not None else None
            merged = mc.reconcile_three_streams(p, o, t)
            if merged is not None and not merged.empty:
                st.markdown(f"##### {label}")
                wrapped_table(merged, height=260, key=f"byod_reconcile_{cat}", T=T)

    st.markdown("#### Sensitivity model")
    variable_cost_per_m = None
    if drill_cost is not None and gs_cost is not None and adv:
        variable_cost_per_m = (drill_cost + gs_cost) / adv
    fixed_cost_per_shift = None
    if byod_labour is not None or byod_machine is not None:
        fixed_cost_per_shift = (byod_labour or 0) + (byod_machine or 0)
    baseline_rate = prod_baseline["avg_advance_rate"]

    missing = []
    if variable_cost_per_m is None:
        missing.append("drilling + ground support cost per metre (upload physical stock data and a price list)")
    if fixed_cost_per_shift is None:
        missing.append("fixed labour/machine cost per shift (above)")
    if baseline_rate is None:
        missing.append("baseline advance rate (upload production data)")
    if missing:
        st.info("Sensitivity model needs: " + ", ".join(missing) + ".")
    else:
        try:
            pcts = [float(x.strip()) / 100.0 for x in byod_pcts_raw.split(",") if x.strip() != ""]
        except ValueError:
            pcts = [0.0, 0.15, 0.30]
        if 0.0 not in pcts:
            pcts = [0.0] + pcts
        result = mc.sensitivity_model(variable_cost_per_m, fixed_cost_per_shift, baseline_rate, pcts)
        if result is not None:
            st.dataframe(result, width="stretch", hide_index=True)
            fig = sensitivity_chart(result, byod_currency)
            st.plotly_chart(fig, width="stretch", key="byod_sensitivity_chart")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_prod = productivity_summary()
render_sidebar(_prod)

if LOGO_PATH.exists():
    lc1, lc2 = st.columns([1, 9])
    with lc1:
        st.image(str(LOGO_PATH), width=64)
    with lc2:
        st.title("DevAdvance Analytics")
else:
    st.title("DevAdvance Analytics")

tab_labels = [
    "Control Room", "Meter Reconciliation", "Consumable Leakage & Bit Yield",
    "Sensitivity Simulator", "Monthly Report", "Research Findings", "Bring Your Own Data",
]
tabs = st.tabs(tab_labels)
with tabs[0]:
    render_control_room(_prod)
with tabs[1]:
    render_reconciliation(_prod)
with tabs[2]:
    render_leakage_bityield()
with tabs[3]:
    render_sensitivity_simulator(_prod)
with tabs[4]:
    render_monthly_report()
with tabs[5]:
    render_research_findings(_prod)
with tabs[6]:
    render_byod()
