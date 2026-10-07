from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.etl.loader import load_all_sources


DEFAULT_DB = Path("data/processed/nifty100.db")
DEFAULT_CONFIG = Path("config/screener_config.yaml")


def load_config(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load screener configuration from YAML."""
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
    """Load the financial_ratios table from SQLite."""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            """,
            conn,
        )


def load_market_data() -> pd.DataFrame:
    """Load valuation metrics from the raw market_cap source."""
    sources = load_all_sources()
    market = sources["market_cap"].copy()

    required = {
        "company_id",
        "year",
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

    return market[list(required)].copy()


def build_screener_dataset(
    db_path: str | Path = DEFAULT_DB,
) -> pd.DataFrame:
    """
    Combine financial KPI data with valuation metrics.

    Financial metrics come from SQLite financial_ratios.
    Valuation metrics come from the raw market_cap source.
    """
    financial = load_financial_ratios(db_path)
    market = load_market_data()

    keys = ["company_id", "year"]

    # Sprint 2 deliberately retained unresolved source variants.
    # Do not arbitrarily select one variant for screening.
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
            "financial_ratios still contains duplicate company-year "
            "records after excluding VARIANT_REVIEW rows."
        )

    if market.duplicated(keys).any():
        raise ValueError(
            "market_cap contains duplicate company-year records."
        )

    valuation_cols = [
        "company_id",
        "year",
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "dividend_yield_pct",
    ]

    dataset = financial.merge(
        market[valuation_cols],
        on=keys,
        how="left",
        validate="one_to_one",
    )

    return dataset


def latest_company_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep the latest safe financial record for each company.

    The screener operates at company level rather than treating each
    historical company-year observation as a separate investment candidate.
    """
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
    "max_pe": "pe_ratio",
    "max_pb": "pb_ratio",
    "min_pat_cagr_5yr": "pat_cagr_5yr",
    "min_dividend_yield_pct": "dividend_yield_pct",
    "min_npm": "engine_net_profit_margin_pct",
    "min_opm": "engine_operating_profit_margin_pct",
    "min_roce": "engine_roce_pct",
    "min_interest_coverage": "engine_interest_coverage",
    "max_capex_intensity_pct": "capex_intensity_pct",
    "min_revenue_cagr_5yr": "revenue_cagr_5yr",
    "min_eps_cagr_5yr": "eps_cagr_5yr",
    "min_asset_turnover": "engine_asset_turnover",
}


def apply_filters(
    df: pd.DataFrame,
    filters: dict[str, Any],
) -> pd.DataFrame:
    """
    Apply YAML threshold filters to a dataframe.

    Filters are expressed as min_* or max_* keys and translated
    to the corresponding dataframe columns.
    """
    result = df.copy()

    for filter_name, threshold in filters.items():
        if threshold is None:
            continue

        if filter_name not in FILTER_COLUMN_MAP:
            raise ValueError(f"Unknown screener filter: {filter_name}")

        column = FILTER_COLUMN_MAP[filter_name]

        if column not in result.columns:
            raise ValueError(
                f"Required filter column '{column}' is missing."
            )

        if filter_name.startswith("min_"):
            result = result[result[column] > threshold]
        elif filter_name.startswith("max_"):
            result = result[result[column] < threshold]
        else:
            raise ValueError(
                f"Filter must start with min_ or max_: {filter_name}"
            )

    return result.copy()


def run_preset(
    preset_name: str,
    db_path: str | Path = DEFAULT_DB,
    config_path: str | Path = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Run one configured screener preset."""
    config = load_config(config_path)

    presets = config["presets"]

    if preset_name not in presets:
        raise ValueError(
            f"Unknown preset '{preset_name}'. "
            f"Available presets: {list(presets)}"
        )

    dataset = build_screener_dataset(db_path)
    dataset = latest_company_records(dataset)

    preset_filters = presets[preset_name].get("filters", {})

    return apply_filters(dataset, preset_filters)


def run_custom(
    filters: dict[str, Any],
    db_path: str | Path = DEFAULT_DB,
) -> pd.DataFrame:
    """Run a custom screener using threshold filters."""
    dataset = build_screener_dataset(db_path)
    return apply_filters(dataset, filters)


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
        print(f"{preset:>12}: {len(result)} rows")
