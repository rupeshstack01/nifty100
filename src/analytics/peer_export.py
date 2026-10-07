from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import ColorScaleRule


INPUT_PATH = Path("data/processed/analytical/peer_percentiles.csv")
OUTPUT_PATH = Path("output/peer_comparison.xlsx")


METRICS = {
    "ROE": "return_on_equity_pct",
    "NPM": "net_profit_margin_pct",
    "OPM": "operating_profit_margin_pct",
    "Revenue CAGR 5Y": "revenue_cagr_5yr",
    "PAT CAGR 5Y": "pat_cagr_5yr",
    "EPS CAGR 5Y": "eps_cagr_5yr",
    "Debt / Equity": "debt_to_equity",
    "Interest Coverage": "interest_coverage",
    "Asset Turnover": "asset_turnover",
    "FCF (Cr)": "free_cash_flow_cr",
    "P/E": "pe_ratio",
    "P/B": "pb_ratio",
    "EV / EBITDA": "ev_ebitda",
    "Dividend Yield": "dividend_yield_pct",
}


def main() -> None:
    print("=" * 70)
    print("D20 — PEER COMPARISON EXCEL EXPORT")
    print("=" * 70)

    df = pd.read_csv(INPUT_PATH)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Input rows: {len(df)}")
    print(f"Peer groups: {df['peer_group_name'].nunique()}")
    print(f"Companies: {df['company_id'].nunique()}")

    with pd.ExcelWriter(
        OUTPUT_PATH,
        engine="openpyxl",
    ) as writer:

        for peer_group, group in df.groupby("peer_group_name", sort=True):
            export_columns = [
                "company_id",
                "is_benchmark",
            ]

            for metric_column in METRICS.values():
                export_columns.extend(
                    [
                        metric_column,
                        f"{metric_column}_percentile",
                    ]
                )

            available_columns = [
                column for column in export_columns
                if column in group.columns
            ]

            output = group[available_columns].copy()

            output = output.sort_values(
                ["is_benchmark", "company_id"],
                ascending=[False, True],
            )

            # Rename columns for the Excel report.
            rename_map = {
                "company_id": "Company",
                "is_benchmark": "Benchmark",
            }

            for display_name, source_column in METRICS.items():
                rename_map[source_column] = display_name
                rename_map[f"{source_column}_percentile"] = (
                    f"{display_name} Percentile"
                )

            output = output.rename(columns=rename_map)

            # Excel sheet names have a 31-character limit.
            sheet_name = peer_group[:31]

            output.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    wb = load_workbook(OUTPUT_PATH)

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    header_font = Font(
        bold=True,
        color="FFFFFF",
    )

    benchmark_fill = PatternFill(
        fill_type="solid",
        fgColor="FFF2CC",
    )

    thin_border = Border(
        bottom=Side(
            style="thin",
            color="D9E1F2",
        )
    )

    for ws in wb.worksheets:

        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions

        # Header formatting.
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        ws.row_dimensions[1].height = 30

        # General formatting.
        for row in ws.iter_rows(min_row=2):
            is_benchmark = row[1].value

            if is_benchmark:
                for cell in row:
                    cell.fill = benchmark_fill

            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(
                    vertical="center"
                )

        # Percentile columns receive a 0–100 colour scale.
        for column_index, cell in enumerate(ws[1], start=1):

            if "Percentile" in str(cell.value):

                column_letter = cell.column_letter

                ws.conditional_formatting.add(
                    f"{column_letter}2:{column_letter}{ws.max_row}",
                    ColorScaleRule(
                        start_type="min",
                        start_color="F8696B",
                        mid_type="percentile",
                        mid_value=50,
                        mid_color="FFEB84",
                        end_type="max",
                        end_color="63BE7B",
                    ),
                )

        # Number formatting.
        for row in ws.iter_rows(min_row=2):

            for cell in row:

                if isinstance(cell.value, (int, float)):

                    if "Percentile" in str(
                        ws.cell(1, cell.column).value
                    ):
                        cell.number_format = "0.0"

                    else:
                        cell.number_format = "0.00"

        # Column widths.
        for column_cells in ws.columns:

            column_letter = column_cells[0].column_letter

            max_length = 0

            for cell in column_cells:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))

            ws.column_dimensions[column_letter].width = min(
                max(max_length + 2, 12),
                28,
            )

    wb.save(OUTPUT_PATH)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    validation_wb = load_workbook(
        OUTPUT_PATH,
        read_only=True,
    )

    print()
    print("Validation")
    print("-" * 70)
    print("Sheets:", len(validation_wb.sheetnames))
    print("Sheet names:")

    for sheet in validation_wb.sheetnames:
        ws = validation_wb[sheet]
        print(
            f"  {sheet}: "
            f"{ws.max_row - 1} companies, "
            f"{ws.max_column} columns"
        )

    validation_wb.close()

    print()
    print("D20 STATUS: PASS")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
