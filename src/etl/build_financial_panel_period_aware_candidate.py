"""Build a reporting-period-aware financial panel in an isolated output directory."""

import os
from pathlib import Path

import pandas as pd

from src.etl.canonical_resolver import normalize_keys

INPUT_DIR = Path(
    os.environ.get(
        "CLEAN_DATASET_INPUT_DIR",
        "/tmp/nifty100_period_aware_test",
    )
)
OUTPUT_DIR = Path(
    os.environ.get(
        "FINANCIAL_PANEL_OUTPUT_DIR",
        "/tmp/nifty100_period_aware_test/analytical",
    )
)

TABLES = [
    "profitandloss",
    "cashflow",
    "balancesheet",
    "financial_ratios",
]

KEYS = ["company_id", "year", "_canonical_period_key"]


def load_table(table_name):
    path = INPUT_DIR / f"{table_name}_cleaned.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")

    df = pd.read_csv(path)
    df = normalize_keys(df)

    df["company_id"] = df["company_id"].astype("string").str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Float64")
    df["_canonical_period_key"] = (
        df["_canonical_period_key"].astype("string")
    )

    df = df.dropna(subset=["company_id", "_canonical_period_key"]).copy()
    return df


def main():
    datasets = {table: load_table(table) for table in TABLES}

    # Build a union of company/year/period keys. Do not discard TTM or
    # other reporting periods merely because their numeric year is missing.
    all_keys = pd.concat(
        [df[KEYS] for df in datasets.values()],
        ignore_index=True,
    ).drop_duplicates()

    all_keys["canonical_reporting_period"] = (
        all_keys["_canonical_period_key"]
    )

    # Retain a source period label for readability; canonical key controls joins.
    period_labels = pd.concat(
        [
            df[KEYS + ["reporting_period"]]
            for df in datasets.values()
            if "reporting_period" in df.columns
        ],
        ignore_index=True,
    ).drop_duplicates(subset=KEYS, keep="first")

    panel = all_keys.merge(
        period_labels,
        on=KEYS,
        how="left",
        validate="one_to_one",
    )
    review = panel[KEYS + ["canonical_reporting_period", "reporting_period"]].copy()

    for table, df in datasets.items():
        counts = (
            df.groupby(KEYS, dropna=False)
            .size()
            .rename(f"{table}_row_count")
            .reset_index()
        )

        panel = panel.merge(
            counts,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )
        count_col = f"{table}_row_count"
        panel[count_col] = panel[count_col].fillna(0).astype(int)
        panel[f"{table}_ambiguous"] = panel[count_col] > 1

        review = review.merge(
            counts,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )
        review[count_col] = review[count_col].fillna(0).astype(int)
        review[f"{table}_status"] = review[count_col].map(
            lambda n: "MISSING" if n == 0
            else "UNAMBIGUOUS" if n == 1
            else "CONFLICT"
        )

        # Classify duplicate groups using business-data values, not IDs
        # or technical period labels. Keep original counts for auditability.
        comparison_exclude = {
            "id", "reporting_period", "_canonical_period_key"
        }
        comparison_columns = [
            c for c in df.columns
            if c not in set(KEYS) | comparison_exclude
        ]

        group_classification = []
        for key, group in df.groupby(KEYS, dropna=False, sort=False):
            if len(group) == 1:
                duplicate_type = "SINGLE"
            else:
                # Compare values while treating nulls as equal.
                normalized = group[comparison_columns].astype("string")
                identical = normalized.drop_duplicates().shape[0] == 1
                duplicate_type = (
                    "EXACT_DUPLICATE" if identical else "VARIANT_DUPLICATE"
                )

            group_classification.append((*key, duplicate_type))

        classification = pd.DataFrame(
            group_classification,
            columns=KEYS + [f"{table}_duplicate_type"],
        )

        # Match classification key dtypes to the already-normalized panel keys.
        classification["company_id"] = (
            classification["company_id"].astype("string").str.strip()
        )
        classification["year"] = pd.to_numeric(
            classification["year"], errors="coerce"
        ).astype("Float64")
        classification["_canonical_period_key"] = (
            classification["_canonical_period_key"].astype("string")
        )

        panel = panel.merge(
            classification,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )
        panel[f"{table}_exact_duplicate"] = (
            panel[f"{table}_duplicate_type"] == "EXACT_DUPLICATE"
        )

        review = review.merge(
            classification,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )
        review[f"{table}_exact_duplicate"] = (
            review[f"{table}_duplicate_type"] == "EXACT_DUPLICATE"
        )
        review[f"{table}_status"] = review[f"{table}_duplicate_type"].map(
            {
                "SINGLE": "UNAMBIGUOUS",
                "EXACT_DUPLICATE": "EXACT_DUPLICATE",
                "VARIANT_DUPLICATE": "CONFLICT",
            }
        ).fillna("MISSING")

        # A single row or an identical-duplicate group can contribute one
        # deterministic copy. Conflicting variants remain unresolved.
        safe_keys = classification.loc[
            classification[f"{table}_duplicate_type"].isin(
                ["SINGLE", "EXACT_DUPLICATE"]
            ),
            KEYS,
        ]
        safe_rows = (
            df.sort_values("id", kind="stable")
            .drop_duplicates(subset=KEYS + comparison_columns, keep="first")
            .merge(
                safe_keys,
                on=KEYS,
                how="inner",
                validate="many_to_one",
            )
            .drop_duplicates(subset=KEYS, keep="first")
            .copy()
        )

        exclude = set(KEYS + ["id", "_canonical_period_key", "reporting_period"])
        value_columns = [c for c in safe_rows.columns if c not in exclude]
        safe_rows = safe_rows.rename(
            columns={
                c: f"{table}_{c}"
                for c in value_columns
            }
        )

        # Keep join keys until after the merge; omit source labels and IDs.
        safe_rows = safe_rows.drop(
            columns=[c for c in ["id", "reporting_period"] if c in safe_rows.columns],
            errors="ignore",
        )

        panel = panel.merge(
            safe_rows,
            on=KEYS,
            how="left",
            validate="one_to_one",
        )

    status_columns = [f"{table}_status" for table in TABLES]
    # Exact duplicates are safely deduplicated; missing sources and
    # conflicting variants still require review.
    accepted_statuses = {"UNAMBIGUOUS", "EXACT_DUPLICATE"}
    review["needs_review"] = (
        ~review[status_columns].isin(accepted_statuses)
    ).any(axis=1)

    # Mark only genuinely conflicting variants as ambiguous.
    for table in TABLES:
        duplicate_type_col = f"{table}_duplicate_type"
        if duplicate_type_col in panel.columns:
            panel[f"{table}_ambiguous"] = (
                panel[duplicate_type_col] == "VARIANT_DUPLICATE"
            )

    # Drop the internal key from deliverable files; retain the canonical period.
    panel = panel.drop(columns=["_canonical_period_key"])
    review = review.drop(columns=["_canonical_period_key"])

    sort_columns = ["company_id", "year", "canonical_reporting_period"]
    panel = panel.sort_values(sort_columns, na_position="last").reset_index(drop=True)
    review = review.sort_values(sort_columns, na_position="last").reset_index(drop=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = OUTPUT_DIR / "financial_panel.csv"
    review_path = OUTPUT_DIR / "financial_panel_review.csv"

    panel.to_csv(panel_path, index=False)
    review.to_csv(review_path, index=False)

    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Panel rows: {len(panel)}")
    print(f"Panel columns: {len(panel.columns)}")
    print("Unique company/year/period keys:", len(panel))
    print("Rows needing review:", int(review["needs_review"].sum()))
    print(f"Saved: {panel_path}")
    print(f"Saved: {review_path}")

    for table in TABLES:
        print(
            f"{table}: "
            f"missing={(review[f'{table}_status'] == 'MISSING').sum()}, "
            f"conflict={(review[f'{table}_status'] == 'CONFLICT').sum()}, "
            f"unambiguous={(review[f'{table}_status'] == 'UNAMBIGUOUS').sum()}"
        )


if __name__ == "__main__":
    main()
