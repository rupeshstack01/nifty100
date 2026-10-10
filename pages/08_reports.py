
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.title("Annual Reports")
st.caption("Browse company annual reports from the Bluestock Nifty 100 dataset.")

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/1788501606362-ba899c04-documents.xlsx"


def extract_url(value):
    if pd.isna(value):
        return None

    text = str(value).strip()

    # Convert Markdown hyperlinks to direct URLs.
    match = re.search(r"\]\((https?://[^)\s]+)\)", text)
    if match:
        return match.group(1)

    match = re.search(r"https?://[^\s)]+", text)
    return match.group(0) if match else None


@st.cache_data(ttl=600)
def load_reports():
    if not SOURCE.exists():
        return pd.DataFrame()

    # First row is a title; second row contains actual headings.
    df = pd.read_excel(SOURCE, sheet_name=0, header=1)
    df.columns = [str(c).strip() for c in df.columns]

    required = ["company_id", "Year", "Annual_Report"]
    if not all(c in df.columns for c in required):
        raise ValueError(f"Unexpected columns: {df.columns.tolist()}")

    df["company_id"] = df["company_id"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Report URL"] = df["Annual_Report"].apply(extract_url)

    df = df.dropna(subset=["Year"])
    df["Year"] = df["Year"].astype(int)

    df = df[df["company_id"].ne("")]
    df = df[df["company_id"].ne("nan")]

    return df.sort_values(
        ["company_id", "Year"], ascending=[True, False]
    )


try:
    reports = load_reports()
except Exception as exc:
    st.error(f"Could not load annual reports: {exc}")
    st.stop()

if reports.empty:
    st.warning("No annual reports are available.")
    st.stop()

companies = sorted(reports["company_id"].unique())
years = sorted(reports["Year"].unique(), reverse=True)

col1, col2 = st.columns(2)

with col1:
    selected_company = st.selectbox(
        "Company",
        ["All Companies"] + companies,
    )

with col2:
    selected_year = st.selectbox(
        "Financial Year",
        ["All Years"] + years,
    )

filtered = reports.copy()

if selected_company != "All Companies":
    filtered = filtered[
        filtered["company_id"] == selected_company
    ]

if selected_year != "All Years":
    filtered = filtered[
        filtered["Year"] == selected_year
    ]

search = st.text_input(
    "Search company",
    placeholder="Enter ticker, e.g. ABB or TCS",
)

if search:
    filtered = filtered[
        filtered["company_id"].str.contains(
            search, case=False, regex=False, na=False
        )
    ]

c1, c2, c3 = st.columns(3)
c1.metric("Reports", f"{len(filtered):,}")
c2.metric("Companies", filtered["company_id"].nunique())
c3.metric("Years", filtered["Year"].nunique())

st.subheader("Available Reports")

display = filtered[
    ["company_id", "Year", "Report URL"]
].copy()

display = display.rename(columns={
    "company_id": "Company",
    "Year": "Financial Year",
})

st.dataframe(
    display,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Report URL": st.column_config.LinkColumn(
            "Annual Report PDF",
            display_text="Open PDF",
        )
    },
)

st.caption(
    "Links are taken from the source workbook. "
    "They have not been independently checked for HTTP errors."
)

st.download_button(
    "Download Report Index CSV",
    data=display.to_csv(index=False).encode("utf-8"),
    file_name="nifty100_annual_reports.csv",
    mime="text/csv",
)

if selected_company != "All Companies":
    st.subheader(f"Report History — {selected_company}")
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
    )
