from pathlib import Path
import os

import numpy as np
import pandas as pd


BASE_DIR = Path(
    os.environ.get(
        "DERIVED_METRICS_CANDIDATE_DIR",
        "/tmp/nifty100_period_aware_test/analytical",
    )
)

INPUT_PATH = BASE_DIR / "financial_panel.csv"
REVIEW_PATH = BASE_DIR / "financial_panel_review.csv"
OUTPUT_PATH = BASE_DIR / "derived_metrics_period_aware_candidate.csv"


def safe_divide(numerator, denominator):
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    result = numerator / denominator
    return result.where(denominator.notna() & denominator.ne(0))


def normalize_period(series):
    return series.astype("string").str.strip().str.lower()


def calculate_annual_growth(df, column):
    """Calculate growth between consecutive full-year periods
    for the same company and reporting month.
    Excludes partial periods, TTM, and other non-month-year labels.
    """
    result = pd.Series(np.nan, index=df.index, dtype="float64")

    labels = (
        df["canonical_reporting_period"]
        .astype("string")
        .str.strip()
        .str.lower()
    )
    month_pattern = (
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec) \d{4}"
    )
    annual_mask = labels.str.fullmatch(month_pattern, na=False)

    annual = df.loc[
        annual_mask,
        ["company_id", "canonical_reporting_period", column],
    ].copy()

    if annual.empty:
        return result

    annual["_period_month"] = (
        annual["canonical_reporting_period"].str[:3].str.lower()
    )
    annual["_period_year"] = pd.to_numeric(
        annual["canonical_reporting_period"].str.extract(
            r"(\d{4})", expand=False
        ),
        errors="coerce",
    )
    annual["_value"] = pd.to_numeric(annual[column], errors="coerce")
    annual = annual.sort_values(
        ["company_id", "_period_month", "_period_year"]
    )

    groups = annual.groupby(["company_id", "_period_month"], sort=False)
    annual["_previous_value"] = groups["_value"].shift(1)
    annual["_previous_year"] = groups["_period_year"].shift(1)

    valid = (
        annual["_period_year"].sub(annual["_previous_year"]).eq(1)
        & annual["_previous_value"].notna()
        & annual["_previous_value"].ne(0)
        & annual["_value"].notna()
    )

    growth = (
        annual["_value"].div(annual["_previous_value"]).sub(1).mul(100)
    )
    result.loc[annual.index] = growth.where(valid)
    return result


