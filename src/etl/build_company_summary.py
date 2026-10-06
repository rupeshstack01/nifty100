from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path(
    "data/processed/analytical/derived_metrics.csv"
)

OUTPUT_DIR = Path(
    "data/processed/analytical"
)

OUTPUT_PATH = (
    OUTPUT_DIR / "company_summary.csv"
)


def safe_mean(series):
    return series.dropna().mean()


def safe_median(series):
    return series.dropna().median()


def calculate_cagr(first_value, last_value, years):
    """
    Calculate CAGR.

    Returns NaN when the values cannot produce
    a meaningful CAGR.
    """

    if (
        pd.isna(first_value)
        or pd.isna(last_value)
        or pd.isna(years)
        or years <= 0
        or first_value <= 0
        or last_value <= 0
    ):
        return np.nan

    return (
        (last_value / first_value) ** (1 / years) - 1
    ) * 100


def summarize_company(group, company_id):
    """
    Create one analytical summary row for one company.
    """

    group = group.sort_values("year").copy()

    first_row = group.iloc[0]
    latest_row = group.iloc[-1]

    first_year = first_row["year"]
    latest_year = latest_row["year"]

    year_span = latest_year - first_year

    revenue_cagr = calculate_cagr(
        first_row["sales"],
        latest_row["sales"],
        year_span,
    )

    profit_cagr = calculate_cagr(
        first_row["net_profit"],
        latest_row["net_profit"],
        year_span,
    )

    return pd.Series(
        {
            "company_id": company_id,

            "first_available_year": first_year,
            "latest_available_year": latest_year,
            "years_available": len(group),

            # Latest financial position
            "latest_sales": latest_row["sales"],
            "latest_net_profit": latest_row["net_profit"],
            "latest_total_assets": latest_row["total_assets"],
            "latest_total_debt": latest_row["total_debt_cr"],
            "latest_equity": (
                latest_row["equity_capital"]
                + latest_row["reserves"]
            ),

            # Latest profitability
            "latest_net_profit_margin_pct": (
                latest_row[
                    "calculated_net_profit_margin_pct"
                ]
            ),

            "latest_opm_pct": (
                latest_row[
                    "calculated_opm_pct"
                ]
            ),

            "latest_roe_pct": (
                latest_row[
                    "calculated_roe_pct"
                ]
            ),

            # Latest leverage / efficiency
            "latest_debt_to_equity": (
                latest_row[
                    "calculated_debt_to_equity"
                ]
            ),

            "latest_asset_turnover": (
                latest_row[
                    "calculated_asset_turnover"
                ]
            ),

            # Latest cash flow
            "latest_fcf_cr": (
                latest_row[
                    "calculated_fcf_cr"
                ]
            ),

            "latest_net_cash_flow": (
                latest_row[
                    "net_cash_flow"
                ]
            ),

            # Growth
            "revenue_cagr_pct": revenue_cagr,
            "net_profit_cagr_pct": profit_cagr,

            "latest_revenue_growth_pct": (
                latest_row[
                    "revenue_growth_pct"
                ]
            ),

            "latest_net_profit_growth_pct": (
                latest_row[
                    "net_profit_growth_pct"
                ]
            ),

            # Historical averages
            "avg_net_profit_margin_pct": safe_mean(
                group[
                    "calculated_net_profit_margin_pct"
                ]
            ),

            "avg_roe_pct": safe_mean(
                group[
                    "calculated_roe_pct"
                ]
            ),

            "avg_debt_to_equity": safe_mean(
                group[
                    "calculated_debt_to_equity"
                ]
            ),

            "avg_asset_turnover": safe_mean(
                group[
                    "calculated_asset_turnover"
                ]
            ),

            "avg_fcf_cr": safe_mean(
                group[
                    "calculated_fcf_cr"
                ]
            ),

            # Data quality / completeness
            "missing_values_total": int(
                group.isna().sum().sum()
            ),

            "records_with_missing_values": int(
                group.isna()
                .any(axis=1)
                .sum()
            ),
        }
    )


def main():

    print("=" * 70)
    print("BUILDING COMPANY-LEVEL FINANCIAL SUMMARY")
    print("=" * 70)

    # ---------------------------------------------------------
    # Load derived analytical dataset
    # ---------------------------------------------------------

    df = pd.read_csv(INPUT_PATH)

    print(
        f"\nInput records: {len(df)}"
    )

    print(
        f"Input companies: "
        f"{df['company_id'].nunique()}"
    )

    # ---------------------------------------------------------
    # Normalize keys
    # ---------------------------------------------------------

    df["company_id"] = (
        df["company_id"]
        .astype(str)
        .str.strip()
    )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Sort
    # ---------------------------------------------------------

    df = df.sort_values(
        ["company_id", "year"]
    )

    # ---------------------------------------------------------
    # Build one summary row per company
    # ---------------------------------------------------------

    summary_rows = []

    for company_id, company_data in df.groupby(
     "company_id",
        sort=True,
    ):
        company_summary = summarize_company(
            company_data,
            company_id,
        )

        summary_rows.append(
            company_summary
        )

    summary = pd.DataFrame(
        summary_rows
    )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    # ---------------------------------------------------------
    # Output verification
    # ---------------------------------------------------------

    print(
        f"\nSaved: {OUTPUT_PATH}"
    )

    print(
        f"Summary rows: {len(summary)}"
    )

    print(
        f"Summary columns: {len(summary.columns)}"
    )

    print(
        f"Unique companies: "
        f"{summary['company_id'].nunique()}"
    )

    print("\nFirst 10 companies:")

    print(
        summary[
            [
                "company_id",
                "first_available_year",
                "latest_available_year",
                "years_available",
                "latest_sales",
                "latest_net_profit",
                "latest_roe_pct",
                "latest_debt_to_equity",
                "revenue_cagr_pct",
                "net_profit_cagr_pct",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
