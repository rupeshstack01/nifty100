from src.etl.loader import load_all_sources
import pandas as pd


KEYS = ["company_id", "year"]

TABLES_TO_CHECK = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def classify_duplicates(name, df):

    print("\n" + "=" * 100)
    print(f"DUPLICATE CLASSIFICATION — {name.upper()}")
    print("=" * 100)

    df = df.copy()

    # Normalize keys
    df["company_id"] = (
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce"
    )

    # Find duplicate company-year groups
    counts = (
        df.groupby(KEYS, dropna=False)
        .size()
        .reset_index(name="row_count")
    )

    duplicates = counts[
        counts["row_count"] > 1
    ]

    if duplicates.empty:
        print("No duplicate groups.")
        return

    print(
        f"Duplicate company-year groups: "
        f"{len(duplicates)}"
    )

    summary = []

    for _, row in duplicates.iterrows():

        company = row["company_id"]
        year = row["year"]

        subset = df[
            (df["company_id"] == company)
            & (df["year"] == year)
        ].copy()

        comparison_columns = [
            c for c in subset.columns
            if c not in ["id"]
        ]

        # Check whether all non-ID values are identical
        normalized = subset[
            comparison_columns
        ].astype(str).fillna("<NA>")

        identical = (
            normalized.drop_duplicates().shape[0] == 1
        )

        if identical:
            duplicate_type = "EXACT_DUPLICATE"
        else:
            duplicate_type = "VARIANT_DUPLICATE"

        summary.append({
            "company_id": company,
            "year": year,
            "row_count": len(subset),
            "duplicate_type": duplicate_type
        })

    result = pd.DataFrame(summary)

    print("\nDUPLICATE TYPE SUMMARY")
    print("-" * 100)

    print(
        result["duplicate_type"]
        .value_counts()
        .to_string()
    )

    print("\nGROUP SUMMARY")
    print("-" * 100)

    print(
        result.to_string(index=False)
    )


def main():

    print("Loading all sources...\n")

    data = load_all_sources()

    for table_name in TABLES_TO_CHECK:

        if table_name not in data:
            print(
                f"\nTable not found: {table_name}"
            )
            continue

        classify_duplicates(
            table_name,
            data[table_name]
        )


if __name__ == "__main__":
    main()
