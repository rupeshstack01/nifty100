"""Period-aware clustering using candidate derived financial metrics."""

from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler


INPUT = Path(
    "/tmp/nifty100_period_aware_test/analytical/"
    "derived_metrics_period_aware_candidate.csv"
)
SECTORS = Path(
    "/tmp/nifty100_period_aware_test/analytical/sectors.csv"
)
OUT = Path("/tmp/nifty100_period_aware_test/output")

FEATURES = [
    "net_profit_margin_pct",
    "debt_to_equity",
    "interest_coverage",
]

MIN_FEATURES = 3
MIN_CLUSTER_SIZE = 3


def truthy(series):
    """Interpret CSV boolean values conservatively."""
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )


def parse_period(value, year):
    """Return (date, is_annual); exclude TTM and interim periods."""
    label = "" if pd.isna(value) else str(value).strip().lower()

    if not label or re.search(r"\bttm\b|trailing\s*twelve", label):
        return pd.NaT, False

    # Accept fiscal annual periods (March/December) and year-only labels.
    match = re.fullmatch(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})", label)
    if match:
        month_name, yr = match.groups()
        month = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }[month_name]
        if month not in (3, 12):
            return pd.NaT, False
        return pd.Timestamp(int(yr), month, 1), True

    if re.fullmatch(r"\d{4}", label):
        return pd.Timestamp(int(label), 12, 31), True

    # If the label cannot be interpreted, do not guess an annual period.
    return pd.NaT, False


def numeric(df, column):
    if column not in df:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def flag(df, column):
    if column not in df:
        return pd.Series(False, index=df.index)
    return truthy(df[column])


