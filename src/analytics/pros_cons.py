
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "nifty100.db"
OUTPUT_DIR = ROOT / "output"
OUTPUT_PATH = OUTPUT_DIR / "pros_cons_generated.csv"

# These are transparent screening heuristics, not universal investment rules.
# Confidence represents rule strength based on the observed threshold,
# not statistical probability that the conclusion is true.
MIN_CONFIDENCE = 60.0

PRO_RULES = [
    {
        "id": "P01",
        "metric": "revenue_cagr_pct",
        "label": "Strong long-term revenue growth",
        "condition": lambda x: x >= 15,
        "confidence": lambda x: min(95.0, 65.0 + (x - 15) * 1.0),
        "unit": "%",
        "threshold": ">= 15%",
    },
    {
        "id": "P02",
        "metric": "net_profit_cagr_pct",
        "label": "Strong long-term profit growth",
        "condition": lambda x: x >= 15,
        "confidence": lambda x: min(95.0, 65.0 + (x - 15) * 1.0),
        "unit": "%",
        "threshold": ">= 15%",
    },
    {
        "id": "P03",
        "metric": "latest_net_profit_margin_pct",
        "label": "Healthy net profit margin",
        "condition": lambda x: x >= 15,
        "confidence": lambda x: min(95.0, 65.0 + (x - 15) * 0.8),
        "unit": "%",
        "threshold": ">= 15%",
    },
    {
        "id": "P04",
        "metric": "latest_roe_pct",
        "label": "Strong return on equity",
        "condition": lambda x: x >= 15,
        "confidence": lambda x: min(95.0, 65.0 + (x - 15) * 0.8),
        "unit": "%",
        "threshold": ">= 15%",
    },
    {
        "id": "P05",
        "metric": "latest_debt_to_equity",
        "label": "Low debt relative to equity",
        "condition": lambda x: 0 <= x <= 0.5,
        "confidence": lambda x: min(90.0, 70.0 + (0.5 - x) * 20),
        "unit": "x",
        "threshold": "0 to 0.5",
    },
    {
        "id": "P06",
        "metric": "latest_fcf_cr",
        "label": "Positive free cash flow",
        "condition": lambda x: x > 0,
        "confidence": lambda x: min(90.0, 65.0 + min(x, 25) * 0.5),
        "unit": "cr",
        "threshold": "> 0 cr",
    },
    {
        "id": "P07",
        "metric": "latest_revenue_growth_pct",
        "label": "Positive latest revenue growth",
        "condition": lambda x: x >= 10,
        "confidence": lambda x: min(92.0, 65.0 + (x - 10) * 0.8),
        "unit": "%",
        "threshold": ">= 10%",
    },
    {
        "id": "P08",
        "metric": "latest_net_profit_growth_pct",
        "label": "Positive latest profit growth",
        "condition": lambda x: x >= 10,
        "confidence": lambda x: min(92.0, 65.0 + (x - 10) * 0.8),
        "unit": "%",
        "threshold": ">= 10%",
    },
    {
        "id": "P09",
        "metric": "avg_net_profit_margin_pct",
        "label": "Historically healthy net margin",
        "condition": lambda x: x >= 12,
        "confidence": lambda x: min(92.0, 65.0 + (x - 12) * 0.8),
        "unit": "%",
        "threshold": ">= 12%",
    },
    {
        "id": "P10",
        "metric": "avg_roe_pct",
        "label": "Consistently strong average ROE",
        "condition": lambda x: x >= 15,
        "confidence": lambda x: min(92.0, 65.0 + (x - 15) * 0.8),
        "unit": "%",
        "threshold": ">= 15%",
    },
    {
        "id": "P11",
        "metric": "avg_debt_to_equity",
        "label": "Historically low leverage",
        "condition": lambda x: 0 <= x <= 0.5,
        "confidence": lambda x: min(90.0, 70.0 + (0.5 - x) * 20),
        "unit": "x",
        "threshold": "0 to 0.5",
    },
    {
        "id": "P12",
        "metric": "avg_fcf_cr",
        "label": "Positive average free cash flow",
        "condition": lambda x: x > 0,
        "confidence": lambda x: min(90.0, 65.0 + min(x, 25) * 0.5),
        "unit": "cr",
        "threshold": "> 0 cr",
    },
]

