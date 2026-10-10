# Nifty 100 Stock Analytics & ETL Pipeline

An end-to-end financial data engineering and analytics project that processes Nifty 100 company data, builds an analytical SQLite database, calculates financial metrics, evaluates company performance, and presents insights through an interactive Streamlit dashboard.

## 1. Project Overview

This project combines data engineering, financial analytics, stock performance analysis, and interactive visualization.

The pipeline transforms raw Excel datasets into cleaned and validated financial tables, integrates company-level and yearly records, calculates derived metrics, and stores analytical outputs in SQLite.

The Streamlit dashboard provides company profiles, stock screening, peer comparison, historical trends, sector analysis, capital allocation analysis, annual report discovery, and valuation analysis.

### Key capabilities

- ETL pipeline for multiple financial datasets
- Duplicate detection, classification, and variant resolution
- Data quality validation and audit reports
- Financial data integration and derived metric calculation
- Company summaries and performance scorecards
- Historical stock returns and annual performance analysis
- Multi-factor stock screener
- Peer comparison and sector analysis
- Financial trend and capital allocation analysis
- P/E versus sector median valuation screening
- FCF yield and dividend yield analysis
- Excel and CSV report generation
- Interactive Streamlit dashboard
- Automated tests using pytest

## 2. Project Objectives

1. Build a reproducible financial ETL pipeline.
2. Detect and document duplicate and variant financial records.
3. Validate financial and stock-price datasets.
4. Integrate financial statements and market data.
5. Calculate financial ratios and derived metrics.
6. Analyze company fundamentals and historical stock performance.
7. Compare companies with peers and sector benchmarks.
8. Build company performance rankings and screening criteria.
9. Generate valuation screening signals.
10. Store analytical datasets in SQLite.
11. Present results through an interactive dashboard.
12. Maintain automated tests and data-quality documentation.

## 3. Technology Stack

| Area | Technology |
|---|---|
| Programming language | Python |
| Data processing | Pandas, NumPy |
| Database | SQLite |
| Interactive dashboard | Streamlit |
| Visualizations | Streamlit charts and Matplotlib-based project outputs |
| Excel processing | openpyxl, Pandas |
| Configuration | YAML |
| Testing | pytest |
| Source data | Excel workbooks and CSV datasets |

The installed packages and dependencies are defined in `requirements.txt`.

## 4. Data Sources

The project uses 12 raw Excel datasets supplied with the project:

- Analysis
- Balance Sheet
- Cash Flow
- Companies
- Documents
- Profit and Loss
- Pros and Cons
- Financial Ratios
- Market Capitalization
- Peer Groups
- Sectors
- Stock Prices

Raw files are stored in `data/raw/`.

Processed financial datasets and the primary SQLite database are stored in `data/processed/`.

The market capitalization workbook includes yearly valuation fields such as:

- Market capitalization
- Enterprise value
- Price-to-earnings ratio (P/E)
- Price-to-book ratio (P/B)
- EV/EBITDA
- Dividend yield

The available valuation dataset covers 92 companies for each year from 2019 through 2024.

**Data note:** The outputs depend on the supplied datasets. Data availability, identifier consistency, duplicate records, and unusual financial values must be reviewed before interpreting results as investment-grade information.

## 5. ETL Architecture

The project follows this general workflow:

```text
Raw Excel Datasets
        |
        v
Data Ingestion and Normalization
        |
        v
Duplicate Detection and Resolution
        |
        v
Data Quality Validation
        |
        v
Clean Financial Tables
        |
        v
Financial Panel and Derived Metrics
        |
        v
Company Summary and Stock Returns
        |
        v
Company Performance Scorecard
        |
        v
SQLite Analytical Database
        |
        +--------------------------+
        |                          |
        v                          v
Financial Analytics         Valuation Analytics
        |                          |
        +-------------+------------+
                      |
                      v
             Streamlit Dashboard
                      |
                      v
          Excel and CSV Exports
```

The ETL modules are located in `src/etl/`.

## 6. Project Structure

```text
nifty100/
├── config/
│   └── screener_config.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   │   ├── nifty100.db
│   │   ├── *_cleaned.csv
│   │   └── analytical/
│   ├── audit/
│   └── review/
├── output/
│   ├── valuation_summary.xlsx
│   ├── valuation_flags.csv
│   └── other analytical exports
├── pages/
│   ├── 01_home.py
│   ├── 02_profile.py
│   ├── 03_screener.py
│   ├── 04_peers.py
│   ├── 05_trends.py
│   ├── 06_sectors.py
│   ├── 07_capital.py
│   ├── 08_reports.py
│   └── 09_valuation.py
├── reports/
│   └── radar_charts/
├── results/
│   └── charts/
├── src/
│   ├── analytics/
│   │   └── valuation.py
│   ├── dashboard/
│   │   ├── app.py
│   │   └── utils/
│   ├── etl/
│   └── screener/
├── tests/
├── inspect_sources.py
├── sql_analysis.sql
├── requirements.txt
├── Makefile
└── README.md
```

Some generated files and optional audit directories may vary as the pipeline is run.

## 7. Installation and Setup

### Prerequisites

- Python 3.11 or later recommended, subject to dependency compatibility
- Git
- macOS, Linux, or Windows
- The supplied project datasets

