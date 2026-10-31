# Nifty100 API Performance Benchmark

## Test configuration

- Warm-up requests per endpoint: 5
- Measured requests per endpoint: 50
- Execution: local FastAPI TestClient, sequential requests
- Successful response expected: HTTP 200
- Database: data/processed/nifty100.db
- Company ID: ABB
- Sector: Industrials

## Results

| Endpoint | Status | Avg ms | P50 ms | P95 ms | P99 ms | RPS | Errors |
|---|---|---:|---:|---:|---:|---:|---:|
| Health | PASS | 0.244 | 0.24 | 0.253 | 0.375 | 4102.68 | 0 |
| Companies list | PASS | 12.0 | 11.802 | 12.389 | 16.646 | 83.33 | 0 |
| Company detail | PASS | 6.568 | 6.143 | 8.01 | 11.603 | 152.24 | 0 |
| Company metrics | PASS | 6.01 | 6.003 | 6.241 | 6.274 | 166.37 | 0 |
| Screener | PASS | 11.965 | 11.836 | 12.711 | 13.886 | 83.57 | 0 |
| Sectors list | PASS | 0.566 | 0.553 | 0.593 | 1.058 | 1766.26 | 0 |
| Sector detail | PASS | 8.638 | 8.41 | 9.864 | 10.069 | 115.76 | 0 |
| Peer comparison | PASS | 7.898 | 7.71 | 8.44 | 12.454 | 126.61 | 0 |
| Clusters list | PASS | 1.122 | 1.108 | 1.204 | 1.246 | 891.24 | 0 |
| Company cluster | PASS | 1.106 | 1.101 | 1.178 | 1.287 | 904.16 | 0 |
| Outliers | PASS | 0.769 | 0.752 | 0.854 | 1.014 | 1299.24 | 0 |
| Valuation | PASS | 5.63 | 5.596 | 5.856 | 6.128 | 177.61 | 0 |
| Portfolio stats | PASS | 0.738 | 0.73 | 0.796 | 0.814 | 1353.71 | 0 |
| Data quality | PASS | 3.783 | 3.77 | 3.9 | 3.918 | 264.31 | 0 |
| Reports | PASS | 0.488 | 0.485 | 0.512 | 0.543 | 2047.06 | 0 |
| Cluster detail | PASS | 1.654 | 1.649 | 1.726 | 1.818 | 604.63 | 0 |

## Summary

- Endpoints tested: 16
- Endpoints passing: 16
- Endpoints with errors or non-200 responses: 0
- Measured requests per passing endpoint: 50

## Limitations

This is a sequential in-process TestClient benchmark. It does not represent production network latency or concurrent-user capacity. No external performance threshold was supplied; results are measurements, not proof of compliance with an unstated SLA.
