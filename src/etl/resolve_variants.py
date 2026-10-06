"""
Resolve duplicate company-year records into identifiable variants.

This module does NOT delete or overwrite records.

It:
1. Normalizes company_id and year.
2. Finds duplicate company-year groups.
3. Creates a fingerprint from financial columns.
4. Distinguishes exact duplicates from different variants.
5. Assigns variant IDs.
6. Produces a diagnostic report.
"""

from src.etl.loader import load_all_sources
from src.etl.normaliser import normalize_ticker, normalize_year

import hashlib
import pandas as pd


KEYS = ["company_id", "year"]

TABLES_TO_CHECK = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]


def normalize_value(value):
    """Convert a value into a stable representation for fingerprinting."""

    if pd.isna(value):
        return "<NA>"

    if isinstance(value, float):
        return f"{value:.10g}"

    return str(value).strip()


def create_fingerprint(row, columns):
    """
    Create a stable hash from all comparison columns.

    Technical 'id' is deliberately excluded.
    """

    values = []

    for column in columns:
        values.append(
            f"{column}={normalize_value(row[column])}"
        )

    payload = "|".join(values)

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:16]


def prepare_dataframe(df):
    """Normalize company and year."""

    df = df.copy()

    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].apply(
            normalize_ticker
        )

    if "year" in df.columns:
        df["year"] = df["year"].apply(
            normalize_year
        )

    return df


def get_comparison_columns(df):
    """
    Return columns used to determine whether two records
    represent the same variant.

    Technical ID is excluded.
    """

    return [
        column
        for column in df.columns
        if column not in ["id"]
    ]


def classify_group(group):
    """
    Classify a duplicate company-year group.

    Returns:
        EXACT_DUPLICATE
        MULTIPLE_VARIANTS
    """

    comparison_columns = get_comparison_columns(group)

    fingerprints = set()

    for _, row in group.iterrows():
        fingerprint = create_fingerprint(
            row,
            comparison_columns,
        )
        fingerprints.add(fingerprint)

    if len(fingerprints) == 1:
        return "EXACT_DUPLICATE", fingerprints

    return "MULTIPLE_VARIANTS", fingerprints


def inspect_table(name, df):
    """Inspect duplicate variants for one table."""

    print("\n" + "=" * 100)
    print(f"VARIANT RESOLUTION ANALYSIS — {name.upper()}")
    print("=" * 100)

    df = prepare_dataframe(df)

    if not all(column in df.columns for column in KEYS):
        print(f"Missing required columns: {KEYS}")
        return pd.DataFrame()

    counts = (
        df.groupby(KEYS, dropna=False)
        .size()
        .reset_index(name="row_count")
    )

    duplicates = counts[
        counts["row_count"] > 1
    ]

    if duplicates.empty:
        print("No duplicate company-year groups found.")
        return pd.DataFrame()

    print(
        f"Duplicate company-year groups: "
        f"{len(duplicates)}"
    )

    results = []

    for _, duplicate in duplicates.iterrows():

        company = duplicate["company_id"]
        year = duplicate["year"]

        subset = df[
            (df["company_id"] == company)
            & (df["year"] == year)
        ].copy()

        classification, fingerprints = classify_group(
            subset
        )

        print("\n" + "-" * 100)
        print(
            f"{company} — "
            f"{int(year) if pd.notna(year) else year}"
        )
        print("-" * 100)

        print(f"Rows: {len(subset)}")
        print(f"Classification: {classification}")
        print(f"Unique variants: {len(fingerprints)}")

        comparison_columns = get_comparison_columns(
            subset
        )

        # Assign variant numbers based on fingerprint.
        fingerprint_to_variant = {}

        for row_index, row in subset.iterrows():

            fingerprint = create_fingerprint(
                row,
                comparison_columns,
            )

            if fingerprint not in fingerprint_to_variant:
                fingerprint_to_variant[fingerprint] = (
                    len(fingerprint_to_variant) + 1
                )

            variant_id = fingerprint_to_variant[
                fingerprint
            ]

            subset.loc[
                row_index,
                "variant_id"
            ] = variant_id

        display_columns = [
            column
            for column in [
                "id",
                "company_id",
                "year",
                "variant_id",
            ]
            if column in subset.columns
        ]

        print(
            subset[
                display_columns
            ].to_string(index=False)
        )

        # Show differences when multiple variants exist.
        if classification == "MULTIPLE_VARIANTS":

            differing_columns = []

            for column in comparison_columns:

                unique_values = (
                    subset[column]
                    .astype(str)
                    .unique()
                )

                if len(unique_values) > 1:
                    differing_columns.append(
                        column
                    )

            print("\nDIFFERING COLUMNS:")

            for column in differing_columns:

                values = (
                    subset[column]
                    .tolist()
                )

                print(
                    f"  {column}: {values}"
                )

        for fingerprint, variant_number in (
            fingerprint_to_variant.items()
        ):

            variant_rows = subset[
                subset.apply(
                    lambda row:
                    create_fingerprint(
                        row,
                        comparison_columns,
                    ) == fingerprint,
                    axis=1,
                )
            ]

            results.append(
                {
                    "table": name,
                    "company_id": company,
                    "year": year,
                    "variant_id": variant_number,
                    "row_count": len(variant_rows),
                    "classification": classification,
                    "fingerprint": fingerprint,
                    "source_ids": ",".join(
                        variant_rows["id"]
                        .astype(str)
                        .tolist()
                    )
                    if "id" in variant_rows.columns
                    else "",
                }
            )

    return pd.DataFrame(results)


def main():

    print("\nLoading all sources...\n")

    data = load_all_sources()

    all_results = []

    for table_name in TABLES_TO_CHECK:

        if table_name not in data:
            print(
                f"\nTable not found: "
                f"{table_name}"
            )
            continue

        result = inspect_table(
            table_name,
            data[table_name],
        )

        if not result.empty:
            all_results.append(result)

    print("\n" + "=" * 100)
    print("VARIANT RESOLUTION SUMMARY")
    print("=" * 100)

    if not all_results:
        print("No duplicate variants found.")
        return

    final_result = pd.concat(
        all_results,
        ignore_index=True,
    )

    print("\nVariants by table:")
    print(
        final_result.groupby(
            "table"
        )["variant_id"]
        .count()
        .to_string()
    )

    print("\nClassification:")
    print(
        final_result.groupby(
            ["table", "classification"]
        )["variant_id"]
        .count()
        .to_string()
    )

    print("\nDetailed variant map:")
    print(
        final_result.to_string(
            index=False
        )
    )

    # Save diagnostic output.
    output_path = (
        "variant_resolution_report.csv"
    )

    final_result.to_csv(
        output_path,
        index=False,
    )

    print(
        f"\nSaved variant report to: "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()
