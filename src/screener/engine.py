from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
import yaml

from src.etl.loader import load_all_sources


DEFAULT_DB = Path("data/processed/nifty100.db")
DEFAULT_CONFIG = Path("config/screener_config.yaml")
PROCESSED = Path("data/processed")


def load_config(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load and validate the analyst-editable screener configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Screener configuration must be a YAML mapping.")

    if "filters" not in config:
        raise ValueError("Configuration is missing 'filters'.")

    if "presets" not in config:
        raise ValueError("Configuration is missing 'presets'.")

    if len(config["filters"]) != 15:
        raise ValueError(
            f"Expected 15 filter thresholds, found {len(config['filters'])}."
        )

    return config


def load_financial_ratios(db_path: str | Path = DEFAULT_DB) -> pd.DataFrame:
    """Load financial ratio engine output from SQLite."""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM financial_ratios",
            conn,
        )


def load_market_data() -> pd.DataFrame:
    """Load market valuation and market-cap data."""
    sources = load_all_sources()
    market = sources["market_cap"].copy()

    required = {
        "company_id",
        "year",
        "market_cap_crore",
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "dividend_yield_pct",
    }

    missing = required - set(market.columns)
    if missing:
        raise ValueError(
            f"market_cap is missing required columns: {sorted(missing)}"
        )

    return market[
        [
            "company_id",
            "year",
            "market_cap_crore",
            "pe_ratio",
            "pb_ratio",
            "ev_ebitda",
            "dividend_yield_pct",
        ]
    ].copy()


def load_profit_loss() -> pd.DataFrame:
    """Load sales and net-profit data from the P&L source."""
    sources = load_all_sources()
    pnl = sources["profitandloss"].copy()

    required = {
        "company_id",
        "year",
        "sales",
        "net_profit",
        "eps",
        "dividend_payout",
    }

    missing = required - set(pnl.columns)
    if missing:
        raise ValueError(
            f"profitandloss is missing required columns: {sorted(missing)}"
        )

    return pnl[
        [
            "company_id",
            "year",
            "sales",
            "net_profit",
            "eps",
            "dividend_payout",
        ]
    ].copy()


def load_company_reference() -> pd.DataFrame:
    """Load company reference fields including company name and ROCE."""
    sources = load_all_sources()
    companies = sources["companies"].copy()

    return companies[
        [
            "id",
            "company_name",
            "roce_percentage",
            "roe_percentage",
        ]
    ].rename(columns={"id": "company_id"})

def load_fcf_cagr_5yr() -> pd.DataFrame:
    """
    Calculate 5-year FCF CAGR from the cleaned cash-flow dataset.

    FCF = Operating Activity + Investing Activity

    CAGR is calculated only when:
    - a 5-year endpoint exists;
    - both starting and ending FCF are positive.

    If either endpoint is zero/negative, CAGR is unavailable.
    """
    cf_path = PROCESSED / "cashflow_cleaned.csv"

    cf = pd.read_csv(cf_path)

    required = {
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
    }

    missing = required - set(cf.columns)
    if missing:
        raise ValueError(
            f"cashflow_cleaned.csv missing columns: {sorted(missing)}"
        )

    cf["company_id"] = (
        cf["company_id"]
        .astype(str)
        .str.strip()
    )

    cf["year"] = pd.to_numeric(
        cf["year"],
        errors="coerce",
    )

    cf["operating_activity"] = pd.to_numeric(
        cf["operating_activity"],
        errors="coerce",
    )

    cf["investing_activity"] = pd.to_numeric(
        cf["investing_activity"],
        errors="coerce",
    )

    cf["fcf_cr"] = (
        cf["operating_activity"]
        + cf["investing_activity"]
    )

    # Only unambiguous company-year records.
    cf = (
        cf.dropna(
            subset=[
                "company_id",
                "year",
                "fcf_cr",
            ]
        )
        .drop_duplicates(
            subset=["company_id", "year"]
        )
        .copy()
    )

    records = []

    for company_id, group in cf.groupby("company_id"):
        group = group.sort_values("year").copy()

        if group.empty:
            continue

        latest_year = int(group["year"].max())
        start_year = latest_year - 5

        start_rows = group.loc[
            group["year"].eq(start_year)
        ]

        end_rows = group.loc[
            group["year"].eq(latest_year)
        ]

        if start_rows.empty or end_rows.empty:
            fcf_cagr = np.nan
        else:
            start_fcf = float(
                start_rows.iloc[0]["fcf_cr"]
            )
            end_fcf = float(
                end_rows.iloc[0]["fcf_cr"]
            )

            if start_fcf > 0 and end_fcf > 0:
                fcf_cagr = (
                    (end_fcf / start_fcf) ** (1 / 5) - 1
                ) * 100
            else:
                fcf_cagr = np.nan

        records.append(
            {
                "company_id": company_id,
                "fcf_cagr_5yr": fcf_cagr,
            }
        )

    return pd.DataFrame(records)


