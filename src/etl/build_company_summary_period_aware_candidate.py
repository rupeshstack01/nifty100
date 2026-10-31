from pathlib import Path
import re

import numpy as np
import pandas as pd

INPUT_PATH = Path(
    "/tmp/nifty100_period_aware_test/analytical/"
    "derived_metrics_period_aware_candidate.csv"
)
OUTPUT_PATH = Path(
    "/tmp/nifty100_period_aware_test/analytical/"
    "company_summary_period_aware_candidate.csv"
)


def safe_mean(series):
    return pd.to_numeric(series, errors="coerce").mean()


def calculate_cagr(first_value, last_value, years):
    if (
        pd.isna(first_value) or pd.isna(last_value)
        or pd.isna(years) or years <= 0
        or first_value <= 0 or last_value <= 0
    ):
        return np.nan
    return ((last_value / first_value) ** (1 / years) - 1) * 100


def annual_period_info(value):
    """Return (fiscal-year-end month, year) for dated annual periods."""
    if pd.isna(value):
        return None, None
    match = re.fullmatch(
        r"(mar|sep|dec)\s+(\d{4})",
        str(value).strip().lower()
    )
    if not match:
        return None, None
    month = {"mar": 3, "sep": 9, "dec": 12}[match.group(1)]
    return month, int(match.group(2))


def summarize_company(group, company_id):
    group = group.copy()
    group["year"] = pd.to_numeric(group["year"], errors="coerce")
    group["canonical_reporting_period"] = (
        group["canonical_reporting_period"]
        .astype("string").str.strip().str.lower()
    )

    parsed = group["canonical_reporting_period"].map(annual_period_info)
    group["_fiscal_month"] = parsed.map(lambda x: x[0])
    group["_period_year"] = parsed.map(lambda x: x[1])

    # Use the company's most common dated annual year-end convention.
    dated = group[group["_fiscal_month"].notna()].copy()
    if dated.empty:
        annual = dated
        fiscal_month = np.nan
    else:
        month_counts = dated["_fiscal_month"].value_counts()
        fiscal_month = int(month_counts.index[0])
        annual = dated[dated["_fiscal_month"].eq(fiscal_month)].copy()

    # A duplicated fiscal year is not silently resolved.
    annual = annual.dropna(subset=["_period_year"])
    duplicate_years = annual["_period_year"].duplicated(keep=False)
    duplicate_year_count = int(duplicate_years.sum())
    annual = annual.loc[~duplicate_years].sort_values("_period_year")

    first = annual.iloc[0] if not annual.empty else None
    latest_annual = annual.iloc[-1] if not annual.empty else None

    # Latest available means the latest dated record, or TTM when present.
    dated_available = group[group["_period_year"].notna()].copy()
    dated_available = dated_available.sort_values("_period_year")
    ttm = group[group["canonical_reporting_period"].eq("ttm")]

    if not ttm.empty:
        latest_available = ttm.iloc[-1]
    elif not dated_available.empty:
        latest_available = dated_available.iloc[-1]
    else:
        latest_available = group.iloc[-1] if not group.empty else None

    def val(row, column):
        if row is None or column not in row.index:
            return np.nan
        return row[column]

    first_year = val(first, "_period_year")
    latest_year = val(latest_annual, "_period_year")
    span = (
        latest_year - first_year
        if pd.notna(first_year) and pd.notna(latest_year)
        else np.nan
    )

    revenue_cagr = calculate_cagr(
        val(first, "profitandloss_sales"),
        val(latest_annual, "profitandloss_sales"),
        span,
    )
    profit_cagr = calculate_cagr(
        val(first, "profitandloss_net_profit"),
        val(latest_annual, "profitandloss_net_profit"),
        span,
    )

    capital = val(latest_annual, "balancesheet_equity_capital")
    reserves = val(latest_annual, "balancesheet_reserves")
    equity = (
        capital + reserves
        if pd.notna(capital) and pd.notna(reserves)
        else np.nan
    )

    return {
        "company_id": company_id,
        "fiscal_year_end_month": fiscal_month,
        "first_annual_reporting_period": val(first, "reporting_period"),
        "latest_annual_reporting_period": val(
            latest_annual, "reporting_period"
        ),
        "latest_available_reporting_period": val(
            latest_available, "reporting_period"
        ),
        "latest_available_year": val(latest_available, "year"),
        "latest_available_sales": val(
            latest_available, "profitandloss_sales"
        ),
        "latest_available_net_profit": val(
            latest_available, "profitandloss_net_profit"
        ),
        "first_annual_year": first_year,
        "latest_annual_year": latest_year,
        "annual_records_used": len(annual),
        "duplicate_annual_year_rows_excluded": duplicate_year_count,
        "latest_annual_sales": val(
            latest_annual, "profitandloss_sales"
        ),
        "latest_annual_net_profit": val(
            latest_annual, "profitandloss_net_profit"
        ),
        "latest_annual_total_assets": val(
            latest_annual, "balancesheet_total_assets"
        ),
        "latest_annual_total_debt_cr": val(
            latest_annual, "financial_ratios_total_debt_cr"
        ),
        "latest_annual_equity": equity,
        "latest_annual_net_profit_margin_pct": val(
            latest_annual, "calculated_net_profit_margin_pct"
        ),
        "latest_annual_opm_pct": val(
            latest_annual, "calculated_opm_pct"
        ),
        "latest_annual_roe_pct": val(
            latest_annual, "calculated_roe_pct"
        ),
        "latest_annual_debt_to_equity": val(
            latest_annual, "calculated_debt_to_equity"
        ),
        "latest_annual_asset_turnover": val(
            latest_annual, "calculated_asset_turnover"
        ),
        "latest_annual_fcf_cr": val(
            latest_annual, "calculated_fcf_cr"
        ),
        "latest_annual_net_cash_flow": val(
            latest_annual, "cashflow_net_cash_flow"
        ),
        "revenue_cagr_pct": revenue_cagr,
        "net_profit_cagr_pct": profit_cagr,
        "latest_annual_revenue_growth_pct": val(
            latest_annual, "revenue_growth_pct"
        ),
        "latest_annual_net_profit_growth_pct": val(
            latest_annual, "net_profit_growth_pct"
        ),
        "avg_annual_net_profit_margin_pct": safe_mean(
            annual["calculated_net_profit_margin_pct"]
        ) if not annual.empty else np.nan,
        "avg_annual_roe_pct": safe_mean(
            annual["calculated_roe_pct"]
        ) if not annual.empty else np.nan,
        "avg_annual_debt_to_equity": safe_mean(
            annual["calculated_debt_to_equity"]
        ) if not annual.empty else np.nan,
        "avg_annual_asset_turnover": safe_mean(
            annual["calculated_asset_turnover"]
        ) if not annual.empty else np.nan,
        "avg_annual_fcf_cr": safe_mean(
            annual["calculated_fcf_cr"]
        ) if not annual.empty else np.nan,
        "period_records": len(group),
        "periods_needing_review": int(
            group.get(
                "panel_needs_review",
                pd.Series(False, index=group.index)
            ).fillna(False).astype(bool).sum()
        ),
    }


