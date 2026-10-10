from pathlib import Path
import sys
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

# Make the project root importable by all Streamlit pages.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("Nifty 100 Analytics")
st.sidebar.caption("Financial Analysis Dashboard")

st.session_state["selected_year"] = st.sidebar.selectbox(
    "Financial year",
    options=list(range(2024, 2018, -1)),
    index=0,
    key="global_financial_year",
)

pages = [
    st.Page(str(ROOT / "pages/01_home.py"),
            title="Home", icon="🏠", default=True),
    st.Page(str(ROOT / "pages/02_profile.py"),
            title="Company Profile", icon="🏢"),
    st.Page(str(ROOT / "pages/03_screener.py"),
            title="Stock Screener", icon="🔎"),
    st.Page(str(ROOT / "pages/04_peers.py"),
            title="Peer Comparison", icon="📊"),
    st.Page(str(ROOT / "pages/05_trends.py"),
            title="Trend Analysis", icon="📈"),
    st.Page(str(ROOT / "pages/06_sectors.py"),
            title="Sector Analysis", icon="🏭"),
    st.Page(str(ROOT / "pages/07_capital.py"),
            title="Capital Allocation", icon="💰"),
    st.Page(str(ROOT / "pages/08_reports.py"),
            title="Annual Reports", icon="📄"),
        st.Page(str(ROOT / "pages/09_valuation.py"),
            title="Valuation Analysis", icon="💹"),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
