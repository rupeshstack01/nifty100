from src.etl.loader import load_all_sources


def main():
    data = load_all_sources()

    company = "ABB"

    tables = [
        "profitandloss",
        "cashflow",
        "balancesheet",
        "financial_ratios",
    ]

    for table in tables:
        df = data[table]

        print("\n" + "=" * 100)
        print(f"{table.upper()} — {company}")
        print("=" * 100)

        company_df = df[df["company_id"] == company].copy()

        dup = company_df[
            company_df.duplicated(["company_id", "year"], keep=False)
        ].sort_values(["year", "id"])

        if dup.empty:
            print("No duplicate company/year records.")
            continue

        print(dup.to_string(index=False))


if __name__ == "__main__":
    main()
