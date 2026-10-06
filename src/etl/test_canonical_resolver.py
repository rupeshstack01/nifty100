from src.etl.loader import load_all_sources
from src.etl.canonical_resolver import resolve_all


def main():

    print("\nLoading all sources...\n")

    data = load_all_sources()

    results = resolve_all(data)

    print("\n" + "=" * 100)
    print("CANONICAL RESOLUTION SUMMARY")
    print("=" * 100)

    for table_name, result in results.items():

        cleaned = result["cleaned"]
        audit = result["audit"]
        review = result["variant_review"]

        print(f"\n{table_name.upper()}")
        print("-" * 60)

        print(f"Cleaned rows: {len(cleaned)}")

        if not audit.empty:
            print(
                "Duplicate groups:",
                len(audit)
            )

        print(
            "Variant groups requiring review:",
            len(review)
        )


if __name__ == "__main__":
    main()