def main():
    df = pd.read_csv(INPUT_PATH)
    required = [
        "company_id", "year", "reporting_period",
        "canonical_reporting_period", "profitandloss_sales",
        "profitandloss_net_profit", "balancesheet_total_assets",
        "balancesheet_equity_capital", "balancesheet_reserves",
        "financial_ratios_total_debt_cr",
        "calculated_net_profit_margin_pct", "calculated_opm_pct",
        "calculated_roe_pct", "calculated_debt_to_equity",
        "calculated_asset_turnover", "calculated_fcf_cr",
        "cashflow_net_cash_flow", "revenue_growth_pct",
        "net_profit_growth_pct",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing: {missing}")

    df["company_id"] = df["company_id"].astype("string").str.strip()
    summary = pd.DataFrame([
        summarize_company(group, company_id)
        for company_id, group in df.groupby("company_id", sort=True)
    ])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_PATH, index=False)

    print(f"Input rows: {len(df)}")
    print(f"Companies: {df['company_id'].nunique()}")
    print(f"Summary rows: {len(summary)}")
    print(f"Duplicate company keys: {summary['company_id'].duplicated().sum()}")
    print(f"Companies without annual history: {summary['latest_annual_year'].isna().sum()}")
    print(f"Companies with no revenue CAGR: {summary['revenue_cagr_pct'].isna().sum()}")
    print(f"Companies with no net-profit CAGR: {summary['net_profit_cagr_pct'].isna().sum()}")
    print(f"Saved: {OUTPUT_PATH}")

    print("\nSIEMENS and VBL:")
    cols = [
        "company_id", "fiscal_year_end_month",
        "latest_annual_reporting_period",
        "latest_available_reporting_period",
        "latest_annual_sales", "latest_available_sales",
        "revenue_cagr_pct", "net_profit_cagr_pct",
        "annual_records_used",
    ]
    print(summary.loc[
        summary["company_id"].isin(["SIEMENS", "VBL"]), cols
    ].to_string(index=False))


if __name__ == "__main__":
    main()
