
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "processed" / "nifty100.db"
OUTPUT_DIR = ROOT / "output"

OUTPUT_PARSED = OUTPUT_DIR / "analysis_parsed.csv"
OUTPUT_FAILURES = OUTPUT_DIR / "parse_failures.csv"
OUTPUT_DIVERGENCE = OUTPUT_DIR / "cagr_divergence.csv"

YEAR_PATTERN = re.compile(
    r"(?P<period>\d+)\s*Years?:?\s*"
    r"(?P<value>-?\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
TTM_PATTERN = re.compile(
    r"TTM\s*:?\s*(?P<value>-?\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
LAST_YEAR_PATTERN = re.compile(
    r"Last\s+Year\s*:?\s*(?P<value>-?\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
ONE_YEAR_PATTERN = re.compile(
    r"1\s*Year\s*:?\s*(?P<value>-?\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

METRICS = [
    "compounded_sales_growth",
    "compounded_profit_growth",
    "stock_price_cagr",
    "roe",
]

DB_CAGR_COLUMNS = {
    "compounded_sales_growth": "revenue_cagr",
    "compounded_profit_growth": "pat_cagr",
}

PARSED_COLUMNS = [
    "company_id",
    "metric_type",
    "period_label",
    "period_years",
    "value_pct",
]

FAILURE_COLUMNS = [
    "company_id",
    "metric_type",
    "raw_value",
    "failure_reason",
]

DIVERGENCE_COLUMNS = [
    "company_id",
    "metric_type",
    "period_years",
    "source_value_pct",
    "engine_value_pct",
    "absolute_difference_pct_points",
    "status",
]


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def find_analysis_workbook() -> Path:
    candidates = sorted(
        p for p in RAW_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".xlsx", ".xls"}
        and "analysis" in p.name.lower()
    )
    if not candidates:
        raise FileNotFoundError(
            f"No analysis workbook found in {RAW_DIR}"
        )
    if len(candidates) > 1:
        print("Multiple analysis workbooks found; using:", candidates[0].name)
    return candidates[0]


def load_analysis(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=1)
    df.columns = [clean_text(c) for c in df.columns]

    required = {"company_id", *METRICS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}. "
            f"Found columns: {df.columns.tolist()}"
        )

    df["company_id"] = df["company_id"].map(clean_text)
    return df[df["company_id"] != ""].copy()


def parse_value(text: str):
    """Return (period_label, period_years, value_pct), or None."""
    match = YEAR_PATTERN.search(text)
    if match:
        years = int(match.group("period"))
        return f"{years} Years", years, float(match.group("value"))

    match = TTM_PATTERN.search(text)
    if match:
        return "TTM", None, float(match.group("value"))

    match = LAST_YEAR_PATTERN.search(text)
    if match:
        return "Last Year", None, float(match.group("value"))

    match = ONE_YEAR_PATTERN.search(text)
    if match:
        return "1 Year", 1, float(match.group("value"))

    return None


def parse_analysis(df: pd.DataFrame):
    parsed = []
    failures = []

    for _, row in df.iterrows():
        company_id = row["company_id"]

        for metric in METRICS:
            text = clean_text(row[metric])
            if not text:
                continue

            result = parse_value(text)
            if result is None:
                failures.append({
                    "company_id": company_id,
                    "metric_type": metric,
                    "raw_value": text,
                    "failure_reason": "Unsupported period/value format",
                })
                continue

            period_label, period_years, value_pct = result
            parsed.append({
                "company_id": company_id,
                "metric_type": metric,
                "period_label": period_label,
                "period_years": period_years,
                "value_pct": value_pct,
            })

    return (
        pd.DataFrame(parsed, columns=PARSED_COLUMNS),
        pd.DataFrame(failures, columns=FAILURE_COLUMNS),
    )


def cross_validate(parsed: pd.DataFrame) -> pd.DataFrame:
    """Compare only multi-year sales/profit CAGR with matching DB periods."""
    if parsed.empty:
        return pd.DataFrame(columns=DIVERGENCE_COLUMNS)

    comparable = parsed[
        parsed["metric_type"].isin(DB_CAGR_COLUMNS)
        & parsed["period_years"].isin([3, 5, 10])
    ].copy()

    if comparable.empty:
        return pd.DataFrame(columns=DIVERGENCE_COLUMNS)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as con:
        columns = {
            row[1]
            for row in con.execute(
                'PRAGMA table_info("financial_ratios")'
            ).fetchall()
        }

        ids = comparable["company_id"].dropna().unique().tolist()
        placeholders = ",".join("?" for _ in ids)

        ratios = pd.read_sql_query(
            f"""
            SELECT *
            FROM financial_ratios
            WHERE company_id IN ({placeholders})
            ORDER BY company_id, year DESC
            """,
            con,
            params=ids,
        )

        known_ids = set()
        for table in ("company_summary", "company_scorecard", "financial_ratios"):
            known_ids.update(
                row[0] for row in con.execute(
                    f'SELECT DISTINCT company_id FROM "{table}"'
                ).fetchall()
            )

    latest = (
        ratios.drop_duplicates("company_id", keep="first").set_index("company_id")
        if not ratios.empty else pd.DataFrame()
    )

    results = []

    for record in comparable.to_dict("records"):
        company_id = record["company_id"]
        metric = record["metric_type"]
        period = int(record["period_years"])
        column = f"{DB_CAGR_COLUMNS[metric]}_{period}yr"

        result = {
            "company_id": company_id,
            "metric_type": metric,
            "period_years": period,
            "source_value_pct": record["value_pct"],
            "engine_value_pct": None,
            "absolute_difference_pct_points": None,
            "status": "",
        }

        if company_id not in known_ids:
            result["status"] = "Database coverage gap: company not found"
        elif column not in columns:
            result["status"] = "Matching engine period unavailable"
        elif latest.empty or company_id not in latest.index:
            result["status"] = "Company not found in financial ratios"
        else:
            engine_value = latest.at[company_id, column]

            if pd.isna(engine_value):
                result["status"] = "Engine CAGR unavailable"
            else:
                difference = abs(float(record["value_pct"]) - float(engine_value))
                result["engine_value_pct"] = float(engine_value)
                result["absolute_difference_pct_points"] = difference
                result["status"] = (
                    "REVIEW: divergence > 5 percentage points"
                    if difference > 5 else "OK"
                )

        results.append(result)

    return pd.DataFrame(results, columns=DIVERGENCE_COLUMNS)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    workbook = find_analysis_workbook()
    print(f"Reading workbook: {workbook.name}")

    source = load_analysis(workbook)
    parsed, failures = parse_analysis(source)
    divergence = cross_validate(parsed)

    parsed.to_csv(OUTPUT_PARSED, index=False)
    failures.to_csv(OUTPUT_FAILURES, index=False)
    divergence.to_csv(OUTPUT_DIVERGENCE, index=False)

    print("\n=== NLP PARSER SUMMARY ===")
    print(f"Source rows: {len(source)}")
    print(f"Unique source companies: {source['company_id'].nunique()}")
    print(f"Parsed metric records: {len(parsed)}")
    print(f"Failed non-empty metric cells: {len(failures)}")

    if not parsed.empty:
        print("\nParsed records by metric and period:")
        print(
            parsed.groupby(["metric_type", "period_label"])
            .size()
            .to_string()
        )

    if not divergence.empty:
        print("\nCAGR cross-validation status:")
        print(divergence["status"].value_counts().to_string())

        review = divergence[
            divergence["status"].str.startswith("REVIEW", na=False)
        ]
        if not review.empty:
            print("\nDivergences requiring review:")
            print(review.to_string(index=False))

    print("\nOutput files:")
    print(OUTPUT_PARSED.relative_to(ROOT))
    print(OUTPUT_FAILURES.relative_to(ROOT))
    print(OUTPUT_DIVERGENCE.relative_to(ROOT))


if __name__ == "__main__":
    main()