def build_screener_dataset(
    db_path: str | Path = DEFAULT_DB,
) -> pd.DataFrame:
    """
    Build the company-year screener dataset.

    Sources:
    - financial_ratios from SQLite
    - market_cap from raw market data
    - profitandloss for sales/net profit
    - companies for company name/reference fields
    - sectors for broad sector classification
    """
    financial = load_financial_ratios(db_path)
    market = load_market_data()
    pnl = load_profit_loss()
    companies = load_company_reference()
    fcf_cagr = load_fcf_cagr_5yr()

    keys = ["company_id", "year"]

    # Unresolved financial source variants are deliberately excluded.
    if "record_status" in financial.columns:
        variant_mask = financial["record_status"].eq("VARIANT_REVIEW")
        variant_rows = int(variant_mask.sum())

        if variant_rows:
            print(
                f"Excluding {variant_rows} VARIANT_REVIEW rows "
                "from screener input."
            )

            financial = financial.loc[~variant_mask].copy()

    if financial.duplicated(keys).any():
        raise ValueError(
            "financial_ratios contains duplicate company-year records."
        )

    if market.duplicated(keys).any():
        raise ValueError(
            "market_cap contains duplicate company-year records."
        )

    # P&L contains source variants in some company-years. Only merge
    # unambiguous company-year records.
    
    pnl_counts = (
    pnl.groupby(keys)
    .size()
    .rename("_pnl_count")
    .reset_index()
    )

    # Keep only company-years with exactly one P&L source row.
    # This prevents unresolved source variants from entering the screener.
    safe_pnl_keys = pnl_counts.loc[
        pnl_counts["_pnl_count"].eq(1),
        keys,
    ]

    pnl = pnl.merge(
        safe_pnl_keys,
        on=keys,
        how="inner",
        validate="many_to_one",
    )

    if pnl.duplicated(keys).any():
        raise ValueError("P&L still contains duplicate company-year rows.")

    dataset = financial.merge(
        market,
        on=keys,
        how="left",
        validate="one_to_one",
    )

    dataset = dataset.merge(
        pnl,
        on=keys,
        how="left",
        validate="one_to_one",
        suffixes=("", "_pnl"),
    )

    dataset = dataset.merge(
    fcf_cagr,
    on="company_id",
    how="left",
    validate="many_to_one",
)

    dataset = dataset.merge(
        companies,
        on="company_id",
        how="left",
        validate="many_to_one",
    )

    # Sectors are already available in the SQLite database.
    # Use a direct company_id -> broad_sector mapping instead of a merge.
    # This avoids column-name collisions while preserving the 92-company
    # sector classification exactly as stored in SQLite.
    with sqlite3.connect(db_path) as conn:
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors",
            conn,
        )

    if sectors.empty:
        raise ValueError("SQLite sectors table is empty.")

    required_sector_columns = {"company_id", "broad_sector"}
    missing_sector_columns = required_sector_columns - set(sectors.columns)

    if missing_sector_columns:
        raise ValueError(
            f"SQLite sectors table is missing columns: "
            f"{sorted(missing_sector_columns)}"
        )

    sector_map = (
        sectors
        .drop_duplicates("company_id")
        .set_index("company_id")["broad_sector"]
    )

    dataset["broad_sector"] = dataset["company_id"].map(sector_map)

    # Some financial companies are represented by reference/source rows
    # without a broad-sector value. Preserve the known Sprint 2 fallback.
    sector_fallback = {
        "UNIONBANK": "Financials",
        "ULTRACEMCO": "Materials",
    }

    dataset["broad_sector"] = dataset["broad_sector"].fillna(
        dataset["company_id"].map(sector_fallback)
    )

    # Numeric conversion for screening fields.
    numeric_columns = [
        "year",
        "market_cap_crore",
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "dividend_yield_pct",
        "sales",
        "net_profit",
        "eps",
        "dividend_payout",
        "engine_return_on_equity_pct",
        "engine_debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_3yr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
        "engine_operating_profit_margin_pct",
        "engine_interest_coverage",
        "engine_asset_turnover",
        "engine_roce_pct",
        "fcf_cagr_5yr",
    ]

    for column in numeric_columns:
        if column in dataset.columns:
            dataset[column] = pd.to_numeric(
                dataset[column],
                errors="coerce",
            )

    # ICR: Debt Free companies are treated as infinite coverage.
    if "icr_label" in dataset.columns:
        debt_free = dataset["icr_label"].astype(str).str.contains(
            "Debt Free",
            case=False,
            na=False,
        )
        if "engine_interest_coverage" in dataset.columns:
            dataset.loc[
                debt_free,
                "engine_interest_coverage",
            ] = float("inf")

    # Historical D/E decline flag.
    dataset = add_debt_declining_flag(dataset)

    return dataset


