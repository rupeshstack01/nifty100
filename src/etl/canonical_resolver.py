"""
Canonical record resolver for financial ETL data.

Purpose:
    Resolve duplicate company-year records conservatively.

Rules:
    1. Exact duplicates are reduced to one record.
    2. Variant duplicates are NOT blindly deleted.
    3. Variant groups are classified as:
         - RESOLVED
         - REVIEW_REQUIRED
    4. A variant is resolved only when a deterministic rule gives
       sufficient evidence.
    5. Unresolved variants are preserved in an audit table.
"""

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


def normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize company_id and year before duplicate resolution.
    """

    result = df.copy()

    result["company_id"] = result["company_id"].apply(normalize_ticker)
    result["year"] = result["year"].apply(normalize_year)

    return result


def classify_group(group: pd.DataFrame) -> str:
    """
    Determine whether a duplicate group is exact or variant.

    id is excluded because different technical IDs do not make
    otherwise identical financial records different.
    """

    comparison_columns = [
        column for column in group.columns
        if column not in ["id"]
    ]

    if group[comparison_columns].drop_duplicates().shape[0] == 1:
        return "EXACT_DUPLICATE"

    return "VARIANT_DUPLICATE"


def remove_exact_duplicates(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Remove exact duplicate records.

    Returns:
        cleaned dataframe
        duplicate audit dataframe
    """

    df = normalize_keys(df)

    audit_rows = []

    for (company_id, year), group in df.groupby(
        KEYS,
        dropna=False,
        sort=True,
    ):
        if len(group) <= 1:
            continue

        duplicate_type = classify_group(group)

        audit_rows.append(
            {
                "company_id": company_id,
                "year": year,
                "row_count": len(group),
                "duplicate_type": duplicate_type,
            }
        )

    audit = pd.DataFrame(audit_rows)

    # Remove only exact duplicate records.
    comparison_columns = [
        column for column in df.columns
        if column != "id"
    ]

    cleaned = df.drop_duplicates(
        subset=comparison_columns,
        keep="first",
    ).copy()

    return cleaned, audit


def build_variant_review(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build an audit table containing unresolved variant duplicates.

    No variant record is deleted here.
    """

    df = normalize_keys(df)

    review_rows = []

    for (company_id, year), group in df.groupby(
        KEYS,
        dropna=False,
        sort=True,
    ):
        if len(group) <= 1:
            continue

        duplicate_type = classify_group(group)

        if duplicate_type != "VARIANT_DUPLICATE":
            continue

        comparison_columns = [
            column for column in group.columns
            if column not in ["id"]
        ]

        differing_columns = []

        for column in comparison_columns:
            values = group[column].astype(str).fillna("<NA>").unique()

            if len(values) > 1:
                differing_columns.append(column)

        review_rows.append(
            {
                "company_id": company_id,
                "year": year,
                "row_count": len(group),
                "duplicate_type": duplicate_type,
                "differing_columns": ", ".join(differing_columns),
                "resolution": "REVIEW_REQUIRED",
            }
        )

    return pd.DataFrame(review_rows)


def resolve_table(
    name: str,
    df: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Resolve one table conservatively.

    Exact duplicates are removed.

    Variant duplicates are retained and separately reported.
    """

    print("\n" + "=" * 100)
    print(f"CANONICAL RESOLUTION — {name.upper()}")
    print("=" * 100)

    original_rows = len(df)

    cleaned, audit = remove_exact_duplicates(df)

    variant_review = build_variant_review(cleaned)

    exact_count = 0
    variant_count = 0

    if not audit.empty:
        exact_count = int(
            (audit["duplicate_type"] == "EXACT_DUPLICATE").sum()
        )

        variant_count = int(
            (audit["duplicate_type"] == "VARIANT_DUPLICATE").sum()
        )

    print(f"Original rows: {original_rows}")
    print(f"Rows after exact duplicate removal: {len(cleaned)}")
    print(f"Exact duplicate groups: {exact_count}")
    print(f"Variant duplicate groups: {variant_count}")

    if not variant_review.empty:
        print("\nVARIANT GROUPS REQUIRING REVIEW:")

        print(
            variant_review.head(20).to_string(index=False)
        )

        if len(variant_review) > 20:
            print(
                f"\n... showing first 20 of "
                f"{len(variant_review)} variant groups ..."
            )
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
    """
    Resolve all financial tables.
    """

    results = {}

    for table_name in TABLES_TO_RESOLVE:

        if table_name not in data:
            print(f"\nTable not found: {table_name}")
            continue

        results[table_name] = resolve_table(
            table_name,
            data[table_name],
        )

    return results
