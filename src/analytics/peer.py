from __future__ import annotations

import sqlite3
from pathlib import Path
from src.etl.loader import load_all_sources
import numpy as np
import pandas as pd


DB_PATH = Path("data/processed/nifty100.db")

METRICS = {
    "ROE": ["return_on_equity_pct", "engine_return_on_equity_pct"],
    "ROCE": ["engine_roce_pct", "roce_pct"],
    "NPM": ["net_profit_margin_pct", "calculated_net_profit_margin_pct"],
    "D/E": ["debt_to_equity", "engine_debt_to_equity"],
    "FCF": ["free_cash_flow_cr", "fcf_cr"],
    "PAT CAGR 5Y": ["pat_cagr_5yr"],
    "Revenue CAGR 5Y": ["revenue_cagr_5yr"],
    "EPS CAGR 5Y": ["eps_cagr_5yr"],
    "Interest Coverage": ["interest_coverage"],
    "Asset Turnover": ["asset_turnover"],
}


def first_existing(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for column in candidates:
        if column in df.columns:
            return pd.to_numeric(df[column], errors="coerce")

    return pd.Series(np.nan, index=df.index, dtype=float)


def percentile_rank(series: pd.Series) -> pd.Series:
    """
    SQL PERCENT_RANK equivalent:

        (RANK - 1) / (N - 1) * 100

    Ties receive the minimum rank, matching SQL RANK().
    """
    result = pd.Series(np.nan, index=series.index, dtype=float)

    valid = series.notna()

    if valid.sum() == 0:
        return result

    values = series.loc[valid]

    if len(values) == 1:
        result.loc[valid] = 100.0
        return result

    ranks = values.rank(method="min")

    result.loc[valid] = (
        (ranks - 1)
        / (len(values) - 1)
        * 100
    )

    return result


def find_peer_group_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "peer_group_name",
        "peer_group",
        "group_name",
        "peer_group_id",
    ]

    for column in candidates:
        if column in df.columns:
            return column

    return None


def build_peer_percentiles() -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    with sqlite3.connect(DB_PATH) as conn:
        financial = pd.read_sql_query(
            "SELECT * FROM financial_ratios",
            conn,
    )

    sources = load_all_sources()
    peer_groups = sources["peer_groups"]

    print(
        f"Financial ratio rows: {len(financial)}"
    )

    print(
        f"Peer group rows: {len(peer_groups)}"
    )

    # --------------------------------------------------------
    # Identify peer-group column
    # --------------------------------------------------------

    peer_column = find_peer_group_column(peer_groups)

    if peer_column is None:
        raise ValueError(
            "Could not identify peer group column. "
            f"Available columns: {list(peer_groups.columns)}"
        )

    if "company_id" not in peer_groups.columns:
        raise ValueError(
            "peer_groups must contain company_id"
        )

    print(f"Using peer-group column: {peer_column}")

    # --------------------------------------------------------
    # Build company -> peer group mapping
    # --------------------------------------------------------

    groups = (
        peer_groups[
            ["company_id", peer_column]
        ]
        .dropna(subset=["company_id"])
        .drop_duplicates("company_id")
        .rename(
            columns={
                peer_column: "peer_group_name"
            }
        )
    )

    # --------------------------------------------------------
    # Latest available financial record per company
    # --------------------------------------------------------

    if "year" not in financial.columns:
        raise ValueError(
            "financial_ratios does not contain year"
        )

    financial["year"] = pd.to_numeric(
        financial["year"],
        errors="coerce",
    )

    financial = (
        financial
        .sort_values(["company_id", "year"])
        .drop_duplicates(
            "company_id",
            keep="last",
        )
    )

    # --------------------------------------------------------
    # Attach peer groups
    # --------------------------------------------------------

    financial = financial.merge(
        groups,
        on="company_id",
        how="left",
        validate="many_to_one",
    )

    financial["peer_group_name"] = (
        financial["peer_group_name"]
        .fillna("No peer group assigned")
    )

    # --------------------------------------------------------
    # Calculate percentile ranks
    # --------------------------------------------------------

    records = []

    for peer_group_name, group in financial.groupby(
        "peer_group_name",
        dropna=False,
    ):

        for metric_name, candidates in METRICS.items():

            values = first_existing(
                group,
                candidates,
            )

            # D/E: lower is better.
            # Calculate normal percentile and invert it.
            percentile = percentile_rank(values)

            if metric_name == "D/E":
                percentile = 100.0 - percentile

            for idx in group.index:

                value = values.loc[idx]

                if pd.isna(value):
                    continue

                records.append(
                    {
                        "company_id": group.loc[
                            idx,
                            "company_id",
                        ],
                        "peer_group_name": peer_group_name,
                        "metric": metric_name,
                        "value": float(value),
                        "percentile_rank": float(
                            percentile.loc[idx]
                        ),
                        "year": int(
                            group.loc[idx, "year"]
                        )
                        if pd.notna(
                            group.loc[idx, "year"]
                        )
                        else None,
                    }
                )

    result = pd.DataFrame(records)

    if result.empty:
        raise ValueError(
            "No peer percentile records were generated."
        )

    # --------------------------------------------------------
    # Validate percentile range
    # --------------------------------------------------------

    invalid = result[
        (result["percentile_rank"] < 0)
        | (result["percentile_rank"] > 100)
    ]

    if not invalid.empty:
        raise ValueError(
            f"Invalid percentile values: {len(invalid)}"
        )

    # --------------------------------------------------------
    # Write SQLite table
    # --------------------------------------------------------

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            "DROP TABLE IF EXISTS peer_percentiles"
        )

        result.to_sql(
            "peer_percentiles",
            conn,
            if_exists="replace",
            index=False,
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_peer_percentiles_company
            ON peer_percentiles(company_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_peer_percentiles_group_metric
            ON peer_percentiles(peer_group_name, metric)
            """
        )

    print(
        f"\nCreated peer_percentiles: {len(result)} rows"
    )

    print(
        f"Companies: {result['company_id'].nunique()}"
    )

    print(
        f"Peer groups: "
        f"{result['peer_group_name'].nunique()}"
    )

    print(
        f"Metrics: {result['metric'].nunique()}"
    )

    return result


if __name__ == "__main__":
    df = build_peer_percentiles()

    print("\nMetric counts:")
    print(
        df.groupby("metric")["company_id"]
        .nunique()
        .to_string()
    )

    print("\nPeer-group counts:")
    print(
        df.groupby("peer_group_name")["company_id"]
        .nunique()
        .to_string()
    )