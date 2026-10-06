import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")

files = sorted(RAW_DIR.glob("*.xlsx"))

print("=" * 100)
print("NIFTY100 SOURCE DATA INSPECTION")
print("=" * 100)

for file in files:
    print(f"\nFILE: {file.name}")
    print("-" * 100)

    try:
        excel = pd.ExcelFile(file)

        print("Sheets:", excel.sheet_names)

        for sheet in excel.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet)

            print(f"\nSheet: {sheet}")
            print(f"Rows: {len(df)}")
            print(f"Columns: {len(df.columns)}")
            print("Column names:")

            for column in df.columns:
                print(f"  - {column}")

            print("\nFirst 2 rows:")
            print(df.head(2).to_string(index=False))

    except Exception as e:
        print(f"ERROR: {e}")

print("\n" + "=" * 100)
print(f"Total Excel files found: {len(files)}")
print("=" * 100)
