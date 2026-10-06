from src.etl.loader import load_all_sources
import pandas as pd


KEY_COLUMNS = ["company_id", "year"]

TABLES = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def normalize_value(value):
    """Normalize values for reliable comparison."""
    if pd.isna(value):
        return "<NA>"

    if isinstance(value, float):
        return round(value, 10)

    return value


def compare_rows(group):
    """
    Compare duplicate rows and identify which columns differ.
    """
    data_columns = [
        col for col in group.columns
        if col not in KEY_COLUMNS and col != "id"
    ]

    differing_columns = []

    for col in data_columns:
        values = [
            normalize_value(v)
            for v in group[col].tolist()
        ]

        if len(set(map(str, values))) > 1:
            differing_columns.append(col)

    return differing_columns


def classify_duplicate(group):
    """
    Classify the duplicate group based on how many
    non-ID columns differ.
    """
    differing_columns = compare_rows(group)

    if not differing_columns:
        return "EXACT_DUPLICATE"

    if len(differing_columns) == 1:
        return "ONE_COLUMN_VARIANT"

    return "MULTI_COLUMN_VARIANT"


def inspect_table(df, table_name):
    print("\n" + "=" * 100)
    print(f"DUPLICATE RESOLUTION ANALYSIS — {table_name.upper()}")
    print("=" * 100)

    if not all(col in df.columns for col in KEY_COLUMNS):
        print(f"Skipping {table_name}: missing key columns")
        return

    duplicate_mask = df.duplicated(
        subset=KEY_COLUMNS,
        keep=False
    )

    duplicates = df[duplicate_mask].copy()

    if duplicates.empty:
        print("No duplicate company-year groups found.")
        return

    group_counts = (
        duplicates
        .groupby(KEY_COLUMNS)
        .size()
        .reset_index(name="row_count")
    )

    print(
        f"Duplicate company-year groups: "
        f"{len(group_counts)}"
    )

    print(
        f"Total rows involved in duplicates: "
        f"{len(duplicates)}"
    )

    print("\nDuplicate group size distribution:")
    print(
        group_counts["row_count"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    # Classification counters
    classification_counts = {
        "EXACT_DUPLICATE": 0,
        "ONE_COLUMN_VARIANT": 0,
        "MULTI_COLUMN_VARIANT": 0,
    }

    print("\n" + "-" * 100)
    print("GROUP-BY-GROUP ANALYSIS")
    print("-" * 100)

    # Only show detailed output for first 20 groups
    # to prevent terminal output becoming enormous.
    shown = 0

    for (company_id, year), group in duplicates.groupby(
        KEY_COLUMNS,
        sort=True
    ):

        classification = classify_duplicate(group)
        classification_counts[classification] += 1

        if shown >= 20:
            continue

        differing_columns = compare_rows(group)

        print("\n" + "-" * 100)
        print(f"{company_id} — {year}")
        print(f"Rows: {len(group)}")
        print(f"Classification: {classification}")

        if differing_columns:
            print(
                "Differing columns: "
                + ", ".join(differing_columns)
            )
        else:
            print("All non-ID columns are identical.")

        print("\nIDs:")
        print(group["id"].tolist())

        if differing_columns:
            print("\nVariant values:")

            for col in differing_columns:
                values = [
                    normalize_value(v)
                    for v in group[col].tolist()
                ]

                print(f"  {col}: {values}")

        shown += 1

    print("\n" + "=" * 100)
    print("CLASSIFICATION SUMMARY")
    print("=" * 100)

    for classification, count in classification_counts.items():
        print(f"{classification:<25} {count}")

    print("\nNote:")
    print("No rows were deleted or modified.")


def main():
    print("=" * 100)
    print("DUPLICATE VARIANT RESOLUTION ANALYSIS")
    print("=" * 100)

    data = load_all_sources()

    for table_name in TABLES:
        if table_name not in data:
            print(f"\nSkipping missing table: {table_name}")
            continue

        inspect_table(
            data[table_name],
            table_name
        )

    print("\n" + "=" * 100)
    print("RESOLUTION ANALYSIS COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
