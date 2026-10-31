
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path("data/processed/analytical/financial_panel.csv")
OUTPUT_DIR = Path("data/processed/analytical")
OUTPUT_PATH = OUTPUT_DIR / "derived_metrics.csv"


def safe_divide(numerator, denominator):
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")

    result = numerator / denominator
    return result.where(denominator.notna() & denominator.ne(0))


def calculate_growth(df, column):
    current = pd.to_numeric(df[column], errors="coerce")
    previous = current.groupby(df["company_id"]).shift(1)

    result = (current / previous - 1) * 100
    return result.where(previous.notna() & previous.ne(0))


def main():
    print("=" * 70)
    print("BUILDING DERIVED FINANCIAL METRICS")
    print("=" * 70)

    df = pd.read_csv(INPUT_PATH)
    print(f"\nInput rows: {len(df)}")

    df["company_id"] = df["company_id"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df.sort_values(["company_id", "year"]).reset_index(drop=True)

    # Profit and loss metrics
    sales = pd.to_numeric(df["profitandloss_sales"], errors="coerce")
    net_profit = pd.to_numeric(df["profitandloss_net_profit"], errors="coerce")
    operating_profit = pd.to_numeric(
        df["profitandloss_operating_profit"], errors="coerce"
    )

    df["revenue_growth_pct"] = calculate_growth(
        df, "profitandloss_sales"
    )
    df["net_profit_growth_pct"] = calculate_growth(
        df, "profitandloss_net_profit"
    )

    # Profitability metrics
    df["calculated_net_profit_margin_pct"] = (
        safe_divide(net_profit, sales) * 100
    )
    df["calculated_opm_pct"] = (
        safe_divide(operating_profit, sales) * 100
    )

    # Balance sheet metrics
    equity = pd.to_numeric(
        df["balancesheet_equity_capital"], errors="coerce"
    )
    reserves = pd.to_numeric(
        df["balancesheet_reserves"], errors="coerce"
    )
    total_debt = pd.to_numeric(
        df["balancesheet_borrowings"], errors="coerce"
    )
    total_assets = pd.to_numeric(
        df["balancesheet_total_assets"], errors="coerce"
    )

    total_equity = equity + reserves

    df["calculated_roe_pct"] = (
        safe_divide(net_profit, total_equity) * 100
    )
    df["calculated_debt_to_equity"] = safe_divide(
        total_debt, total_equity
    )
    df["calculated_asset_turnover"] = safe_divide(
        sales, total_assets
    )

    # Cash flow metrics
    operating_cash_flow = pd.to_numeric(
        df["cashflow_operating_activity"], errors="coerce"
    )
    investing_cash_flow = pd.to_numeric(
        df["cashflow_investing_activity"], errors="coerce"
    )
    financing_cash_flow = pd.to_numeric(
        df["cashflow_financing_activity"], errors="coerce"
    )
    net_cash_flow = pd.to_numeric(
        df["cashflow_net_cash_flow"], errors="coerce"
    )

        # Calculate free cash flow using available operating cash flow and CapEx.
    capex = pd.to_numeric(
        df["financial_ratios_capex_cr"],
        errors="coerce",
    )

    df["calculated_fcf_cr"] = operating_cash_flow - capex

    df["net_cash_flow_margin_pct"] = (
        safe_divide(net_cash_flow, sales) * 100
    )

    # Record data-quality context for downstream users.
        # Attach the authoritative review flags from the panel review file.
    REVIEW_PATH = OUTPUT_DIR / "financial_panel_review.csv"

    review = pd.read_csv(
        REVIEW_PATH,
        usecols=["company_id", "year", "needs_review"],
    )

    review["company_id"] = (
        review["company_id"].astype(str).str.strip()
    )
    review["year"] = pd.to_numeric(
        review["year"], errors="coerce"
    ).astype("Int64")

    df = df.drop(columns=["needs_review"], errors="ignore")

    df = df.merge(
        review,
        on=["company_id", "year"],
        how="left",
        validate="one_to_one",
    )

    df["derived_metrics_needs_review"] = (
        df["needs_review"].fillna(True).astype(bool)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Rows: {len(df)}")
    print(
        "Rows needing review: "
        f"{int(df['derived_metrics_needs_review'].sum())}"
    )
    print(
        "Rows with missing sales: "
        f"{int(sales.isna().sum())}"
    )
    print(
        "Rows with missing operating cash flow: "
        f"{int(operating_cash_flow.isna().sum())}"
    )


if __name__ == "__main__":
    main()
