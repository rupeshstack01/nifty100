from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

DB_PATH = Path("data/processed/nifty100.db")
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "cashflow_intelligence.xlsx"
DISTRESS_FILE = OUTPUT_DIR / "distress_alerts.csv"


def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        financial = pd.read_sql_query(
            """
            SELECT
                company_id, year, sales, operating_profit, net_profit,
                operating_activity, investing_activity,
                financing_activity, net_cash_flow, borrowings,
                free_cash_flow_cr, capex_cr
            FROM financial_panel
            ORDER BY company_id, year
            """,
            conn,
        )

        sectors = pd.read_sql_query(
            """
            SELECT company_id, broad_sector
            FROM sectors
            """,
            conn,
        )

        summary = pd.read_sql_query(
            """
            SELECT company_id, latest_net_profit
            FROM company_summary
            """,
            conn,
        )


    # Keep one sector mapping per company.

    # Normalize company IDs to prevent whitespace mismatches.
    for frame in (financial, sectors, summary):
        frame["company_id"] = frame["company_id"].astype(str).str.strip()

    # Normalize sector names and keep one mapping per company.
    sectors["broad_sector"] = sectors["broad_sector"].astype("string").str.strip()
    sectors = sectors.drop_duplicates("company_id").copy()

    # Fill the two known missing sector mappings.
    sector_fallbacks = {
        "ULTRACEMCO": "Materials",
        "UNIONBANK": "Financials",
    }

    for company_id, sector in sector_fallbacks.items():
        mask = sectors["company_id"].eq(company_id)
        if mask.any():
            sectors.loc[mask, "broad_sector"] = sector
        else:
            sectors = pd.concat(
                [
                    sectors,
                    pd.DataFrame(
                        [{"company_id": company_id, "broad_sector": sector}]
                    ),
                ],
                ignore_index=True,
            )

    return financial, sectors, summary




def safe_ratio(numerator, denominator):
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


def classify_cfo_quality(ratio):
    if pd.isna(ratio):
        return "Insufficient Data"
    if ratio > 1.0:
        return "High Quality"
    if ratio >= 0.5:
        return "Moderate"
    return "Accrual Risk"


def classify_capex_intensity(value):
    if pd.isna(value):
        return "Insufficient Data"
    if value < 3:
        return "Asset Light"
    if value <= 8:
        return "Moderate"
    return "Capital Intensive"


def free_cash_flow(operating_activity, investing_activity):
    if operating_activity is None and investing_activity is None:
        return None
    return (operating_activity or 0) + (investing_activity or 0)


def cfo_pat_ratio(cfo, pat):
    if pat is None or pat == 0:
        return None
    if cfo is None:
        return None
    return cfo / pat


def cfo_quality_label(ratio):
    if ratio is None or pd.isna(ratio):
        return None
    if ratio > 1.0:
        return "High Quality"
    if ratio >= 0.5:
        return "Moderate"
    return "Accrual Risk"


def capex_intensity(investing_activity, sales):
    if sales is None or pd.isna(sales) or sales == 0:
        return None
    if investing_activity is None or pd.isna(investing_activity):
        investing_activity = 0
    return abs(investing_activity) / sales * 100


def capex_intensity_label(value):
    if value is None or pd.isna(value):
        return None
    if value < 3:
        return "Asset Light"
    if value <= 8:
        return "Moderate"
    return "Capital Intensive"


def fcf_conversion_rate(free_cash_flow_value, operating_profit):
    if free_cash_flow_value is None or operating_profit is None:
        return None
    if pd.isna(free_cash_flow_value) or pd.isna(operating_profit) or operating_profit == 0:
        return None
    return free_cash_flow_value / operating_profit * 100


def sign(value):
    if value is None or pd.isna(value):
        return "0"
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return "0"


def classify_capital_allocation(row):
    cfo = row["operating_activity"]
    cfi = row["investing_activity"]
    cff = row["financing_activity"]

    if pd.isna(cfo) or pd.isna(cfi) or pd.isna(cff):
        return "Unclassified"

    if cfo < 0 and cff > 0:
        return "Distress Signal"
    if cfo > 0 and cfi < 0 and cff < 0:
        return "Deleveraging / Shareholder Returns"
    if cfo > 0 and cfi < 0 and cff > 0:
        return "Growth Investment"
    if cfo > 0 and cfi >= 0 and cff < 0:
        return "Cash Generation / Debt Reduction"
    if cfo > 0 and cfi >= 0 and cff > 0:
        return "Cash Accumulation / External Funding"
    if cfo < 0 and cfi < 0 and cff > 0:
        return "Externally Funded Investment"
    if cfo < 0 and cff <= 0:
        return "Cash Burn"
    return "Mixed / Unclassified"


