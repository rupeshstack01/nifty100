from __future__ import annotations

import pandas as pd


PROFITABILITY_WEIGHT = 0.50
GROWTH_WEIGHT = 0.30
VALUATION_WEIGHT = 0.20


def percentile_score(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """Convert a metric into a 0-100 percentile score."""
    numeric = pd.to_numeric(series, errors="coerce")

    if not higher_is_better:
        numeric = -numeric

    return numeric.rank(pct=True, method="average") * 100


def sector_percentile(
    df: pd.DataFrame,
    column: str,
    higher_is_better: bool = True,
) -> pd.Series:
    """Calculate percentile score within each broad sector."""
    return df.groupby("broad_sector", group_keys=False)[column].transform(
        lambda s: percentile_score(s, higher_is_better)
    )


def build_ranking_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the Sprint 3 composite ranking.

    Composite:
      50% profitability
      30% growth
      20% valuation

    Each component is normalized to 0-100 using sector-relative
    percentile ranks.
    """
    result = df.copy()

    # Profitability: ROE + NPM + OPM
    profitability_metrics = [
        "engine_return_on_equity_pct",
        "engine_net_profit_margin_pct",
        "engine_operating_profit_margin_pct",
    ]

    profitability_scores = []
    for column in profitability_metrics:
        profitability_scores.append(
            sector_percentile(result, column, higher_is_better=True)
        )

    result["profitability_score"] = pd.concat(
        profitability_scores, axis=1
    ).mean(axis=1, skipna=True)

    # Growth: Revenue CAGR + PAT CAGR + EPS CAGR
    growth_metrics = [
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
    ]

    growth_scores = []
    for column in growth_metrics:
        growth_scores.append(
            sector_percentile(result, column, higher_is_better=True)
        )

    result["growth_score"] = pd.concat(
        growth_scores, axis=1
    ).mean(axis=1, skipna=True)

    # Valuation: lower P/E, P/B and EV/EBITDA are better
    valuation_metrics = [
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
    ]

    valuation_scores = []
    for column in valuation_metrics:
        valuation_scores.append(
            sector_percentile(result, column, higher_is_better=False)
        )

    result["valuation_score"] = pd.concat(
        valuation_scores, axis=1
    ).mean(axis=1, skipna=True)

        # ---------------------------------------------------------
    # Composite score: 50% profitability, 30% growth, 20% valuation
    # Missing components are excluded and remaining weights are
    # normalized. A minimum of 2 components is required.
    # ---------------------------------------------------------
    component_weights = pd.DataFrame(
        {
            "profitability": result["profitability_score"].notna() * 0.50,
            "growth": result["growth_score"].notna() * 0.30,
            "valuation": result["valuation_score"].notna() * 0.20,
        },
        index=result.index,
    )

    available_weight = component_weights.sum(axis=1)

    weighted_total = (
        result["profitability_score"].fillna(0)
        * component_weights["profitability"]
        + result["growth_score"].fillna(0)
        * component_weights["growth"]
        + result["valuation_score"].fillna(0)
        * component_weights["valuation"]
    )

    result["component_count"] = (
        result[
            [
                "profitability_score",
                "growth_score",
                "valuation_score",
            ]
        ]
        .notna()
        .sum(axis=1)
    )

    result["score_completeness"] = (
        result["component_count"] / 3 * 100
    )

    result["composite_score"] = weighted_total / available_weight

    # Require at least two ranking components.
    result.loc[
        result["component_count"] < 2,
        "composite_score"
    ] = pd.NA

    result["ranking_status"] = "COMPLETE"

    result.loc[
        result["component_count"] == 2,
        "ranking_status"
    ] = "PARTIAL_DATA"

    result.loc[
        result["component_count"] < 2,
        "ranking_status"
    ] = "INSUFFICIENT_DATA"

    result["sector_rank"] = (
        result.groupby("broad_sector")["composite_score"]
        .rank(method="min", ascending=False)
    )

    result["overall_rank"] = result["composite_score"].rank(
        method="min",
        ascending=False,
    )

    return result.sort_values(
        ["composite_score", "company_id"],
        ascending=[False, True],
    ).reset_index(drop=True)


def rank_latest_companies(df: pd.DataFrame) -> pd.DataFrame:
    """Rank the latest company-level records."""
    return build_ranking_scores(df)
