# Nifty 100 Stock Analytics & Financial Data Engineering Platform

An end-to-end Python-based financial data engineering and analytics project that combines ETL automation, financial statement analysis, stock performance evaluation, company screening, valuation analytics, interactive dashboards and REST API development.

The platform processes company-level financial and market datasets, performs data cleaning and validation, calculates financial metrics, generates analytical reports, and exposes selected insights through a Streamlit dashboard and FastAPI.

> **Project purpose:** Educational, analytical and software engineering demonstration. This project is not a live trading platform or a source of investment advice.

---

## 1. Project Overview

The Nifty 100 Analytics project is designed to transform financial datasets into structured, reusable and interpretable analytical outputs.

It brings together:

- Financial data engineering and ETL pipelines.
- Data cleaning, normalization and validation.
- Financial ratios and derived metric calculations.
- Company performance scorecards.
- Historical stock return analysis.
- Stock screening and peer comparison.
- Sector and valuation analysis.
- Capital allocation and cash flow intelligence.
- Interactive Streamlit dashboard.
- FastAPI-based read-only REST API.
- Machine learning-based company clustering.
- Automated testing and performance benchmarking.
- PDF, Excel, CSV and visualization reports.

The analytical universe covers **92 companies across 10 sectors** in the prepared project outputs.

## 2. Key Features

### Data Engineering and ETL

- Ingestion of multiple financial datasets.
- Data normalization and cleaning.
- Duplicate detection and canonical company resolution.
- Financial data validation and quality checks.
- Integration of company-level and annual financial records.
- Construction of financial panels and analytical tables.
- SQLite database generation and structured storage.

### Financial Analytics

- Financial ratio calculations.
- Derived financial metrics.
- Company performance scorecards.
- Historical stock returns and annual performance.
- Company-level financial trend analysis.
- Peer benchmarking and sector comparisons.
- Valuation screening using P/E and sector medians.
- Free cash flow yield and dividend yield analysis.
- Cash flow and capital allocation analysis.

### Interactive Dashboard

The Streamlit dashboard provides an interactive interface for exploring company and sector-level insights.

Major analytical areas include:

- Home and overview.
- Company profiles.
- Stock screening.
- Peer comparison.
- Financial trend analysis.
- Sector analysis.
- Capital allocation.
- Annual report discovery.
- Valuation analysis.

### REST API

A FastAPI application provides read-only access to analytical information.

- REST endpoints for company and sector analytics.
- Structured JSON responses.
- Interactive API documentation.
- Exported OpenAPI schema.
- API endpoint tests and performance benchmarks.

API documentation is available at `/docs` when the application is running.

### Sprint 6 Analytics

The final sprint extends the platform with:

- Company clustering.
- K-Means-based analytical segmentation.
- StandardScaler-based feature scaling.
- Cluster profiles and labels.
- Outlier analysis.
- Portfolio statistics.
- Correlation heatmap.
- Elbow plot.
- Company tearsheets.
- Sector reports.
- Portfolio summary.
- Acceptance checklist and performance reports.

## 3. Technology Stack

| Area | Technologies |
|---|---|
| Programming | Python |
| Data processing | Pandas, NumPy |
| Database | SQLite |
| Dashboard | Streamlit |
| API | FastAPI, Uvicorn |
| Machine learning | Scikit-learn |
| Visualization | Matplotlib |
| Excel processing | Pandas, openpyxl |
| Configuration | YAML |
| Testing | pytest |
| Version control | Git, GitHub |

The Python dependencies are maintained in `requirements.txt`.

## 4. System Architecture

The project follows a modular data engineering and analytics architecture.

```text
             FINANCIAL DATASETS
                     |
                     v
              DATA INGESTION
                     |
                     v
           NORMALIZATION & CLEANING
                     |
                     v
          DUPLICATE DETECTION AND
             CANONICAL RESOLUTION
                     |
                     v
             DATA VALIDATION
                     |
                     v
           CLEAN FINANCIAL TABLES
                     |
                     v
          FINANCIAL PANEL BUILDING
                     |
                     v
           DERIVED METRIC ENGINE
                     |
                     v
          COMPANY SUMMARY & RETURNS
                     |
                     v
             SQLITE DATABASE
                     |
          +----------+----------+
          |          |          |
          v          v          v
      FINANCIAL   VALUATION   SPRINT 6
      ANALYTICS   ANALYTICS   ANALYTICS
          |          |          |
          +----------+----------+
                     |
             +-------+-------+
             |               |
             v               v
        STREAMLIT         FASTAPI
        DASHBOARD       REST INTERFACE
             |               |
             v               v
       VISUAL REPORTS    JSON RESPONSES
             |
             v
       PDF / EXCEL / CSV
```

