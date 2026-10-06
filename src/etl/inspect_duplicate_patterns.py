from src.etl.loader import load_all_sources


def inspect_table(df, table_name):
    print("\n" + "=" * 80)
    print(f"TABLE: {table_name}")
    print("=" * 80)

    dup = df[df.duplicated(["company_id", "year"], keep=False)].copy()

    if dup.empty:
        print("No duplicates.")
        return

    grouped = (
        dup.groupby(["company_id", "year"])
        .size()
        .reset_index(name="row_count")
    )

    print(f"Duplicate groups: {len(grouped)}")
    print(f"Duplicate rows: {len(dup)}")

    print("\nDuplicate groups by company:")
    print(
        grouped.groupby("company_id")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    print("\nDuplicate groups by year:")
    print(
        grouped.groupby("year")
        .size()
        .sort_index()
    )


def main():
    data = load_all_sources()

    tables = [
        "profitandloss",
        "cashflow",
        "balancesheet",
        "financial_ratios",
    ]

    for table in tables:
        inspect_table(data[table], table)

    print("\n" + "=" * 80)
    print("DUPLICATE PATTERN INSPECTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
