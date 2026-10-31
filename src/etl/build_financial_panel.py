
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

KEYS = ["company_id", "year"]


def load_table(table_name):
    path = PROCESSED_DIR / f"{table_name}_cleaned.csv"

    df = pd.read_csv(path)
    df["company_id"] = df["company_id"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    # Invalid keys cannot be joined safely.
    df = df.dropna(subset=KEYS).copy()

    return df


def build_table_summary(table_name, df):
    """Count source records and identify ambiguous company-years."""
    counts = (
        df.groupby(KEYS, dropna=False)
        .size()
        .rename(f"{table_name}_row_count")
        .reset_index()
    )

    counts[f"{table_name}_status"] = counts[
        f"{table_name}_row_count"
    ].map(
        lambda n: "MISSING" if n == 0
        else "UNAMBIGUOUS" if n == 1
        else "CONFLICT"
    )

    return counts


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    datasets = {table: load_table(table) for table in TABLES}

    # Build the full set of company-year keys present in any table.
    all_keys = pd.concat(
        [df[KEYS] for df in datasets.values()],
        ignore_index=True,
    ).drop_duplicates()

    panel = all_keys.copy()
    review = all_keys.copy()

    for table, df in datasets.items():
        counts = (
            df.groupby(KEYS)
            .size()
            .rename(f"{table}_row_count")
            .reset_index()
        )

        panel = panel.merge(
            counts,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )

        panel[f"{table}_row_count"] = (
            panel[f"{table}_row_count"].fillna(0).astype(int)
        )

        panel[f"{table}_ambiguous"] = (
            panel[f"{table}_row_count"] > 1
        )

        review = review.merge(
            counts,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )

        review[f"{table}_row_count"] = (
            review[f"{table}_row_count"].fillna(0).astype(int)
        )

        # Only a single-record company-year can safely contribute
        # financial values to the analytical panel.
        unique_keys = counts.loc[
            counts[f"{table}_row_count"] == 1, KEYS
        ]

        safe_rows = df.merge(
    unique_keys,
    on=KEYS,
    how="inner",
    validate="many_to_one",
).copy()

        # Do not carry technical IDs or review metadata into the panel.
        safe_rows = safe_rows.drop(
            columns=[
                col for col in ["id", "review_status"]
                if col in safe_rows.columns
            ],
            errors="ignore",
        )

        # For conflicting or missing source records, leave the
        # corresponding financial values null.
        financial_columns = [
            col for col in safe_rows.columns if col not in KEYS
        ]

        safe_rows = safe_rows.rename(
            columns={
                col: f"{table}_{col}"
                for col in financial_columns
            }
        )

        panel = panel.merge(
            safe_rows,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )

        review[f"{table}_status"] = review[
            f"{table}_row_count"
        ].map(
            lambda n: "MISSING" if n == 0
            else "UNAMBIGUOUS" if n == 1
            else "CONFLICT"
        )

    # A row needs review if any source table is missing or ambiguous.
    status_columns = [f"{table}_status" for table in TABLES]
    review["needs_review"] = review[status_columns].ne(
        "UNAMBIGUOUS"
    ).any(axis=1)

    review = review.sort_values(KEYS).reset_index(drop=True)
    panel = panel.sort_values(KEYS).reset_index(drop=True)

    panel_path = OUTPUT_DIR / "financial_panel.csv"
    review_path = OUTPUT_DIR / "financial_panel_review.csv"

    panel.to_csv(panel_path, index=False)
    review.to_csv(review_path, index=False)

    print(f"Saved: {panel_path}")
    print(f"Saved: {review_path}")
    print(f"Panel rows: {len(panel)}")
    print(f"Panel columns: {len(panel.columns)}")
    print(f"Unique company-year keys: {len(panel.drop_duplicates(KEYS))}")
    print(f"Company-years needing review: {int(review['needs_review'].sum())}")

    for table in TABLES:
        print(
            f"{table}: "
            f"missing={int((review[f'{table}_status'] == 'MISSING').sum())}, "
            f"conflict={int((review[f'{table}_status'] == 'CONFLICT').sum())}, "
            f"unambiguous={int((review[f'{table}_status'] == 'UNAMBIGUOUS').sum())}"
        )


if __name__ == "__main__":
    main()