## 5. Project Structure

The public repository contains source code, configuration, tests and selected documentation and reports. Local datasets, databases and generated working outputs are excluded.

```text
nifty100/
│
├── config/
│   └── screener_config.yaml
│
├── docs/
│   ├── analyst_guide.pdf
│   ├── acceptance_checklist.pdf
│   └── openapi.json
│
├── notebooks/
│   └── exploratory_queries.sql
│
├── reports/
│   ├── performance/
│   ├── portfolio/
│   ├── sector/
│   ├── tearsheets/
│   ├── correlation_heatmap.png
│   └── elbow_plot.png
│
├── src/
│   ├── analytics/
│   ├── api/
│   │   └── main.py
│   ├── dashboard/
│   │   └── app.py
│   ├── etl/
│   ├── nlp/
│   └── validation/
│
├── tests/
│   ├── analytics/
│   ├── etl/
│   ├── performance/
│   └── API and integration tests
│
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

**Note:** The local development environment contains additional directories and data files that are intentionally not published.

## 6. Installation and Setup

### Prerequisites

- Python 3.11 or later, subject to dependency compatibility.
- Git.
- pip.
- The required project input datasets for full pipeline execution.

The development environment was tested using Python 3.14.

### Step 1: Clone the repository

```bash
git clone https://github.com/rupeshstack01/nifty100.git

cd nifty100
```

### Step 2: Create a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv

source .venv/bin/activate
```

### Step 3: Install dependencies

```bash
python -m pip install --upgrade pip

python -m pip install -r requirements.txt
```

### Step 4: Prepare input data

The raw financial datasets and SQLite database are not included in this public repository.

To run the complete data pipeline, obtain the authorized project input datasets and place them in the expected local data directories. Follow the Analyst Guide for the required data preparation and execution sequence.

Do not commit private datasets, credentials or local database files.

## 7. Running the Applications

### Streamlit Dashboard

From the project root:

```bash
python -m streamlit run src/dashboard/app.py
```

Open the local URL printed by Streamlit, normally:

```text
http://localhost:8501
```

The dashboard requires the relevant prepared analytical data and supporting local files.

### FastAPI Application

Start the API:

