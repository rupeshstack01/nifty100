from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


DB_PATH = Path("data/processed/nifty100.db")
OUTPUT_DIR = Path("reports/radar_charts")


AXES = [
    "ROE",
    "ROCE",
    "NPM",
    "D/E",
    "FCF Score",
    "PAT CAGR 5Y",
    "Revenue CAGR 5Y",
    "Composite Score",
]


METRIC_MAP = {
    "ROE": "ROE",
    "ROCE": "ROCE",
    "NPM": "NPM",
    "D/E": "D/E",
    "FCF Score": "FCF",
    "PAT CAGR 5Y": "PAT CAGR 5Y",
    "Revenue CAGR 5Y": "Revenue CAGR 5Y",
}


def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        percentiles = pd.read_sql_query(
            "SELECT * FROM peer_percentiles",
            conn,
        )

        financial = pd.read_sql_query(
            "SELECT * FROM financial_ratios",
            conn,
        )

    return percentiles, financial


def latest_financial_records(financial: pd.DataFrame) -> pd.DataFrame:
    financial = financial.copy()

    financial["year"] = pd.to_numeric(
        financial["year"],
        errors="coerce",
    )

    return (
        financial
        .sort_values(["company_id", "year"])
        .drop_duplicates(
            "company_id",
            keep="last",
        )
        .reset_index(drop=True)
    )


def build_percentile_matrix(
    percentiles: pd.DataFrame,
) -> pd.DataFrame:

    pivot = percentiles.pivot_table(
        index=[
            "company_id",
            "peer_group_name",
            "year",
        ],
        columns="metric",
        values="percentile_rank",
        aggfunc="first",
    ).reset_index()

    return pivot


def calculate_composite_scores(
    financial: pd.DataFrame,
) -> pd.DataFrame:

    try:
        from src.screener.engine import build_screener_dataset
        from src.screener.ranking import build_ranking_scores

        screener = build_screener_dataset()
        ranked = build_ranking_scores(screener)

        return ranked[
            [
                "company_id",
                "composite_quality_score",
            ]
        ].drop_duplicates("company_id")

    except Exception as exc:
        print(
            f"Warning: could not load screener composite: {exc}"
        )

        return pd.DataFrame(
            columns=[
                "company_id",
                "composite_quality_score",
            ]
        )


def percentile_value(
    row: pd.Series,
    metric: str,
) -> float:

    value = row.get(metric, np.nan)

    if pd.isna(value):
        return np.nan

    return float(value)


def build_company_radar_data(
    company_id: str,
    matrix: pd.DataFrame,
    composite_scores: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:

    company_rows = matrix[
        matrix["company_id"].eq(company_id)
    ]

    if company_rows.empty:
        raise ValueError(
            f"No percentile data for {company_id}"
        )

    company = company_rows.iloc[0]

    peer_group = company["peer_group_name"]

    if peer_group == "No peer group assigned":
        peer_rows = matrix[
            matrix["peer_group_name"]
            .ne("No peer group assigned")
        ]
    else:
        peer_rows = matrix[
            matrix["peer_group_name"].eq(peer_group)
        ]

    return company, peer_rows


def build_radar(
    company: pd.Series,
    peer_rows: pd.DataFrame,
    composite_scores: pd.DataFrame,
    company_id: str,
) -> go.Figure:

    company_values = []

    for axis in AXES[:-1]:
        metric = METRIC_MAP[axis]

        company_values.append(
            percentile_value(
                company,
                metric,
            )
        )

    composite_row = composite_scores[
        composite_scores["company_id"].eq(company_id)
    ]

    if composite_row.empty:
        composite_value = np.nan
    else:
        composite_value = float(
            composite_row.iloc[0][
                "composite_quality_score"
            ]
        )

    company_values.append(composite_value)

    # --------------------------------------------------------
    # Peer / Nifty100 reference
    # --------------------------------------------------------

    reference_values = []

    for axis in AXES[:-1]:

        metric = METRIC_MAP[axis]

        if metric not in peer_rows.columns:
            reference_values.append(np.nan)
            continue

        reference_values.append(
            peer_rows[metric].mean()
        )

    if composite_scores.empty:
        reference_composite = np.nan
    else:
        reference_composite = (
            composite_scores[
                "composite_quality_score"
            ]
            .mean()
        )

    reference_values.append(reference_composite)

    # --------------------------------------------------------
    # Close polygons
    # --------------------------------------------------------

    labels = AXES + [AXES[0]]

    company_plot = (
        company_values
        + [company_values[0]]
    )

    reference_plot = (
        reference_values
        + [reference_values[0]]
    )

    peer_group = company["peer_group_name"]

    if peer_group == "No peer group assigned":
        reference_name = "Nifty100 Average"
        reference_dash = "dash"
    else:
        reference_name = "Peer Average"
        reference_dash = "dash"

    fig = go.Figure()

    # Company polygon
    fig.add_trace(
        go.Scatterpolar(
            r=company_plot,
            theta=labels,
            fill="toself",
            name=company_id,
            line=dict(width=2),
        )
    )

    # Reference polygon
    fig.add_trace(
        go.Scatterpolar(
            r=reference_plot,
            theta=labels,
            fill=None,
            name=reference_name,
            line=dict(
                width=2,
                dash=reference_dash,
            ),
        )
    )

    fig.update_layout(
        title=(
            f"{company_id} — "
            f"{reference_name}"
        ),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
            )
        ),
        showlegend=True,
        width=800,
        height=800,
    )

    return fig


def generate_all_radars() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    percentiles, financial = load_data()

    print(
        f"Peer percentile rows: "
        f"{len(percentiles)}"
    )

    print(
        f"Companies: "
        f"{percentiles['company_id'].nunique()}"
    )

    matrix = build_percentile_matrix(
        percentiles
    )

    composite_scores = calculate_composite_scores(
        financial
    )

    companies = sorted(
        percentiles["company_id"]
        .dropna()
        .unique()
    )

    generated = 0
    skipped = []

    for company_id in companies:

        try:
            company, peer_rows = (
                build_company_radar_data(
                    company_id,
                    matrix,
                    composite_scores,
                )
            )

            fig = build_radar(
                company,
                peer_rows,
                composite_scores,
                company_id,
            )

            output_path = (
                OUTPUT_DIR
                / f"{company_id}_radar.png"
            )

            pio.write_image(
                fig,
                output_path,
                format="png",
                width=800,
                height=800,
            )

            generated += 1

        except Exception as exc:

            skipped.append(
                {
                    "company_id": company_id,
                    "error": str(exc),
                }
            )

    print(
        f"\nGenerated: {generated}"
    )

    print(
        f"Skipped: {len(skipped)}"
    )

    if skipped:
        print("\nSkipped companies:")

        for item in skipped:
            print(
                f"  {item['company_id']}: "
                f"{item['error']}"
            )


if __name__ == "__main__":
    generate_all_radars()