
import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils.db import _query

st.title("Trend Analysis")
st.caption("Explore historical financial performance of Nifty 100 companies.")

METRICS = {
    "Revenue (Sales)": "sales",
    "Operating Profit": "operating_profit",
    "Net Profit": "net_profit",
    "Operating Profit Margin (%)": "opm_percentage",
    "Net Profit Margin (%)": "net_profit_margin_pct",
    "Return on Equity (%)": "return_on_equity_pct",
    "Debt-to-Equity": "debt_to_equity",
    "Asset Turnover": "asset_turnover",
    "Free Cash Flow (Cr)": "free_cash_flow_cr",
    "Earnings Per Share (EPS)": "eps",
}


@st.cache_data(ttl=600)
def load_trend_data():
    columns = ", ".join(["company_id", "year"] + list(METRICS.values()))
    return _query(
        f"""
        SELECT {columns}
        FROM derived_metrics
        ORDER BY company_id, year
        """
    )


data = load_trend_data()

if data.empty:
    st.warning("No historical financial data is available.")
    st.stop()

data["year"] = pd.to_numeric(data["year"], errors="coerce")
data = data.dropna(subset=["company_id", "year"])
data["year"] = data["year"].astype(int)

for column in METRICS.values():
    data[column] = pd.to_numeric(data[column], errors="coerce")

companies = sorted(data["company_id"].astype(str).unique())

company = st.selectbox("Select company", companies)

available_years = sorted(data["year"].unique())
if len(available_years) > 1:
    selected_years = st.slider(
        "Select year range",
        min_value=int(min(available_years)),
        max_value=int(max(available_years)),
        value=(int(min(available_years)), int(max(available_years))),
        step=1,
    )
else:
    selected_years = (int(available_years[0]), int(available_years[0]))

selected_metrics = st.multiselect(
    "Select up to 3 metrics",
    options=list(METRICS.keys()),
    default=["Revenue (Sales)", "Net Profit"],
    max_selections=3,
)

company_data = data[
    (data["company_id"].astype(str) == company)
    & data["year"].between(selected_years[0], selected_years[1])
].copy()

company_data = company_data.sort_values("year")

if company_data.empty:
    st.info("No data is available for this company and year range.")
    st.stop()

st.subheader(f"Historical Performance — {company}")

if not selected_metrics:
    st.info("Select at least one metric to display a trend chart.")
else:
    for metric_label in selected_metrics:
        column = METRICS[metric_label]
        chart_data = company_data[["year", column]].dropna().copy()

        if chart_data.empty:
            st.warning(f"No data available for {metric_label}.")
            continue

        chart_data["year"] = chart_data["year"].astype(str)

        figure = px.line(
            chart_data,
            x="year",
            y=column,
            markers=True,
            title=metric_label,
            labels={"year": "Financial Year", column: metric_label},
        )
        figure.update_layout(
            height=350,
            xaxis_title="Year",
            yaxis_title=metric_label,
            hovermode="x unified",
        )
        st.plotly_chart(figure, use_container_width=True)

st.subheader("Year-over-Year Change")

yoy_metric = st.selectbox(
    "Metric for YoY analysis",
    options=list(METRICS.keys()),
    index=0,
    key="yoy_metric",
)

yoy_column = METRICS[yoy_metric]
yoy_data = company_data[["year", yoy_column]].dropna().copy()
yoy_data = yoy_data.sort_values("year")
yoy_data["Previous Year Value"] = yoy_data[yoy_column].shift(1)
yoy_data["Change"] = yoy_data[yoy_column] - yoy_data["Previous Year Value"]

previous = yoy_data["Previous Year Value"]
yoy_data["YoY Change (%)"] = (
    yoy_data["Change"].div(previous.abs()).mul(100).where(previous != 0)
)

yoy_data = yoy_data.rename(
    columns={yoy_column: "Current Value", "year": "Year"}
)

st.dataframe(
    yoy_data[
        ["Year", "Current Value", "Previous Year Value", "Change", "YoY Change (%)"]
    ].round(2),
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "YoY change compares each year with the previous available year in the selected "
    "range. Percentage changes are not shown when the previous value is zero."
)

with st.expander("View underlying historical data"):
    st.dataframe(company_data, hide_index=True, use_container_width=True)
