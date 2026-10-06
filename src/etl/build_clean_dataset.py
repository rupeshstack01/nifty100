import os
import pandas as pd

from src.etl.loader import load_all_sources
from src.etl.deduplicator import normalize_keys, classify_duplicate_group


TABLES_TO_PROCESS = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


OUTPUT_DIR = "data/processed"
AUDIT_DIR = os.path.join(OUTPUT_DIR, "audit")
REVIEW_DIR = os.path.join(OUTPUT_DIR, "review")


def classify_groups(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify duplicate company-year groups and classify them
    as EXACT_DUPLICATE or VARIANT_DUPLICATE.
    """

    rows = []

    valid = df.dropna(subset=["company_id", "year"]).copy()

    grouped = valid.groupby(
        ["company_id", "year"],
        dropna=False
    )

    for (company_id, year), group in grouped:

        if len(group) <= 1:
            continue

        duplicate_type = classify_duplicate_group(group)

        differing_columns = []

        comparison_columns = [
            column
            for column in group.columns
            if column not in ["id"]
        ]

        for column in comparison_columns:

            values = (
                group[column]
                .astype(str)
                .fillna("<NA>")
                .unique()
            )

            if len(values) > 1:
                differing_columns.append(column)

        rows.append(
            {
                "company_id": company_id,
                "year": year,
                "row_count": len(group),
                "duplicate_type": duplicate_type,
                "differing_columns": ", ".join(differing_columns),
            }
        )

    return pd.DataFrame(rows)


def process_table(table_name: str, df: pd.DataFrame):

    print("\n" + "=" * 100)
    print(f"BUILD CLEAN DATASET — {table_name.upper()}")
    print("=" * 100)

    original_rows = len(df)

    # ---------------------------------------------------------
    # 1. Normalize keys
    # ---------------------------------------------------------

    df = normalize_keys(df)

    normalized_rows = len(df)

    # ---------------------------------------------------------
    # 2. Classify duplicate groups
    # ---------------------------------------------------------

    audit = classify_groups(df)

    if audit.empty:

        print("No duplicate company-year groups found.")

        cleaned = df.copy()
        review = pd.DataFrame()

    else:

        exact_groups = audit[
            audit["duplicate_type"] == "EXACT_DUPLICATE"
        ]

        variant_groups = audit[
            audit["duplicate_type"] == "VARIANT_DUPLICATE"
        ]

        # -----------------------------------------------------
        # 3. Remove exact duplicate rows only
        # -----------------------------------------------------

        cleaned = df.drop_duplicates(
            subset=[
                column
                for column in df.columns
                if column != "id"
            ],
            keep="first",
        ).copy()

        # -----------------------------------------------------
        # 4. Extract variant groups for manual review
        # -----------------------------------------------------

        review_keys = variant_groups[
            ["company_id", "year"]
        ].copy()

        if not review_keys.empty:

            review = df.merge(
                review_keys,
                on=["company_id", "year"],
                how="inner",
            ).copy()

            review.insert(
                0,
                "review_status",
                "REVIEW_REQUIRED",
            )

        else:

            review = pd.DataFrame()

        print(f"Original rows: {original_rows}")
        print(f"Normalized rows: {normalized_rows}")
        print(f"Exact duplicate groups: {len(exact_groups)}")
        print(f"Variant duplicate groups: {len(variant_groups)}")
        print(f"Rows after exact duplicate removal: {len(cleaned)}")

    # ---------------------------------------------------------
    # 5. Save cleaned dataset
    # ---------------------------------------------------------

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    os.makedirs(REVIEW_DIR, exist_ok=True)

    cleaned_path = os.path.join(
        OUTPUT_DIR,
        f"{table_name}_cleaned.csv",
    )

    cleaned.to_csv(
        cleaned_path,
        index=False,
    )

    # ---------------------------------------------------------
    # 6. Save duplicate audit
    # ---------------------------------------------------------

    audit_path = os.path.join(
        AUDIT_DIR,
        f"{table_name}_duplicate_audit.csv",
    )

    audit.to_csv(
        audit_path,
        index=False,
    )

    # ---------------------------------------------------------
    # 7. Save variant review file
    # ---------------------------------------------------------

    review_path = os.path.join(
        REVIEW_DIR,
        f"{table_name}_variant_review.csv",
    )

    review.to_csv(
        review_path,
        index=False,
    )

    print(f"Cleaned dataset: {cleaned_path}")
    print(f"Audit report:    {audit_path}")
    print(f"Review file:     {review_path}")

    return {
        "table": table_name,
        "original_rows": original_rows,
        "normalized_rows": normalized_rows,
        "cleaned_rows": len(cleaned),
        "duplicate_groups": len(audit),
        "variant_groups": (
            len(audit[
                audit["duplicate_type"] == "VARIANT_DUPLICATE"
            ])
            if not audit.empty
            else 0
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