def main():
    print("=" * 70)
    print("PERIOD-AWARE DERIVED METRICS CANDIDATE")
    print("=" * 70)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Panel not found: {INPUT_PATH}")
    if not REVIEW_PATH.exists():
        raise FileNotFoundError(f"Review file not found: {REVIEW_PATH}")

    df = pd.read_csv(INPUT_PATH)
    review = pd.read_csv(REVIEW_PATH)

    required_panel = {
        "company_id", "year", "reporting_period",
        "canonical_reporting_period",
    }
    required_review = {
        "company_id", "year", "canonical_reporting_period", "needs_review",
    }

    missing_panel = required_panel - set(df.columns)
    missing_review = required_review - set(review.columns)

    if missing_panel:
        raise ValueError(f"Panel missing required columns: {sorted(missing_panel)}")
    if missing_review:
        raise ValueError(f"Review file missing required columns: {sorted(missing_review)}")

    df = df.reset_index(drop=True)
    df["company_id"] = df["company_id"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["canonical_reporting_period"] = normalize_period(
        df["canonical_reporting_period"]
    )

    keys = ["company_id", "year", "canonical_reporting_period"]

    review["company_id"] = review["company_id"].astype(str).str.strip()
    review["year"] = pd.to_numeric(
        review["year"], errors="coerce"
    ).astype("Int64")
    review["canonical_reporting_period"] = normalize_period(
        review["canonical_reporting_period"]
    )

    if df.duplicated(keys).any():
        raise ValueError("Panel contains duplicate company-period keys.")
    if review.duplicated(keys).any():
        raise ValueError("Review file contains duplicate company-period keys.")

    print("Input rows:", len(df))

    # Growth is limited to consecutive annual March periods.
    df["revenue_growth_pct"] = calculate_annual_growth(
        df, "profitandloss_sales"
    )
    df["net_profit_growth_pct"] = calculate_annual_growth(
        df, "profitandloss_net_profit"
    )

    # Profitability metrics
    sales = pd.to_numeric(df["profitandloss_sales"], errors="coerce")
    net_profit = pd.to_numeric(df["profitandloss_net_profit"], errors="coerce")
    operating_profit = pd.to_numeric(
        df["profitandloss_operating_profit"], errors="coerce"
    )

    df["calculated_net_profit_margin_pct"] = safe_divide(
        net_profit, sales
    ) * 100
    df["calculated_opm_pct"] = safe_divide(
        operating_profit, sales
    ) * 100

    # Source-quality checks: preserve source columns; never silently repair them.
    pl_opm = pd.to_numeric(
        df["profitandloss_opm_percentage"], errors="coerce"
    )
    ratios_opm = pd.to_numeric(
        df["financial_ratios_operating_profit_margin_pct"],
        errors="coerce",
    )
    df["opm_source_disagreement"] = (
        pl_opm.notna()
        & ratios_opm.notna()
        & ((pl_opm - ratios_opm).abs() > 0.01)
    )
    opm_source = pl_opm.combine_first(ratios_opm)
    opm_calculated = df["calculated_opm_pct"]

    df["opm_validation_status"] = "MISSING_SOURCE"
    invalid_opm_inputs = (
        sales.isna() | sales.eq(0) | operating_profit.isna()
    )
    df.loc[invalid_opm_inputs, "opm_validation_status"] = "INVALID_INPUT"

    comparable_opm = (
        opm_source.notna()
        & opm_calculated.notna()
        & ~invalid_opm_inputs
    )
    opm_diff = (opm_source - opm_calculated).abs()
    df.loc[comparable_opm & opm_diff.le(0.5),
           "opm_validation_status"] = "MATCH"
    df.loc[comparable_opm & opm_diff.gt(0.5),
           "opm_validation_status"] = "MISMATCH"

    # Reported OPM versus calculated OPM mismatch flag.
    df["opm_calculated_mismatch"] = (
        df["opm_validation_status"].eq("MISMATCH")
    )

    # Balance sheet metrics
    equity = pd.to_numeric(df["balancesheet_equity_capital"], errors="coerce")
    reserves = pd.to_numeric(df["balancesheet_reserves"], errors="coerce")
    total_debt = pd.to_numeric(df["balancesheet_borrowings"], errors="coerce")
    total_assets = pd.to_numeric(df["balancesheet_total_assets"], errors="coerce")
    total_equity = equity + reserves

    df["calculated_roe_pct"] = safe_divide(net_profit, total_equity) * 100
    df["calculated_debt_to_equity"] = safe_divide(total_debt, total_equity)
    df["calculated_asset_turnover"] = safe_divide(sales, total_assets)

    # Cash flow metrics
    operating_cash_flow = pd.to_numeric(
        df["cashflow_operating_activity"], errors="coerce"
    )
    net_cash_flow = pd.to_numeric(df["cashflow_net_cash_flow"], errors="coerce")
    capex = pd.to_numeric(df["financial_ratios_capex_cr"], errors="coerce")

    # Conventional capex-based FCF: CFO minus positive capex.
    df["calculated_fcf_cr"] = operating_cash_flow - capex

    # Preserve the source dataset's reconciliation separately:
    # CFO plus signed investing activity.
    investing_cash_flow = pd.to_numeric(
        df["cashflow_investing_activity"], errors="coerce"
    )
    df["calculated_fcf_from_cashflow_statement_cr"] = (
        operating_cash_flow + investing_cash_flow
    )

    source_fcf = pd.to_numeric(
        df["financial_ratios_free_cash_flow_cr"], errors="coerce"
    )

    # Compare source FCF with conventional capex-based FCF.
    df["fcf_validation_status"] = "MISSING_SOURCE"
    invalid_fcf_inputs = operating_cash_flow.isna() | capex.isna()
    df.loc[invalid_fcf_inputs, "fcf_validation_status"] = "INVALID_INPUT"

    comparable_fcf = (
        source_fcf.notna()
        & df["calculated_fcf_cr"].notna()
        & ~invalid_fcf_inputs
    )
    fcf_diff = (source_fcf - df["calculated_fcf_cr"]).abs()
    df.loc[comparable_fcf & fcf_diff.le(0.5),
           "fcf_validation_status"] = "MATCH"
    df.loc[comparable_fcf & fcf_diff.gt(0.5),
           "fcf_validation_status"] = "MISMATCH"

    # Separately validate whether source FCF reconciles to CFO + signed
    # investing activity. This does not redefine conventional FCF.
    df["source_fcf_reconciliation_status"] = "MISSING_SOURCE"
    invalid_reconciliation_inputs = (
        operating_cash_flow.isna() | investing_cash_flow.isna()
    )
    df.loc[
        invalid_reconciliation_inputs,
        "source_fcf_reconciliation_status"
    ] = "INVALID_INPUT"

    comparable_reconciliation = (
        source_fcf.notna()
        & df["calculated_fcf_from_cashflow_statement_cr"].notna()
        & ~invalid_reconciliation_inputs
    )
    reconciliation_diff = (
        source_fcf - df["calculated_fcf_from_cashflow_statement_cr"]
    ).abs()
    df.loc[
        comparable_reconciliation & reconciliation_diff.le(0.5),
        "source_fcf_reconciliation_status"
    ] = "MATCH"
    df.loc[
        comparable_reconciliation & reconciliation_diff.gt(0.5),
        "source_fcf_reconciliation_status"
    ] = "MISMATCH"
    df["net_cash_flow_margin_pct"] = safe_divide(
        net_cash_flow, sales
    ) * 100

    # Attach review flags using the full reporting-period key.
    review = review[keys + ["needs_review"]].copy()
    df = df.merge(
        review,
        on=keys,
        how="left",
        validate="one_to_one",
        indicator="_review_match",
    )

    unmatched = int(df["_review_match"].ne("both").sum())
    if unmatched:
        raise ValueError(
            f"{unmatched} panel rows did not match the review file."
        )

    # Include metric validation failures in the overall review flag.
    metric_validation_status_columns = [
        "opm_validation_status",
        "fcf_validation_status",
        "source_fcf_reconciliation_status",
    ]

    missing_status_columns = (
        set(metric_validation_status_columns) - set(df.columns)
    )
    if missing_status_columns:
        raise ValueError(
            "Missing validation status columns: "
            f"{sorted(missing_status_columns)}"
        )

    review_statuses = {"MISMATCH", "INVALID_INPUT", "MISSING_SOURCE"}
    df["metric_validation_needs_review"] = (
        df[metric_validation_status_columns]
        .isin(review_statuses)
        .any(axis=1)
        | df["opm_source_disagreement"].fillna(True).astype(bool)
    )

    df["derived_metrics_needs_review"] = (
        df["needs_review"].fillna(True).astype(bool)
        | df["metric_validation_needs_review"]
    )
    df["review_flag_missing"] = df["needs_review"].isna()
    df = df.drop(columns=["_review_match"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    annual_mask = df["canonical_reporting_period"].astype("string").str.strip().str.lower().str.fullmatch(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec) \d{4}", na=False
    )

    print("Saved:", OUTPUT_PATH)
    print("Output rows:", len(df))
    print("Annual March rows:", int(annual_mask.sum()))
    print("Non-annual rows:", int((~annual_mask).sum()))
    print("Rows needing review:", int(df["derived_metrics_needs_review"].sum()))
    print("Missing review flags:", int(df["review_flag_missing"].sum()))
    print("Revenue growth populated:", int(df["revenue_growth_pct"].notna().sum()))
    print("Net profit growth populated:", int(df["net_profit_growth_pct"].notna().sum()))
    print("Non-annual rows with growth:", int(
        df.loc[~annual_mask, [
            "revenue_growth_pct", "net_profit_growth_pct"
        ]].notna().any(axis=1).sum()
    ))


if __name__ == "__main__":
    main()
