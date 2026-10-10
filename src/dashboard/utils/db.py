from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "processed" / "nifty100.db"
VALUATION_PATH = ROOT / "output" / "valuation_summary.xlsx"


def _query(sql, params=()):
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def _table_exists(table):
    tables = _query(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    return not tables.empty and table in tables["name"].tolist()


@st.cache_data(ttl=600)
def get_companies():
    companies = _query("""
        SELECT cs.*, s.broad_sector, s.sub_sector,
               s.market_cap_category
        FROM company_summary cs
        LEFT JOIN sectors s ON cs.company_id = s.company_id
        ORDER BY cs.company_id
    """)
    if not companies.empty:
        companies["company_name"] = companies["company_id"]
    return companies


@st.cache_data(ttl=600)
def get_ratios(ticker, year=None):
    if year is None:
        return _query("""
            SELECT * FROM financial_ratios
            WHERE UPPER(company_id) = UPPER(?)
            ORDER BY year
        """, (ticker,))
    return _query("""
        SELECT * FROM financial_ratios
        WHERE UPPER(company_id) = UPPER(?) AND year = ?
        ORDER BY year
    """, (ticker, int(year)))


@st.cache_data(ttl=600)
def get_pl(ticker):
    return _query("""
        SELECT company_id, year, sales, expenses, operating_profit,
               opm_percentage, other_income, interest, depreciation,
               profit_before_tax, tax_percentage, net_profit, eps,
               dividend_payout
        FROM derived_metrics
        WHERE UPPER(company_id) = UPPER(?)
        ORDER BY year
    """, (ticker,))


@st.cache_data(ttl=600)
def get_bs(ticker):
    return _query("""
        SELECT company_id, year, equity_capital, reserves, borrowings,
               other_liabilities, total_liabilities, fixed_assets,
               cwip, investments, other_asset, total_assets
        FROM derived_metrics
        WHERE UPPER(company_id) = UPPER(?)
        ORDER BY year
    """, (ticker,))


@st.cache_data(ttl=600)
def get_cf(ticker):
    return _query("""
        SELECT company_id, year, operating_activity, investing_activity,
               financing_activity, net_cash_flow, free_cash_flow_cr,
               capex_cr, cash_from_operations_cr
        FROM derived_metrics
        WHERE UPPER(company_id) = UPPER(?)
        ORDER BY year
    """, (ticker,))


@st.cache_data(ttl=600)
def get_sectors():
    return _query("""
        SELECT s.*, cs.latest_sales, cs.latest_net_profit,
               cs.latest_roe_pct, cs.latest_net_profit_margin_pct,
               cs.latest_fcf_cr, cs.revenue_cagr_pct,
               cs.latest_debt_to_equity
        FROM sectors s
        LEFT JOIN company_summary cs ON s.company_id = cs.company_id
        ORDER BY s.broad_sector, s.company_id
    """)


@st.cache_data(ttl=600)
def get_peers(group_name):
    return _query("""
        SELECT * FROM peer_percentiles
        WHERE peer_group_name = ?
        ORDER BY company_id, metric
    """, (group_name,))


@st.cache_data(ttl=600)
def get_valuation(ticker):
    if VALUATION_PATH.exists():
        df = pd.read_excel(VALUATION_PATH)
        if "company_id" in df.columns:
            return df[
                df["company_id"].astype(str).str.upper()
                == str(ticker).upper()
            ].copy()
    return pd.DataFrame()
