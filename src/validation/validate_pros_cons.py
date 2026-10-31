from pathlib import Path
import pandas as pd

OUTPUT_PATH = Path("output/pros_cons_generated.csv")

def main():
    if not OUTPUT_PATH.exists():
        raise FileNotFoundError(f"Output not found: {OUTPUT_PATH}")

    df = pd.read_csv(OUTPUT_PATH)

    required_columns = [
        "company_id", "finding_type", "rule_id", "finding",
        "metric", "metric_value", "confidence_pct",
    ]

    missing_columns = [c for c in required_columns if c not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")

    checks = {
        "Rows": len(df),
        "Unique companies": df["company_id"].nunique(),
        "Exact duplicate rows": int(df.duplicated().sum()),
        "Duplicate company/type/rule combinations": int(
            df.duplicated(["company_id", "finding_type", "rule_id"]).sum()
        ),
        "Missing company IDs": int(df["company_id"].isna().sum()),
        "Missing finding text": int(df["finding"].isna().sum()),
        "Missing metric values": int(df["metric_value"].isna().sum()),
        "Confidence outside 0-100": int(
            (~df["confidence_pct"].between(0, 100)).sum()
        ),
    }

    print("=== PROS AND CONS VALIDATION ===")
    for label, value in checks.items():
        print(f"{label}: {value}")

    print("\nFindings by type:")
    print(df["finding_type"].value_counts().to_string())

    problems = [
        "Exact duplicate rows",
        "Duplicate company/type/rule combinations",
        "Missing company IDs",
        "Missing finding text",
        "Missing metric values",
        "Confidence outside 0-100",
    ]

    failed = [name for name in problems if checks[name] != 0]
    if failed:
        raise SystemExit(f"\nVALIDATION FAILED: {', '.join(failed)}")

    print("\nVALIDATION PASSED")

if __name__ == "__main__":
    main()