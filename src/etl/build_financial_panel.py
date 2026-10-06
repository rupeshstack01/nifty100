from pathlib import Path
import pandas as pd


PROCESSED_DIR = Path("data/processed")
OUTPUT_DIR = PROCESSED_DIR / "analytical"

TABLES = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def load_table(table_name):
    path = PROCESSED_DIR / f"{table_name}_cleaned.csv"

    df = pd.read_csv(path)

    df["company_id"] = (
        df["company_id"]
        .astype(str)
        .str.strip()
    )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce",
    ).astype("Int64")

    return df


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Load cleaned financial tables
    # ---------------------------------------------------------

    datasets = {
        table: load_table(table)
        for table in TABLES
    }

    # ---------------------------------------------------------
    # Count rows per company-year in each table
    # ---------------------------------------------------------

    counts = {}

    for table, df in datasets.items():

        counts[table] = (
            df.groupby(
                ["company_id", "year"]
            )
            .size()
            .rename(f"{table}_row_count")
        )

    count_table = pd.concat(
        counts.values(),
        axis=1,
    ).reset_index()

    count_columns = [
        f"{table}_row_count"
        for table in TABLES
    ]

    # ---------------------------------------------------------
    # Keep only company-year keys having exactly one row
    # in every financial table
    # ---------------------------------------------------------

    safe_mask = (
        count_table[count_columns]
        .eq(1)
        .all(axis=1)
    )

    safe_keys = count_table.loc[
        safe_mask,
        ["company_id", "year"],
    ].copy()

    print(
        f"Unambiguous company-year keys: "
        f"{len(safe_keys)}"
    )

    # ---------------------------------------------------------
    # Build analytical panel
    # ---------------------------------------------------------

    panel = safe_keys.copy()

    for table in TABLES:

        df = datasets[table]

        # Keep only safe company-year records
        df = df.merge(
            safe_keys,
            on=["company_id", "year"],
            how="inner",
            validate="many_to_one",
        )

        # Rename source-specific ID
        if "id" in df.columns:
            df = df.rename(
                columns={
                    "id": f"{table}_id"
                }
            )

        # Remove any columns that are already in panel
        # except the two join keys.
        duplicate_columns = [
            col
            for col in df.columns
            if col in panel.columns
            and col not in ["company_id", "year"]
        ]

        df = df.drop(
            columns=duplicate_columns
        )

        panel = panel.merge(
            df,
            on=["company_id", "year"],
            how="left",
            validate="one_to_one",
        )

    # ---------------------------------------------------------
    # Sort final panel
    # ---------------------------------------------------------

    panel = panel.sort_values(
        ["company_id", "year"]
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # Save analytical panel
    # ---------------------------------------------------------

    output_path = (
        OUTPUT_DIR /
        "financial_panel.csv"
    )

    panel.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Saved: {output_path}"
    )

    print(
        f"Rows: {len(panel)}"
    )

    print(
        f"Columns: {len(panel.columns)}"
    )


if __name__ == "__main__":
    main()