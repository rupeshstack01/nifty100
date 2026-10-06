"""
Nifty100 Excel-to-SQLite ETL loader.

Reads the source Excel files from data/raw/, applies basic
normalisation, and prepares datasets for SQLite loading.
"""

from pathlib import Path
from typing import Dict

import pandas as pd

from src.etl.normaliser import normalize_ticker, normalize_year


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "output"


# ------------------------------------------------------------
# Source file mapping
# ------------------------------------------------------------

SOURCE_FILES: Dict[str, str] = {
    "analysis": "1788501604303-57986a9b-analysis.xlsx",
    "balancesheet": "1788501604829-ac8c0874-balancesheet.xlsx",
    "cashflow": "1788501605758-8e951681-cashflow.xlsx",
    "companies": "1788501606103-7177b6c2-companies.xlsx",
    "documents": "1788501606362-ba899c04-documents.xlsx",
    "profitandloss": "1788501607124-aad40f4f-profitandloss.xlsx",
    "prosandcons": "1788501607452-d6bbe55b-prosandcons.xlsx",
    "financial_ratios": "1788501620089-fb3ae469-financial_ratios.xlsx",
    "market_cap": "1788501620397-69ae3e7f-market_cap.xlsx",
    "peer_groups": "1788501620796-5060f580-peer_groups.xlsx",
    "sectors": "1788501621129-8684701e-sectors.xlsx",
    "stock_prices": "1788501621395-a51977cd-stock_prices.xlsx",
}


# ------------------------------------------------------------
# Load Excel file
# ------------------------------------------------------------

def load_excel(file_path: Path) -> pd.DataFrame:
    """
    Read an Excel file and automatically detect the real header row.

    Some source files contain a metadata/title row before the actual
    column headers. This function detects that structure and loads
    the correct header.

    Args:
        file_path: Path to Excel file.

    Returns:
        Loaded DataFrame with the correct column headers.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    # Read the first few rows without assuming a header.
    preview = pd.read_excel(file_path, header=None, nrows=5)

    header_row = 0

    # Look for a row containing common data-field names.
    header_candidates = {
        "id",
        "company_id",
        "year",
        "date",
        "sales",
        "company_name",
    }

    for index, row in preview.iterrows():
        values = {
            str(value).strip().lower()
            for value in row.tolist()
            if pd.notna(value)
        }

        if values.intersection(header_candidates):
            header_row = index
            break

    df = pd.read_excel(file_path, header=header_row)

    # Remove completely empty rows.
    df = df.dropna(how="all").reset_index(drop=True)

    return df


# ------------------------------------------------------------
# Basic column normalisation
# ------------------------------------------------------------

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize DataFrame column names.

    Converts:
        'Company ID' -> 'company_id'
        'Operating Profit' -> 'operating_profit'

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with normalized column names.
    """
    df = df.copy()

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace("&", "and", regex=False)
        .str.replace("%", "pct", regex=False)
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    return df


# ------------------------------------------------------------
# Dataset-specific normalisation
# ------------------------------------------------------------

def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply basic normalisation to a dataset.

    Detects common company ID and year columns and applies
    the project normalisation functions.
    """
    df = normalize_columns(df)

    # Normalize company/ticker identifier
    company_columns = [
        "id",     
        "company_id",
        "ticker",
        "symbol",
    ]

    for column in company_columns:
        if column in df.columns:
            df[column] = df[column].apply(normalize_ticker)
           

    # Normalize year
    if "year" in df.columns:
        df["year"] = df["year"].apply(normalize_year)

    return df


# ------------------------------------------------------------
# Load all source files
# ------------------------------------------------------------

def load_all_sources() -> Dict[str, pd.DataFrame]:
    """
    Load and normalize all configured source Excel files.

    Returns:
        Dictionary mapping dataset names to DataFrames.
    """
    datasets = {}

    for dataset_name, filename in SOURCE_FILES.items():
        file_path = RAW_DIR / filename

        print(f"Loading: {filename}")

        df = load_excel(file_path)
        df = normalize_dataset(df)

        datasets[dataset_name] = df

        print(
            f"  -> {dataset_name}: "
            f"{len(df):,} rows x {len(df.columns)} columns"
        )

    return datasets


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    """Run the source loading process."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    datasets = load_all_sources()

    print("\n" + "=" * 70)
    print("SOURCE LOADING COMPLETE")
    print("=" * 70)

    total_rows = sum(len(df) for df in datasets.values())

    print(f"Datasets loaded: {len(datasets)}")
    print(f"Total rows loaded: {total_rows:,}")


if __name__ == "__main__":
    main()
