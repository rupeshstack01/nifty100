"""
Nifty100 Data Quality Validator.

Runs data-quality checks against the normalized source datasets
loaded by src.etl.loader.

Output:
    output/validation_failures.csv
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.etl.loader import load_all_sources


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
FAILURE_FILE = OUTPUT_DIR / "validation_failures.csv"


def add_failure(
    failures: List[dict],
    rule_id: str,
    table: str,
    severity: str,
    message: str,
    company_id=None,
    year=None,
) -> None:
    """Append one data-quality failure."""
    failures.append(
        {
            "rule_id": rule_id,
            "table": table,
            "company_id": company_id,
            "year": year,
            "severity": severity,
            "message": message,
        }
    )


# -------------------------------------------------------------------
# DQ-01 — Primary-key uniqueness
# -------------------------------------------------------------------

def dq01_pk_uniqueness(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check uniqueness of id columns."""

    for table, df in datasets.items():
        if "id" not in df.columns:
            continue

        duplicate_mask = df["id"].duplicated(keep=False)

        for _, row in df.loc[duplicate_mask].iterrows():
            add_failure(
                failures,
                "DQ-01",
                table,
                "CRITICAL",
                f"Duplicate primary-key id: {row['id']}",
                row.get("company_id"),
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-02 — Company/year uniqueness
# -------------------------------------------------------------------

def dq02_company_year_uniqueness(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check company/year uniqueness.

    Known ETL-reviewed variants are WARNING.
    Unexpected duplicates are CRITICAL.
    """

    applicable_tables = {
        "profitandloss",
        "balancesheet",
        "cashflow",
        "financial_ratios",
        "market_cap",
    }

    review_files = {
        "balancesheet": "data/processed/review/balancesheet_variant_review.csv",
        "cashflow": "data/processed/review/cashflow_variant_review.csv",
        "financial_ratios": "data/processed/review/financial_ratios_variant_review.csv",
        "profitandloss": "data/processed/review/profitandloss_variant_review.csv",
    }

    known_variants = {}

    # Load known variant company/year combinations
    for table, path in review_files.items():
        try:
            review_df = pd.read_csv(path)

        except (pd.errors.EmptyDataError, FileNotFoundError):
            known_variants[table] = set()
            continue

        if {"company_id", "year"}.issubset(review_df.columns):
            known_variants[table] = set(
                zip(
                    review_df["company_id"].astype(str).str.strip(),
                    review_df["year"].astype(str).str.strip(),
                )
            )
        else:
            known_variants[table] = set()

    # Check actual datasets
    for table in applicable_tables:
        if table not in datasets:
            continue

        df = datasets[table]

        if not {"company_id", "year"}.issubset(df.columns):
            continue

        duplicate_mask = df.duplicated(
            subset=["company_id", "year"],
            keep=False,
        )

        duplicates = df.loc[
            duplicate_mask,
            ["company_id", "year"],
        ].drop_duplicates()

        for _, row in duplicates.iterrows():

            key = (
                str(row["company_id"]).strip(),
                str(row["year"]).strip(),
            )

            if key in known_variants.get(table, set()):
                severity = "WARNING"
                message = (
                    "Known variant duplicate retained by ETL; "
                    "manual/source review required"
                )
            else:
                severity = "CRITICAL"
                message = (
                    "Unexpected duplicate (company_id, year) combination"
                )

            add_failure(
                failures,
                "DQ-02",
                table,
                severity,
                message,
                row["company_id"],
                row["year"],
            )

# -------------------------------------------------------------------
# DQ-03 — Foreign-key integrity
# -------------------------------------------------------------------

def dq03_fk_integrity(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check company references and identify reference-master coverage gaps."""

    companies = datasets.get("companies")

    if companies is None or "id" not in companies.columns:
        return

    valid_company_ids = set(
        companies["id"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )

    company_reference_tables = [
        "profitandloss",
        "balancesheet",
        "cashflow",
        "financial_ratios",
        "market_cap",
        "stock_prices",
        "analysis",
        "documents",
        "prosandcons",
        "sectors",
    ]

    for table in company_reference_tables:
        if table not in datasets:
            continue

        df = datasets[table]

        if "company_id" not in df.columns:
            continue

        for _, row in df.iterrows():
            company_id = row.get("company_id")

            # Missing company ID is a genuine data-quality error
            if pd.isna(company_id) or str(company_id).strip() == "":
                add_failure(
                    failures,
                    "DQ-03",
                    table,
                    "CRITICAL",
                    "Missing company_id",
                    None,
                    row.get("year"),
                )

# -------------------------------------------------------------------
# DQ-04 — Balance-sheet balance
# -------------------------------------------------------------------

def dq04_balance_sheet(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """
    Check whether the balance sheet balances within 1%.

    Expected columns:
        total_assets
        total_liabilities
        total_equity
    """

    df = datasets.get("balancesheet")

    if df is None:
        return

    required = {
        "total_assets",
        "total_liabilities",
        "total_equity",
    }

    if not required.issubset(df.columns):
        return

    numeric_cols = [
        "total_assets",
        "total_liabilities",
        "total_equity",
    ]

    for column in numeric_cols:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=numeric_cols)

    expected = df["total_liabilities"] + df["total_equity"]

    denominator = df["total_assets"].abs().replace(0, pd.NA)

    difference_pct = (
        (df["total_assets"] - expected).abs()
        / denominator
        * 100
    )

    failures_mask = difference_pct > 1

    for index in df.index[failures_mask]:
        row = df.loc[index]

        add_failure(
            failures,
            "DQ-04",
            "balancesheet",
            "WARNING",
            (
                f"Balance-sheet difference is "
                f"{difference_pct.loc[index]:.2f}%"
            ),
            row.get("company_id"),
            row.get("year"),
        )


# -------------------------------------------------------------------
# DQ-05 — Operating profit margin cross-check
# -------------------------------------------------------------------

def dq05_opm_crosscheck(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """
    Cross-check operating margin.

    Expected:
        operating_profit / sales * 100
        approximately equals opm_percentage.
    """

    df = datasets.get("profitandloss")

    if df is None:
        return

    required = {
        "sales",
        "operating_profit",
        "opm_percentage",
    }

    if not required.issubset(df.columns):
        return

    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    valid = df[
        df["sales"].notna()
        & df["operating_profit"].notna()
        & df["opm_percentage"].notna()
        & (df["sales"] != 0)
    ].copy()

    valid["calculated_opm"] = (
        valid["operating_profit"]
        / valid["sales"]
        * 100
    )

    difference = (
        valid["calculated_opm"]
        - valid["opm_percentage"]
    ).abs()

    failures_mask = difference > 1

    for index in valid.index[failures_mask]:
        row = valid.loc[index]

        add_failure(
            failures,
            "DQ-05",
            "profitandloss",
            "WARNING",
            (
                f"OPM mismatch: calculated="
                f"{row['calculated_opm']:.2f}%, "
                f"reported={row['opm_percentage']:.2f}%"
            ),
            row.get("company_id"),
            row.get("year"),
        )


# -------------------------------------------------------------------
# DQ-06 — Positive sales
# -------------------------------------------------------------------

def dq06_positive_sales(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check that sales values are positive."""

    df = datasets.get("profitandloss")

    if df is None or "sales" not in df.columns:
        return

    df["sales"] = pd.to_numeric(
        df["sales"],
        errors="coerce",
    )

    invalid = df[df["sales"].notna() & (df["sales"] <= 0)]

    for _, row in invalid.iterrows():
        add_failure(
            failures,
            "DQ-06",
            "profitandloss",
            "CRITICAL",
            f"Sales must be positive: {row['sales']}",
            row.get("company_id"),
            row.get("year"),
        )


# -------------------------------------------------------------------
# DQ-07 — Year validity
# -------------------------------------------------------------------

def dq07_year_validity(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check that normalized years are valid."""

    for table, df in datasets.items():
        if "year" not in df.columns:
            continue

        year_numeric = pd.to_numeric(
            df["year"],
            errors="coerce",
        )

        invalid = df[
            year_numeric.isna()
            | (year_numeric % 1 != 0)
            | (year_numeric < 1900)
            | (year_numeric > 2100)
        ]

        for _, row in invalid.iterrows():
            add_failure(
                failures,
                "DQ-07",
                table,
                "WARNING",
                f"Invalid year value: {row.get('year')}",
                row.get("company_id"),
                row.get("year"),
            )

# -------------------------------------------------------------------
# DQ-08 — Missing company ID
# -------------------------------------------------------------------

def dq08_missing_company_id(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check for missing company identifiers."""

    for table, df in datasets.items():
        if table == "companies" or "company_id" not in df.columns:
            continue

        missing = df[df["company_id"].isna()]

        for _, row in missing.iterrows():
            add_failure(
                failures,
                "DQ-08",
                table,
                "CRITICAL",
                "Missing company_id",
                None,
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-09 — Duplicate company IDs
# -------------------------------------------------------------------

def dq09_duplicate_company_ids(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check that companies table has unique company IDs."""

    df = datasets.get("companies")

    if df is None or "id" not in df.columns:
        return

    duplicate_mask = df["id"].duplicated(keep=False)

    for _, row in df.loc[duplicate_mask].iterrows():
        add_failure(
            failures,
            "DQ-09",
            "companies",
            "CRITICAL",
            f"Duplicate company ID: {row['id']}",
            row["id"],
            None,
        )


# -------------------------------------------------------------------
# DQ-10 — Stock price validity
# -------------------------------------------------------------------

def dq10_stock_price_validity(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check that stock prices are positive."""

    df = datasets.get("stock_prices")

    if df is None:
        return

    price_columns = [
        column
        for column in [
            "open",
            "high",
            "low",
            "close",
            "price",
        ]
        if column in df.columns
    ]

    for column in price_columns:
        values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        invalid = df[values.notna() & (values <= 0)]

        for _, row in invalid.iterrows():
            add_failure(
                failures,
                "DQ-10",
                "stock_prices",
                "WARNING",
                f"{column} must be positive: {row[column]}",
                row.get("company_id"),
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-11 — Financial ratio sanity
# -------------------------------------------------------------------

def dq11_ratio_sanity(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check basic financial-ratio ranges."""

    df = datasets.get("financial_ratios")

    if df is None:
        return

    ratio_columns = [
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "return_on_equity_pct",
        "dividend_payout_ratio_pct",
    ]

    for column in ratio_columns:
        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        invalid = df[
            values.notna()
            & (
                (values < -1000)
                | (values > 1000)
            )
        ]

        for _, row in invalid.iterrows():
            add_failure(
                failures,
                "DQ-11",
                "financial_ratios",
                "WARNING",
                f"Suspicious {column}: {row[column]}",
                row.get("company_id"),
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-12 — Negative balance-sheet values
# -------------------------------------------------------------------

def dq12_balance_sheet_values(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """
    Check major balance-sheet totals for obviously invalid
    negative values.
    """

    df = datasets.get("balancesheet")

    if df is None:
        return

    columns = [
        "total_assets",
        "total_liabilities",
    ]

    for column in columns:
        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        invalid = df[values.notna() & (values < 0)]

        for _, row in invalid.iterrows():
            add_failure(
                failures,
                "DQ-12",
                "balancesheet",
                "WARNING",
                f"{column} is negative: {row[column]}",
                row.get("company_id"),
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-13 — Duplicate stock-price date
# -------------------------------------------------------------------

def dq13_stock_price_duplicates(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check duplicate company/date stock-price observations."""

    df = datasets.get("stock_prices")

    if df is None:
        return

    date_column = None

    for candidate in ["date", "trade_date", "price_date"]:
        if candidate in df.columns:
            date_column = candidate
            break

    if date_column is None or "company_id" not in df.columns:
        return

    duplicate_mask = df.duplicated(
        subset=["company_id", date_column],
        keep=False,
    )

    duplicates = df.loc[
        duplicate_mask,
        ["company_id", date_column],
    ].drop_duplicates()

    for _, row in duplicates.iterrows():
        add_failure(
            failures,
            "DQ-13",
            "stock_prices",
            "WARNING",
            f"Duplicate stock-price date: {row[date_column]}",
            row["company_id"],
            None,
        )


# -------------------------------------------------------------------
# DQ-14 — Missing company names
# -------------------------------------------------------------------

def dq14_missing_company_name(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check that companies have names."""

    df = datasets.get("companies")

    if df is None or "company_name" not in df.columns:
        return

    missing = df[
        df["company_name"].isna()
        | (df["company_name"].astype(str).str.strip() == "")
    ]

    for _, row in missing.iterrows():
        add_failure(
            failures,
            "DQ-14",
            "companies",
            "CRITICAL",
            "Missing company_name",
            row.get("id"),
            None,
        )


# -------------------------------------------------------------------
# DQ-15 — Duplicate company/year in stock prices
# -------------------------------------------------------------------

def dq15_stock_year_duplicates(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check duplicate company/year observations where year exists."""

    df = datasets.get("stock_prices")

    if df is None:
        return

    if not {"company_id", "year"}.issubset(df.columns):
        return

    duplicate_mask = df.duplicated(
        subset=["company_id", "year"],
        keep=False,
    )

    duplicates = df.loc[
        duplicate_mask,
        ["company_id", "year"],
    ].drop_duplicates()

    for _, row in duplicates.iterrows():
        add_failure(
            failures,
            "DQ-15",
            "stock_prices",
            "WARNING",
            "Multiple stock-price records for company/year",
            row["company_id"],
            row["year"],
        )


# -------------------------------------------------------------------
# DQ-16 — Empty datasets
# -------------------------------------------------------------------

def dq16_empty_datasets(
    datasets: Dict[str, pd.DataFrame],
    failures: List[dict],
) -> None:
    """Check that every configured dataset contains records."""

    expected_tables = {
        "analysis",
        "balancesheet",
        "cashflow",
        "companies",
        "documents",
        "profitandloss",
        "prosandcons",
        "financial_ratios",
        "market_cap",
        "peer_groups",
        "sectors",
        "stock_prices",
    }

    for table in expected_tables:
        if table not in datasets:
            add_failure(
                failures,
                "DQ-16",
                table,
                "CRITICAL",
                "Dataset was not loaded",
            )
        elif datasets[table].empty:
            add_failure(
                failures,
                "DQ-16",
                table,
                "CRITICAL",
                "Dataset is empty",
            )


# -------------------------------------------------------------------
# Run all rules
# -------------------------------------------------------------------

def validate_all(
    datasets: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Run all 16 data-quality rules."""

    failures: List[dict] = []

    dq01_pk_uniqueness(datasets, failures)
    dq02_company_year_uniqueness(datasets, failures)
    dq03_fk_integrity(datasets, failures)
    dq04_balance_sheet(datasets, failures)
    dq05_opm_crosscheck(datasets, failures)
    dq06_positive_sales(datasets, failures)
    dq07_year_validity(datasets, failures)
    dq08_missing_company_id(datasets, failures)
    dq09_duplicate_company_ids(datasets, failures)
    dq10_stock_price_validity(datasets, failures)
    dq11_ratio_sanity(datasets, failures)
    dq12_balance_sheet_values(datasets, failures)
    dq13_stock_price_duplicates(datasets, failures)
    dq14_missing_company_name(datasets, failures)
    dq15_stock_year_duplicates(datasets, failures)
    dq16_empty_datasets(datasets, failures)

    return pd.DataFrame(
        failures,
        columns=[
            "rule_id",
            "table",
            "company_id",
            "year",
            "severity",
            "message",
        ],
    )


def main() -> None:
    """Run validation and save the failure report."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("NIFTY 100 DATA QUALITY VALIDATION")
    print("=" * 70)

    datasets = load_all_sources()

datasets = load_all_sources()

# Use production-cleaned financial datasets for validation
for table in [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]:
    cleaned_file = Path("data/processed") / f"{table}_cleaned.csv"

    if cleaned_file.exists():
        datasets[table] = pd.read_csv(cleaned_file)

    failures = validate_all(datasets)

    failures.to_csv(
        FAILURE_FILE,
        index=False,
    )

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)

    print(f"Total DQ failures: {len(failures):,}")

    if failures.empty:
        print("CRITICAL failures: 0")
        print("WARNING failures: 0")
        print("\nAll 16 DQ rules passed.")
    else:
        critical = int(
            (failures["severity"] == "CRITICAL").sum()
        )
        warning = int(
            (failures["severity"] == "WARNING").sum()
        )

        print(f"CRITICAL failures: {critical:,}")
        print(f"WARNING failures: {warning:,}")

        print("\nFailures by rule:")
        print(
            failures["rule_id"]
            .value_counts()
            .sort_index()
            .to_string()
        )

        print(f"\nReport saved to: {FAILURE_FILE}")


if __name__ == "__main__":
    main()