def add_debt_declining_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Mark company-years where D/E declined versus the previous year."""
    result = df.copy()

    result = result.sort_values(
        ["company_id", "year"]
    )

    result["_previous_de"] = (
        result.groupby("company_id")["engine_debt_to_equity"]
        .shift(1)
    )

    result["debt_to_equity_declining"] = (
        result["engine_debt_to_equity"].notna()
        & result["_previous_de"].notna()
        & (
            result["engine_debt_to_equity"]
            < result["_previous_de"]
        )
    )

    result = result.drop(columns="_previous_de")

    return result


def latest_company_records(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest safe record for each company."""
    if df.empty:
        return df.copy()

    latest = (
        df.sort_values(["company_id", "year"])
        .groupby("company_id", as_index=False)
        .tail(1)
        .sort_values("company_id")
        .reset_index(drop=True)
    )

    return latest


FILTER_COLUMN_MAP = {
    "min_roe": "engine_return_on_equity_pct",
    "max_de": "engine_debt_to_equity",
    "min_fcf": "free_cash_flow_cr",
    "min_revenue_cagr_5yr": "revenue_cagr_5yr",
    "min_pat_cagr_5yr": "pat_cagr_5yr",
    "min_opm": "engine_operating_profit_margin_pct",
    "max_pe": "pe_ratio",
    "max_pb": "pb_ratio",
    "min_dividend_yield_pct": "dividend_yield_pct",
    "min_interest_coverage": "engine_interest_coverage",
    "min_market_cap_crore": "market_cap_crore",
    "min_net_profit_cr": "net_profit",
    "min_eps_cagr_5yr": "eps_cagr_5yr",
    "min_asset_turnover": "engine_asset_turnover",
    "min_sales_cr": "sales",
    "max_dividend_payout_pct": "dividend_payout",
    "min_revenue_cagr_3yr": "revenue_cagr_3yr",
}