The current development environment has been tested with Python 3.14.

### Step 1: Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd nifty100
```

Replace the placeholder with your actual repository URL.

### Step 2: Create a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you use the existing virtual environment on macOS, commands can be run with `./.venv/bin/python` without activating it.

### Step 4: Verify the project

```bash
python -m pytest -q
```

## 8. Running the Dashboard

Start the Streamlit application from the project root:

```bash
python -m streamlit run src/dashboard/app.py
```

Streamlit prints a local URL in the terminal, usually:

```text
http://localhost:8501
```

The port may differ if another Streamlit application is already running.

### Dashboard pages

| Page | Purpose |
|---|---|
| Home | High-level company and sector metrics |
| Company Profile | Company-level financial information |
| Stock Screener | Filter and rank companies |
| Peer Comparison | Compare companies with peer groups |
| Trend Analysis | Explore historical financial trends |
| Sector Analysis | Compare sector-level performance |
| Capital Allocation | Examine cash flow and capital allocation metrics |
| Annual Reports | Browse available annual report links |
| Valuation Analysis | Compare valuation multiples and yields |

## 9. Valuation Analysis

The valuation engine is implemented in `src/analytics/valuation.py`.

### Generate valuation reports

Run:

```bash
python src/analytics/valuation.py
```

The script reads the market capitalization workbook and financial data from the SQLite database.

### Valuation metrics

**FCF yield**

FCF yield compares free cash flow with market capitalization:

[
\text{FCF Yield (\%)} =
\frac{\text{Free Cash Flow}}{\text{Market Capitalization}}
\times 100
]

Both inputs must use consistent units.

**P/E relative to sector median**

[
\text{Relative P/E} =
\frac{\text{Company P/E}}{\text{Sector Median P/E}}
]

The screening classifications currently use these rules:

| Classification | Rule |
|---|---|
| Discount | Positive P/E below 70% of sector median |
| Fair | P/E from 70% through 150% of sector median |
| Caution | P/E above 150% of sector median |
| Insufficient Data | Invalid P/E or unavailable valid sector median |

These labels are relative valuation screening signals. They do not establish intrinsic value or constitute investment recommendations.

### Generated reports

The valuation engine writes:

```text
output/
├── valuation_summary.xlsx
└── valuation_flags.csv
```

The Excel workbook contains the full valuation summary and a separate worksheet for Discount and Caution companies. The CSV contains companies assigned those two flags.

The Streamlit valuation page reads the generated Excel workbook. Regenerate the report after changing the source data or valuation calculations.

### Data-quality considerations

- Missing FCF must not be interpreted as zero FCF.
- The report records the year associated with the FCF used for the yield calculation.
- FCF year and valuation year may differ.
- Unusually large financial values should be checked against source records.
- Sector medians depend on the companies and valid P/E observations available in each sector.
- The quality of valuation conclusions depends on the reliability of the supplied financial data.

## 10. Testing and Validation

The project includes automated tests under `tests/`.

Run the full suite:

```bash
python -m pytest -q
```

For more detailed output:

```bash
python -m pytest -v
```

The current development run completed with **63 passing tests**.

Automated tests validate the covered code paths. They do not, by themselves, guarantee the correctness of every financial source record, dashboard interaction, or valuation conclusion.

## 11. SQL Analysis and Outputs

SQL analysis is maintained in:

```text
sql_analysis.sql
```

Generated analytical outputs may include:

- Company performance scorecards
- Annual stock returns
- Peer comparison reports
- Screener results
- Capital allocation exports
- Valuation summaries
- Data-quality and duplicate-resolution reports
- Company radar charts and other visualizations

Generated files are stored under `output/`, `results/`, and `reports/`.

## 12. Reproducibility

For a repeatable workflow:

1. Preserve the original input files in `data/raw/`.
2. Use the project's virtual environment and `requirements.txt`.
3. Run the required ETL modules in the intended pipeline order.
4. Validate the resulting database and financial tables.
5. Run the automated tests.
6. Generate the valuation reports.
7. Launch the Streamlit dashboard.
8. Record any unresolved data-quality issues.

Do not rebuild or overwrite analytical data until the required ETL sequence and its dependencies have been confirmed.

## 13. Limitations

- The project analyzes supplied datasets and is not a live market-data platform.
- Some financial records or metrics may be missing or inconsistent.
- Company identifiers may differ between source datasets.
- Annual report links originate from the supplied workbook and may require independent verification.
- Historical financial and stock performance does not guarantee future results.
- Valuation flags are screening outputs, not personalized financial advice.
- Financial figures should be independently verified before being used for investment decisions.

## 14. Future Improvements

Potential improvements include:

- Stronger company identifier reconciliation
- Additional validation for unusual financial values
- More comprehensive data-quality reporting
- Automated dashboard integration tests
- Improved valuation metrics and configurable screening thresholds
- Reproducible end-to-end ETL orchestration
- Automated documentation and deployment
- Additional market-data validation and refresh mechanisms

## 15. Author and Project Information

**Project:** Nifty 100 Stock Analytics & ETL Pipeline

**Repository:** Add your GitHub repository URL.

**Author:** Add your preferred name and contact information.

---

*This project is intended for educational, analytical, and software engineering demonstration purposes. Verify all financial information independently before relying on it for investment decisions.*
