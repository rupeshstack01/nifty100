
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "nifty100.db"
OUTPUT_PATH = ROOT / "output" / "pattern_changes.csv"

METRICS = {
    "sales": "Revenue",
    "net_profit": "Net profit",
    "operating_profit_margin_pct": "Operating profit margin",
    "net_profit_margin_pct": "Net profit margin",
    "operating_activity": "Operating cash flow",
    "free_cash_flow_cr": "Free cash flow",
    "borrowings": "Borrowings",
}


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT company_id, year, sales, net_profit,
                   operating_profit_margin_pct, net_profit_margin_pct,
                   operating_activity, free_cash_flow_cr, borrowings
            FROM financial_panel
            ORDER BY company_id, year
            """,
            conn,
        )

    if df.empty:
        raise ValueError("financial_panel contains no records")

    df["company_id"] = df["company_id"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["company_id", "year"])
    df = df.sort_values(["company_id", "year"])

    # Compare each company with its previous available annual record.
    for metric in METRICS:
        df[f"previous_{metric}"] = df.groupby("company_id")[metric].shift(1)

    latest = df.groupby("company_id", as_index=False).tail(1).copy()
    rows = []

    for _, company in latest.iterrows():
        company_id = company["company_id"]
        year = int(company["year"])

        for metric, label in METRICS.items():
            current = company[metric]
            previous = company[f"previous_{metric}"]

            if pd.isna(current) or pd.isna(previous):
                continue

            current = float(current)
            previous = float(previous)
            change = current - previous

            if previous != 0:
                change_pct = change / abs(previous) * 100
            else:
                change_pct = np.nan

            if change > 0:
                direction = "Increased"
            elif change < 0:
                direction = "Decreased"
            else:
                direction = "Unchanged"

            # A directional change is descriptive, not automatically good or bad.
            rows.append({
                "company_id": company_id,
                "latest_year": year,
                "previous_year": int(
                    df.loc[
                        (df["company_id"] == company_id)
                        & (df["year"] < year), "year"
                    ].max()
                ),
                "metric": metric,
                "metric_label": label,
                "previous_value": previous,
                "latest_value": current,
                "absolute_change": change,
                "change_pct": change_pct,
                "direction": direction,
            })

    columns = [
        "company_id", "latest_year", "previous_year", "metric",
        "metric_label", "previous_value", "latest_value",
        "absolute_change", "change_pct", "direction",
    ]
    result = pd.DataFrame(rows, columns=columns)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False)

    print("=== PATTERN CHANGE REPORT ===")
    print(f"Companies in financial panel: {df['company_id'].nunique()}")
    print(f"Companies with reportable changes: {result['company_id'].nunique()}")
    print(f"Metric comparisons written: {len(result)}")
    print(f"Saved: {OUTPUT_PATH.relative_to(ROOT)}")
    if not result.empty:
        print("\nSample rows:")
        print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
