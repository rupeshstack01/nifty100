from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path(
    "data/processed/analytical/financial_panel.csv"
)

OUTPUT_DIR = Path(
    "data/processed/analytical"
)

OUTPUT_PATH = (
    OUTPUT_DIR / "derived_metrics.csv"
)


def safe_divide(numerator, denominator):
    """
    Divide numerator by denominator safely.

    Returns NaN when denominator is zero
    or either value is missing.
    """
    numerator = pd.to_numeric(
        numerator,
        errors="coerce",
    )

    denominator = pd.to_numeric(
        denominator,
        errors="coerce",
    )

    return np.where(
        denominator != 0,
        numerator / denominator,
        np.nan,
    )


def calculate_growth(df, column):
    """
    Calculate year-over-year percentage growth
    within each company.
    """

    previous = (
        df.groupby("company_id")[column]
        .shift(1)
    )

    current = pd.to_numeric(
        df[column],
        errors="coerce",
    )

    previous = pd.to_numeric(
        previous,
        errors="coerce",
    )

    return np.where(
        previous != 0,
        (current / previous - 1) * 100,
        np.nan,
    )


def main():

    print("=" * 70)
    print("BUILDING DERIVED FINANCIAL METRICS")
    print("=" * 70)

    # ---------------------------------------------------------
    # Load analytical panel
    # ---------------------------------------------------------

    df = pd.read_csv(INPUT_PATH)

    print(
        f"\nInput rows: {len(df)}"
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
    ).astype("Int64")

    # ---------------------------------------------------------
    # Sort before calculating year-over-year metrics
    # ---------------------------------------------------------

    df = df.sort_values(
        ["company_id", "year"]
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # Revenue growth
    # ---------------------------------------------------------

    df["revenue_growth_pct"] = (
        calculate_growth(
            df,
            "sales",
        )
    )

    # ---------------------------------------------------------
    # Net profit growth
    # ---------------------------------------------------------

    df["net_profit_growth_pct"] = (
        calculate_growth(
            df,
            "net_profit",
        )
    )

    # ---------------------------------------------------------
    # Calculated Net Profit Margin
    # ---------------------------------------------------------

    df["calculated_net_profit_margin_pct"] = (
        safe_divide(
            df["net_profit"],
            df["sales"],
        ) * 100
    )

    # ---------------------------------------------------------
    # Calculated Operating Profit Margin
    # ---------------------------------------------------------

    df["calculated_opm_pct"] = (
        safe_divide(
            df["operating_profit"],
            df["sales"],
        ) * 100
    )

    # ---------------------------------------------------------
    # Calculated ROE
    # ---------------------------------------------------------

    df["calculated_roe_pct"] = (
        safe_divide(
            df["net_profit"],
            df["equity_capital"] + df["reserves"],
        ) * 100
    )

    # ---------------------------------------------------------
    # Calculated Debt-to-Equity
    # ---------------------------------------------------------

    df["calculated_debt_to_equity"] = (
        safe_divide(
            df["total_debt_cr"],
            df["equity_capital"] + df["reserves"],
        )
    )

    # ---------------------------------------------------------
    # Calculated Asset Turnover
    # ---------------------------------------------------------

    df["calculated_asset_turnover"] = (
        safe_divide(
            df["sales"],
            df["total_assets"],
        )
    )

    # ---------------------------------------------------------
    # Calculated Free Cash Flow
    # ---------------------------------------------------------

    df["calculated_fcf_cr"] = (
        pd.to_numeric(
            df["cash_from_operations_cr"],
            errors="coerce",
        )
        -
        pd.to_numeric(
            df["capex_cr"],
            errors="coerce",
        )
    )

    # ---------------------------------------------------------
    # Net Cash Flow Margin
    # ---------------------------------------------------------

    df["net_cash_flow_margin_pct"] = (
        safe_divide(
            df["net_cash_flow"],
            df["sales"],
        ) * 100
    )

    # ---------------------------------------------------------
    # Save derived metrics
    # ---------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print(
        f"\nSaved: {OUTPUT_PATH}"
    )

    print(
        f"Rows: {len(df)}"
    )

    print(
        f"Columns: {len(df.columns)}"
    )

    derived_columns = [
        "revenue_growth_pct",
        "net_profit_growth_pct",
        "calculated_net_profit_margin_pct",
        "calculated_opm_pct",
        "calculated_roe_pct",
        "calculated_debt_to_equity",
        "calculated_asset_turnover",
        "calculated_fcf_cr",
        "net_cash_flow_margin_pct",
    ]

    print("\nDerived metrics:")

    for column in derived_columns:
        print(
            f"{column}: "
            f"{df[column].notna().sum()} "
            f"non-null values"
        )


if __name__ == "__main__":
    main()

