
import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils.db import _query

st.title("Capital Allocation")
st.caption(
    "Explore how companies generate cash and allocate capital "
    "across operating, investing, and financing activities."
)


@st.cache_data(ttl=600)
def load_capital_data():
    return _query("""
        SELECT
            d.company_id,
            d.year,
            d.sales,
            d.net_profit,
            d.operating_activity,
            d.investing_activity,
            d.financing_activity,
            d.net_cash_flow,
            d.free_cash_flow_cr,
            d.capex_cr,
            s.broad_sector,
            s.sub_sector
        FROM derived_metrics AS d
        LEFT JOIN sectors AS s
            ON d.company_id = s.company_id
        WHERE d.year = (
            SELECT MAX(d2.year)
            FROM derived_metrics AS d2
            WHERE d2.company_id = d.company_id
        )
    """)


try:
    data = load_capital_data()
except Exception as exc:
    st.error(f"Could not load capital allocation data: {exc}")
    st.stop()

if data.empty:
    st.warning("No capital allocation data is available.")
    st.stop()

numeric_columns = [
    "year", "sales", "net_profit", "operating_activity",
    "investing_activity", "financing_activity", "net_cash_flow",
    "free_cash_flow_cr", "capex_cr",
]

for column in numeric_columns:
    data[column] = pd.to_numeric(data[column], errors="coerce")

data["broad_sector"] = data["broad_sector"].fillna("Unclassified")
data["sub_sector"] = data["sub_sector"].fillna("Unclassified")

sectors = sorted(data["broad_sector"].unique())
selected_sectors = st.multiselect(
    "Filter by sector",
    sectors,
    default=sectors,
)

filtered = data[data["broad_sector"].isin(selected_sectors)].copy()

if filtered.empty:
    st.info("Select at least one sector to continue.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)

c1.metric("Companies", f"{filtered['company_id'].nunique():,}")

operating_median = filtered["operating_activity"].median()
c2.metric(
    "Median Operating Cash Flow",
    f"{operating_median:,.2f}" if pd.notna(operating_median) else "N/A",
)

fcf_median = filtered["free_cash_flow_cr"].median()
c3.metric(
    "Median Free Cash Flow",
    f"{fcf_median:,.2f}" if pd.notna(fcf_median) else "N/A",
)

capex_median = filtered["capex_cr"].median()
c4.metric(
    "Median CapEx",
    f"{capex_median:,.2f}" if pd.notna(capex_median) else "N/A",
)

st.subheader("Capital Allocation Overview")

pattern = st.selectbox(
    "Choose allocation view",
    [
        "Operating Cash Flow",
        "Investing Activity",
        "Financing Activity",
        "Free Cash Flow",
        "Capital Expenditure",
        "Net Cash Flow",
        "Net Profit",
        "Revenue",
    ],
)

value_columns = {
    "Operating Cash Flow": "operating_activity",
    "Investing Activity": "investing_activity",
    "Financing Activity": "financing_activity",
    "Free Cash Flow": "free_cash_flow_cr",
    "Capital Expenditure": "capex_cr",
    "Net Cash Flow": "net_cash_flow",
    "Net Profit": "net_profit",
    "Revenue": "sales",
}

value_column = value_columns[pattern]

tree_data = filtered.dropna(
    subset=["company_id", value_column]
).copy()

# Treemaps require non-negative areas. Preserve the signed value in
# the hover data and size rectangles by absolute magnitude.
tree_data["treemap_size"] = tree_data[value_column].abs()
tree_data = tree_data[tree_data["treemap_size"] > 0]

if not tree_data.empty:
    tree = px.treemap(
        tree_data,
        path=["broad_sector", "company_id"],
        values="treemap_size",
        color=value_column,
        color_continuous_scale="RdYlGn",
        hover_data={
            value_column: ":.2f",
            "year": True,
            "sub_sector": True,
        },
        title=f"{pattern} by Sector and Company",
    )
    tree.update_layout(height=650)
    st.plotly_chart(tree, use_container_width=True)
    st.caption(
        "Rectangle area represents the absolute magnitude of the selected "
        "metric. The original signed value is shown in the hover details. "
        "Positive and negative cash flows should be interpreted separately."
    )
else:
    st.info(f"No non-zero values are available for {pattern}.")

st.subheader("Cash Flow Composition")

cash_columns = [
    "operating_activity",
    "investing_activity",
    "financing_activity",
]

cash_summary = (
    filtered.groupby("broad_sector")[cash_columns]
    .median()
    .reset_index()
)

cash_summary = cash_summary.rename(columns={
    "broad_sector": "Sector",
    "operating_activity": "Operating Cash Flow",
    "investing_activity": "Investing Cash Flow",
    "financing_activity": "Financing Cash Flow",
})

cash_long = cash_summary.melt(
    id_vars="Sector",
    var_name="Cash Flow Type",
    value_name="Median Amount",
)

cash_chart = px.bar(
    cash_long,
    x="Sector",
    y="Median Amount",
    color="Cash Flow Type",
    barmode="group",
    title="Median Cash Flow by Sector",
)
cash_chart.update_layout(xaxis_tickangle=-35, height=500)
st.plotly_chart(cash_chart, use_container_width=True)

st.subheader("Company-Level Capital Allocation")

display_columns = [
    "company_id",
    "broad_sector",
    "sub_sector",
    "year",
    "sales",
    "net_profit",
    "operating_activity",
    "investing_activity",
    "financing_activity",
    "net_cash_flow",
    "free_cash_flow_cr",
    "capex_cr",
]

st.dataframe(
    filtered[display_columns]
    .sort_values(["broad_sector", "company_id"])
    .round(2),
    hide_index=True,
    use_container_width=True,
)

csv_data = filtered[display_columns].to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Capital Allocation CSV",
    data=csv_data,
    file_name="capital_allocation.csv",
    mime="text/csv",
)

st.caption(
    "The page uses each company's latest available record. Financial years "
    "may differ. Cash flow values retain their original signs in the table."
)
