from src.etl.loader import load_all_sources
import pandas as pd

d = load_all_sources()

tables = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]

print("\n" + "=" * 100)
print("CROSS-TABLE DUPLICATE MAP")
print("=" * 100)

for table in tables:
    df = d[table].copy()

    counts = (
        df.groupby(["company_id", "year"])
        .size()
        .reset_index(name="row_count")
    )

    duplicates = counts[counts["row_count"] > 1]

    print("\n" + "-" * 100)
    print(f"{table.upper()}")
    print("-" * 100)

    if duplicates.empty:
        print("No duplicate company/year groups.")
    else:
        print(duplicates.to_string(index=False))


print("\n" + "=" * 100)
print("CROSS-TABLE OVERLAP")
print("=" * 100)

duplicate_sets = {}

for table in tables:
    df = d[table]

    counts = (
        df.groupby(["company_id", "year"])
        .size()
        .reset_index(name="row_count")
    )

    duplicate_sets[table] = set(
        zip(
            counts.loc[counts["row_count"] > 1, "company_id"],
            counts.loc[counts["row_count"] > 1, "year"],
        )
    )

all_keys = set().union(*duplicate_sets.values())

rows = []

for company, year in sorted(all_keys):
    row = {
        "company_id": company,
        "year": year,
    }

    for table in tables:
        row[table] = (
            "DUPLICATE"
            if (company, year) in duplicate_sets[table]
            else "single"
        )

    rows.append(row)

result = pd.DataFrame(rows)

print(result.to_string(index=False))
