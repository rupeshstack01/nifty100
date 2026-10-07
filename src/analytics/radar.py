from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


INPUT_PATH = Path(
    "data/processed/analytical/peer_percentiles.csv"
)

OUTPUT_DIR = Path(
    "reports/radar_charts"
)


AXES = {
    "ROE": "return_on_equity_pct_percentile",
    "NPM": "net_profit_margin_pct_percentile",
    "OPM": "operating_profit_margin_pct_percentile",
    "Revenue CAGR": "revenue_cagr_5yr_percentile",
    "PAT CAGR": "pat_cagr_5yr_percentile",
    "EPS CAGR": "eps_cagr_5yr_percentile",
    "FCF": "free_cash_flow_cr_percentile",
    "Dividend Yield": "dividend_yield_pct_percentile",
}


def build_radar(
    company_row: pd.Series,
    peer_data: pd.DataFrame,
) -> go.Figure:

    labels = list(AXES.keys())

    company_values = [
        company_row[column]
        for column in AXES.values()
    ]

    peer_values = [
        peer_data[column].mean()
        for column in AXES.values()
    ]

    company_values.append(company_values[0])
    peer_values.append(peer_values[0])

    closed_labels = labels + [labels[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=company_values,
            theta=closed_labels,
            fill="toself",
            name=str(company_row["company_id"]),
        )
    )

    fig.add_trace(
        go.Scatterpolar(
            r=peer_values,
            theta=closed_labels,
            fill="toself",
            name="Peer Average",
        )
    )

    fig.update_layout(
        title=(
            f"{company_row['company_id']} — "
            f"{company_row['peer_group_name']}"
        ),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
            )
        ),
        showlegend=True,
        width=900,
        height=700,
    )

    return fig


def main() -> None:

    print("=" * 70)
    print("D19 — PEER RADAR CHART GENERATION")
    print("=" * 70)

    df = pd.read_csv(INPUT_PATH)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated = 0
    skipped = 0

    # Build all figures first.
    figures = []

    for peer_group, group in df.groupby(
        "peer_group_name"
    ):

        for _, company_row in group.iterrows():

            company_values = pd.to_numeric(
                [
                    company_row[column]
                    for column in AXES.values()
                ],
                errors="coerce",
            )

            if pd.notna(company_values).sum() == 0:
                skipped += 1
                continue

            figures.append(
                (
                    company_row["company_id"],
                    build_radar(
                        company_row,
                        group,
                    ),
                )
            )

    print("Charts prepared:", len(figures))
    print("Charts skipped:", skipped)

    # Render using a single persistent Kaleido session.
    print("Rendering PNG files...")

    for index, (company_id, fig) in enumerate(figures, start=1):
        output_path = OUTPUT_DIR / f"{company_id}_radar.png"

        pio.write_image(
            fig,
            str(output_path),
            format="png",
            scale=2,
        )

        generated += 1

        if generated % 10 == 0:
            print(f"Generated {generated}/{len(figures)}")
  

    print()
    print("Peer-group companies:",
          df["company_id"].nunique())

    print("Peer groups:",
          df["peer_group_name"].nunique())

    print("Charts generated:",
          generated)

    print("Charts skipped:",
          skipped)

    print("Output directory:",
          OUTPUT_DIR)


if __name__ == "__main__":
    main()
