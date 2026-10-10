import streamlit as st
import pandas as pd

from src.screener.engine import (
    load_config,
    build_screener_dataset,
    latest_company_records,
    apply_filters,
)
from src.screener.ranking import build_ranking_scores

st.title("Stock Screener")
st.caption("Filter Nifty 100 companies using financial fundamentals")

@st.cache_data(ttl=600)
def load_screen_data():
    data = build_screener_dataset()
    latest = latest_company_records(data)
    ranked = build_ranking_scores(latest)
    return ranked

try:
    config = load_config()
    data = load_screen_data()
except Exception as exc:
    st.error(f"Unable to load screener data: {exc}")
    st.stop()

presets = config.get("presets", {})
preset_names = ["Custom Filters"] + [
    name.replace("_", " ").title() for name in presets
]
selected = st.selectbox("Screening strategy", preset_names)

preset_key = next(
    (
        key for key in presets
        if key.replace("_", " ").title() == selected
    ),
    None,
)

if preset_key:
    st.info(presets[preset_key].get("description", ""))

st.subheader("Financial Filters")
st.caption("Leave a filter disabled to include companies regardless of that metric.")

available_filters = {
    "min_roe": ("Minimum ROE (%)", -100.0, 100.0, 5.0),
    "max_de": ("Maximum Debt / Equity", 0.0, 20.0, 0.25),
    "min_fcf": ("Minimum Free Cash Flow (₹ Cr)", -100000.0, 100000.0, 100.0),
    "min_revenue_cagr_5yr": ("Minimum Revenue CAGR 5Y (%)", -100.0, 200.0, 5.0),
    "min_pat_cagr_5yr": ("Minimum PAT CAGR 5Y (%)", -100.0, 300.0, 5.0),
    "min_opm": ("Minimum Operating Margin (%)", -100.0, 100.0, 5.0),
    "max_pe": ("Maximum P/E", 0.0, 300.0, 5.0),
    "max_pb": ("Maximum P/B", 0.0, 100.0, 1.0),
    "min_dividend_yield_pct": ("Minimum Dividend Yield (%)", 0.0, 20.0, 0.5),
    "min_interest_coverage": ("Minimum Interest Coverage", 0.0, 100.0, 1.0),
    "min_market_cap_crore": ("Minimum Market Cap (₹ Cr)", 0.0, 3000000.0, 10000.0),
    "min_net_profit_cr": ("Minimum Net Profit (₹ Cr)", -100000.0, 100000.0, 100.0),
    "min_eps_cagr_5yr": ("Minimum EPS CAGR 5Y (%)", -100.0, 300.0, 5.0),
    "min_asset_turnover": ("Minimum Asset Turnover", 0.0, 20.0, 0.25),
    "min_sales_cr": ("Minimum Revenue (₹ Cr)", 0.0, 500000.0, 1000.0),
}

active_filters = {}

if preset_key:
    active_filters.update(presets[preset_key].get("filters", {}))

with st.expander("Adjust filters", expanded=not bool(preset_key)):
    cols = st.columns(2)
    for i, (key, (label, low, high, step)) in enumerate(available_filters.items()):
        preset_value = active_filters.get(key)
        enabled = cols[i % 2].checkbox(
            f"Enable: {label}",
            value=preset_value is not None,
            key=f"enable_{selected}_{key}",
        )
        if enabled:
            default = preset_value if preset_value is not None else low
            default = min(max(float(default), low), high)
            active_filters[key] = cols[i % 2].number_input(
                label,
                min_value=low,
                max_value=high,
                value=default,
                step=step,
                key=f"value_{selected}_{key}",
            )
        else:
            active_filters.pop(key, None)

try:
    if preset_key and not active_filters:
        results = data.copy()
    else:
        results = apply_filters(data, active_filters)

    # Recalculate ranking if filtering returns a subset.
    results = build_ranking_scores(results)
except Exception as exc:
    st.error(f"Could not apply filters: {exc}")
    st.stop()

st.subheader("Screening Results")
st.metric("Matching companies", len(results))

if results.empty:
    st.warning("No companies match these filters. Try relaxing one or more conditions.")
else:
    preferred = [
        "company_id", "rank", "overall_score", "latest_roe_pct",
        "engine_roce_pct", "latest_debt_to_equity",
        "latest_fcf_cr", "revenue_cagr_5yr", "pat_cagr_5yr",
        "latest_sales", "latest_net_profit",
    ]
    columns = [c for c in preferred if c in results.columns]
    if not columns:
        columns = results.columns.tolist()

    st.dataframe(
        results[columns].sort_values(
            "overall_score", ascending=False
        ) if "overall_score" in columns else results[columns],
        hide_index=True,
        use_container_width=True,
    )

    csv = results.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download results as CSV",
        data=csv,
        file_name="nifty100_screener_results.csv",
        mime="text/csv",
    )