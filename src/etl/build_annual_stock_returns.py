from pathlib import Path
import pandas as pd


INPUT_FILE = Path("data/processed/analytical/stock_prices.csv")
OUTPUT_FILE = Path("data/processed/analytical/annual_stock_returns.csv")


def main():
    print("=" * 70)
    print("BUILDING ANNUAL STOCK RETURNS")
    print("=" * 70)

    df = pd.read_csv(INPUT_FILE)

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(["company_id", "date"]).copy()

    df["year"] = df["date"].dt.year

    annual = (
        df.groupby(["company_id", "year"])
        .agg(
            first_price=("adjusted_close", "first"),
            last_price=("adjusted_close", "last"),
        )
        .reset_index()
    )

    annual["annual_return_pct"] = (
        (annual["last_price"] / annual["first_price"] - 1) * 100
    ).round(2)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    annual.to_csv(OUTPUT_FILE, index=False)

    print()
    print(f"Rows: {len(annual)}")
    print(f"Companies: {annual['company_id'].nunique()}")
    print(f"Years: {annual['year'].nunique()}")
    print(f"Year range: {annual['year'].min()} to {annual['year'].max()}")
    print()
    print("Sample:")
    print(annual.head(20).to_string(index=False))
    print()
    print(f"Saved: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
