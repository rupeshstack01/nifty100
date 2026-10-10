import streamlit as st
import plotly.express as px
from src.dashboard.utils.db import _query, get_companies

st.title("Company Profile")
st.caption("Historical financial performance and company fundamentals")

companies = get_companies()

if companies.empty:
    st.error("Company data is unavailable. Check the SQLite database.")
    st.stop()

tickers = sorted(companies["company_id"].dropna().unique())
ticker = st.selectbox("Search company or ticker", tickers)

summary_rows = companies[
    companies["company_id"].astype(str).str.upper() == ticker.upper()
]
summary = summary_rows.iloc[0] if not summary_rows.empty else None

history = _query("""
    SELECT company_id, year, sales, net_profit,
           return_on_equity_pct, net_profit_margin_pct,
           debt_to_equity, free_cash_flow_cr
    FROM derived_metrics
    WHERE UPPER(company_id) = UPPER(?)
    ORDER BY year
""", (ticker,))

ratios = _query("""
    SELECT year, engine_roce_pct, revenue_cagr_5yr,
           record_status
    FROM financial_ratios
    WHERE UPPER(company_id) = UPPER(?)
      AND (record_status IS NULL OR record_status != 'VARIANT_REVIEW')
    ORDER BY year
""", (ticker,))

if not history.empty:
    history = history.drop_duplicates(subset=["year"], keep="last")

if not ratios.empty:
    ratios = ratios.drop_duplicates(subset=["year"], keep="last")
    history = history.merge(
        ratios[["year", "engine_roce_pct", "revenue_cagr_5yr"]],
        on="year",
        how="left",
        validate="one_to_one",
    )
else:
    history["engine_roce_pct"] = float("nan")
    history["revenue_cagr_5yr"] = float("nan")

def latest_value(column):
    if history.empty or column not in history.columns:
        return None
    values = history[column].dropna()
    return None if values.empty else float(values.iloc[-1])

def display_pct(value):
    return "N/A" if value is None else f"{value:.2f}%"

def display_number(value):
    return "N/A" if value is None else f"{value:,.2f}"

roe = latest_value("return_on_equity_pct")
roce = latest_value("engine_roce_pct")
npm = latest_value("net_profit_margin_pct")
de = latest_value("debt_to_equity")
fcf = latest_value("free_cash_flow_cr")
cagr = latest_value("revenue_cagr_5yr")

# Prefer the five-year CAGR from the latest eligible ratio record.
if not ratios.empty and ratios["revenue_cagr_5yr"].notna().any():
    cagr = float(ratios["revenue_cagr_5yr"].dropna().iloc[-1])

st.subheader(ticker)

if summary is not None:
    sector = summary.get("broad_sector")
    if sector is not None and str(sector) != "nan":
        st.caption(f"Sector: {sector}")

kpis = [
    ("Return on Equity", display_pct(roe)),
    ("Return on Capital Employed", display_pct(roce)),
    ("Net Profit Margin", display_pct(npm)),
    ("Debt / Equity", display_number(de)),
    ("Revenue CAGR (5Y)", display_pct(cagr)),
    ("Free Cash Flow (₹ Cr)", display_number(fcf)),
]

cols = st.columns(3)
for i, (label, value) in enumerate(kpis):
    cols[i % 3].metric(label, value)

st.divider()

if history.empty:
    st.warning(f"No historical financial data is available for {ticker}.")
    st.stop()

history["year"] = history["year"].astype(int)

st.subheader("Revenue and Net Profit History")
financial_chart = history.melt(
    id_vars="year",
    value_vars=["sales", "net_profit"],
    var_name="Metric",
    value_name="₹ Crore",
).dropna(subset=["₹ Crore"])

if not financial_chart.empty:
    financial_chart["Metric"] = financial_chart["Metric"].map({
        "sales": "Revenue",
        "net_profit": "Net Profit",
    })
    fig = px.line(
        financial_chart,
        x="year",
        y="₹ Crore",
        color="Metric",
        markers=True,
    )
    fig.update_layout(
        height=420,
        xaxis_title="Financial Year",
        yaxis_title="₹ Crore",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Revenue and net profit history is unavailable.")

st.subheader("ROE vs ROCE")
returns_chart = history.melt(
    id_vars="year",
    value_vars=["return_on_equity_pct", "engine_roce_pct"],
    var_name="Metric",
    value_name="Return (%)",
).dropna(subset=["Return (%)"])

if not returns_chart.empty:
    returns_chart["Metric"] = returns_chart["Metric"].map({
        "return_on_equity_pct": "ROE",
        "engine_roce_pct": "ROCE",
    })
    fig = px.line(
        returns_chart,
        x="year",
        y="Return (%)",
        color="Metric",
        markers=True,
    )
    fig.update_layout(height=380, xaxis_title="Financial Year")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Historical ROE/ROCE data is unavailable.")

with st.expander("View historical financial data"):
    st.dataframe(history, hide_index=True, use_container_width=True)

st.subheader("Company Pros and Cons")
st.info(
    "Pros and cons are not available in the current SQLite database. "
    "They can be added when a verified company-specific source is connected."
)