def apply_filters(
    df: pd.DataFrame,
    filters: dict[str, Any],
) -> pd.DataFrame:
    """
    Apply configured thresholds.

    Special handling:
    - D/E filters are not applied to Financials.
    - Debt Free ICR is represented as infinity.
    - Turnaround requires D/E decline versus previous year.
    """
    result = df.copy()

    for filter_name, threshold in filters.items():

        if threshold is None:
            continue

        if filter_name == "debt_to_equity_declining":
            if bool(threshold):
                if "debt_to_equity_declining" not in result.columns:
                    raise ValueError(
                        "Debt-decline information is unavailable."
                    )

                result = result[
                    result["debt_to_equity_declining"].fillna(False)
                ]

            continue

        if filter_name not in FILTER_COLUMN_MAP:
            raise ValueError(
                f"Unknown screener filter: {filter_name}"
            )

        column = FILTER_COLUMN_MAP[filter_name]

        if column not in result.columns:
            raise ValueError(
                f"Required filter column '{column}' is missing."
            )

        # Financial-sector D/E is not a useful cross-sector leverage
        # comparison. Automatically exclude D/E from the predicate there.
        if filter_name == "max_de" and "broad_sector" in result.columns:
            financial_mask = (
                result["broad_sector"]
                .astype(str)
                .str.strip()
                .str.casefold()
                .eq("financials")
            )

            non_financial = result.loc[~financial_mask].copy()
            financial = result.loc[financial_mask].copy()

            if float(threshold) == 0:
                # Debt-Free Blue Chip requires D/E exactly equal to zero.
                non_financial = non_financial[
                    non_financial[column].eq(0)
                ]
            else:
                non_financial = non_financial[
                    non_financial[column] < threshold
                ]

            result = pd.concat(
                [financial, non_financial],
                ignore_index=True,
            )

            continue

        if filter_name.startswith("min_"):
            result = result[
                result[column] > threshold
            ]

        elif filter_name.startswith("max_"):
            result = result[
                result[column] < threshold
            ]

        else:
            raise ValueError(
                f"Unsupported filter type: {filter_name}"
            )

    return result.copy()


def run_preset(
    preset_name: str,
    db_path: str | Path = DEFAULT_DB,
    config_path: str | Path = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Run one configured preset on the latest company records."""
    config = load_config(config_path)

    if preset_name not in config["presets"]:
        raise ValueError(
            f"Unknown preset '{preset_name}'. "
            f"Available presets: {list(config['presets'])}"
        )

    dataset = build_screener_dataset(db_path)

    # Turnaround uses historical observations. Other presets operate
    # on the latest company record.
    preset_filters = config["presets"][preset_name].get(
        "filters",
        {},
    )

    if "debt_to_equity_declining" in preset_filters:
        dataset = latest_company_records(dataset)

    else:
        dataset = latest_company_records(dataset)

    result = apply_filters(
        dataset,
        preset_filters,
    )

    # Preserve a composite score column for downstream ranking.
    if "composite_quality_score" not in result.columns:
        result["composite_quality_score"] = pd.NA

    return result.sort_values(
        "company_id"
    ).reset_index(drop=True)


def run_custom(
    filters: dict[str, Any],
    db_path: str | Path = DEFAULT_DB,
) -> pd.DataFrame:
    """Run a custom screener using threshold filters."""
    dataset = build_screener_dataset(db_path)

    dataset = latest_company_records(dataset)

    result = apply_filters(
        dataset,
        filters,
    )

    if "composite_quality_score" not in result.columns:
        result["composite_quality_score"] = pd.NA

    return result.sort_values(
        "company_id"
    ).reset_index(drop=True)


if __name__ == "__main__":
    config = load_config()

    print("SCREENER ENGINE")
    print("=" * 60)
    print("Filter thresholds:", len(config["filters"]))
    print("Confirmed presets:", ", ".join(config["presets"]))

    data = build_screener_dataset()

    print("Combined dataset:", data.shape)
    print("Companies:", data["company_id"].nunique())
    print("Years:", data["year"].min(), "-", data["year"].max())

    for preset in config["presets"]:
        result = run_preset(preset)
        print(f"{preset:>24}: {len(result)} rows")