```bash
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

The exported API schema is available in:

```text
docs/openapi.json
```

The API uses the project's prepared analytical data. A fresh clone may require local data preparation before all endpoints can return project results.

## 8. Financial Analytics

The project implements multiple layers of financial analysis.

### Company Performance

- Company-level financial summaries.
- Historical performance.
- Annual stock returns.
- Financial ratio analysis.
- Derived financial indicators.
- Company scorecards.

### Peer and Sector Analysis

- Peer group comparisons.
- Sector-level benchmarking.
- Company ranking and screening.
- Sector performance summaries.

### Valuation Analysis

The valuation analysis includes:

- Price-to-Earnings (P/E).
- Price-to-Book (P/B).
- Enterprise Value (EV).
- EV/EBITDA.
- Dividend yield.
- Free Cash Flow (FCF) yield.
- Relative P/E against sector median.

Example formulas:

**Free Cash Flow Yield**

\[
FCF\ Yield = \frac{Free\ Cash\ Flow}{Market\ Capitalization}\times100
\]

**Relative P/E**

\[
Relative\ P/E = \frac{Company\ P/E}{Sector\ Median\ P/E}
\]

Valuation classifications are screening indicators based on the available data and configured thresholds. They do not establish intrinsic value.

### Cash Flow and Capital Allocation

The project also analyzes financial trends and cash flow-related indicators to support company-level financial evaluation.

## 9. Sprint 6: Clustering and Advanced Analytics

Sprint 6 adds machine learning and advanced reporting capabilities.

### K-Means Clustering

The clustering workflow uses:

- Feature preparation.
- StandardScaler normalization.
- K-Means clustering.
- Five selected clusters.
- Reproducible random state (`42`).
- Cluster labels and cluster profiles.

The clustering outputs support descriptive segmentation of companies based on selected analytical features.

### Generated Analytical Outputs

Selected outputs include:

- Cluster labels.
- Cluster profiles.
- Outlier reports.
- Portfolio statistics.
- Correlation heatmap.
- Elbow plot.
- Company tearsheets.
- Sector reports.
- Portfolio summary.

**Interpretation note:** Cluster labels are descriptive analytical groupings, not buy/sell recommendations. Very small clusters require additional stability and sensitivity analysis.

## 10. Database Design

The local SQLite analytical database is:

```text
data/processed/nifty100.db
```

It contains 10 principal analytical tables:

| Table | Rows |
|---|---:|
| annual_stock_returns | 460 |
| company_scorecard | 90 |
| company_summary | 92 |
| derived_metrics | 973 |
| financial_panel | 973 |
| financial_ratios | 1,076 |
| peer_percentiles | 816 |
| sectors | 92 |
| stock_prices | 5,520 |
| stock_returns | 5,520 |

The database is excluded from GitHub to keep the public repository focused on code and documentation.

## 11. Testing and Validation

Automated testing is maintained using pytest.

Run the test suite:

```bash
python -m pytest -q
```

Run with verbose output:

```bash
python -m pytest -v
```

### Latest recorded development results

| Test / Validation | Result |
|---|---|
| Full pytest suite | 134 passed |
| Warnings | 2 |
| API benchmark endpoints | 16 of 16 passed |
| API benchmark errors | 0 |
| Sector detail regression tests | 12 passed |
| Acceptance gates | 19 of 20 passed |
| Reviewer sign-off | Pending |

The API benchmark used sequential in-process FastAPI TestClient requests with warm-up and measured iterations. It is not a production network or concurrent load test.

The acceptance checklist intentionally leaves reviewer sign-off pending until an actual reviewer approves the project.

## 12. Documentation and Reports

The repository includes selected project documentation and generated reports:

| File / Directory | Description |
|---|---|
| `docs/analyst_guide.pdf` | Project architecture, analytical methods and operating guide |
| `docs/acceptance_checklist.pdf` | Sprint acceptance and validation status |
| `docs/openapi.json` | API specification |
| `reports/sector/` | Sector-level reports |
| `reports/tearsheets/` | Company-level analytical reports |
| `reports/portfolio/` | Portfolio summary |
| `reports/performance/` | API benchmark results |
| `reports/elbow_plot.png` | Clustering evaluation visualization |
| `reports/correlation_heatmap.png` | Feature correlation visualization |

## 13. Data and Project Limitations

Please consider the following before interpreting results:

1. This is an educational and analytical prototype, not a live financial data service.
2. Raw input datasets and the SQLite database are excluded from the public repository.
3. Some prepared market-price inputs are simulated and must not be interpreted as verified live market prices.
4. Financial data availability and quality depend on the supplied source datasets.
5. Company identifiers and financial reporting periods may require reconciliation.
6. Missing or unusual financial values can affect calculated metrics.
7. Historical performance does not guarantee future returns.
8. Machine learning clusters are descriptive, not investment signals.
9. Valuation classifications are screening outputs, not investment recommendations.
10. API benchmark results are local test measurements, not production performance guarantees.

Always independently verify financial information before making investment decisions.

## 14. Future Improvements

Potential areas for further development:

- Automated end-to-end ETL orchestration.
- Additional financial data validation.
- Improved company identifier reconciliation.
- More comprehensive dashboard integration testing.
- Sensitivity analysis for clustering.
- Live, licensed market-data integration.
- API authentication and deployment hardening.
- Automated report generation and scheduled refreshes.
- Production deployment and monitoring.

## 15. Running the Project: Quick Reference

| Task | Command |
|---|---|
| Install dependencies | `python -m pip install -r requirements.txt` |
| Run tests | `python -m pytest -q` |
| Launch dashboard | `python -m streamlit run src/dashboard/app.py` |
| Launch API | `python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000` |
| Run clustering | `python -m src.analytics.clustering_submission` |
| Generate Sprint 6 reports | `python -m src.analytics.build_sprint6_reports` |

Some commands require local datasets or a prepared database that are not included in the public repository.

---

## Project Information

**Project:** Nifty 100 Stock Analytics & Financial Data Engineering Platform

**Repository:** https://github.com/rupeshstack01/nifty100

**Primary language:** Python

**Purpose:** Financial data engineering, analytics, visualization and API development.

**License:** No license has been specified. All rights reserved unless a license is added to the repository.

---

*Built as a hands-on project demonstrating data engineering, financial analytics, machine learning, API development, software testing and technical documentation.*