def build_intelligence(financial, sectors, summary):
    df = financial.merge(sectors, on="company_id", how="left")
    df = df.sort_values(["company_id", "year"]).reset_index(drop=True)

    # CFO/PAT is not meaningful when PAT is zero or missing.
    df["cfo_pat_ratio"] = df.apply(
        lambda r: safe_ratio(r["operating_activity"], r["net_profit"]),
        axis=1,
    )

    # Use the mean of up to five available annual ratios.
    df["cfo_quality_score"] = (
        df.groupby("company_id")["cfo_pat_ratio"]
        .transform(lambda s: s.tail(5).mean())
    )
    df["cfo_quality_label"] = df["cfo_quality_score"].apply(
        classify_cfo_quality
    )

    # Sprint specification: absolute investing activity / sales.
    df["capex_intensity_pct"] = df.apply(
        lambda r: (
            abs(r["investing_activity"]) / r["sales"] * 100
            if pd.notna(r["investing_activity"])
            and pd.notna(r["sales"])
            and r["sales"] > 0
            else np.nan
        ),
        axis=1,
    )

    # Latest-year snapshot.
    latest = (
        df.sort_values(["company_id", "year"])
        .groupby("company_id", as_index=False)
        .tail(1)
        .copy()
    )

    latest["capex_label"] = latest["capex_intensity_pct"].apply(
        classify_capex_intensity
    )

    # Year-over-year borrowing change.
    df["previous_borrowings"] = (
        df.groupby("company_id")["borrowings"].shift(1)
    )
    latest_borrowings = df[
        ["company_id", "year", "borrowings", "previous_borrowings"]
    ]
    latest = latest.merge(
        latest_borrowings,
        on=["company_id", "year", "borrowings"],
        how="left",
    )

    latest["distress_flag"] = (
        latest["operating_activity"].lt(0)
        & latest["financing_activity"].gt(0)
    )
    latest["deleveraging_flag"] = (
        latest["financing_activity"].lt(0)
        & latest["borrowings"].lt(latest["previous_borrowings"])
    )

    latest["capital_allocation_label"] = latest.apply(
        classify_capital_allocation, axis=1
    )

    # Five-year FCF CAGR is only calculated when both endpoint values
    # are positive and five years apart.
    def calculate_fcf_cagr(group):
        group = group.sort_values("year")
        if group.empty:
            return np.nan

        end_year = group["year"].max()
        start_year = end_year - 5
        start_rows = group[group["year"] == start_year]
        end_rows = group[group["year"] == end_year]

        if start_rows.empty or end_rows.empty:
            return np.nan

        start_value = start_rows.iloc[-1]["free_cash_flow_cr"]
        end_value = end_rows.iloc[-1]["free_cash_flow_cr"]

        if (
            pd.isna(start_value)
            or pd.isna(end_value)
            or start_value <= 0
            or end_value <= 0
        ):
            return np.nan

        return ((end_value / start_value) ** (1 / 5) - 1) * 100

    fcf_cagr = (
        df.groupby("company_id")
        .apply(calculate_fcf_cagr, include_groups=False)
        .rename("fcf_cagr_5yr")
        .reset_index()
    )
    latest = latest.merge(fcf_cagr, on="company_id", how="left")

        # FCF conversion requires free cash flow and operating profit.
    latest["fcf_conversion_pct"] = latest.apply(
        lambda r: (
            r["free_cash_flow_cr"] / r["operating_profit"] * 100
            if pd.notna(r["free_cash_flow_cr"])
            and pd.notna(r["operating_profit"])
            and r["operating_profit"] != 0
            else np.nan
        ),
        axis=1,
    )

    latest = latest.merge(summary, on="company_id", how="left")

    output_columns = [
        "company_id",
        "broad_sector",
        "cfo_quality_score",
        "cfo_quality_label",
        "capex_intensity_pct",
        "capex_label",
        "fcf_cagr_5yr",
        "fcf_conversion_pct",
        "distress_flag",
        "deleveraging_flag",
        "capital_allocation_label",
    ]

    result = latest[output_columns].rename(
        columns={"broad_sector": "sector"}
    )
    result = result.sort_values("company_id").reset_index(drop=True)

    distress = latest[latest["distress_flag"]].copy()
    distress = distress[
        [
            "company_id",
            "year",
            "operating_activity",
            "financing_activity",
            "net_profit",
        ]
    ].rename(
        columns={
            "operating_activity": "cfo_cr",
            "financing_activity": "cff_cr",
            "net_profit": "latest_net_profit_cr",
        }
    )

    return result, distress


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    financial, sectors, summary = load_data()
    result, distress = build_intelligence(financial, sectors, summary)

    result.to_excel(OUTPUT_FILE, index=False)
    distress.to_csv(DISTRESS_FILE, index=False)

    print("=== CASH FLOW INTELLIGENCE ===")
    print(f"Companies: {result['company_id'].nunique()}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Distress alerts: {len(distress)}")
    print(f"Distress output: {DISTRESS_FILE}")
    print("\nCFO quality:")
    print(result["cfo_quality_label"].value_counts(dropna=False).to_string())
    print("\nCapEx intensity:")
    print(result["capex_label"].value_counts(dropna=False).to_string())
    print("\nCapital allocation:")
    print(
        result["capital_allocation_label"]
        .value_counts(dropna=False)
        .to_string()
    )


if __name__ == "__main__":
    main()
