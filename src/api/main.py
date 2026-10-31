from pathlib import Path
import re

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query

ROOT = Path(__file__).resolve().parents[2]
DATA = Path("/tmp/nifty100_period_aware_test/analytical")
METRICS = DATA / "derived_metrics_period_aware_candidate.csv"
LABELS = ROOT / "output/cluster_labels.csv"
SECTORS_FILE = DATA / "sectors.csv"

app = FastAPI(
    title="Nifty 100 Analytics API",
    description="Read-only analytical API backed by candidate CSV outputs.",
    version="1.0.0",
)


def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def metrics():
    return read_csv(METRICS)


def labels():
    return read_csv(LABELS)


def sector_data():
    return read_csv(SECTORS_FILE)


def clean(df):
    return df.replace({np.nan: None, np.inf: None, -np.inf: None})


def records(df):
    return clean(df).to_dict(orient="records")


def company_rows(company_id):
    df = metrics()
    if "company_id" not in df:
        return df.iloc[0:0]
    return df[df["company_id"].astype(str).str.upper() == company_id.upper()]


def latest_rows():
    df = metrics()
    if df.empty or "company_id" not in df:
        return df
    if "canonical_reporting_period" in df:
        period = df["canonical_reporting_period"].fillna("").astype(str).str.lower()
        annual = period.str.contains(r"\b(?:mar|dec|sep)\b|^\s*\d{4}\s*$", regex=True)
        df = df[annual].copy()
    if "year" in df:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df = df.sort_values("year")
    return df.drop_duplicates("company_id", keep="last")


def joined_latest():
    df = latest_rows()
    cl = labels()
    if not df.empty and not cl.empty and "company_id" in cl:
        cols = [c for c in ["company_id", "cluster_id", "cluster_name",
                            "distance_from_centroid"] if c in cl]
        df = df.merge(cl[cols].drop_duplicates("company_id"),
                      on="company_id", how="left")
    return df


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "metrics_file_exists": METRICS.exists(),
        "cluster_labels_exist": LABELS.exists(),
        "data_source": "candidate CSV files; production database is not modified",
    }


@app.get("/companies", tags=["Companies"])
def list_companies(limit: int = Query(100, ge=1, le=500),
                   offset: int = Query(0, ge=0)):
    df = joined_latest()
    if df.empty:
        return {"total": 0, "items": []}
    df = df.sort_values("company_id")
    return {"total": len(df), "items": records(df.iloc[offset:offset + limit])}


@app.get("/companies/{company_id}", tags=["Companies"])
def company_detail(company_id: str):
    df = company_rows(company_id)
    if df.empty:
        raise HTTPException(404, "Company not found")
    df = df.sort_values("year") if "year" in df else df
    return {"company_id": company_id.upper(), "periods": records(df)}


@app.get("/companies/{company_id}/metrics", tags=["Companies"])
def company_metrics(company_id: str):
    df = company_rows(company_id)
    if df.empty:
        raise HTTPException(404, "Company not found")
    return {"company_id": company_id.upper(), "metrics": records(df)}


