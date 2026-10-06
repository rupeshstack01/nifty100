import pandas as pd

from src.etl.normaliser import normalize_ticker, normalize_year


KEYS = ["company_id", "year"]


def normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize company_id and year columns.
    """

    result = df.copy()

    if "company_id" in result.columns:
        result["company_id"] = (
            result["company_id"]
            .apply(normalize_ticker)
        )

    if "year" in result.columns:
        result["year"] = (
            result["year"]
            .apply(normalize_year)
        )

    return result


def find_duplicate_groups(df: pd.DataFrame) -> pd.DataFrame:
    """
    Find company-year groups containing more than one row.

    Rows with missing company_id or year are excluded because
    they cannot be reliably assigned to a canonical company-year key.
    """

    if not all(column in df.columns for column in KEYS):
        raise ValueError(
            f"Missing required columns: {KEYS}"
        )

    valid = df.dropna(subset=KEYS).copy()

    counts = (
        valid.groupby(KEYS)
        .size()
        .reset_index(name="row_count")
    )

    return counts[counts["row_count"] > 1].copy()

def classify_duplicate_group(group: pd.DataFrame) -> str:
    """
    Classify a duplicate group.

    Returns:
        EXACT_DUPLICATE
        VARIANT_DUPLICATE
    """

    comparison_columns = [
        column
        for column in group.columns
        if column not in ["id"]
    ]

    if group[comparison_columns].drop_duplicates().shape[0] == 1:
        return "EXACT_DUPLICATE"

    return "VARIANT_DUPLICATE"


def create_duplicate_audit(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create an audit table describing duplicate groups.
    """

    df = normalize_keys(df)

    duplicate_groups = find_duplicate_groups(df)

    audit_rows = []

    for _, key in duplicate_groups.iterrows():

        company_id = key["company_id"]
        year = key["year"]

        group = df[
            (df["company_id"] == company_id)
            & (df["year"] == year)
        ].copy()

        classification = classify_duplicate_group(group)

        audit_rows.append(
            {
                "company_id": company_id,
                "year": year,
                "row_count": len(group),
                "duplicate_type": classification,
            }
        )

    return pd.DataFrame(audit_rows)


def remove_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows that are completely identical
    except for technical ID.
    """

    result = normalize_keys(df)

    comparison_columns = [
        column
        for column in result.columns
        if column != "id"
    ]

    result = result.drop_duplicates(
        subset=comparison_columns,
        keep="first",
    )

    return result.reset_index(drop=True)
