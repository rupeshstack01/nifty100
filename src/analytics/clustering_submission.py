from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
DATA = Path("/tmp/nifty100_period_aware_test/analytical")
INPUT = DATA / "derived_metrics_period_aware_candidate.csv"
SECTORS = DATA / "sectors.csv"
OUT = ROOT / "output"
REPORTS = ROOT / "reports"

FEATURES = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]


def number(df, col):
    """Convert a column to numeric and replace infinite values with missing."""
    if col not in df:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def annual_date(period, year):
    """Parse annual March, December, or year-only reporting periods."""
    label = "" if pd.isna(period) else str(period).strip()
    match = re.fullmatch(
        r"(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})",
        label,
    )
    if match:
        month = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }[match.group(1).lower()]
        # Accept explicit fiscal-year-end months, including September.
        return pd.Timestamp(int(match.group(2)), month, 1)
    if re.fullmatch(r"\d{4}", label):
        return pd.Timestamp(int(label), 12, 31)
    if not label and pd.notna(year):
        return pd.Timestamp(int(year), 12, 31)
    return pd.NaT


def cagr(start, end):
    """Calculate five-year CAGR only when both endpoint values are positive."""
    if pd.isna(start) or pd.isna(end) or start <= 0 or end <= 0:
        return np.nan
    return ((end / start) ** (1 / 5) - 1) * 100


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not INPUT.exists():
        raise FileNotFoundError(f"Candidate data not found: {INPUT}")

    df = pd.read_csv(INPUT, low_memory=False)
    required = {"company_id", "year", "canonical_reporting_period"}
    if not required.issubset(df.columns):
        raise ValueError(f"Input missing columns: {sorted(required - set(df.columns))}")

    df["company_id"] = df["company_id"].astype("string").str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["_date"] = [
        annual_date(p, y)
        for p, y in zip(df["canonical_reporting_period"], df["year"])
    ]
    df = df[df["_date"].notna()].copy()
    df["year"] = df["_date"].dt.year
    # Prefer explicit annual periods over year-only labels. If multiple
    # explicit records remain for a company/year, prefer March, then December,
    # then September. Do not silently pick between duplicate rows of equal rank.
    df["_period_label"] = (
        df["canonical_reporting_period"].fillna("").astype(str).str.strip().str.lower()
    )
    df["_period_rank"] = df["_period_label"].map(
        lambda x: 0 if re.fullmatch(r"\d{4}", x) else
                  3 if x.startswith("mar ") else
                  2 if x.startswith("dec ") else
                  1 if x.startswith("sep ") else 0
    )
    df = df.sort_values(
        ["company_id", "year", "_period_rank", "_date"],
        ascending=[True, True, False, False],
    )
    top_rank = df.groupby(["company_id", "year"])["_period_rank"].transform("max")
    df = df[df["_period_rank"].eq(top_rank)].copy()

    # Identical top-ranked rows can be collapsed; conflicting rows are excluded
    # from feature construction rather than arbitrarily choosing one.
    key_cols = ["company_id", "year"]
    data_cols = [
        c for c in df.columns
        if c not in {"_date", "_period_label", "_period_rank"}
    ]
    duplicated = df.duplicated(key_cols, keep=False)
    if duplicated.any():
        keep_indices = []
        for _, group in df[duplicated].groupby(key_cols, dropna=False):
            if len(group[data_cols].drop_duplicates()) == 1:
                keep_indices.append(group.index[0])
        unambiguous = df[~duplicated]
        df = pd.concat(
            [unambiguous, df.loc[keep_indices]], axis=0
        ).sort_values(["company_id", "year"])
    else:
        df = df.sort_values(["company_id", "year"])

    df["_sales"] = number(df, "profitandloss_sales")
    df["_fcf"] = number(df, "calculated_fcf_cr")

    for flag, value_col in [
        ("profitandloss_ambiguous", "_sales"),
        ("cashflow_ambiguous", "_fcf"),
    ]:
        if flag in df:
            bad = df[flag].astype(str).str.lower().isin(["true", "1", "yes"])
            df.loc[bad, value_col] = np.nan

    # Compute CAGRs from observations exactly five years apart.
    sales = df.set_index(["company_id", "year"])["_sales"].to_dict()
    fcf = df.set_index(["company_id", "year"])["_fcf"].to_dict()
    latest = df.groupby("company_id", sort=False).tail(1).copy()

    revenue_growth = []
    fcf_growth = []
    for _, row in latest.iterrows():
        company, year = str(row["company_id"]), int(row["year"])
        revenue_growth.append(cagr(
            sales.get((company, year - 5), np.nan), row["_sales"]
        ))
        fcf_growth.append(cagr(
            fcf.get((company, year - 5), np.nan), row["_fcf"]
        ))

    latest["return_on_equity_pct"] = number(latest, "calculated_roe_pct")
    latest["debt_to_equity"] = number(latest, "calculated_debt_to_equity")
    latest["revenue_cagr_5yr"] = revenue_growth
    latest["fcf_cagr_5yr"] = fcf_growth
    latest["operating_profit_margin_pct"] = number(latest, "calculated_opm_pct")

    # Remove values from ambiguous source records.
    for flag, features in [
        ("profitandloss_ambiguous", ["revenue_cagr_5yr", "operating_profit_margin_pct"]),
        ("balancesheet_ambiguous", ["debt_to_equity"]),
        ("cashflow_ambiguous", ["fcf_cagr_5yr"]),
    ]:
        if flag in latest:
            bad = latest[flag].astype(str).str.lower().isin(["true", "1", "yes"])
            latest.loc[bad, features] = np.nan

    latest["broad_sector"] = "Unknown"
    if SECTORS.exists():
        sectors = pd.read_csv(SECTORS, low_memory=False)
        if "company_id" in sectors:
            sectors["company_id"] = sectors["company_id"].astype("string").str.strip()
            sector_col = next(
                (c for c in ["broad_sector", "sector", "sector_name"] if c in sectors),
                None,
            )
            if sector_col:
                sectors = sectors[["company_id", sector_col]].drop_duplicates("company_id")
                latest = latest.drop(columns=["broad_sector"]).merge(
                    sectors, on="company_id", how="left", validate="one_to_one"
                )
                latest["broad_sector"] = latest[sector_col].fillna("Unknown").astype(str)

            # Use the sector file as the company universe when it is available.
            universe = set(sectors["company_id"].dropna().astype(str))
            latest = latest[latest["company_id"].astype(str).isin(universe)].copy()

    if len(latest) < 5:
        raise ValueError(f"Only {len(latest)} companies available for five clusters.")

    X = latest[FEATURES].replace([np.inf, -np.inf], np.nan).copy()

    # Sector median imputation, then global median if a sector has no observations.
    for feature in FEATURES:
        sector_median = X[feature].groupby(latest["broad_sector"]).transform("median")
        X[feature] = X[feature].fillna(sector_median)
        median = X[feature].median()
        if pd.isna(median):
            raise ValueError(f"No valid observations exist for {feature}.")
        X[feature] = X[feature].fillna(median)

    scaler = StandardScaler()
    scaled = scaler.fit_transform(X)
    model = KMeans(n_clusters=5, random_state=42, n_init=20)
    labels = model.fit_predict(scaled)
    distance = np.linalg.norm(scaled - model.cluster_centers_[labels], axis=1)

    # Heuristic archetype names based on scaled cluster-centroid profiles.
    centers = pd.DataFrame(model.cluster_centers_, columns=FEATURES)
    quality = (
        centers["return_on_equity_pct"] - centers["debt_to_equity"]
        + centers["revenue_cagr_5yr"] + centers["fcf_cagr_5yr"]
        + centers["operating_profit_margin_pct"]
    )
    names = [
        "High-Quality Compounders", "Emerging Growth", "Balanced Performers",
        "Value Cyclicals", "Distressed or Turnaround",
    ]
    ranked_clusters = list(quality.sort_values(ascending=False).index)
    name_map = {int(cid): names[i] for i, cid in enumerate(ranked_clusters)}

    latest["cluster_id"] = labels
    latest["cluster_name"] = [name_map[int(x)] for x in labels]
    latest["distance_from_centroid"] = distance
    latest["features_missing_before_imputation"] = latest[FEATURES].isna().sum(axis=1)

    label_cols = [
        "company_id", "cluster_id", "cluster_name", "distance_from_centroid",
        "broad_sector", "year", *FEATURES, "features_missing_before_imputation",
    ]
    latest[label_cols].sort_values("company_id").to_csv(
        OUT / "cluster_labels.csv", index=False
    )

    profiles = []
    for cid, group in latest.groupby("cluster_id"):
        row = {
            "cluster_id": int(cid),
            "cluster_name": name_map[int(cid)],
            "company_count": len(group),
        }
        for feature in FEATURES:
            row[f"{feature}_mean"] = group[feature].mean()
            row[f"{feature}_median"] = group[feature].median()
        profiles.append(row)
    pd.DataFrame(profiles).to_csv(OUT / "cluster_profiles.csv", index=False)

    # Elbow curve for k=2..10; the submitted model itself remains fixed at k=5.
    elbow_rows = []
    for k in range(2, min(10, len(X) - 1) + 1):
        candidate = KMeans(n_clusters=k, random_state=42, n_init=20).fit(scaled)
        elbow_rows.append({"k": k, "inertia": candidate.inertia_})
    elbow = pd.DataFrame(elbow_rows)
    elbow.to_csv(OUT / "elbow_metrics.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(elbow["k"], elbow["inertia"], marker="o")
    ax.axvline(5, linestyle="--", label="Required k=5")
    ax.set(title="KMeans Elbow Plot", xlabel="k", ylabel="Inertia")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(REPORTS / "elbow_plot.png", dpi=160)
    plt.close(fig)

    print("Clustering completed.")
    print("Companies:", len(latest))
    print("Distinct clusters:", latest["cluster_id"].nunique())
    print(latest["cluster_id"].value_counts().sort_index().to_string())
    print("Labels:", OUT / "cluster_labels.csv")
    print("Profiles:", OUT / "cluster_profiles.csv")
    print("Elbow plot:", REPORTS / "elbow_plot.png")

    if len(latest) != 92:
        warnings.warn(
            f"Expected 92 companies, but found {len(latest)}. "
            "Do not claim acceptance gate AC-15 passes until the universe is reconciled."
        )


if __name__ == "__main__":
    main()