def build_features(df):
    """Build feature columns and mask metrics affected by ambiguous sources."""
    pl_bad = flag(df, "profitandloss_ambiguous")
    bs_bad = flag(df, "balancesheet_ambiguous")
    cf_bad = flag(df, "cashflow_ambiguous")
    ratios_bad = flag(df, "financial_ratios_ambiguous")

    # Calculated income-statement ratios.
    df["net_profit_margin_pct"] = numeric(
        df, "calculated_net_profit_margin_pct"
    ).mask(pl_bad)

    df["debt_to_equity"] = numeric(
        df, "calculated_debt_to_equity"
    ).mask(bs_bad)

    # Prefer a transparent calculation from operating profit / interest expense.
    # If unavailable, use the reported ratio only when that source is unambiguous.
    operating_profit = numeric(df, "profitandloss_operating_profit")
    interest = numeric(df, "profitandloss_interest").abs()
    derived_coverage = operating_profit / interest.where(interest > 1e-12)
    reported_coverage = numeric(df, "financial_ratios_interest_coverage")

    df["interest_coverage"] = derived_coverage.mask(pl_bad)
    fallback = df["interest_coverage"].isna() & ~ratios_bad
    df.loc[fallback, "interest_coverage"] = reported_coverage.loc[fallback]

    # Exclude mathematically invalid or extreme infinite values.
    for col in FEATURES:
        df[col] = numeric(df, col)

    # Retain FCF for interpretation only; never use raw currency amounts to cluster.
    df["free_cash_flow_cr"] = numeric(df, "calculated_fcf_cr").mask(cf_bad)

    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    if not INPUT.exists():
        raise FileNotFoundError(f"Candidate input not found: {INPUT}")

    df = pd.read_csv(INPUT, low_memory=False)

    required = {"company_id", "canonical_reporting_period", "year"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["company_id"] = df["company_id"].astype("string").str.strip()
    df = df.loc[df["company_id"].notna() & df["company_id"].ne("")].copy()

    parsed = df.apply(
        lambda row: parse_period(
            row["canonical_reporting_period"], row["year"]
        ),
        axis=1,
        result_type="expand",
    )
    df["_period_date"] = pd.to_datetime(parsed[0], errors="coerce")
    df["_is_annual"] = parsed[1].astype(bool)

    df = df.loc[df["_is_annual"] & df["_period_date"].notna()].copy()

    duplicate_mask = df.duplicated(
        ["company_id", "_period_date"], keep=False
    )
    if duplicate_mask.any():
        df.loc[duplicate_mask].to_csv(
            OUT / "clustering_duplicate_periods.csv", index=False
        )
        raise ValueError(
            "Duplicate annual company-period records found. "
            "See clustering_duplicate_periods.csv; no clustering performed."
        )

    df = build_features(df)

    # Choose each company's latest annual record with enough valid features.
    df["_valid_feature_count"] = df[FEATURES].notna().sum(axis=1)
    eligible_periods = df.loc[
        df["_valid_feature_count"] >= MIN_FEATURES
    ].copy()

    eligible_periods = eligible_periods.sort_values(
        ["company_id", "_period_date"]
    )
    selected = eligible_periods.groupby(
        "company_id", sort=False, as_index=False
    ).tail(1).copy()

    all_companies = set(df["company_id"].dropna().astype(str))
    selected_companies = set(selected["company_id"].dropna().astype(str))

    exclusions = []
    for company in sorted(all_companies - selected_companies):
        company_rows = df.loc[df["company_id"].astype(str).eq(company)]
        max_features = (
            int(company_rows["_valid_feature_count"].max())
            if not company_rows.empty else 0
        )
        exclusions.append({
            "company_id": company,
            "reason": (
                f"No annual reporting period had at least {MIN_FEATURES} "
                "usable financial features"
            ),
            "max_usable_features": max_features,
            "annual_periods_checked": len(company_rows),
        })

    pd.DataFrame(
        exclusions,
        columns=[
            "company_id", "reason",
            "max_usable_features", "annual_periods_checked"
        ],
    ).to_csv(OUT / "cluster_exclusions.csv", index=False)

    if len(selected) < 6:
        raise ValueError(
            f"Only {len(selected)} companies qualified. "
            "Not enough data for reliable clustering."
        )

    # Clip extreme values to reduce the influence of data errors and outliers.
    X_raw = selected[FEATURES].copy()
    lower = X_raw.quantile(0.01)
    upper = X_raw.quantile(0.99)
    X_clipped = X_raw.clip(lower=lower, upper=upper, axis="columns")

    # Median imputation is applied only after the per-company feature threshold.
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X_clipped)
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    selection_rows = []
    candidate_models = []

    max_k = min(8, len(selected) - 1)
    for k in range(2, max_k + 1):
        model = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels = model.fit_predict(X_scaled)
        counts = pd.Series(labels).value_counts()
        min_size = int(counts.min())

        score = (
            float(silhouette_score(X_scaled, labels))
            if len(counts) > 1 else float("nan")
        )

        acceptable = min_size >= MIN_CLUSTER_SIZE and np.isfinite(score)
        selection_rows.append({
            "k": k,
            "inertia": float(model.inertia_),
            "silhouette_score": score,
            "minimum_cluster_size": min_size,
            "meets_minimum_cluster_size": acceptable,
        })

        if acceptable:
            candidate_models.append((score, k, model, labels))

    selection = pd.DataFrame(selection_rows)
    selection.to_csv(OUT / "clustering_model_selection.csv", index=False)

    if not candidate_models:
        raise ValueError(
            "No tested clustering solution satisfies the minimum cluster "
            f"size of {MIN_CLUSTER_SIZE}. Inspect clustering_model_selection.csv. "
            "No cluster labels were generated."
        )

    # Highest silhouette score among solutions that pass the size constraint.
    _, selected_k, model, labels = max(
        candidate_models, key=lambda item: item[0]
    )

    selected["cluster"] = labels + 1
    selected["selected_reporting_period"] = (
        selected["_period_date"].dt.strftime("%b %Y")
    )
    selected["clustering_features_used"] = ", ".join(FEATURES)
    selected["features_missing_before_imputation"] = (
        selected[FEATURES].isna().sum(axis=1)
    )

    # Optional sector metadata, if the candidate file is available and compatible.
    if SECTORS.exists():
        sectors = pd.read_csv(SECTORS, low_memory=False)
        if "company_id" in sectors.columns:
            sectors["company_id"] = (
                sectors["company_id"].astype("string").str.strip()
            )
            add_cols = [
                c for c in sectors.columns
                if c == "company_id"
                or c not in selected.columns
            ]
            selected = selected.merge(
                sectors[add_cols].drop_duplicates("company_id"),
                on="company_id",
                how="left",
                validate="many_to_one",
            )

    selected.drop(
        columns=["_period_date", "_is_annual", "_valid_feature_count"],
        errors="ignore",
    ).to_csv(OUT / "cluster_labels.csv", index=False)

    profiles = selected.groupby("cluster")[FEATURES].median()
    profiles["company_count"] = selected.groupby("cluster").size()
    profiles.to_csv(OUT / "cluster_profiles.csv")

    # Elbow plot.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(selection["k"], selection["inertia"], marker="o")
    ax.set_title("K-Means Elbow Plot")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Inertia")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "elbow_plot.png", dpi=150)
    plt.close(fig)

    # Correlation heatmap of the original, selected feature values.
    corr = selected[FEATURES].corr()
    fig, ax = plt.subplots(figsize=(9, 7))
    image = ax.imshow(corr, aspect="auto", vmin=-1, vmax=1)
    ax.set_xticks(range(len(FEATURES)))
    ax.set_yticks(range(len(FEATURES)))
    ax.set_xticklabels(FEATURES, rotation=60, ha="right")
    ax.set_yticklabels(FEATURES)
    ax.set_title("Financial Feature Correlation")
    fig.colorbar(image, ax=ax, label="Correlation")
    fig.tight_layout()
    fig.savefig(OUT / "correlation_heatmap.png", dpi=150)
    plt.close(fig)

    counts = selected["cluster"].value_counts().sort_index()

    print("\nPERIOD-AWARE CLUSTERING COMPLETE")
    print("Candidate input:", INPUT)
    print("Companies clustered:", len(selected))
    print("Companies excluded:", len(exclusions))
    print("Features:", ", ".join(FEATURES))
    print("Minimum usable features per company:", MIN_FEATURES)
    print("Minimum permitted cluster size:", MIN_CLUSTER_SIZE)
    print("Selected k:", selected_k)
    print("\nModel selection:")
    print(selection.to_string(index=False))
    print("\nCluster counts:")
    print(counts.to_string())
    print("\nSelected reporting periods:")
    print(
        selected["selected_reporting_period"]
        .value_counts()
        .head(15)
        .to_string()
    )
    print("\nOutputs:", OUT)


if __name__ == "__main__":
    main()
