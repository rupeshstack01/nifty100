import pandas as pd

from src.etl.loader import load_all_sources
from src.etl.deduplicator import (
    normalize_keys,
    find_duplicate_groups,
    classify_duplicate_group,
)


TABLES_TO_CHECK = [
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def inspect_variants(name, df):
    print("\n" + "=" * 100)
    print(f"VARIANT VALUE INSPECTION — {name.upper()}")
    print("=" * 100)

    df = normalize_keys(df)

    duplicate_groups = find_duplicate_groups(df)

    if duplicate_groups.empty:
        print("No duplicate groups.")
        return

    variant_count = 0

    for _, key in duplicate_groups.iterrows():

        company_id = key["company_id"]
        year = key["year"]

        group = df[
            (df["company_id"] == company_id)
            & (df["year"] == year)
        ].copy()

        duplicate_type = classify_duplicate_group(group)

        if duplicate_type != "VARIANT_DUPLICATE":
            continue

        variant_count += 1

        print("\n" + "-" * 100)
        print(f"Company : {company_id}")
        print(f"Year    : {int(year) if pd.notna(year) else year}")
        print(f"Rows    : {len(group)}")
        print("-" * 100)

        comparison_columns = [
            column
            for column in group.columns
            if column != "id"
        ]

        # Display each variant separately
        for index, (_, row) in enumerate(group.iterrows(), start=1):

            print(f"\nRECORD {index}")
            print("-" * 50)

            for column in comparison_columns:

                value = row[column]

                if pd.isna(value):
                    value = "<NA>"

                print(f"{column}: {value}")

        # Show only columns that actually differ
        differing_columns = []

        for column in comparison_columns:

            values = group[column].astype(str).fillna("<NA>").unique()

            if len(values) > 1:
                differing_columns.append(column)

        print("\nDIFFERING COLUMNS")
        print("-" * 50)

        for column in differing_columns:

            print(f"\n{column}")

            for index, value in enumerate(
                group[column].tolist(),
                start=1,
            ):
                print(f"  Record {index}: {value}")

        # Only inspect a manageable number initially
        if variant_count >= 15:
            print(
                "\n... showing first 15 variant groups only ..."
            )
            break

    print("\n" + "=" * 100)
    print(f"Total variant groups inspected: {variant_count}")
    print("=" * 100)


def main():

    print("Loading all sources...\n")

    data = load_all_sources()

    for table_name in TABLES_TO_CHECK:

        if table_name not in data:

            print(f"\nTable not found: {table_name}")
            continue

        inspect_variants(
            table_name,
            data[table_name],
        )


if __name__ == "__main__":
    main()