CON_RULES = [
    {
        "id": "C01",
        "metric": "revenue_cagr_pct",
        "label": "Weak long-term revenue growth",
        "condition": lambda x: x < 5,
        "confidence": lambda x: min(95.0, 65.0 + (5 - x) * 1.5),
        "unit": "%",
        "threshold": "< 5%",
    },
    {
        "id": "C02",
        "metric": "net_profit_cagr_pct",
        "label": "Weak long-term profit growth",
        "condition": lambda x: x < 5,
        "confidence": lambda x: min(95.0, 65.0 + (5 - x) * 1.5),
        "unit": "%",
        "threshold": "< 5%",
    },
    {
        "id": "C03",
        "metric": "latest_net_profit_margin_pct",
        "label": "Thin net profit margin",
        "condition": lambda x: x < 5,
        "confidence": lambda x: min(95.0, 65.0 + (5 - x) * 2),
        "unit": "%",
        "threshold": "< 5%",
    },
    {
        "id": "C04",
        "metric": "latest_roe_pct",
        "label": "Low return on equity",
        "condition": lambda x: x < 8,
        "confidence": lambda x: min(95.0, 65.0 + (8 - x) * 2),
        "unit": "%",
        "threshold": "< 8%",
    },
    {
        "id": "C05",
        "metric": "latest_debt_to_equity",
        "label": "High debt relative to equity",
        "condition": lambda x: x > 2,
        "confidence": lambda x: min(95.0, 65.0 + (x - 2) * 8),
        "unit": "x",
        "threshold": "> 2",
    },
    {
        "id": "C06",
        "metric": "latest_fcf_cr",
        "label": "Negative free cash flow",
        "condition": lambda x: x < 0,
        "confidence": lambda x: min(95.0, 65.0 + min(abs(x), 25) * 0.5),
        "unit": "cr",
        "threshold": "< 0 cr",
    },
       {
        "id": "C07",
        "metric": "latest_opm_pct",
        "label": "Operating margin below Nifty 100 sample median",
        "condition": lambda x: x < 23.377,
        "confidence": lambda x: min(90.0, 65.0 + (23.377 - x) * 1.0),
        "unit": "%",
        "threshold": "< 23.377% (sample median)",
    },
    {
        "id": "C08",
        "metric": "latest_net_profit_growth_pct",
        "label": "Latest profit contraction",
        "condition": lambda x: x < 0,
        "confidence": lambda x: min(95.0, 65.0 + min(abs(x), 20) * 1.2),
        "unit": "%",
        "threshold": "< 0%",
    },
       {
        "id": "C09",
        "metric": "avg_net_profit_margin_pct",
        "label": "Average net margin below Nifty 100 sample median",
        "condition": lambda x: x < 11.315,
        "confidence": lambda x: min(90.0, 65.0 + (11.315 - x) * 1.0),
        "unit": "%",
        "threshold": "< 11.315% (sample median)",
    },
        {
        "id": "C10",
        "metric": "avg_roe_pct",
        "label": "Average ROE below Nifty 100 sample median",
        "condition": lambda x: x < 15.614,
        "confidence": lambda x: min(90.0, 65.0 + (15.614 - x) * 1.0),
        "unit": "%",
        "threshold": "< 15.614% (sample median)",
    },
    {
        "id": "C11",
        "metric": "avg_debt_to_equity",
        "label": "Historically high leverage",
        "condition": lambda x: x > 2,
        "confidence": lambda x: min(95.0, 65.0 + (x - 2) * 8),
        "unit": "x",
        "threshold": "> 2",
    },
    {
        "id": "C12",
        "metric": "avg_fcf_cr",
        "label": "Negative average free cash flow",
        "condition": lambda x: x < 0,
        "confidence": lambda x: min(95.0, 65.0 + min(abs(x), 25) * 0.5),
        "unit": "cr",
        "threshold": "< 0 cr",
    },
    {
        "id": "C13",
        "metric": "latest_revenue_growth_pct",
        "label": "Latest revenue contraction",
        "condition": lambda x: x < 0,
        "confidence": lambda x: min(95.0, 65.0 + min(abs(x), 20) * 1.2),
        "unit": "%",
        "threshold": "< 0%",
    },

]


def load_companies() -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            "SELECT * FROM company_summary ORDER BY company_id",
            con,
        )

    if df.empty:
        raise ValueError("company_summary contains no companies")

    if df["company_id"].duplicated().any():
        raise ValueError("company_summary has duplicate company_id values")

    return df


def evaluate_rules(
    companies: pd.DataFrame,
    rules: list[dict],
    finding_type: str,
) -> list[dict]:
    findings = []

    for _, company in companies.iterrows():
        company_id = str(company["company_id"])

        for rule in rules:
            value = company.get(rule["metric"])

            # Missing or non-finite values must not trigger a finding.
            if pd.isna(value):
                continue

            value = float(value)
            if not pd.notna(value):
                continue

            if not rule["condition"](value):
                continue

            confidence = float(rule["confidence"](value))
            confidence = max(0.0, min(100.0, confidence))

            # Keep only findings above the required confidence threshold.
            if confidence <= MIN_CONFIDENCE:
                continue

            findings.append({
                "company_id": company_id,
                "finding_type": finding_type,
                "rule_id": rule["id"],
                "finding": rule["label"],
                "metric": rule["metric"],
                "metric_value": value,
                "unit": rule["unit"],
                "threshold": rule["threshold"],
                "confidence_pct": round(confidence, 2),
                "source_table": "company_summary",
            })

    return findings


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    companies = load_companies()

    findings = (
        evaluate_rules(companies, PRO_RULES, "PRO")
        + evaluate_rules(companies, CON_RULES, "CON")
    )

    columns = [
        "company_id",
        "finding_type",
        "rule_id",
        "finding",
        "metric",
        "metric_value",
        "unit",
        "threshold",
        "confidence_pct",
        "source_table",
    ]

    result = pd.DataFrame(findings, columns=columns)

    if not result.empty:
        result = result.sort_values(
            ["company_id", "finding_type", "confidence_pct"],
            ascending=[True, True, False],
        )

    result.to_csv(OUTPUT_PATH, index=False)

    print("\n=== PROS AND CONS GENERATOR ===")
    print(f"Companies evaluated: {len(companies)}")
    print(f"Pro rules configured: {len(PRO_RULES)}")
    print(f"Con rules configured: {len(CON_RULES)}")
    print(f"Total rules configured: {len(PRO_RULES) + len(CON_RULES)}")
    print(f"Confidence requirement: > {MIN_CONFIDENCE:.0f}%")
    print(f"Generated findings: {len(result)}")

    if result.empty:
        print("No findings passed the confidence threshold.")
    else:
        print("\nFindings by type:")
        print(result["finding_type"].value_counts().to_string())

        print("\nUnique companies with at least one pro:")
        print(result.loc[result["finding_type"] == "PRO", "company_id"].nunique())

        print("Unique companies with at least one con:")
        print(result.loc[result["finding_type"] == "CON", "company_id"].nunique())

        print("\nTop findings:")
        print(result.head(10).to_string(index=False))

    print(f"\nSaved: {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
