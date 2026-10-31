import os
import pandas as pd

from src.etl.loader import load_all_sources
from src.etl.canonical_resolver import normalize_keys, resolve_table


TABLES_TO_PROCESS = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


OUTPUT_DIR = os.environ.get("CLEAN_DATASET_OUTPUT_DIR", "data/processed")
AUDIT_DIR = os.path.join(OUTPUT_DIR, "audit")
REVIEW_DIR = os.path.join(OUTPUT_DIR, "review")


def process_table(table_name: str, df: pd.DataFrame):
    """Resolve duplicates by company and canonical reporting period."""

    print("\\n" + "=" * 100)
    print(f"BUILD CLEAN DATASET — {table_name.upper()}")
    print("=" * 100)

    original_rows = len(df)

    # The resolver removes exact duplicates only within the same period.
    result = resolve_table(table_name, df)
    cleaned = result["cleaned"].copy()
    audit = result["audit"].copy()
    variant_review = result["variant_review"].copy()

    keys = ["company_id", "year", "_canonical_period_key"]

    # Add review details to the group-level audit.
    if not audit.empty:
        if not variant_review.empty:
            details = variant_review[
                keys + ["differing_columns", "resolution"]
            ].copy()
            audit = audit.merge(details, on=keys, how="left")
        else:
            audit["differing_columns"] = ""
            audit["resolution"] = ""

        audit["differing_columns"] = audit["differing_columns"].fillna("")
        audit["resolution"] = audit["resolution"].fillna("")
        audit.rename(
            columns={"_canonical_period_key": "canonical_reporting_period"},
            inplace=True,
        )

    # Expand conflicting groups into their original row-level records.
    if not variant_review.empty:
        normalized = normalize_keys(df)
        review_keys = variant_review[
            keys + ["differing_columns", "resolution"]
        ].copy()

        review = normalized.merge(
            review_keys,
            on=keys,
            how="inner",
        )
        review.rename(
            columns={"_canonical_period_key": "canonical_reporting_period"},
            inplace=True,
        )
        review.insert(0, "review_status", "REVIEW_REQUIRED")
    else:
        # Keep a valid CSV schema even when there are no conflict rows.
        review = normalize_keys(df).iloc[0:0].copy()
        review["differing_columns"] = pd.Series(dtype="object")
        review["resolution"] = pd.Series(dtype="object")
        review.rename(
            columns={"_canonical_period_key": "canonical_reporting_period"},
            inplace=True,
        )
        review.insert(0, "review_status", pd.Series(dtype="object"))

    print(f"Original rows: {original_rows}")
    print(f"Rows after exact duplicate removal: {len(cleaned)}")
    print(f"Duplicate groups: {len(audit)}")
    print(
        "Variant groups requiring review: "
        f"{int((audit['duplicate_type'] == 'VARIANT_DUPLICATE').sum()) if not audit.empty else 0}"
    )

    # All paths are configurable for safe testing.
    audit_dir = os.path.join(OUTPUT_DIR, "audit")
    review_dir = os.path.join(OUTPUT_DIR, "review")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(audit_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)

    cleaned_path = os.path.join(OUTPUT_DIR, f"{table_name}_cleaned.csv")
    audit_path = os.path.join(audit_dir, f"{table_name}_duplicate_audit.csv")
    review_path = os.path.join(review_dir, f"{table_name}_variant_review.csv")

    cleaned.to_csv(cleaned_path, index=False)
    audit.to_csv(audit_path, index=False)
    review.to_csv(review_path, index=False)

    print(f"Cleaned dataset: {cleaned_path}")
    print(f"Audit report:    {audit_path}")
    print(f"Review file:     {review_path}")

    return {
        "table": table_name,
        "original_rows": original_rows,
        "normalized_rows": original_rows,
        "cleaned_rows": len(cleaned),
        "duplicate_groups": (
            int((audit["duplicate_type"] == "EXACT_DUPLICATE").sum())
            if not audit.empty else 0
        ),
        "total_audit_groups": len(audit),
        "variant_groups": (
            int((audit["duplicate_type"] == "VARIANT_DUPLICATE").sum())
            if not audit.empty else 0
        ),
    }


def main():

    print("=" * 100)
    print("BUILDING PRODUCTION CLEAN DATASETS")
    print("=" * 100)

    data = load_all_sources()

    summary = []

    for table_name in TABLES_TO_PROCESS:

        if table_name not in data:

            print(
                f"\nWARNING: Table not found: {table_name}"
            )

            continue

        result = process_table(
            table_name,
            data[table_name],
        )

        summary.append(result)

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    summary_df = pd.DataFrame(summary)

    summary_path = os.path.join(
        AUDIT_DIR,
        "cleaning_summary.csv",
    )

    summary_df.to_csv(
        summary_path,
        index=False,
    )

    print("\n" + "=" * 100)
    print("CLEANING SUMMARY")
    print("=" * 100)

    print(
        summary_df.to_string(index=False)
    )

    print("\nSummary saved to:")
    print(summary_path)


if __name__ == "__main__":
    main()
