# Nifty100 Stock Analytics & ETL Pipeline

## 1. Project Overview

This project builds an end-to-end ETL and analytics pipeline for Nifty100
companies using financial, sector, and stock-price datasets.

The pipeline transforms raw Excel files into validated, cleaned and
analytically useful datasets and stores the final analytical layer in a
SQLite database.

The project combines:

- Data ingestion
- Data cleaning
- Duplicate detection
- Duplicate classification
- Data-quality validation
- Financial data integration
- Derived financial metrics
- Company-level summaries
- Stock return calculation
- Annual stock performance analysis
- Company performance scoring
- SQL-based business analysis
- Data visualization

---

## 2. Project Objectives

The main objectives are:

1. Build a reliable ETL pipeline for Nifty100 financial data.
2. Detect and document duplicate and variant financial records.
3. Validate financial and stock-price data.
4. Integrate multiple financial datasets at company-year level.
5. Calculate additional financial metrics.
6. Analyze historical stock performance.
7. Compare company fundamentals with stock performance.
8. Build a multi-factor company performance scorecard.
9. Store analytical datasets in SQLite.
10. Generate business-oriented analytical insights and visualizations.

---

## 3. Data Sources

The project uses 12 raw Excel datasets:

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

The raw files are stored under:

`data/raw/`

Raw data is preserved and is not overwritten during processing.

---

## 4. ETL Architecture

The project follows this pipeline:

Raw Excel Files
        |
        v
Data Ingestion
        |
        v
Normalization
        |
        v
Duplicate Detection
        |
        v
Duplicate Classification
        |
        v
Data Quality Validation
        |
        v
Clean Financial Tables
        |
        v
Financial Panel
        |
        v
Derived Metrics
        |
        v
Company Summary
        |
        +--------------------+
        |                    |
        v                    v
Stock Prices          Annual Returns
        |                    |
        +---------+----------+
                  |
                  v
        Company Performance
             Scorecard
                  |
                  v
             SQLite DB
                  |
                  v
          SQL Analytics
                  |
                  v
          Visualizations

---

## 5. Project Structure

```text
nifty100/
│
├── data/
│   ├── raw/
│   └── processed/
│       ├── analytical/
│       ├── audit/
│       └── review/
│
├── src/
│   └── etl/
│       ├── loader.py
│       ├── normaliser.py
│       ├── validator.py
│       ├── deduplicator.py
│       ├── canonical_resolver.py
│       ├── build_clean_dataset.py
│       ├── build_financial_panel.py
│       ├── build_derived_metrics.py
│       ├── build_company_summary.py
│       ├── build_stock_returns.py
│       ├── build_annual_stock_returns.py
│       ├── build_company_scorecard.py
│       ├── build_database.py
│       └── build_visualizations.py
│
├── results/
│   └── charts/
│
├── sql_analysis.sql
├── requirements.txt
└── README.md
