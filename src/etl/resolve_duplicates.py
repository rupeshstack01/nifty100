import os
import pandas as pd

from src.etl.loader import load_all_sources


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_DIR = "data/processed"
AUDIT_DIR = "data/audit"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)


# Columns used to identify a logical record
KEY_COLUMNS = ["company_id", "year"]


# ============================================================
# HELPERS
# ============================================================

def normalize_year(df):
    """Normalize year values so 2024 and 2024.0 match."""
    df = df.copy()

    if "year" in df.columns:
        df["year"] = pd.to_numeric(
            df["year"],
            errors="coerce"
        ).astype("Int64")

    return df


def remove_exact_duplicates(df, table_name):
    """
    Remove completely identical records while preserving
    the first occurrence.
    """

    before = len(df)

    duplicate_mask = df.duplicated(
        keep="first"
    )

    removed = df.loc[
        duplicate_mask
    ].copy()

    cleaned = df.loc[
        ~duplicate_mask
    ].copy()

    after = len(cleaned)

    print()
    print("=" * 80)
    print(f"{table_name} — EXACT DUPLICATE REMOVAL")
    print("=" * 80)

    print(f"Rows before : {before}")
    print(f"Rows removed: {len(removed)}")
    print(f"Rows after  : {after}")

    return cleaned, removed


def find_duplicate_groups(df):
    """Return company-year groups having more than one row."""

    if not all(col in df.columns for col in KEY_COLUMNS):
        return pd.DataFrame()

    counts = (
        df.groupby(KEY_COLUMNS, dropna=False)
        .size()
        .reset_index(name="row_count")
    )

    return counts[counts["row_count"] > 1]


def remove_zero_variant_groups(df, table_name):
    """
    Remove an obvious zero-information variant when:

    1. A company/year has multiple records.
    2. One variant has all financial numeric fields equal to zero.
    3. Another variant contains non-zero information.

    This rule is deliberately conservative.
    """

    df = df.copy()

    duplicate_groups = find_duplicate_groups(df)

    if duplicate_groups.empty:
        return df, pd.DataFrame()

    audit_rows = []
    rows_to_remove = []

    numeric_columns = [
        col
        for col in df.columns
        if col not in KEY_COLUMNS
        and pd.api.types.is_numeric_dtype(df[col])
    ]

    for _, group in duplicate_groups.iterrows():

        company = group["company_id"]
        year = group["year"]

        mask = (
            (df["company_id"] == company)
            & (df["year"] == year)
        )

        subset = df.loc[mask].copy()

        if len(subset) < 2:
            continue

        # Number of non-zero numeric values per row
        non_zero_counts = (
            subset[numeric_columns]
            .fillna(0)
            .ne(0)
            .sum(axis=1)
        )

        zero_rows = subset[
            non_zero_counts == 0
        ]

        non_zero_rows = subset[
            non_zero_counts > 0
        ]

        # Only remove zero variant when another
        # meaningful variant exists.
        if len(zero_rows) >= 1 and len(non_zero_rows) >= 1:

            for idx in zero_rows.index:

                rows_to_remove.append(idx)

                audit_rows.append({
                    "table": table_name,
                    "company_id": company,
                    "year": year,
                    "removed_index": idx,
                    "reason": "ZERO_INFORMATION_VARIANT"
                })

    cleaned = df.drop(
        index=rows_to_remove
    ).copy()

    audit = pd.DataFrame(audit_rows)

    print()
    print("=" * 80)
    print(f"{table_name} — ZERO VARIANT REMOVAL")
    print("=" * 80)

    print(f"Rows removed: {len(rows_to_remove)}")

    return cleaned, audit


