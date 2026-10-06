from pathlib import Path
import sqlite3

import pandas as pd
import matplotlib.pyplot as plt


DB_FILE = Path("data/processed/nifty100.db")
OUTPUT_DIR = Path("results/charts")


def save_plot(filename):
    path = OUTPUT_DIR / filename
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def main():

    print("=" * 70)
    print("BUILDING NIFTY100 VISUALIZATIONS")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)

    # ------------------------------------------------------------
    # 1. TOP 10 COMPANY PERFORMANCE SCORE
    # ------------------------------------------------------------

    df = pd.read_sql_query(
        """
        SELECT
            company_id,
            overall_score
        FROM company_scorecard
        ORDER BY overall_score DESC
        LIMIT 10
        """,
        conn
    )

    plt.figure(figsize=(10, 6))
    plt.barh(
        df["company_id"][::-1],
        df["overall_score"][::-1]
    )
    plt.xlabel("Overall Score")
    plt.ylabel("Company")
    plt.title("Top 10 Companies by Overall Performance Score")
    save_plot("01_top10_company_score.png")


    # ------------------------------------------------------------
    # 2. TOP 10 CUMULATIVE STOCK RETURNS
    # ------------------------------------------------------------

    df = pd.read_sql_query(
        """
        SELECT
            company_id,
            cumulative_return_pct
        FROM company_scorecard
        ORDER BY cumulative_return_pct DESC
        LIMIT 10
        """,
        conn
    )

    plt.figure(figsize=(10, 6))
    plt.barh(
        df["company_id"][::-1],
        df["cumulative_return_pct"][::-1]
    )
    plt.xlabel("Cumulative Return (%)")
    plt.ylabel("Company")
    plt.title("Top 10 Companies by Cumulative Stock Return")
    save_plot("02_top10_stock_returns.png")


    # ------------------------------------------------------------
    # 3. FINANCIAL PERFORMANCE TREND
    # ------------------------------------------------------------

    df = pd.read_sql_query(
        """
        SELECT
            year,
            SUM(sales) AS total_sales,
            SUM(net_profit) AS total_net_profit,
            SUM(net_profit) * 100.0 /
                NULLIF(SUM(sales), 0) AS net_profit_margin
        FROM financial_panel
        GROUP BY year
        ORDER BY year
        """,
        conn
    )

    # Exclude years with very low company coverage
    df_plot = df[df["year"].between(2013, 2023)].copy()

    plt.figure(figsize=(11, 6))
    plt.plot(
        df_plot["year"],
        df_plot["total_sales"],
        marker="o",
        label="Total Sales"
    )
    plt.plot(
        df_plot["year"],
        df_plot["total_net_profit"],
        marker="o",
        label="Total Net Profit"
    )
    plt.xlabel("Year")
    plt.ylabel("Amount")
    plt.title("Nifty100 Aggregate Sales and Net Profit Trend")
    plt.legend()
    save_plot("03_financial_performance_trend.png")


    # ------------------------------------------------------------
    # 4. SECTOR FINANCIAL PERFORMANCE
    # ------------------------------------------------------------

    df = pd.read_sql_query(
        """
        SELECT
            s.broad_sector,
            SUM(f.net_profit) AS total_net_profit,
            SUM(f.net_profit) * 100.0 /
                NULLIF(SUM(f.sales), 0) AS net_profit_margin
        FROM financial_panel f
        JOIN sectors s
            ON f.company_id = s.company_id
        WHERE f.year = 2023
        GROUP BY s.broad_sector
        ORDER BY total_net_profit DESC
        """,
        conn
    )

    plt.figure(figsize=(11, 7))
    plt.barh(
        df["broad_sector"][::-1],
        df["total_net_profit"][::-1]
    )
    plt.xlabel("Total Net Profit")
    plt.ylabel("Sector")
    plt.title("Sector-wise Net Profit — 2023")
    save_plot("04_sector_net_profit.png")


    # ------------------------------------------------------------
    # 5. SECTOR STOCK PERFORMANCE
    # ------------------------------------------------------------

    df = pd.read_sql_query(
        """
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
            AVG(cumulative_return_pct)
                AS avg_cumulative_return
        FROM company_returns
        GROUP BY broad_sector
        ORDER BY avg_cumulative_return DESC
        """,
        conn
    )

    plt.figure(figsize=(11, 7))
    plt.barh(
        df["broad_sector"][::-1],
        df["avg_cumulative_return"][::-1]
    )
    plt.xlabel("Average Company Cumulative Return (%)")
    plt.ylabel("Sector")
    plt.title("Sector-wise Stock Performance (2020–2024)")
    save_plot("05_sector_stock_performance.png")


    # ------------------------------------------------------------
    # 6. FUNDAMENTALS VS STOCK PERFORMANCE
    # ------------------------------------------------------------

    df = pd.read_sql_query(
        """
        SELECT
            revenue_cagr_pct,
            latest_net_profit_margin_pct,
            cumulative_return_pct
        FROM company_scorecard
        WHERE revenue_cagr_pct IS NOT NULL
          AND latest_net_profit_margin_pct IS NOT NULL
          AND cumulative_return_pct IS NOT NULL
        """,
        conn
    )

    plt.figure(figsize=(9, 6))
    plt.scatter(
        df["revenue_cagr_pct"],
        df["cumulative_return_pct"],
        alpha=0.7
    )

    plt.xlabel("Revenue CAGR (%)")
    plt.ylabel("Cumulative Stock Return (%)")
    plt.title("Revenue Growth vs Cumulative Stock Return")
    save_plot("06_revenue_growth_vs_stock_return.png")


    conn.close()

    print()
    print("ALL VISUALIZATIONS CREATED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()
