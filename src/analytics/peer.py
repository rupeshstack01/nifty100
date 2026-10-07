from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.etl.loader import load_all_sources
from src.screener.engine import (
    build_screener_dataset,
    latest_company_records,
)


OUTPUT_PATH = Path(
    "data/processed/analytical/peer_percentiles.csv"
)


# Metrics used for peer comparison.
# Higher values are generally better except valuation multiples.
METRICS = {
    "return_on_equity_pct": (
        "engine_return_on_equity_pct",
        True,
    ),
    "net_profit_margin_pct": (
        "engine_net_profit_margin_pct",
        True,
    ),
    "operating_profit_margin_pct": (
        "engine_operating_profit_margin_pct",
        True,
    ),
    "revenue_cagr_5yr": (
        "revenue_cagr_5yr",
        True,
    ),
    "pat_cagr_5yr": (
        "pat_cagr_5yr",
        True,
    ),
    "eps_cagr_5yr": (
        "eps_cagr_5yr",
        True,
    ),
    "debt_to_equity": (
        "engine_debt_to_equity",
        False,
    ),
    "interest_coverage": (
        "engine_interest_coverage",
        True,
    ),
    "asset_turnover": (
        "engine_asset_turnover",
        True,
    ),
    "free_cash_flow_cr": (
        "free_cash_flow_cr",
        True,
    ),
    "pe_ratio": (
        "pe_ratio",
        False,
    ),
    "pb_ratio": (
        "pb_ratio",
        False,
    ),
    "ev_ebitda": (
        "ev_ebitda",
        False,
    ),
    "dividend_yield_pct": (
        "dividend_yield_pct",
        True,
    ),
}


def percent_rank(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """
    Calculate percentile rank from 0 to 100.

    Missing values remain missing.

    For metrics where lower is better, the percentile is
    inverted so that a higher percentile always represents
    better relative performance.
    """
    numeric = pd.to_numeric(series, errors="coerce")

    valid = numeric.notna()

    result = pd.Series(
        pd.NA,
        index=series.index,
        dtype="Float64",
    )

    if valid.sum() == 0:
        return result

    values = numeric.loc[valid]

    if higher_is_better:
        ranks = values.rank(
            method="min",
            pct=True,
        )
    else:
        ranks = (-values).rank(
            method="min",
            pct=True,
        )

    result.loc[valid] = ranks * 100

    return result


def build_peer_percentiles() -> pd.DataFrame:
    sources = load_all_sources()

    peer_groups = sources["peer_groups"].copy()

    financial = latest_company_records(
        build_screener_dataset()
    ).copy()

    # Keep only companies that actually belong to a peer group.
    result = peer_groups.merge(
        financial,
        on="company_id",
        how="left",
        validate="many_to_one",
    )

    # Calculate percentile for each metric within peer group.
    for output_name, (
        source_column,
        higher_is_better,
    ) in METRICS.items():

        if source_column not in result.columns:
            result[output_name] = pd.NA
            result[f"{output_name}_percentile"] = pd.NA
            continue

        result[output_name] = pd.to_numeric(
            result[source_column],
            errors="coerce",
        )

        result[
            f"{output_name}_percentile"
        ] = result.groupby(
            "peer_group_name"
        )[output_name].transform(
            lambda s: percent_rank(
                s,
                higher_is_better,
            )
        )

    output_columns = [
        "peer_group_name",
        "company_id",
        "is_benchmark",
    ]

    for output_name in METRICS:
        output_columns.extend(
            [
                output_name,
                f"{output_name}_percentile",
            ]
        )

    result = result[output_columns].copy()

    result = result.sort_values(
        [
            "peer_group_name",
            "is_benchmark",
            "company_id",
        ],
        ascending=[
            True,
            False,
            True,
        ],
    ).reset_index(drop=True)

    return result


def main() -> None:
    print("=" * 70)
    print("D18 — PEER PERCENTILE ENGINE")
    print("=" * 70)

    result = build_peer_percentiles()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("Rows:", len(result))
    print(
        "Peer groups:",
        result["peer_group_name"].nunique(),
    )
    print(
        "Companies:",
        result["company_id"].nunique(),
    )
    print(
        "Benchmarks:",
        result["is_benchmark"].sum(),
    )

    print("\nRows per peer group:")
    print(
        result["peer_group_name"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nCreated:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