def create_ambiguous_variant_report(df, table_name):
    """
    Create an audit report for duplicate company/year records
    that remain after safe cleaning.

    These are NOT automatically deleted.
    """

    duplicate_groups = find_duplicate_groups(df)

    records = []

    for _, group in duplicate_groups.iterrows():

        company = group["company_id"]
        year = group["year"]

        mask = (
            (df["company_id"] == company)
            & (df["year"] == year)
        )

        subset = df.loc[mask].copy()

        for idx, row in subset.iterrows():

            record = {
                "table": table_name,
                "company_id": company,
                "year": year,
                "row_index": idx
            }

            for col in df.columns:
                if col not in KEY_COLUMNS:
                    record[col] = row[col]

            records.append(record)

    return pd.DataFrame(records)


# ============================================================
# MAIN PROCESS
# ============================================================

def main():

    print()
    print("=" * 80)
    print("NIFTY100 DATA CLEANING PIPELINE")
    print("=" * 80)

    data = load_all_sources()

    all_audits = []
    ambiguous_reports = []

    # --------------------------------------------------------
    # TABLES TO CLEAN
    # --------------------------------------------------------

    tables = [
        "profitandloss",
        "cashflow",
        "balancesheet",
        "financial_ratios",
    ]

    for table_name in tables:

        print()
        print("#" * 80)
        print(f"PROCESSING: {table_name}")
        print("#" * 80)

        df = data[table_name].copy()

        # Normalize year
        df = normalize_year(df)

        # ----------------------------------------------------
        # 1. Remove exact duplicates
        # ----------------------------------------------------

        df, exact_removed = remove_exact_duplicates(
            df,
            table_name
        )

        if not exact_removed.empty:

            exact_removed = exact_removed.copy()

            exact_removed["table"] = table_name
            exact_removed["reason"] = "EXACT_DUPLICATE"

            all_audits.append(
                exact_removed
            )

        # ----------------------------------------------------
        # 2. Remove obvious zero variants
        # ----------------------------------------------------

        df, zero_audit = remove_zero_variant_groups(
            df,
            table_name
        )

        if not zero_audit.empty:
            all_audits.append(
                zero_audit
            )

        # ----------------------------------------------------
        # 3. Find remaining ambiguous variants
        # ----------------------------------------------------

        ambiguous = create_ambiguous_variant_report(
            df,
            table_name
        )

        if not ambiguous.empty:

            ambiguous_reports.append(
                ambiguous
            )

        # ----------------------------------------------------
        # 4. Save cleaned table
        # ----------------------------------------------------

        output_path = os.path.join(
            OUTPUT_DIR,
            f"{table_name}_cleaned.csv"
        )

        df.to_csv(
            output_path,
            index=False
        )

        print()
        print(f"Saved: {output_path}")
        print(f"Final rows: {len(df)}")

    # ========================================================
    # SAVE AUDIT LOG
    # ========================================================

    if all_audits:

        audit_frames = []

        for audit in all_audits:

            audit_frames.append(
                audit.copy()
            )

        audit_df = pd.concat(
            audit_frames,
            ignore_index=True
        )

        audit_path = os.path.join(
            AUDIT_DIR,
            "duplicate_removal_audit.csv"
        )

        audit_df.to_csv(
            audit_path,
            index=False
        )

        print()
        print("=" * 80)
        print("AUDIT LOG")
        print("=" * 80)

        print(
            audit_df[
                ["table", "reason"]
            ]
            .value_counts()
        )

        print()
        print(f"Saved: {audit_path}")

    # ========================================================
    # SAVE AMBIGUOUS VARIANTS
    # ========================================================

    if ambiguous_reports:

        ambiguous_df = pd.concat(
            ambiguous_reports,
            ignore_index=True
        )

        ambiguous_path = os.path.join(
            AUDIT_DIR,
            "ambiguous_duplicate_variants.csv"
        )

        ambiguous_df.to_csv(
            ambiguous_path,
            index=False
        )

        print()
        print("=" * 80)
        print("AMBIGUOUS VARIANTS")
        print("=" * 80)

        print(
            ambiguous_df[
                ["table", "company_id", "year"]
            ]
            .drop_duplicates()
            .to_string(index=False)
        )

        print()
        print(
            f"Saved: {ambiguous_path}"
        )

    print()
    print("=" * 80)
    print("CLEANING PIPELINE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
