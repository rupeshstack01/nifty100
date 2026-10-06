from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path(
    "data/processed/analytical/derived_metrics.csv"
)

OUTPUT_PATH = Path(
    "data/processed/analytical/derived_metrics_validation.csv"
)


def compare_columns(
    df,
    calculated,
    source,
    tolerance,
):
    calc = pd.to_numeric(
        df[calculated],
        errors="coerce",
    )

    src = pd.to_numeric(
        df[source],
        errors="coerce",
    )

    valid = calc.notna() & src.notna()

    difference = (calc - src).abs()

    comparable = difference[valid]

    if len(comparable) == 0:
        return {
            "calculated_metric": calculated,
            "source_metric": source,
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
        "comparable_records": len(comparable),
        "matching_records": int(matching.sum()),
        "mismatch_records": int((~matching).sum()),
        "match_pct": round(
            matching.mean() * 100,
            2,
        ),
        "mean_abs_difference": round(
            comparable.mean(),
            6,
        ),
        "max_abs_difference": round(
            comparable.max(),
            6,
        ),
    }


def main():

    print("=" * 70)
    print("VALIDATING DERIVED FINANCIAL METRICS")
    print("=" * 70)

    df = pd.read_csv(INPUT_PATH)

    comparisons = [
        (
            "calculated_net_profit_margin_pct",
            "net_profit_margin_pct",
            0.05,
        ),
        (
            "calculated_opm_pct",
            "opm_percentage",
            0.5,
        ),
        (
            "calculated_roe_pct",
            "return_on_equity_pct",
            0.05,
        ),
        (
            "calculated_debt_to_equity",
            "debt_to_equity",
            0.0002,
        ),
        (
            "calculated_asset_turnover",
            "asset_turnover",
            0.0002,
        ),
        (
            "calculated_fcf_cr",
            "free_cash_flow_cr",
            0.5,
        ),
    ]

    results = []

    for calculated, source, tolerance in comparisons:

        result = compare_columns(
            df,
            calculated,
            source,
            tolerance,
        )

        results.append(result)

    report = pd.DataFrame(results)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("\nValidation results:\n")

    print(
        report.to_string(
            index=False
        )
    )

    print(
        f"\nSaved: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
