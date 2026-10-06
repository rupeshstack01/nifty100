from src.etl.loader import load_all_sources

import pandas as pd


KEYS = ["company_id", "year"]

TABLES = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def inspect_table(name, df):
    print("\n" + "=" * 80)
    print(f"TABLE: {name}")
    print("=" * 80)

    # Make sure the key columns exist
    missing = [col for col in KEYS if col not in df.columns]

    if missing:
        print(f"Missing key columns: {missing}")
        return

    # Find duplicate groups
    group_sizes = (
        df.groupby(KEYS)
        .size()
        .reset_index(name="row_count")
    )

    duplicate_groups = group_sizes[
        group_sizes["row_count"] > 1
    ].copy()

    duplicate_rows = df[
        df.duplicated(KEYS, keep=False)
    ].copy()

    print(f"Total rows: {len(df)}")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Duplicate rows: {len(duplicate_rows)}")

    if duplicate_groups.empty:
        print("No duplicates found.")
        return

    print("\nDuplicate group sizes:")
    print(
        duplicate_groups["row_count"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    # Exact duplicate analysis
    data_columns = [
        col for col in df.columns
        if col not in ["id", "company_id", "year"]
    ]

    duplicate_rows["exact_duplicate"] = duplicate_rows.duplicated(
        subset=KEYS + data_columns,
        keep=False
    )

    exact_count = duplicate_rows["exact_duplicate"].sum()
    non_exact_count = len(duplicate_rows) - exact_count

    print("\nDuplicate classification:")
    print(f"Exact duplicate rows: {exact_count}")
    print(f"Non-identical duplicate rows: {non_exact_count}")

    # Companies with the most duplicate groups
    company_counts = (
        duplicate_groups
        .groupby("company_id")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    print("\nCompanies with most duplicate groups:")
    print(company_counts.to_string())

    # Years with most duplicate groups
    year_counts = (
        duplicate_groups
        .groupby("year")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    print("\nYears with most duplicate groups:")
    print(year_counts.to_string())

    # Show first 10 non-identical duplicate groups
    print("\nSample non-identical duplicate groups:")

    non_exact = duplicate_rows[
        ~duplicate_rows["exact_duplicate"]
    ].copy()

    if non_exact.empty:
        print("None.")
    else:
        shown = 0

        for (company, year), group in non_exact.groupby(KEYS):

            print(f"\n--- {company} / {year} ---")

            print(
                group[
                    ["id"] + data_columns
                ].to_string(index=False)
            )

            shown += 1

            if shown >= 10:
                break


def main():
    data = load_all_sources()

    for table in TABLES:
        inspect_table(table, data[table])

    print("\n" + "=" * 80)
    print("DUPLICATE INSPECTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
