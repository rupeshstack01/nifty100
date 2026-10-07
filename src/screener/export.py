from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.screener.engine import (
    build_screener_dataset,
    latest_company_records,
    load_config,
    run_preset,
)
from src.screener.ranking import rank_latest_companies


OUTPUT_PATH = Path("output/screener_output.xlsx")


EXPORT_COLUMNS = [
    # Identification
    "company_id",
    "broad_sector",

    # Ranking
    "profitability_score",
    "growth_score",
    "valuation_score",
    "composite_score",
    "component_count",
    "score_completeness",
    "ranking_status",
    "overall_rank",
    "sector_rank",

    # Profitability KPIs
    "engine_return_on_equity_pct",
    "engine_net_profit_margin_pct",
    "engine_operating_profit_margin_pct",
    "engine_roce_pct",
    "engine_roa_pct",

    # Leverage / efficiency
    "engine_debt_to_equity",
    "engine_interest_coverage",
    "engine_asset_turnover",

    # Cash flow
    "free_cash_flow_cr",
    "cash_from_operations_cr",
    "capex_cr",
    "capex_intensity_pct",
    "fcf_conversion_pct",
    "cfo_pat_ratio",

    # Growth
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",

    # Per-share / dividend
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",

    # Valuation
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield_pct",
]


def prepare_sheet(df: pd.DataFrame) -> pd.DataFrame:
    columns = [c for c in EXPORT_COLUMNS if c in df.columns]

    result = df[columns].copy()

    if "composite_score" in result.columns:
        result = result.sort_values(
            ["composite_score", "company_id"],
            ascending=[False, True],
            na_position="last",
        )

    return result.reset_index(drop=True)


def format_workbook(writer: pd.ExcelWriter) -> None:
    workbook = writer.book

    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter

            for cell in column_cells:
                value = cell.value
                if value is not None:
                    max_length = max(max_length, len(str(value)))

            worksheet.column_dimensions[column_letter].width = min(
                max(max_length + 2, 12),
                28,
            )


def main() -> None:
    print("=" * 70)
    print("D17 — SCREENER EXCEL EXPORT")
    print("=" * 70)

    config = load_config()

    dataset = build_screener_dataset()
    latest = latest_company_records(dataset)
    ranked = rank_latest_companies(latest)

    sheets = {
        "Ranking": ranked,
    }

    for preset_name in config["presets"]:
        preset_result = run_preset(preset_name)

        # Merge ranking information into preset result.
        ranking_columns = [
            c
            for c in [
                "profitability_score",
                "growth_score",
                "valuation_score",
                "composite_score",
                "component_count",
                "score_completeness",
                "ranking_status",
                "overall_rank",
                "sector_rank",
            ]
            if c in ranked.columns
        ]

        preset_result = preset_result.merge(
            ranked[
                ["company_id"] + ranking_columns
            ],
            on="company_id",
            how="left",
        )

        sheets[preset_name[:31]] = preset_result

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(
        OUTPUT_PATH,
        engine="openpyxl",
    ) as writer:

        for sheet_name, sheet_df in sheets.items():
            export_df = prepare_sheet(sheet_df)
            export_df.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

        format_workbook(writer)

    print()
    print("Created:", OUTPUT_PATH)
    print("Sheets:", len(sheets))

    for sheet_name, sheet_df in sheets.items():
        print(f"{sheet_name}: {len(sheet_df)} rows")


if __name__ == "__main__":
    main()