@app.get("/screener", tags=["Screening"])
def screener(
    min_roe: float | None = None,
    max_debt_to_equity: float | None = None,
    min_opm: float | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    df = joined_latest()
    mapping = {
        "min_roe": ("calculated_roe_pct", min_roe, "min"),
        "max_debt_to_equity": ("calculated_debt_to_equity", max_debt_to_equity, "max"),
        "min_opm": ("calculated_opm_pct", min_opm, "min"),
    }
    for _, (col, threshold, direction) in mapping.items():
        if threshold is not None and col in df:
            values = pd.to_numeric(df[col], errors="coerce")
            df = df[values >= threshold] if direction == "min" else df[values <= threshold]
    return {"count": len(df), "items": records(df.head(limit))}


@app.get("/sectors", tags=["Sectors"])
def list_sectors():
    df = sector_data()
    if df.empty:
        return {"sectors": [], "note": "Sector source file unavailable"}
    col = next((c for c in ["broad_sector", "sector", "sector_name"] if c in df), None)
    if col is None:
        return {"sectors": [], "note": "No recognized sector column"}
    return {"sectors": sorted(df[col].dropna().astype(str).unique().tolist())}


@app.get("/sectors/{sector_name}", tags=["Sectors"])
def sector_detail(sector_name: str):
    sectors = sector_data()

    if sectors.empty or not {"company_id", "broad_sector"}.issubset(sectors.columns):
        raise HTTPException(404, "Sector data unavailable")

    sectors = sectors.copy()
    sectors["company_id"] = sectors["company_id"].astype(str).str.strip()
    sectors["broad_sector"] = sectors["broad_sector"].astype(str).str.strip()

    sector_rows = sectors[
        sectors["broad_sector"].str.casefold() == sector_name.strip().casefold()
    ].drop_duplicates("company_id")

    if sector_rows.empty:
        raise HTTPException(404, "Sector not found")

    company_metrics = joined_latest()

    if not company_metrics.empty and "company_id" in company_metrics.columns:
        company_metrics = company_metrics.copy()
        company_metrics["company_id"] = (
            company_metrics["company_id"].astype(str).str.strip()
        )
        company_metrics = company_metrics.drop_duplicates("company_id")

        subset = sector_rows.merge(
            company_metrics,
            on="company_id",
            how="left",
        )
    else:
        subset = sector_rows

    return {
        "sector": sector_name,
        "count": len(subset),
        "companies": records(subset),
    }

@app.get("/peers/{company_id}", tags=["Peers"])
def peers(company_id: str, limit: int = Query(10, ge=1, le=50)):
    df = joined_latest()
    match = df[df["company_id"].astype(str).str.upper() == company_id.upper()]
    if match.empty:
        raise HTTPException(404, "Company not found")
    sector_col = next((c for c in ["broad_sector", "sector", "sector_name"] if c in df), None)
    if sector_col:
        sector = match.iloc[0][sector_col]
        result = df[(df[sector_col] == sector) &
                    (df["company_id"].astype(str).str.upper() != company_id.upper())]
    elif "cluster_id" in df:
        cluster = match.iloc[0]["cluster_id"]
        result = df[(df["cluster_id"] == cluster) &
                    (df["company_id"].astype(str).str.upper() != company_id.upper())]
    else:
        result = df[df["company_id"].astype(str).str.upper() != company_id.upper()]
    return {"company_id": company_id.upper(), "peers": records(result.head(limit))}


@app.get("/clusters", tags=["Clustering"])
def list_clusters():
    df = labels()
    if df.empty:
        return {"clusters": [], "note": "Cluster labels file unavailable"}
    return {"clusters": records(
        df.groupby(["cluster_id", "cluster_name"], dropna=False)
          .size().reset_index(name="company_count")
    )}


@app.get("/clusters/{cluster_id}", tags=["Clustering"])
def cluster_detail(cluster_id: int):
    df = labels()
    if df.empty or "cluster_id" not in df:
        raise HTTPException(404, "Cluster labels unavailable")
    df["cluster_id"] = pd.to_numeric(df["cluster_id"], errors="coerce")
    subset = df[df["cluster_id"] == cluster_id]
    if subset.empty:
        raise HTTPException(404, "Cluster not found")
    return {"cluster_id": cluster_id, "companies": records(subset)}


@app.get("/companies/{company_id}/cluster", tags=["Clustering"])
def company_cluster(company_id: str):
    df = labels()
    if df.empty:
        raise HTTPException(404, "Cluster labels unavailable")
    subset = df[df["company_id"].astype(str).str.upper() == company_id.upper()]
    if subset.empty:
        raise HTTPException(404, "Company has no cluster label")
    return records(subset)[0]


@app.get("/outliers", tags=["Analytics"])
def outliers():
    path = ROOT / "output/outlier_report.csv"
    df = read_csv(path)
    return {"count": len(df), "items": records(df)}


@app.get("/valuation", tags=["Analytics"])
def valuation(company_id: str | None = None):
    df = joined_latest()
    cols = [c for c in df.columns if re.search(
        r"valuation|price_to|price_earnings|pe_ratio|ev_ebitda|market_cap",
        c, re.I
    )]
    if company_id:
        df = df[df["company_id"].astype(str).str.upper() == company_id.upper()]
    return {
        "items": records(df[["company_id"] + cols]) if cols else [],
        "available_valuation_columns": cols,
        "note": "Only fields present in the source data are returned; no valuation is fabricated.",
    }


@app.get("/portfolio/stats", tags=["Portfolio"])
def portfolio_stats():
    df = read_csv(ROOT / "output/portfolio_stats.csv")
    return {"statistics": records(df)}


@app.get("/data-quality", tags=["Data Quality"])
def data_quality():
    df = metrics()
    if df.empty:
        return {"rows": 0, "columns": [], "missing_percent": {}}
    return {
        "rows": len(df),
        "companies": int(df["company_id"].nunique()) if "company_id" in df else None,
        "columns": df.columns.tolist(),
        "missing_percent": (df.isna().mean() * 100).round(2).to_dict(),
    }


@app.get("/reports", tags=["Reports"])
def available_reports():
    paths = [ROOT / "reports", ROOT / "output", ROOT / "docs"]
    files = []
    for directory in paths:
        if directory.exists():
            files.extend(str(p.relative_to(ROOT)) for p in directory.iterdir() if p.is_file())
    return {"files": sorted(files)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
