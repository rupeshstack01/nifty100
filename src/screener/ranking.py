from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# DAY 17 COMPOSITE SCORE
# ============================================================

CATEGORY_WEIGHTS = {
    "profitability": 0.35,
    "cash_quality": 0.30,
    "growth": 0.20,
    "leverage": 0.15,
}

METRIC_WEIGHTS = {
    "roe": 0.15,
    "roce": 0.10,
    "npm": 0.10,

    "fcf_cagr_5yr": 0.15,
    "cfo_pat": 0.10,
    "fcf_positive": 0.05,

    "revenue_cagr_5yr": 0.10,
    "pat_cagr_5yr": 0.10,

    "de": 0.10,
    "icr": 0.05,
}


def _first_existing(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """
    Return the first available column from a list of aliases.
    If none exists, return an all-NaN Series.
    """
    for column in columns:
        if column in df.columns:
            return pd.to_numeric(df[column], errors="coerce")

    return pd.Series(np.nan, index=df.index, dtype=float)


def _cfo_pat_ratio(df: pd.DataFrame) -> pd.Series:
    """
    CFO / PAT.

    Prefer an existing precomputed column when available.
    Otherwise calculate it from CFO and net profit.
    """
    existing = _first_existing(
        df,
        [
            "cfo_pat_ratio",
            "cash_from_operations_to_pat",
            "cfo_to_pat",
        ],
    )

    if existing.notna().any():
        return existing

    cfo = _first_existing(
        df,
        [
            "cash_from_operations_cr",
            "operating_activity",
            "cash_from_operations",
        ],
    )

    pat = _first_existing(
        df,
        [
            "net_profit_cr",
            "net_profit",
            "pat",
        ],
    )

    result = pd.Series(np.nan, index=df.index, dtype=float)

    valid = pat.notna() & cfo.notna() & pat.ne(0)

    result.loc[valid] = cfo.loc[valid] / pat.loc[valid]

    return result


def _fcf_positive_flag(df: pd.DataFrame) -> pd.Series:
    """
    FCF positive = 100, FCF non-positive = 0.
    """
    fcf = _first_existing(
        df,
        [
            "free_cash_flow_cr",
            "fcf_cr",
            "free_cash_flow",
        ],
    )

    result = pd.Series(np.nan, index=df.index, dtype=float)

    valid = fcf.notna()

    result.loc[valid] = np.where(
        fcf.loc[valid] > 0,
        100.0,
        0.0,
    )

    return result


def _winsor_scale(
    series: pd.Series,
    inverse: bool = False,
) -> pd.Series:
    """
    P10/P90 winsorisation followed by 0-100 scaling.

    Missing values remain NaN.

    inverse=True means lower values receive higher scores.
    """
    s = pd.to_numeric(series, errors="coerce")

    result = pd.Series(np.nan, index=s.index, dtype=float)

    valid = s.notna()

    if not valid.any():
        return result

    values = s.loc[valid]

    p10 = values.quantile(0.10)
    p90 = values.quantile(0.90)

    # Avoid division by zero when all values are identical.
    if pd.isna(p10) or pd.isna(p90):
        return result

    if p90 == p10:
        result.loc[valid] = 100.0
        return result

    clipped = values.clip(lower=p10, upper=p90)

    if inverse:
        scaled = (p90 - clipped) / (p90 - p10) * 100.0
    else:
        scaled = (clipped - p10) / (p90 - p10) * 100.0

    result.loc[valid] = scaled

    return result


def _sector_relative_score(
    df: pd.DataFrame,
    series: pd.Series,
    inverse: bool = False,
) -> pd.Series:
    """
    Apply P10/P90 winsorisation and 0-100 scaling
    independently inside broad_sector.
    """
    result = pd.Series(np.nan, index=df.index, dtype=float)

    if "broad_sector" not in df.columns:
        return _winsor_scale(series, inverse=inverse)

    temp = pd.DataFrame(
        {
            "_sector": df["broad_sector"],
            "_value": pd.to_numeric(series, errors="coerce"),
        },
        index=df.index,
    )

    for sector, index in temp.groupby("_sector", dropna=False).groups.items():
        sector_values = temp.loc[index, "_value"]

        result.loc[index] = _winsor_scale(
            sector_values,
            inverse=inverse,
        )

    return result


def _weighted_available_score(
    score_columns: dict[str, pd.Series],
    weights: dict[str, float],
    index: pd.Index,
) -> pd.Series:
    """
    Calculate a weighted score using only available metrics.

    Missing metrics do not become zero.

    Instead, their weight is redistributed proportionally
    across the metrics that are available for that company.

    Example:

        A = 60% available
        B = 40% missing

    The available A score receives 100% of the category weight.
    """
    result = pd.Series(np.nan, index=index, dtype=float)

    numerator = pd.Series(0.0, index=index)
    denominator = pd.Series(0.0, index=index)

    for metric, score in score_columns.items():
        weight = weights[metric]

        valid = score.notna()

        numerator.loc[valid] += score.loc[valid] * weight
        denominator.loc[valid] += weight

    valid_rows = denominator.gt(0)

    result.loc[valid_rows] = (
        numerator.loc[valid_rows]
        / denominator.loc[valid_rows]
    )

    return result


def _coverage_pct(
    score_columns: dict[str, pd.Series],
    weights: dict[str, float],
    index: pd.Index,
) -> pd.Series:
    """
    Percentage of category weight supported by available metrics.
    """
    result = pd.Series(0.0, index=index)

    for metric, score in score_columns.items():
        result.loc[score.notna()] += weights[metric] * 100.0

    return result


def build_ranking_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the Day 17 0-100 composite quality score.

    Process:
      1. Keep latest available record per company.
      2. Calculate metric-level scores.
      3. Apply P10/P90 winsorisation.
      4. Normalize metrics within broad sector.
      5. Calculate four weighted categories.
      6. Redistribute missing metric weights.
      7. Calculate final 35/30/20/15 composite.
    """

    df = df.copy()

    # --------------------------------------------------------
    # Latest company record
    # --------------------------------------------------------

    if "year" in df.columns:
        df["year"] = pd.to_numeric(
            df["year"],
            errors="coerce",
        )

        df = (
            df.sort_values(["company_id", "year"])
            .drop_duplicates(
                "company_id",
                keep="last",
            )
            .reset_index(drop=True)
        )

    # --------------------------------------------------------
    # Raw metrics
    # --------------------------------------------------------

    roe = _first_existing(
        df,
        [
            "engine_return_on_equity_pct",
            "return_on_equity_pct",
            "roe",
        ],
    )

    roce = _first_existing(
        df,
        [
            "engine_roce_pct",
            "roce_pct",
            "roce",
        ],
    )

    npm = _first_existing(
        df,
        [
            "calculated_net_profit_margin_pct",
            "net_profit_margin_pct",
            "npm",
        ],
    )

    fcf_cagr = _first_existing(
        df,
        [
            "fcf_cagr_5yr",
        ],
    )

    cfo_pat = _cfo_pat_ratio(df)

    fcf_positive = _fcf_positive_flag(df)

    revenue_cagr = _first_existing(
        df,
        [
            "revenue_cagr_5yr",
        ],
    )

    pat_cagr = _first_existing(
        df,
        [
            "pat_cagr_5yr",
        ],
    )

    debt_to_equity = _first_existing(
        df,
        [
            "engine_debt_to_equity",
            "debt_to_equity",
        ],
    )

    interest_coverage = _first_existing(
        df,
        [
            "interest_coverage",
        ],
    )

    # --------------------------------------------------------
    # Sector-relative metric scores
    # --------------------------------------------------------

    score_roe = _sector_relative_score(
        df,
        roe,
    )

    score_roce = _sector_relative_score(
        df,
        roce,
    )

    score_npm = _sector_relative_score(
        df,
        npm,
    )

    score_fcf_cagr = _sector_relative_score(
        df,
        fcf_cagr,
    )

    score_cfo_pat = _sector_relative_score(
        df,
        cfo_pat,
    )

    # FCF positive is already a 0/100 flag.
    score_fcf_positive = fcf_positive

    score_revenue_cagr = _sector_relative_score(
        df,
        revenue_cagr,
    )

    score_pat_cagr = _sector_relative_score(
        df,
        pat_cagr,
    )

    # Lower D/E is better.
    score_de = _sector_relative_score(
        df,
        debt_to_equity,
        inverse=True,
    )

    # Higher ICR is better.
    score_icr = _sector_relative_score(
        df,
        interest_coverage,
    )

    # --------------------------------------------------------
    # Category score dictionaries
    # --------------------------------------------------------

    profitability_scores = {
        "roe": score_roe,
        "roce": score_roce,
        "npm": score_npm,
    }

    profitability_weights = {
        "roe": METRIC_WEIGHTS["roe"],
        "roce": METRIC_WEIGHTS["roce"],
        "npm": METRIC_WEIGHTS["npm"],
    }

    cash_scores = {
        "fcf_cagr_5yr": score_fcf_cagr,
        "cfo_pat": score_cfo_pat,
        "fcf_positive": score_fcf_positive,
    }

    cash_weights = {
        "fcf_cagr_5yr": METRIC_WEIGHTS["fcf_cagr_5yr"],
        "cfo_pat": METRIC_WEIGHTS["cfo_pat"],
        "fcf_positive": METRIC_WEIGHTS["fcf_positive"],
    }

    growth_scores = {
        "revenue_cagr_5yr": score_revenue_cagr,
        "pat_cagr_5yr": score_pat_cagr,
    }

    growth_weights = {
        "revenue_cagr_5yr": METRIC_WEIGHTS["revenue_cagr_5yr"],
        "pat_cagr_5yr": METRIC_WEIGHTS["pat_cagr_5yr"],
    }

    leverage_scores = {
        "de": score_de,
        "icr": score_icr,
    }

    leverage_weights = {
        "de": METRIC_WEIGHTS["de"],
        "icr": METRIC_WEIGHTS["icr"],
    }

    # --------------------------------------------------------
    # Category scores with missing-weight redistribution
    # --------------------------------------------------------

    profitability_score = _weighted_available_score(
        profitability_scores,
        profitability_weights,
        df.index,
    )

    cash_quality_score = _weighted_available_score(
        cash_scores,
        cash_weights,
        df.index,
    )

    growth_score = _weighted_available_score(
        growth_scores,
        growth_weights,
        df.index,
    )

    leverage_score = _weighted_available_score(
        leverage_scores,
        leverage_weights,
        df.index,
    )

    # --------------------------------------------------------
    # Category coverage
    # --------------------------------------------------------

    profitability_coverage = _coverage_pct(
        profitability_scores,
        profitability_weights,
        df.index,
    )

    cash_coverage = _coverage_pct(
        cash_scores,
        cash_weights,
        df.index,
    )

    growth_coverage = _coverage_pct(
        growth_scores,
        growth_weights,
        df.index,
    )

    leverage_coverage = _coverage_pct(
        leverage_scores,
        leverage_weights,
        df.index,
    )

    # --------------------------------------------------------
    # Final composite
    #
    # The category weights remain exactly:
    # Profitability 35%
    # Cash Quality  30%
    # Growth        20%
    # Leverage      15%
    #
    # A category with at least one usable metric contributes
    # its full category weight.
    # --------------------------------------------------------

    category_scores = {
        "profitability": profitability_score,
        "cash_quality": cash_quality_score,
        "growth": growth_score,
        "leverage": leverage_score,
    }

    category_weight_sum = pd.Series(0.0, index=df.index)
    category_weighted_sum = pd.Series(0.0, index=df.index)

    for category, score in category_scores.items():
        weight = CATEGORY_WEIGHTS[category]

        valid = score.notna()

        category_weighted_sum.loc[valid] += (
            score.loc[valid] * weight
        )

        category_weight_sum.loc[valid] += weight

    composite = pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )

    valid_composite = category_weight_sum.gt(0)

    composite.loc[valid_composite] = (
        category_weighted_sum.loc[valid_composite]
        / category_weight_sum.loc[valid_composite]
    )

    # --------------------------------------------------------
    # Overall score coverage
    # --------------------------------------------------------

    score_coverage = (
        profitability_coverage
        + cash_coverage
        + growth_coverage
        + leverage_coverage
    )
   

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    result = df.copy()

    result["roe_score"] = score_roe
    result["roce_score"] = score_roce
    result["npm_score"] = score_npm

    result["fcf_cagr_score"] = score_fcf_cagr
    result["cfo_pat_score"] = score_cfo_pat
    result["fcf_positive_score"] = score_fcf_positive

    result["revenue_cagr_score"] = score_revenue_cagr
    result["pat_cagr_score"] = score_pat_cagr

    result["de_score"] = score_de
    result["icr_score"] = score_icr

    result["profitability_score"] = profitability_score
    result["cash_quality_score"] = cash_quality_score
    result["growth_score"] = growth_score
    result["leverage_score"] = leverage_score

    result["profitability_coverage_pct"] = profitability_coverage
    result["cash_quality_coverage_pct"] = cash_coverage
    result["growth_coverage_pct"] = growth_coverage
    result["leverage_coverage_pct"] = leverage_coverage

    result["score_coverage_pct"] = score_coverage

    result["composite_quality_score"] = composite.round(2)

    return result