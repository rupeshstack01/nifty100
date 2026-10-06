-- ============================================================
-- NIFTY100 ANALYTICAL SQL QUERIES
-- ============================================================

-- 1. TOP 10 COMPANIES BY OVERALL PERFORMANCE SCORE
SELECT
    rank,
    company_id,
    ROUND(overall_score, 2) AS overall_score
FROM company_scorecard
ORDER BY rank
LIMIT 10;


-- 2. TOP 10 COMPANIES BY CUMULATIVE STOCK RETURN
SELECT
    company_id,
    ROUND(cumulative_return_pct, 2) AS cumulative_return_pct
FROM company_scorecard
ORDER BY cumulative_return_pct DESC
LIMIT 10;


-- 3. COMPANIES WITH THE HIGHEST REVENUE CAGR
SELECT
    company_id,
    ROUND(revenue_cagr_pct, 2) AS revenue_cagr_pct
FROM company_scorecard
WHERE revenue_cagr_pct IS NOT NULL
ORDER BY revenue_cagr_pct DESC
LIMIT 10;


-- 4. COMPANIES WITH THE HIGHEST NET PROFIT MARGIN
SELECT
    company_id,
    ROUND(latest_net_profit_margin_pct, 2) AS net_profit_margin_pct
FROM company_scorecard
WHERE latest_net_profit_margin_pct IS NOT NULL
ORDER BY latest_net_profit_margin_pct DESC
LIMIT 10;


-- 5. SECTOR-WISE 2023 FINANCIAL PERFORMANCE
SELECT
    s.broad_sector,
    COUNT(DISTINCT f.company_id) AS companies,
    SUM(f.sales) AS total_sales,
    SUM(f.net_profit) AS total_net_profit,
    ROUND(
        SUM(f.net_profit) * 100.0 /
        NULLIF(SUM(f.sales), 0),
        2
    ) AS net_profit_margin_pct,
    ROUND(
        SUM(f.net_profit) * 100.0 /
        NULLIF(
            SUM(f.equity_capital + f.reserves),
            0
        ),
        2
    ) AS aggregate_roe
FROM financial_panel f
JOIN sectors s
    ON f.company_id = s.company_id
WHERE f.year = 2023
GROUP BY s.broad_sector
ORDER BY total_net_profit DESC;


-- 6. YEAR-WISE NIFTY100 FINANCIAL PERFORMANCE
SELECT
    year,
    COUNT(DISTINCT company_id) AS companies,
    SUM(sales) AS total_sales,
    SUM(net_profit) AS total_net_profit,
    ROUND(
        SUM(net_profit) * 100.0 /
        NULLIF(SUM(sales), 0),
        2
    ) AS net_profit_margin_pct
FROM financial_panel
GROUP BY year
ORDER BY year;


-- 7. TOP COMPANIES BY FREE CASH FLOW
SELECT
    company_id,
    ROUND(latest_fcf_cr, 2) AS latest_fcf_cr
FROM company_summary
WHERE latest_fcf_cr IS NOT NULL
ORDER BY latest_fcf_cr DESC
LIMIT 10;


-- 8. TOP COMPANIES BY ROE
SELECT
    company_id,
    ROUND(latest_roe_pct, 2) AS roe_pct
FROM company_summary
WHERE latest_roe_pct IS NOT NULL
ORDER BY latest_roe_pct DESC
LIMIT 10;


-- 9. LOWEST DEBT-TO-EQUITY COMPANIES
SELECT
    company_id,
    ROUND(latest_debt_to_equity, 3) AS debt_to_equity
FROM company_summary
WHERE latest_debt_to_equity IS NOT NULL
ORDER BY latest_debt_to_equity ASC
LIMIT 10;


-- 10. ANNUAL STOCK PERFORMANCE
SELECT
    year,
    COUNT(DISTINCT company_id) AS companies,
    ROUND(AVG(annual_return_pct), 2) AS average_annual_return_pct,
    SUM(
        CASE
            WHEN annual_return_pct > 0 THEN 1
            ELSE 0
        END
    ) AS positive_company_years,
    SUM(
        CASE
            WHEN annual_return_pct < 0 THEN 1
            ELSE 0
        END
    ) AS negative_company_years
FROM annual_stock_returns
GROUP BY year
ORDER BY year;


-- 11. SECTOR-WISE STOCK PERFORMANCE
WITH company_returns AS (
    SELECT
        a.company_id,
        s.broad_sector,
        (
            EXP(
                SUM(
                    LN(
                        1 + a.annual_return_pct / 100.0
                    )
                )
            ) - 1
        ) * 100 AS cumulative_return_pct
    FROM annual_stock_returns a
    JOIN sectors s
        ON a.company_id = s.company_id
    GROUP BY
        a.company_id,
        s.broad_sector
)
SELECT
    broad_sector,
    COUNT(*) AS companies,
    ROUND(
        AVG(cumulative_return_pct),
        2
    ) AS avg_company_cumulative_return_pct
FROM company_returns
GROUP BY broad_sector
ORDER BY avg_company_cumulative_return_pct DESC;


-- 12. COMPANY FUNDAMENTALS + STOCK PERFORMANCE
SELECT
    c.company_id,
    ROUND(c.revenue_cagr_pct, 2) AS revenue_cagr_pct,
    ROUND(c.net_profit_cagr_pct, 2) AS net_profit_cagr_pct,
    ROUND(c.latest_net_profit_margin_pct, 2)
        AS net_profit_margin_pct,
    ROUND(c.latest_roe_pct, 2) AS roe_pct,
    ROUND(c.latest_debt_to_equity, 2)
        AS debt_to_equity,
    ROUND(c.latest_fcf_cr, 2) AS free_cash_flow,
    ROUND(s.cumulative_return_pct, 2)
        AS cumulative_stock_return_pct
FROM company_summary c
JOIN (
    SELECT
        company_id,
        (
            EXP(
                SUM(
                    LN(
                        1 + annual_return_pct / 100.0
                    )
                )
            ) - 1
        ) * 100 AS cumulative_return_pct
    FROM annual_stock_returns
    GROUP BY company_id
) s
    ON c.company_id = s.company_id
ORDER BY cumulative_return_pct DESC;


-- 13. COMPANIES WITH BOTH STRONG STOCK RETURNS
--     AND STRONG OVERALL SCORE
SELECT
    company_id,
    rank,
    ROUND(overall_score, 2) AS overall_score,
    ROUND(cumulative_return_pct, 2)
        AS cumulative_return_pct
FROM company_scorecard
WHERE overall_score >= 60
  AND cumulative_return_pct >= 50
ORDER BY overall_score DESC;


-- 14. COMPANY DATA COVERAGE
SELECT
    company_id,
    first_available_year,
    latest_available_year,
    years_available
FROM company_summary
ORDER BY years_available DESC, company_id;


-- 15. DATABASE SUMMARY
SELECT 'financial_panel' AS table_name, COUNT(*) AS rows
FROM financial_panel
UNION ALL
SELECT 'derived_metrics', COUNT(*)
FROM derived_metrics
UNION ALL
SELECT 'company_summary', COUNT(*)
FROM company_summary
UNION ALL
SELECT 'company_scorecard', COUNT(*)
FROM company_scorecard
UNION ALL
SELECT 'sectors', COUNT(*)
FROM sectors
UNION ALL
SELECT 'stock_prices', COUNT(*)
FROM stock_prices
UNION ALL
SELECT 'stock_returns', COUNT(*)
FROM stock_returns
UNION ALL
SELECT 'annual_stock_returns', COUNT(*)
FROM annual_stock_returns;
