
import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils.db import _query

st.title("Sector Analysis")
st.caption(
    "Explore sector-level financial performance and compare companies."
)


@st.cache_data(ttl=600)
def load_sector_data():
    return _query("""
        SELECT
            d.company_id,
            d.year,
            d.sales,
            d.net_profit,
            d.return_on_equity_pct,
            d.revenue_growth_pct,
            d.net_profit_margin_pct,
            d.debt_to_equity,
            d.free_cash_flow_cr,
            r.revenue_cagr_5yr,
            s.broad_sector,
            s.sub_sector,
            s.index_weight_pct,
            s.market_cap_category
        FROM derived_metrics AS d
        LEFT JOIN sectors AS s
            ON d.company_id = s.company_id
        LEFT JOIN financial_ratios AS r
            ON d.financial_ratios_id = r.id
        WHERE d.year = (
            SELECT MAX(d2.year)
            FROM derived_metrics AS d2
            WHERE d2.company_id = d.company_id
        )
    """)


try:
    data = load_sector_data()
except Exception as exc:
    st.error(f"Could not load sector financial data: {exc}")
    st.stop()

if data.empty:
    st.warning("No sector financial data is available.")
    st.stop()

numeric_columns = [
    "year", "sales", "net_profit", "return_on_equity_pct",
    "revenue_growth_pct", "net_profit_margin_pct", "debt_to_equity",
    "free_cash_flow_cr", "revenue_cagr_5yr", "index_weight_pct",
]

for column in numeric_columns:
    data[column] = pd.to_numeric(data[column], errors="coerce")

data["broad_sector"] = data["broad_sector"].fillna("Unclassified")
data["sub_sector"] = data["sub_sector"].fillna("Unclassified")

sectors = sorted(data["broad_sector"].unique())
selected_sectors = st.multiselect(
    "Filter sectors", sectors, default=sectors
)

filtered = data[data["broad_sector"].isin(selected_sectors)].copy()

if filtered.empty:
    st.info("Select at least one sector to view the analysis.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Companies", f"{filtered['company_id'].nunique():,}")

valid_roe = filtered["return_on_equity_pct"].dropna()
valid_sales = filtered["sales"].dropna()

c2.metric(
    "Median ROE",
    f"{valid_roe.median():.2f}%" if not valid_roe.empty else "N/A",
)
c3.metric(
    "Median Revenue",
    f"{valid_sales.median():,.2f}" if not valid_sales.empty else "N/A",
)

st.subheader("Sector Performance")

sector_summary = (
    filtered.groupby("broad_sector")
    .agg(
        Companies=("company_id", "nunique"),
        Median_Revenue=("sales", "median"),
        Median_Net_Profit=("net_profit", "median"),
        Median_ROE=("return_on_equity_pct", "median"),
        Median_NPM=("net_profit_margin_pct", "median"),
        Median_FCF=("free_cash_flow_cr", "median"),
    )
    .reset_index()
    .sort_values("Median_ROE", ascending=False, na_position="last")
)

chart = px.bar(
    sector_summary,
    x="broad_sector",
    y="Median_ROE",
    hover_data=["Companies", "Median_Revenue", "Median_Net_Profit"],
    title="Median Return on Equity by Sector",
    labels={
        "broad_sector": "Sector",
        "Median_ROE": "Median ROE (%)",
    },
)
chart.update_layout(xaxis_tickangle=-35, height=450)
st.plotly_chart(chart, use_container_width=True)

st.subheader("Company Comparison")

plot_data = filtered.dropna(
    subset=["sales", "return_on_equity_pct"]
).copy()

if not plot_data.empty:
    plot_data["bubble_size"] = (
        plot_data["index_weight_pct"].fillna(0).clip(lower=0)
    )
    plot_data["bubble_size"] = plot_data["bubble_size"].replace(0, 0.01)

    bubble = px.scatter(
        plot_data,
        x="sales",
        y="return_on_equity_pct",
        size="bubble_size",
        color="sub_sector",
        hover_name="company_id",
        hover_data=[
            "broad_sector", "net_profit", "revenue_growth_pct",
            "revenue_cagr_5yr", "net_profit_margin_pct",
            "market_cap_category",
        ],
        size_max=35,
        title="Revenue vs ROE",
        labels={
            "sales": "Revenue",
            "return_on_equity_pct": "Return on Equity (%)",
            "sub_sector": "Sub-sector",
            "bubble_size": "Index weight",
        },
    )
    bubble.update_layout(height=550)
    st.plotly_chart(bubble, use_container_width=True)
else:
    st.info("Insufficient revenue and ROE data for the bubble chart.")

st.subheader("Sector Summary")

summary_display = sector_summary.rename(columns={
    "broad_sector": "Sector",
    "Median_Revenue": "Median Revenue",
    "Median_Net_Profit": "Median Net Profit",
    "Median_ROE": "Median ROE (%)",
    "Median_NPM": "Median Net Profit Margin (%)",
    "Median_FCF": "Median Free Cash Flow",
})

st.dataframe(
    summary_display.round(2),
    hide_index=True,
    use_container_width=True,
)

st.subheader("Company-Level Details")

detail_columns = [
    "company_id", "broad_sector", "sub_sector", "year", "sales",
    "net_profit", "return_on_equity_pct", "revenue_growth_pct",
    "revenue_cagr_5yr", "net_profit_margin_pct", "debt_to_equity",
    "free_cash_flow_cr",
]

st.dataframe(
    filtered[detail_columns]
    .sort_values(["broad_sector", "company_id"])
    .round(2),
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Each company uses its latest available financial record, so financial "
    "years may differ. Revenue growth is the recorded year-over-year metric; "
    "5-year revenue CAGR is sourced from financial_ratios. Missing values "
    "are excluded from calculations."
)

