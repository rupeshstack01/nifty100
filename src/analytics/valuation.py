
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

st.title("Valuation Analysis")
st.caption(
    "Compare company valuations with sector P/E benchmarks, "
    "free cash flow yield, and dividend yield."
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "valuation_summary.xlsx"


@st.cache_data(ttl=600)
def load_valuation():
    if not REPORT_PATH.exists():
        return pd.DataFrame()

    df = pd.read_excel(
        REPORT_PATH,
        sheet_name="Valuation Summary",
    )

    numeric_columns = [
        "year",
        "market_cap_crore",
        "enterprise_value_crore",
        "pe_ratio",
        "sector_median_pe",
        "pe_to_sector_median_pct",
        "pb_ratio",
        "ev_ebitda",
        "dividend_yield_pct",
        "free_cash_flow_cr",
        "fcf_yield_pct",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


try:
    data = load_valuation()
except Exception as exc:
    st.error(f"Could not load the valuation report: {exc}")
    st.stop()

if data.empty:
    st.warning(
        "Valuation report not found. Run "
        "`./.venv/bin/python src/analytics/valuation.py` first."
    )
    st.stop()

if "valuation_flag" not in data.columns:
    st.error("The report is missing the valuation_flag column.")
    st.stop()

# The valuation engine currently exports its latest available year.
report_years = sorted(data["year"].dropna().unique(), reverse=True)
if not report_years:
    st.error("No valid financial year is available.")
    st.stop()

selected_year = st.selectbox(
    "Financial Year",
    report_years,
    index=0,
)

data = data.loc[data["year"] == selected_year].copy()

st.info(
    "Valuation flags are relative P/E screening signals, not "
    "investment recommendations. FCF yield uses the FCF year "
    "shown in the table, which may differ from the valuation year."
)

# Sidebar filters
st.sidebar.subheader("Valuation Filters")

available_sectors = sorted(
    data["broad_sector"].dropna().astype(str).unique()
)
sector_options = st.sidebar.multiselect(
    "Sector",
    available_sectors,
    default=available_sectors,
)

flag_options = ["Discount", "Fair", "Caution", "Insufficient Data"]
available_flags = [
    flag for flag in flag_options
    if data["valuation_flag"].eq(flag).any()
]
selected_flags = st.sidebar.multiselect(
    "Valuation classification",
    available_flags,
    default=available_flags,
)

search = st.sidebar.text_input(
    "Company ticker",
    placeholder="e.g. TCS",
)

filtered = data.copy()

if sector_options:
    filtered = filtered[
        filtered["broad_sector"].isin(sector_options)
    ]
else:
    filtered = filtered.iloc[0:0]

if selected_flags:
    filtered = filtered[
        filtered["valuation_flag"].isin(selected_flags)
    ]
else:
    filtered = filtered.iloc[0:0]

if search.strip():
    filtered = filtered[
        filtered["company_id"].astype(str).str.contains(
            search.strip(), case=False, regex=False, na=False
        )
    ]

# Summary KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Companies", f"{len(filtered):,}")
k2.metric(
    "Discount",
    int(filtered["valuation_flag"].eq("Discount").sum()),
)
k3.metric(
    "Fair",
    int(filtered["valuation_flag"].eq("Fair").sum()),
)
k4.metric(
    "Caution",
    int(filtered["valuation_flag"].eq("Caution").sum()),
)

st.divider()

st.subheader("P/E vs Sector Median")

chart_data = filtered.dropna(
    subset=["pe_ratio", "sector_median_pe"]
).copy()

chart_data = chart_data[
    (chart_data["pe_ratio"] > 0)
    & (chart_data["sector_median_pe"] > 0)
]

if chart_data.empty:
    st.info("No valid P/E comparisons match the current filters.")
else:
    chart_data["P/E vs Sector Median"] = (
        chart_data["pe_ratio"] / chart_data["sector_median_pe"]
    )
    chart_data = chart_data.set_index("company_id")
    st.bar_chart(
        chart_data[["P/E vs Sector Median"]].sort_values(
            "P/E vs Sector Median"
        ),
        horizontal=True,
    )

st.caption(
    "A ratio below 1 means P/E is below the sector median; "
    "above 1 means it is above the sector median."
)

st.subheader("FCF Yield and Dividend Yield")

yield_data = filtered[
    ["company_id", "fcf_yield_pct", "dividend_yield_pct"]
].copy().set_index("company_id")

yield_data = yield_data.rename(columns={
    "fcf_yield_pct": "FCF Yield (%)",
    "dividend_yield_pct": "Dividend Yield (%)",
})

if yield_data.empty:
    st.info("No yield data matches the current filters.")
else:
    st.bar_chart(yield_data)

st.subheader("Valuation Results")

display_columns = [
    "company_id",
    "broad_sector",
    "market_cap_crore",
    "pe_ratio",
    "sector_median_pe",
    "pe_to_sector_median_pct",
    "pb_ratio",
    "ev_ebitda",
    "free_cash_flow_cr",
    "fcf_year",
    "fcf_yield_pct",
    "dividend_yield_pct",
    "valuation_flag",
    "data_quality_note",
]

display_columns = [
    col for col in display_columns if col in filtered.columns
]

display = filtered[display_columns].copy()

st.dataframe(
    display,
    hide_index=True,
    use_container_width=True,
    column_config={
        "market_cap_crore": st.column_config.NumberColumn(
            "Market Cap (₹ crore)", format="%,.2f"
        ),
        "pe_ratio": st.column_config.NumberColumn("P/E", format="%.2f"),
        "sector_median_pe": st.column_config.NumberColumn(
            "Sector Median P/E", format="%.2f"
        ),
        "pe_to_sector_median_pct": st.column_config.NumberColumn(
            "P/E vs Median (%)", format="%.2f%%"
        ),
        "free_cash_flow_cr": st.column_config.NumberColumn(
            "FCF (₹ crore)", format="%,.2f"
        ),
        "fcf_yield_pct": st.column_config.NumberColumn(
            "FCF Yield (%)", format="%.2f%%"
        ),
        "dividend_yield_pct": st.column_config.NumberColumn(
            "Dividend Yield (%)", format="%.2f%%"
        ),
    },
)

st.download_button(
    "Download filtered valuation CSV",
    data=display.to_csv(index=False).encode("utf-8"),
    file_name=f"nifty100_valuation_{int(selected_year)}.csv",
    mime="text/csv",
)

st.caption(
    "Source: project valuation_summary.xlsx. "
    "Missing values remain blank rather than being treated as zero."
)
