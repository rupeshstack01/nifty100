from src.etl.loader import load_all_sources

d = load_all_sources()

company = "ABB"
year = 2024

tables = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]

for table in tables:
    df = d[table]

    print("\n" + "=" * 100)
    print(f"{table.upper()} — {company} — {year}")
    print("=" * 100)

    result = df[
        (df["company_id"] == company) &
        (df["year"] == year)
    ]

    print(result.to_string(index=False))


print("\n" + "=" * 100)
print("DOCUMENT")
print("=" * 100)

documents = d["documents"]

doc = documents[
    (documents["company_id"] == company) &
    (documents["year"] == year)
]

print(doc.to_string(index=False))
