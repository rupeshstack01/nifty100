-- NIFTY 100 PROJECT: EXPLORATORY SQL QUERIES
-- Database: data/processed/nifty100.db
-- Run these queries against the database in read-only mode.

-- Q1. Top 20 companies by overall score
SELECT company_id, overall_score, rank,
       revenue_cagr_pct, net_profit_cagr_pct,
       latest_net_profit_margin_pct, latest_roe_pct
FROM company_scorecard
ORDER BY overall_score DESC
LIMIT 20;

-- Q2. Company financial overview
SELECT company_id, first_available_year, latest_available_year,
       latest_sales, latest_net_profit,
       latest_net_profit_margin_pct, latest_roe_pct,
       latest_debt_to_equity, latest_fcf_cr
FROM company_summary
ORDER BY latest_sales DESC
LIMIT 20;

-- Q3. Number of companies in each broad sector
SELECT broad_sector,
       COUNT(DISTINCT company_id) AS company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC, broad_sector;

-- Q4. Average financial ratios by sector
SELECT broad_sector,
       COUNT(*) AS records,
       ROUND(AVG(engine_net_profit_margin_pct), 2) AS avg_net_profit_margin,
       ROUND(AVG(engine_return_on_equity_pct), 2) AS avg_roe,
       ROUND(AVG(engine_debt_to_equity), 2) AS avg_debt_to_equity,
       ROUND(AVG(engine_interest_coverage), 2) AS avg_interest_coverage
FROM financial_ratios
GROUP BY broad_sector
ORDER BY avg_roe DESC;

-- Q5. Companies flagged for high leverage
SELECT company_id, broad_sector, year,
       engine_debt_to_equity, engine_interest_coverage,
       high_leverage_flag, icr_label, icr_warning
FROM financial_ratios
WHERE high_leverage_flag = 1
ORDER BY engine_debt_to_equity DESC
LIMIT 50;

-- Q6. Cash-flow quality distribution
SELECT cfo_quality_label,
       COUNT(*) AS record_count,
       ROUND(AVG(fcf_conversion_pct), 2) AS avg_fcf_conversion,
       ROUND(AVG(cfo_pat_ratio), 2) AS avg_cfo_pat_ratio
FROM financial_ratios
GROUP BY cfo_quality_label
ORDER BY record_count DESC;

-- Q7. Five-year revenue and profit CAGR flag distribution
SELECT 'Revenue CAGR 5Y' AS metric,
       revenue_cagr_5yr_flag AS flag,
       COUNT(*) AS record_count
FROM financial_ratios
GROUP BY revenue_cagr_5yr_flag
UNION ALL
SELECT 'PAT CAGR 5Y',
       pat_cagr_5yr_flag,
       COUNT(*)
FROM financial_ratios
GROUP BY pat_cagr_5yr_flag
ORDER BY metric, record_count DESC;

-- Q8. Peer percentile distribution by metric
SELECT metric,
       COUNT(*) AS observations,
       ROUND(AVG(percentile_rank), 2) AS avg_percentile,
       ROUND(MIN(percentile_rank), 2) AS min_percentile,
       ROUND(MAX(percentile_rank), 2) AS max_percentile
FROM peer_percentiles
GROUP BY metric
ORDER BY avg_percentile DESC;

-- Q9. Average annual stock returns
SELECT year,
       COUNT(*) AS company_observations,
       ROUND(AVG(annual_return_pct), 2) AS avg_annual_return_pct,
       ROUND(MIN(annual_return_pct), 2) AS lowest_return_pct,
       ROUND(MAX(annual_return_pct), 2) AS highest_return_pct
FROM annual_stock_returns
GROUP BY year
ORDER BY year;

-- Q10. Monthly return observations by company
SELECT company_id,
       COUNT(monthly_return_pct) AS return_observations,
       ROUND(AVG(monthly_return_pct), 2) AS avg_monthly_return_pct,
       ROUND(MIN(monthly_return_pct), 2) AS lowest_return_pct,
       ROUND(MAX(monthly_return_pct), 2) AS highest_return_pct
FROM stock_returns
GROUP BY company_id
ORDER BY avg_monthly_return_pct DESC
LIMIT 20;

-- Q11. Financial quality review status
SELECT quality_score_status,
       panel_needs_review,
       COUNT(*) AS record_count,
       ROUND(AVG(composite_quality_score), 2) AS avg_quality_score
FROM financial_ratios
GROUP BY quality_score_status, panel_needs_review
ORDER BY record_count DESC;

-- Q12. Company-level financial panel coverage
SELECT company_id,
       COUNT(*) AS available_years,
       MIN(year) AS first_year,
       MAX(year) AS latest_year,
       ROUND(AVG(net_profit_margin_pct), 2) AS avg_net_profit_margin,
       ROUND(AVG(return_on_equity_pct), 2) AS avg_roe
FROM financial_panel
GROUP BY company_id
ORDER BY available_years DESC, company_id;
