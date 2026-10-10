import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.db import _query

st.title("Peer Comparison")
st.caption("Compare a company against its peer-group benchmark")

@st.cache_data(ttl=600)
def load_peer_data():
    return _query("""
        SELECT company_id, peer_group_name, metric,
               value, percentile_rank, year
        FROM peer_percentiles
        WHERE peer_group_name != 'No peer group assigned'
        ORDER BY year
    """)

data = load_peer_data()

if data.empty:
    st.warning("Peer comparison data is unavailable.")
    st.stop()

data["year"] = pd.to_numeric(data["year"], errors="coerce")
data["value"] = pd.to_numeric(data["value"], errors="coerce")
data["percentile_rank"] = pd.to_numeric(
    data["percentile_rank"], errors="coerce"
)

groups = sorted(data["peer_group_name"].dropna().unique())
group = st.selectbox("Peer group", groups)

group_data = data[data["peer_group_name"] == group].copy()

if group_data.empty:
    st.info("No companies are available in this peer group.")
    st.stop()

# Retain the most recent record for each company and metric.
group_data = (
    group_data.sort_values("year")
    .drop_duplicates(["company_id", "metric"], keep="last")
)

companies = sorted(group_data["company_id"].dropna().unique())

if not companies:
    st.info("No companies are available for this peer group.")
    st.stop()

ticker = st.selectbox("Select company", companies)
company_data = group_data[group_data["company_id"] == ticker]

# Use peer percentiles for a comparable radar-chart scale.
benchmark = (
    group_data.groupby("metric")["percentile_rank"]
    .mean()
    .dropna()
)
company_scores = (
    company_data.set_index("metric")["percentile_rank"]
    .dropna()
)

metrics = sorted(set(benchmark.index) & set(company_scores.index))

if metrics:
    radar = go.Figure()
    radar.add_trace(go.Scatterpolar(
        r=[company_scores[m] for m in metrics],
        theta=metrics,
        fill="toself",
        name=ticker,
    ))
    radar.add_trace(go.Scatterpolar(
        r=[benchmark[m] for m in metrics],
        theta=metrics,
        fill="toself",
        name="Peer-group average",
    ))
    radar.update_layout(
        title="Company vs Peer Group — Percentile Comparison",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=520,
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(radar, use_container_width=True)
else:
    st.info("There are not enough common percentile metrics for a radar chart.")

st.subheader("Financial Metric Comparison")

company_values = (
    company_data.set_index("metric")["value"]
    .rename("Selected Company")
)
peer_values = (
    group_data.groupby("metric")["value"]
    .mean()
    .rename("Peer-group Average")
)

comparison = pd.concat([company_values, peer_values], axis=1)
comparison["Difference"] = (
    comparison["Selected Company"] - comparison["Peer-group Average"]
)
comparison.index.name = "Metric"
comparison = comparison.reset_index()

st.dataframe(
    comparison.round(2),
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Radar values are percentile ranks from 0 to 100. "
    "The table shows raw metric values and the peer-group mean. "
    "Missing values are excluded from calculations."
)

with st.expander("View underlying peer data"):
    st.dataframe(group_data, hide_index=True, use_container_width=True)