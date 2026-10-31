from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sqlite3
import csv
import json
import time
import math
import statistics
from urllib.parse import quote

from fastapi.testclient import TestClient
from src.api.main import app

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/processed/nifty100.db"
OUTPUT = ROOT / "reports/performance"

WARMUP = 5
ITERATIONS = 50

OUTPUT.mkdir(parents=True, exist_ok=True)

# Obtain real identifiers from the production database.
with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as con:
    con.execute("PRAGMA query_only = ON")
    company_row = con.execute(
        "SELECT company_id FROM company_summary LIMIT 1"
    ).fetchone()
    sector_row = con.execute(
        "SELECT broad_sector FROM sectors LIMIT 1"
    ).fetchone()

    if not company_row or not sector_row:
        raise RuntimeError("Could not find company or sector test data.")

    company_id = str(company_row[0])
    sector_name = str(sector_row[0])

requests_to_test = [
    ("Health", "/health"),
    ("Companies list", "/companies?limit=100&offset=0"),
    ("Company detail", f"/companies/{quote(company_id, safe='')}"),
    ("Company metrics", f"/companies/{quote(company_id, safe='')}/metrics"),
    ("Screener", "/screener?limit=100"),
    ("Sectors list", "/sectors"),
    ("Sector detail", f"/sectors/{quote(sector_name, safe='')}"),
    ("Peer comparison", f"/peers/{quote(company_id, safe='')}?limit=10"),
    ("Clusters list", "/clusters"),
    ("Company cluster", f"/companies/{quote(company_id, safe='')}/cluster"),
    ("Outliers", "/outliers"),
    ("Valuation", f"/valuation?company_id={quote(company_id, safe='')}"),
    ("Portfolio stats", "/portfolio/stats"),
    ("Data quality", "/data-quality"),
    ("Reports", "/reports"),
]

def find_cluster_ids(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"cluster_id", "cluster"}:
                if isinstance(item, int) or (
                    isinstance(item, str) and item.isdigit()
                ):
                    found.append(int(item))
            found.extend(find_cluster_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(find_cluster_ids(item))
    return found

results = []

with TestClient(app) as client:
    # Discover a real cluster ID from the API response.
    cluster_response = client.get("/clusters")
    if cluster_response.status_code == 200:
        cluster_ids = sorted(set(find_cluster_ids(cluster_response.json())))
        if cluster_ids:
            requests_to_test.append(
                ("Cluster detail", f"/clusters/{cluster_ids[0]}")
            )

    print("Company ID used:", company_id)
    print("Sector used:", sector_name)
    print("Warm-up requests per endpoint:", WARMUP)
    print("Measured requests per endpoint:", ITERATIONS)
    print("\n===== API BENCHMARK =====")

    for name, path in requests_to_test:
        # Initial smoke check.
        try:
            response = client.get(path)
            initial_status = response.status_code
        except Exception as exc:
            print(f"{name}: ERROR - {exc}")
            results.append({
                "endpoint": name,
                "path": path,
                "status": "ERROR",
                "requests": 0,
                "errors": 1,
                "avg_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "min_ms": None,
                "max_ms": None,
                "requests_per_second": None,
                "error_detail": str(exc),
            })
            continue

        if initial_status != 200:
            print(f"{name}: HTTP {initial_status} - not benchmarked")
            results.append({
                "endpoint": name,
                "path": path,
                "status": initial_status,
                "requests": 0,
                "errors": 1,
                "avg_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "min_ms": None,
                "max_ms": None,
                "requests_per_second": None,
                "error_detail": "Initial smoke check did not return HTTP 200",
            })
            continue

        # Warm-up.
        for _ in range(WARMUP):
            client.get(path)

        timings = []
        errors = 0
        start_all = time.perf_counter()

        for _ in range(ITERATIONS):
            start = time.perf_counter()
            try:
                response = client.get(path)
                elapsed = (time.perf_counter() - start) * 1000
                timings.append(elapsed)
                if response.status_code != 200:
                    errors += 1
            except Exception:
                timings.append((time.perf_counter() - start) * 1000)
                errors += 1

        total_seconds = time.perf_counter() - start_all
        ordered = sorted(timings)

        def percentile(p):
            index = max(0, math.ceil(p * len(ordered)) - 1)
            return round(ordered[index], 3)

        row = {
            "endpoint": name,
            "path": path,
            "status": "PASS" if errors == 0 else "ERROR",
            "requests": len(timings),
            "errors": errors,
            "avg_ms": round(statistics.mean(timings), 3),
            "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95),
            "p99_ms": percentile(0.99),
            "min_ms": round(min(timings), 3),
            "max_ms": round(max(timings), 3),
            "requests_per_second": round(
                len(timings) / total_seconds, 2
            ) if total_seconds else 0,
            "error_detail": "",
        }
        results.append(row)

        print(
            f"{name}: {row['status']} | "
            f"avg={row['avg_ms']} ms | "
            f"p95={row['p95_ms']} ms | "
            f"RPS={row['requests_per_second']} | "
            f"errors={errors}"
        )

# Save detailed CSV.
csv_path = OUTPUT / "api_performance_results.csv"
with csv_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    writer.writeheader()
    writer.writerows(results)

successful = [r for r in results if r["status"] == "PASS"]
failed = [r for r in results if r["status"] != "PASS"]

# Save readable report.
report_path = OUTPUT / "api_performance_report.md"
with report_path.open("w") as f:
    f.write("# Nifty100 API Performance Benchmark\n\n")
    f.write("## Test configuration\n\n")
    f.write(f"- Warm-up requests per endpoint: {WARMUP}\n")
    f.write(f"- Measured requests per endpoint: {ITERATIONS}\n")
    f.write("- Execution: local FastAPI TestClient, sequential requests\n")
    f.write("- Successful response expected: HTTP 200\n")
    f.write("- Database: data/processed/nifty100.db\n")
    f.write("- Company ID: " + company_id + "\n")
    f.write("- Sector: " + sector_name + "\n\n")
    f.write("## Results\n\n")
    f.write("| Endpoint | Status | Avg ms | P50 ms | P95 ms | P99 ms | RPS | Errors |\n")
    f.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
    for r in results:
        f.write(
            f"| {r['endpoint']} | {r['status']} | "
            f"{r['avg_ms']} | {r['p50_ms']} | {r['p95_ms']} | "
            f"{r['p99_ms']} | {r['requests_per_second']} | "
            f"{r['errors']} |\n"
        )
    f.write("\n## Summary\n\n")
    f.write(f"- Endpoints tested: {len(results)}\n")
    f.write(f"- Endpoints passing: {len(successful)}\n")
    f.write(f"- Endpoints with errors or non-200 responses: {len(failed)}\n")
    f.write(f"- Measured requests per passing endpoint: {ITERATIONS}\n")
    f.write("\n## Limitations\n\n")
    f.write(
        "This is a sequential in-process TestClient benchmark. "
        "It does not represent production network latency or concurrent-user "
        "capacity. No external performance threshold was supplied; results "
        "are measurements, not proof of compliance with an unstated SLA.\n"
    )

print("\n===== BENCHMARK SUMMARY =====")
print("Endpoints:", len(results))
print("Passing:", len(successful))
print("Failed/non-200:", len(failed))
print("CSV:", csv_path)
print("Report:", report_path)

if failed:
    print("\nReview these endpoints:")
    for r in failed:
        print(r["endpoint"], r["path"], r["status"], r["error_detail"])
