"""
Variant duplicate resolution utilities.

Exact duplicates are removed automatically.

Variant duplicates are NOT automatically deleted unless
there is sufficient deterministic evidence to select one record.

Resolution states:
    AUTO_RESOLVED
    REVIEW_REQUIRED
"""

from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REVIEW_DIR = PROCESSED_DIR / "review"
AUDIT_DIR = PROCESSED_DIR / "audit"

TABLES = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]

GROUP_KEYS = ["company_id", "year"]


def completeness_score(row):
    """
    Count non-null business-data values.

    Technical/audit columns are excluded because they
    should not influence financial-data quality.
    """

    excluded = {
        "id",
        "review_status",
    }

    values = row.drop(labels=[
        col for col in excluded
        if col in row.index
    ])

    return int(values.notna().sum())


def check_balance_sheet(row):
    """
    Check basic balance-sheet consistency.

    total_assets should equal total_liabilities.
    """

    try:
        assets = float(row["total_assets"])
        liabilities = float(row["total_liabilities"])

        return int(abs(assets - liabilities) < 0.01)

    except (KeyError, TypeError, ValueError):
        return 0


def check_cashflow(row):
    """
    Check basic cash-flow arithmetic.

    operating + investing + financing
    should equal net cash flow.
    """

    try:
        operating = float(row["operating_activity"])
        investing = float(row["investing_activity"])
        financing = float(row["financing_activity"])
        net_cash = float(row["net_cash_flow"])

        calculated = operating + investing + financing

        return int(abs(calculated - net_cash) < 0.01)

    except (KeyError, TypeError, ValueError):
        return 0


def score_balance_sheet(df):
    """Calculate balance-sheet quality scores."""

    df = df.copy()

    df["completeness_score"] = df.apply(
        completeness_score,
        axis=1
    )

    df["accounting_consistency"] = df.apply(
        check_balance_sheet,
        axis=1
    )

    df["resolution_score"] = (
        df["accounting_consistency"] * 100
        + df["completeness_score"]
    )

    return df


def score_cashflow(df):
    """Calculate cash-flow quality scores."""

    df = df.copy()

    df["completeness_score"] = df.apply(
        completeness_score,
        axis=1
    )

    df["cashflow_consistency"] = df.apply(
        check_cashflow,
        axis=1
    )

    df["resolution_score"] = (
        df["cashflow_consistency"] * 100
        + df["completeness_score"]
    )

    return df


def score_generic(df):
    """Calculate generic completeness scores."""

    df = df.copy()

    df["completeness_score"] = df.apply(
        completeness_score,
        axis=1
    )

    df["resolution_score"] = df["completeness_score"]

    return df


def classify_resolution(group):
    """
    Decide whether a variant group can be automatically resolved.

    A group is automatically resolved only when there is a
    unique highest-scoring record.

    Ties remain REVIEW_REQUIRED.
    """

    group = group.copy()

    max_score = group["resolution_score"].max()

    winners = group[
        group["resolution_score"] == max_score
    ]

    if len(winners) == 1:

        group["resolution_status"] = "AUTO_RESOLVED"
        group["resolution_reason"] = "UNIQUE_HIGHER_SCORE"

        group["selected_record"] = (
            group.index == winners.index[0]
        )

    else:

        group["resolution_status"] = "REVIEW_REQUIRED"
        group["resolution_reason"] = (
            "TIED_SCORE_OR_INSUFFICIENT_EVIDENCE"
        )

        group["selected_record"] = False

    return group


def resolve_groups(df):
    """
    Apply resolution logic independently to every
    company-year variant group.
    """

    if df.empty:
        return df

    resolved_groups = []

    for _, group in df.groupby(
        GROUP_KEYS,
        dropna=False
    ):

        resolved = classify_resolution(group)

        resolved_groups.append(resolved)

    if not resolved_groups:
        return df

    return pd.concat(
        resolved_groups,
        ignore_index=True
    )


def inspect_variants(table_name):
    """
    Load, score and classify variant records.
    """

    review_file = (
        REVIEW_DIR /
        f"{table_name}_variant_review.csv"
    )

    if not review_file.exists():

        print(
            f"Review file not found: {review_file}"
        )

        return None

    if review_file.stat().st_size == 0:

        print(
            f"{table_name}: review file is empty."
        )

        return pd.DataFrame()

    try:

        df = pd.read_csv(review_file)

    except pd.errors.EmptyDataError:

        print(
            f"{table_name}: no variant records found."
        )

        return pd.DataFrame()

    if df.empty:

        print(
            f"{table_name}: no variant records found."
        )

        return df

    # Score records according to table type.

    if table_name == "balancesheet":

        df = score_balance_sheet(df)

    elif table_name == "cashflow":

        df = score_cashflow(df)

    else:

        df = score_generic(df)

    # Resolve each company-year group.

    df = resolve_groups(df)

    return df


def save_resolution_audit(table_name, df):

    """Save complete resolution audit."""

    output_file = (
        AUDIT_DIR /
        f"{table_name}_variant_resolution_audit.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(
        f"Saved: {output_file}"
    )


def print_resolution_summary(table_name, df):

    """Print resolution summary."""

    print("\nResolution status:")

    print(
        df["resolution_status"]
        .value_counts()
        .to_string()
    )

    print("\nResolution reasons:")

    print(
        df["resolution_reason"]
        .value_counts()
        .to_string()
    )


def main():

    print("=" * 100)
    print("VARIANT DUPLICATE RESOLUTION AUDIT")
    print("=" * 100)

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    for table_name in TABLES:

        print("\n" + "=" * 100)
        print(
            f"TABLE: {table_name.upper()}"
        )
        print("=" * 100)

        df = inspect_variants(table_name)

        if df is None or df.empty:
            continue

        print(
            f"Variant records: {len(df)}"
        )

        print("\nResolution score statistics:")

        print(
            df["resolution_score"].describe()
        )

        print_resolution_summary(
            table_name,
            df
        )

        save_resolution_audit(
            table_name,
            df
        )


if __name__ == "__main__":
    main()
