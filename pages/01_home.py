import streamlit as st
import plotly.express as px
from src.dashboard.utils.db import _query, get_companies, get_sectors

st.title("Nifty 100 Analytics")
st.caption("Market overview and financial performance")

companies = get_companies()
sectors = get_sectors()

if companies.empty:
    st.error("Could not load company data. Check data/processed/nifty100.db.")
    st.stop()

year = st.session_state.get("selected_year", 2024)

# KPI calculations use the latest available company summary data.
total_companies = companies["company_id"].nunique()
total_sectors = (
    sectors["broad_sector"].nunique()
    if not sectors.empty else 0
)
avg_roe = companies["latest_roe_pct"].mean()
avg_margin = companies["latest_net_profit_margin_pct"].mean()
positive_fcf = (
    companies["latest_fcf_cr"].gt(0).sum()
    if "latest_fcf_cr" in companies else 0
)
avg_revenue_growth = companies["revenue_cagr_pct"].mean()

kpis = [
    ("Companies", f"{total_companies}"),
    ("Sectors", f"{total_sectors}"),
    ("Average ROE", f"{avg_roe:.2f}%" if avg_roe == avg_roe else "N/A"),
    ("Average Net Margin", f"{avg_margin:.2f}%" if avg_margin == avg_margin else "N/A"),
    ("Positive FCF", f"{positive_fcf}"),
    ("Average Revenue CAGR", f"{avg_revenue_growth:.2f}%" if avg_revenue_growth == avg_revenue_growth else "N/A"),
]

cols = st.columns(6)
for col, (label, value) in zip(cols, kpis):
    col.metric(label, value)

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Sector Distribution")
    if not sectors.empty and "broad_sector" in sectors.columns:
        sector_counts = (
            sectors.dropna(subset=["broad_sector"])
            .groupby("broad_sector")["company_id"]
            .nunique()
            .reset_index(name="Companies")
        )
        if not sector_counts.empty:
            fig = px.pie(
                sector_counts,
                names="broad_sector",
                values="Companies",
                hole=0.48,
                title="Companies by sector",
            )
            fig.update_layout(height=420, margin=dict(t=50, b=20, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sector classifications are unavailable.")
    else:
        st.info("Sector data is unavailable.")

with right:
    st.subheader("Top 5 Companies")
    ranking = _query("""
        SELECT company_id, overall_score, rank
        FROM company_scorecard
        WHERE overall_score IS NOT NULL
        ORDER BY overall_score DESC
        LIMIT 5
    """)
    if not ranking.empty:
        ranking = ranking.rename(columns={
            "company_id": "Company",
            "overall_score": "Composite Score",
            "rank": "Rank",
        })
        st.dataframe(ranking, hide_index=True, use_container_width=True)
        fig = px.bar(
            ranking.sort_values("Composite Score"),
            x="Composite Score",
            y="Company",
            orientation="h",
            title="Highest composite scores",
        )
        fig.update_layout(height=320, margin=dict(t=50, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Company ranking data is not available.")

st.caption(
    f"Selected financial year: {year}. "
    "Company-summary KPIs use each company's latest available data; "
    "they are not restricted to the selected year."
)
