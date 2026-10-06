from src.etl.loader import load_all_sources
from src.etl.deduplicator import (
    normalize_keys,
    create_duplicate_audit,
    remove_exact_duplicates,
)


TABLES = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def main():

    data = load_all_sources()

    for table_name in TABLES:

        print("\n" + "=" * 100)
        print(f"DUPLICATE AUDIT — {table_name.upper()}")
        print("=" * 100)

        df = data[table_name]

        print(f"Original rows: {len(df)}")

        normalized = normalize_keys(df)

        print(
            f"Normalized rows: {len(normalized)}"
        )

        audit = create_duplicate_audit(normalized)

        if audit.empty:

            print("No duplicate company-year groups.")

        else:

            print(
                f"Duplicate company-year groups: {len(audit)}"
            )

            print("\nDuplicate type summary:")

            print(
                audit["duplicate_type"]
                .value_counts()
                .to_string()
            )

            print("\nFirst duplicate groups:")

            print(
                audit.head(20)
                .to_string(index=False)
            )

        cleaned = remove_exact_duplicates(normalized)

        print(
            f"\nRows after exact-duplicate removal: "
            f"{len(cleaned)}"
        )


if __name__ == "__main__":
    main()
