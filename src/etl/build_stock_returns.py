from pathlib import Path

import pandas as pd


INPUT_FILE = Path("data/processed/analytical/stock_prices.csv")
OUTPUT_FILE = Path("data/processed/analytical/stock_returns.csv")


def main():
    print("=" * 70)
    print("BUILDING MONTHLY STOCK RETURNS")
    print("=" * 70)

    df = pd.read_csv(INPUT_FILE)

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(["company_id", "date"]).copy()

    # Calculate monthly return using adjusted close
    df["monthly_return_pct"] = (
        df.groupby("company_id")["adjusted_close"]
        .pct_change()
        * 100
    )

    # Save return dataset
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print()
    print(f"Rows: {len(df)}")
    print(f"Companies: {df['company_id'].nunique()}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(
        f"Non-null returns: "
        f"{df['monthly_return_pct'].notna().sum()}"
    )
    print(
        f"Missing returns: "
        f"{df['monthly_return_pct'].isna().sum()}"
    )

    print()
    print("Sample:")
    print(
        df[
            [
                "company_id",
                "date",
                "adjusted_close",
                "monthly_return_pct",
            ]
        ].head(15).to_string(index=False)
    )

    print()
    print(f"Saved: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
