import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = Path("data/processed/nifty100.db")
ANALYTICAL_DIR = Path("data/processed/analytical")


TABLE_FILES = {
    "financial_panel": "financial_panel.csv",
    "derived_metrics": "derived_metrics.csv",
    "company_summary": "company_summary.csv",
    "company_scorecard": "company_scorecard.csv",
    "sectors": "sectors.csv",
    "stock_prices": "stock_prices.csv",
    "stock_returns": "stock_returns.csv",
    "annual_stock_returns": "annual_stock_returns.csv",
 
}


def load_csv(filename):
    path = ANALYTICAL_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    return pd.read_csv(path)


def create_database():
    print("=" * 70)
    print("BUILDING NIFTY100 SQLITE DATABASE")
    print("=" * 70)

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Remove previous database so the build is reproducible
    if DB_PATH.exists():
        DB_PATH.unlink()

    connection = sqlite3.connect(DB_PATH)

    try:
        for table_name, filename in TABLE_FILES.items():

            print(f"\nLoading: {filename}")

            df = load_csv(filename)

            print(f"Rows: {len(df)}")
            print(f"Columns: {len(df.columns)}")

            df.to_sql(
                table_name,
                connection,
                if_exists="replace",
                index=False,
            )

            print(f"Created table: {table_name}")

        connection.commit()

    finally:
        connection.close()

    print("\n" + "=" * 70)
    print("DATABASE BUILD COMPLETE")
    print("=" * 70)

    print(f"\nDatabase: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)

    try:
        tables = pd.read_sql_query(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """,
            connection,
        )

        print("\nTables created:")
        print(tables.to_string(index=False))

        print("\nRow counts:")

        for table_name in TABLE_FILES:
            result = pd.read_sql_query(
                f"SELECT COUNT(*) AS row_count FROM {table_name}",
                connection,
            )

            print(
                f"{table_name}: "
                f"{result.loc[0, 'row_count']}"
            )

    finally:
        connection.close()


if __name__ == "__main__":
    create_database()
