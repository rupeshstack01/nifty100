from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path("/tmp/nifty100_period_aware_test/analytical")
INPUT_PATH = BASE / "derived_metrics_period_aware_candidate.csv"
OUTPUT_PATH = BASE / "derived_metrics_validation_period_aware_candidate.csv"


COMPARISONS = [
    ("calculated_net_profit_margin_pct",
     "financial_ratios_net_profit_margin_pct", 0.05),
    ("calculated_opm_pct",
     "financial_ratios_operating_profit_margin_pct", 0.5),
    ("calculated_roe_pct",
     "financial_ratios_return_on_equity_pct", 0.05),
    ("calculated_debt_to_equity",
     "financial_ratios_debt_to_equity", 0.0002),
    ("calculated_asset_turnover",
     "financial_ratios_asset_turnover", 0.0002),
    ("calculated_fcf_cr",
     "financial_ratios_free_cash_flow_cr", 0.5),
]


def compare_columns(df, calculated, source, tolerance):
    calc = pd.to_numeric(df[calculated], errors="coerce")
    src = pd.to_numeric(df[source], errors="coerce")
    valid = calc.notna() & src.notna()
    difference = (calc - src).abs()
    comparable = difference[valid]

    if comparable.empty:
        return {
            "calculated_metric": calculated,
            "source_metric": source,
            "tolerance": tolerance,
            "comparable_records": 0,
            "matching_records": 0,
            "mismatch_records": 0,
            "match_pct": np.nan,
            "mean_abs_difference": np.nan,
            "max_abs_difference": np.nan,
        }

    matching = comparable <= tolerance
    return {
        "calculated_metric": calculated,
        "source_metric": source,
        "tolerance": tolerance,
        "comparable_records": len(comparable),
        "matching_records": int(matching.sum()),
        "mismatch_records": int((~matching).sum()),
        "match_pct": round(matching.mean() * 100, 2),
        "mean_abs_difference": round(comparable.mean(), 6),
        "max_abs_difference": round(comparable.max(), 6),
    }


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Candidate input not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)
    required = {
        "company_id", "year", "reporting_period",
        "canonical_reporting_period", "needs_review",
        "derived_metrics_needs_review", "review_flag_missing",
        "revenue_growth_pct", "net_profit_growth_pct",
    }
    required.update(c for c, s, _ in COMPARISONS)
    required.update(s for c, s, _ in COMPARISONS)

    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    period = df["canonical_reporting_period"].astype("string").str.strip().str.lower()
    annual = period.str.fullmatch(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec) \d{4}",
        na=False,
    )
    keys = ["company_id", "year", "canonical_reporting_period"]

    print("=" * 70)
    print("PERIOD-AWARE DERIVED METRICS VALIDATION")
    print("=" * 70)
    print("Rows:", len(df))
    print("Duplicate company-period keys:", int(df.duplicated(keys).sum()))
    print("Missing reporting-period labels:", int(
        df["reporting_period"].isna().sum()
        + df["reporting_period"].astype("string").str.strip().eq("").sum()
    ))
    print("Full-year period rows:", int(annual.sum()))
    print("Non-annual rows:", int((~annual).sum()))
    print("Non-annual rows with revenue growth:", int(
        df.loc[~annual, "revenue_growth_pct"].notna().sum()
    ))
    print("Non-annual rows with net-profit growth:", int(
        df.loc[~annual, "net_profit_growth_pct"].notna().sum()
    ))
    print("Missing review flags:", int(df["review_flag_missing"].sum()))
    print("Rows needing review:", int(df["derived_metrics_needs_review"].sum()))
    print(
        "Review flag disagreement:",
        int(
            df["derived_metrics_needs_review"].astype(bool).ne(
                df["needs_review"].fillna(True).astype(bool)
            ).sum()
        ),
    )

    results = [
        compare_columns(df, calculated, source, tolerance)
        for calculated, source, tolerance in COMPARISONS
    ]
    report = pd.DataFrame(results)
    report.to_csv(OUTPUT_PATH, index=False)

    print("\n=== FINANCIAL METRIC COMPARISONS ===")
    print(report.to_string(index=False))
    print("\nSaved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
