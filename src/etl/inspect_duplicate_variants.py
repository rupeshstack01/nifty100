from src.etl.loader import load_all_sources
import pandas as pd


KEYS = ["company_id", "year"]

TABLES_TO_CHECK = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def inspect_table(name, df):
    print("\n" + "=" * 100)
    print(f"DUPLICATE VARIANT INSPECTION — {name.upper()}")
    print("=" * 100)

    if not all(col in df.columns for col in KEYS):
        print(f"Missing required columns: {KEYS}")
        return

    # Normalize year for reliable grouping
    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    counts = (
        df.groupby(KEYS, dropna=False)
        .size()
        .reset_index(name="row_count")
    )

    duplicates = counts[counts["row_count"] > 1]

    if duplicates.empty:
        print("No duplicate company-year groups found.")
        return

    print(f"Duplicate company-year groups: {len(duplicates)}")

    # Inspect each duplicate group
    for _, group in duplicates.iterrows():

        company = group["company_id"]
        year = group["year"]

        subset = df[
            (df["company_id"] == company) &
            (df["year"] == year)
        ].copy()

        print("\n" + "-" * 100)
        print(f"{company} — {int(year) if pd.notna(year) else year}")
        print(f"Rows: {len(subset)}")
        print("-" * 100)

        # Remove technical ID from comparison
        comparison_columns = [
            c for c in subset.columns
            if c not in ["id"]
        ]

        # Show complete records
        print(subset[comparison_columns].to_string(index=False))

        # Find columns containing different values
        differing_columns = []

        for column in comparison_columns:
            values = subset[column].astype(str).fillna("<NA>").unique()

            if len(values) > 1:
                differing_columns.append(column)

        if differing_columns:
            print("\nDIFFERING COLUMNS:")
            for column in differing_columns:
                values = subset[column].tolist()
                print(f"  {column}: {values}")
        else:
            print("\nAll non-ID columns are identical.")

        # Stop after a manageable number of groups
        # Remove this limit later if required.
        if duplicates.index.get_loc(_) >= 19:
            print("\n... showing first 20 duplicate groups only ...")
            break


def main():
    print("Loading all sources...\n")

    data = load_all_sources()

    for table_name in TABLES_TO_CHECK:
        if table_name not in data:
            print(f"\nTable not found: {table_name}")
            continue

        inspect_table(table_name, data[table_name])


if __name__ == "__main__":
    main()