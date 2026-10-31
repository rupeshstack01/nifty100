"""Conservative, reporting-period-aware resolver for financial ETL data."""

import re
from typing import Dict, Tuple

import pandas as pd

from src.etl.normaliser import normalize_ticker, normalize_year

KEYS = ["company_id", "year"]

TABLES_TO_RESOLVE = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def canonical_period(value):
    """Create a matching key without changing the original period label."""
    if pd.isna(value):
        return "<MISSING_PERIOD>"

    text = str(value).strip()
    if not text:
        return "<MISSING_PERIOD>"

    match = re.fullmatch(
        r"(?i)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[- /]+(\d{2}|\d{4})",
        text,
    )
    if match:
        month = match.group(1).title()
        year_text = match.group(2)
        year = int(year_text)

        if len(year_text) == 2:
            year = 2000 + year if year <= 50 else 1900 + year

        return f"{month} {year:04d}"

    return text.casefold()


def normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize company/year and derive a period-aware matching key."""
    result = df.copy()

    if "company_id" in result.columns:
        result["company_id"] = result["company_id"].apply(normalize_ticker)

    if "reporting_period" not in result.columns and "year" in result.columns:
        result["reporting_period"] = result["year"].astype("string").str.strip()

    if "year" in result.columns:
        result["year"] = result["year"].apply(normalize_year)

    if "reporting_period" in result.columns:
        result["_canonical_period_key"] = result["reporting_period"].apply(
            canonical_period
        )
    elif "year" in result.columns:
        result["_canonical_period_key"] = result["year"].apply(
            lambda value: str(value) if pd.notna(value) else "<MISSING_PERIOD>"
        )
    else:
        result["_canonical_period_key"] = "<MISSING_PERIOD>"

    return result


def group_keys(df: pd.DataFrame):
    keys = [key for key in KEYS if key in df.columns]
    if "_canonical_period_key" in df.columns:
        keys.append("_canonical_period_key")
    return keys


def comparison_columns(df: pd.DataFrame):
    excluded = {"id", "reporting_period", "_canonical_period_key"}
    return [column for column in df.columns if column not in excluded]


def classify_group(group: pd.DataFrame) -> str:
    columns = comparison_columns(group)
    if group[columns].drop_duplicates().shape[0] == 1:
        return "EXACT_DUPLICATE"
    return "VARIANT_DUPLICATE"


def remove_exact_duplicates(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Remove only duplicate financial records within the same canonical period."""
    df = normalize_keys(df)
    keys = group_keys(df)
    audit_rows = []

    for group_key, group in df.groupby(keys, dropna=False, sort=False):
        if len(group) <= 1:
            continue

        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        entry = dict(zip(keys, group_key))
        entry["row_count"] = len(group)
        entry["duplicate_type"] = classify_group(group)
        audit_rows.append(entry)

    audit = pd.DataFrame(audit_rows)

    financial_columns = comparison_columns(df)
    subset = list(dict.fromkeys(keys + financial_columns))
    cleaned = df.drop_duplicates(subset=subset, keep="first").copy()
    cleaned.drop(
        columns=["_canonical_period_key"], inplace=True, errors="ignore"
    )

    return cleaned, audit


def build_variant_review(df: pd.DataFrame) -> pd.DataFrame:
    """List conflicting records for review; do not choose a winner automatically."""
    df = normalize_keys(df)
    keys = group_keys(df)
    columns = comparison_columns(df)
    review_rows = []

    for group_key, group in df.groupby(keys, dropna=False, sort=False):
        if len(group) <= 1 or classify_group(group) != "VARIANT_DUPLICATE":
            continue

        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        entry = dict(zip(keys, group_key))
        differing = []

        for column in columns:
            values = group[column].astype("string").fillna("<NA>").unique()
            if len(values) > 1:
                differing.append(column)

        entry.update({
            "row_count": len(group),
            "duplicate_type": "VARIANT_DUPLICATE",
            "differing_columns": ", ".join(differing),
            "resolution": "REVIEW_REQUIRED",
        })
        review_rows.append(entry)

    return pd.DataFrame(review_rows)


def resolve_table(name: str, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    print("\n" + "=" * 100)
    print(f"CANONICAL RESOLUTION — {name.upper()}")
    print("=" * 100)

    cleaned, audit = remove_exact_duplicates(df)
    variant_review = build_variant_review(cleaned)

    exact_count = (
        int((audit["duplicate_type"] == "EXACT_DUPLICATE").sum())
        if not audit.empty else 0
    )
    variant_count = (
        int((audit["duplicate_type"] == "VARIANT_DUPLICATE").sum())
        if not audit.empty else 0
    )

    print(f"Original rows: {len(df)}")
    print(f"Rows after exact duplicate removal: {len(cleaned)}")
    print(f"Exact duplicate groups: {exact_count}")
    print(f"Variant duplicate groups: {variant_count}")

    if not variant_review.empty:
        print("\nVARIANT GROUPS REQUIRING REVIEW:")
        print(variant_review.head(20).to_string(index=False))
        if len(variant_review) > 20:
            print(f"... first 20 of {len(variant_review)} groups shown ...")
    else:
        print("\nNo unresolved variant duplicates.")

    return {
        "cleaned": cleaned,
        "audit": audit,
        "variant_review": variant_review,
    }


def resolve_all(
    data: Dict[str, pd.DataFrame],
) -> Dict[str, Dict[str, pd.DataFrame]]:
    results = {}

    for table_name in TABLES_TO_RESOLVE:
        if table_name not in data:
            print(f"\nTable not found: {table_name}")
            continue
        results[table_name] = resolve_table(table_name, data[table_name])

    return results
