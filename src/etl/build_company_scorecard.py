from pathlib import Path
import sqlite3
import pandas as pd


DB_FILE = Path("data/processed/nifty100.db")
OUTPUT_FILE = Path("data/processed/analytical/company_scorecard.csv")


def percentile_score(series, higher_is_better=True):
    """
    Convert a metric into a 0-100 percentile score.
    Missing values remain missing.
    """
    rank = series.rank(method="average", pct=True) * 100

    if higher_is_better:
        return rank
    else:
        return 100 - rank + (100 / series.notna().sum())


def main():

    print("=" * 70)
    print("BUILDING COMPANY PERFORMANCE SCORECARD")
    print("=" * 70)

    conn = sqlite3.connect(DB_FILE)

    query = """
    SELECT
        c.company_id,
        c.revenue_cagr_pct,
        c.net_profit_cagr_pct,
        c.latest_net_profit_margin_pct,
        c.latest_roe_pct,
        c.latest_debt_to_equity,
        c.latest_fcf_cr,

        (
            EXP(
                SUM(
                    LN(1 + a.annual_return_pct / 100.0)
                )
            ) - 1
        ) * 100 AS cumulative_return_pct

    FROM company_summary c

    JOIN annual_stock_returns a
        ON c.company_id = a.company_id

    GROUP BY
        c.company_id,
        c.revenue_cagr_pct,
        c.net_profit_cagr_pct,
        c.latest_net_profit_margin_pct,
        c.latest_roe_pct,
        c.latest_debt_to_equity,
        c.latest_fcf_cr
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    print(f"Companies loaded: {len(df)}")

    # ---------------------------------------------------------
    # Calculate percentile scores
    # ---------------------------------------------------------

    df["stock_return_score"] = percentile_score(
        df["cumulative_return_pct"],
        higher_is_better=True
    )

    df["revenue_growth_score"] = percentile_score(
        df["revenue_cagr_pct"],
        higher_is_better=True
    )

    df["profit_growth_score"] = percentile_score(
        df["net_profit_cagr_pct"],
        higher_is_better=True
    )

    df["margin_score"] = percentile_score(
        df["latest_net_profit_margin_pct"],
        higher_is_better=True
    )

    df["roe_score"] = percentile_score(
        df["latest_roe_pct"],
        higher_is_better=True
    )

    df["debt_score"] = percentile_score(
        df["latest_debt_to_equity"],
        higher_is_better=False
    )

    df["fcf_score"] = percentile_score(
        df["latest_fcf_cr"],
        higher_is_better=True
    )

    score_columns = [
        "stock_return_score",
        "revenue_growth_score",
        "profit_growth_score",
        "margin_score",
        "roe_score",
        "debt_score",
        "fcf_score",
    ]

    # ---------------------------------------------------------
    # Overall score
    # Average available component scores.
    # ---------------------------------------------------------

    df["overall_score"] = df[score_columns].mean(
        axis=1,
        skipna=True
    )

    df["rank"] = (
        df["overall_score"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    # ---------------------------------------------------------
    # Sort
    # ---------------------------------------------------------

    df = df.sort_values(
        ["overall_score", "cumulative_return_pct"],
        ascending=[False, False]
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # ---------------------------------------------------------
    # Display
    # ---------------------------------------------------------

    print()
    print("TOP 10 COMPANIES")
    print("-" * 70)

    print(
        df[
            [
                "rank",
                "company_id",
                "overall_score",
                "cumulative_return_pct",
                "revenue_cagr_pct",
                "net_profit_cagr_pct",
                "latest_net_profit_margin_pct",
                "latest_roe_pct",
                "latest_debt_to_equity",
                "latest_fcf_cr",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print(f"Saved: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
