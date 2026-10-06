import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

PROCESSED = ROOT / "data" / "processed"
ANALYTICAL = PROCESSED / "analytical"
OUTPUT = ROOT / "output"
DB_PATH = PROCESSED / "nifty100.db"

ANALYTICAL.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def safe_num(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def cagr(start_value, end_value, years):
    """
    Financial CAGR with explicit edge-case handling.
    """
    start_value = safe_num(start_value)
    end_value = safe_num(end_value)

    if start_value is None or end_value is None:
        return None, "INSUFFICIENT"

    if years is None or years <= 0:
        return None, "INSUFFICIENT"

    if start_value == 0:
        return None, "ZERO_BASE"

    if start_value > 0 and end_value > 0:
        value = ((end_value / start_value) ** (1 / years) - 1) * 100
        return value, "NORMAL"

    if start_value > 0 and end_value <= 0:
        return None, "DECLINE_TO_LOSS"

    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"

    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    return None, "INSUFFICIENT"


def percentile_score(series, inverse=False):
    """
    Convert a KPI into a 0-100 percentile score.
    """
    result = pd.Series(np.nan, index=series.index, dtype=float)

    valid = series.notna()

    if valid.sum() == 0:
        return result

    ranked = series[valid].rank(pct=True) * 100

    if inverse:
        ranked = 100 - ranked

    result.loc[valid] = ranked

    return result


def sign(value):
    if value is None or pd.isna(value):
        return "0"

    if value > 0:
        return "+"

    if value < 0:
        return "-"

    return "0"


def capital_allocation(cfo, cfi, cff, cfo_pat_ratio=None):
    """
    Classify annual capital allocation using CFO/CFI/CFF signs.
    """

    pattern = (
        sign(cfo),
        sign(cfi),
        sign(cff),
    )

    if pattern == ("+", "-", "-"):
        if cfo_pat_ratio is not None and cfo_pat_ratio > 1:
            return "Shareholder Returns"
        return "Reinvestor"

    if pattern == ("+", "+", "-"):
        return "Liquidating Assets"

    if pattern == ("-", "+", "+"):
        return "Distress Signal"

    if pattern == ("-", "-", "+"):
        return "Growth Funded by Debt"

    if pattern == ("+", "+", "+"):
        return "Cash Accumulator"

    if pattern == ("-", "-", "-"):
        return "Pre-Revenue"

    if pattern == ("+", "-", "+"):
        return "Mixed"

    return "Unclassified"


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("NIFTY100 RATIO ENGINE")
print("=" * 70)

ratio_path = PROCESSED / "financial_ratios_cleaned.csv"
panel_path = ANALYTICAL / "financial_panel.csv"
pl_path = PROCESSED / "profitandloss_cleaned.csv"
bs_path = PROCESSED / "balancesheet_cleaned.csv"
cf_path = PROCESSED / "cashflow_cleaned.csv"
cf_path = PROCESSED / "cashflow_cleaned.csv"
sector_path = ANALYTICAL / "sectors.csv"

ratios = pd.read_csv(ratio_path)
panel = pd.read_csv(panel_path)
pl = pd.read_csv(pl_path)
bs = pd.read_csv(bs_path)
cf = pd.read_csv(cf_path)
sectors = pd.read_csv(sector_path)

for df in [ratios, panel, pl, bs, cf, sectors]:
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].astype(str).str.strip()

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")


print(f"Source ratio rows: {len(ratios):,}")
print(
    "Unique ratio company-year keys:",
    ratios[["company_id", "year"]].drop_duplicates().shape[0],
)

# ============================================================
# IDENTIFY VARIANT RECORDS
# ============================================================

ratio_key_counts = (
    ratios.groupby(["company_id", "year"])
    .size()
    .reset_index(name="record_count")
)

ratio_key_counts["record_status"] = np.where(
    ratio_key_counts["record_count"] > 1,
    "VARIANT_REVIEW",
    "NORMAL",
)

ratios = ratios.merge(
    ratio_key_counts[
        ["company_id", "year", "record_count", "record_status"]
    ],
    on=["company_id", "year"],
    how="left",
)

print(
    "Variant company-year groups:",
    (ratio_key_counts["record_count"] > 1).sum(),
)

print(
    "Rows requiring variant review:",
    (ratios["record_status"] == "VARIANT_REVIEW").sum(),
)


# ============================================================
# SECTOR LOOKUP
# ============================================================

sector_cols = [c for c in sectors.columns]

sector_col = None

for candidate in ["broad_sector", "sector", "sector_name"]:
    if candidate in sector_cols:
        sector_col = candidate
        break

if sector_col is not None:
    sector_lookup = (
        sectors[["company_id", sector_col]]
        .drop_duplicates("company_id")
        .rename(columns={sector_col: "broad_sector"})
    )
else:
    sector_lookup = pd.DataFrame(
        columns=["company_id", "broad_sector"]
    )

ratios = ratios.merge(
    sector_lookup,
    on="company_id",
    how="left",
)

# Controlled sector fallback for financial-data-only companies
sector_fallback = {
    "UNIONBANK": "Financials",
    "ULTRACEMCO": "Materials",
}

ratios["broad_sector"] = ratios["broad_sector"].fillna(
    ratios["company_id"].map(sector_fallback)
)


# ============================================================
# JOIN SAFE FINANCIAL PANEL
# ============================================================

panel_lookup = panel.copy()

panel_lookup = panel_lookup.drop_duplicates(
    ["company_id", "year"]
)

# Rename only fields that may overlap with ratio-source columns.
panel_lookup = panel_lookup.rename(
    columns={
        "operating_profit": "_panel_operating_profit",
        "other_income": "_panel_other_income",
        "interest": "_panel_interest",
        "equity_capital": "_panel_equity_capital",
        "reserves": "_panel_reserves",
        "borrowings": "_panel_borrowings",
        "investments": "_panel_investments",
        "total_assets": "_panel_total_assets",
        "cash_from_operating_activity": "_panel_cfo",
        "cash_from_investing_activity": "_panel_cfi",
        "cash_from_financing_activity": "_panel_cff",
        "sales": "_panel_sales",
        "net_profit": "_panel_net_profit",
    }
)

panel_fields = [
    "company_id",
    "year",
    "_panel_operating_profit",
    "_panel_other_income",
    "_panel_interest",
    "_panel_equity_capital",
    "_panel_reserves",
    "_panel_borrowings",
    "_panel_investments",
    "_panel_total_assets",
    "_panel_cfo",
    "_panel_cfi",
    "_panel_cff",
    "_panel_sales",
    "_panel_net_profit",
]

panel_fields = [
    c for c in panel_fields
    if c in panel_lookup.columns
]

ratios = ratios.merge(
    panel_lookup[panel_fields],
    on=["company_id", "year"],
    how="left",
)


# ============================================================
# CALCULATE ENGINE KPIs
# ============================================================

print("\nCalculating ratio KPIs...")


def calculate_engine_row(row):
    sales = safe_num(row.get("_panel_sales"))
    net_profit = safe_num(row.get("_panel_net_profit"))
    operating_profit = safe_num(row.get("_panel_operating_profit"))
    other_income = safe_num(row.get("_panel_other_income"))
    interest = safe_num(row.get("_panel_interest"))
    equity_capital = safe_num(row.get("_panel_equity_capital"))
    reserves = safe_num(row.get("_panel_reserves"))
    borrowings = safe_num(row.get("_panel_borrowings"))
    investments = safe_num(row.get("_panel_investments"))
    total_assets = safe_num(row.get("_panel_total_assets"))

    equity = (equity_capital or 0) + (reserves or 0)

    # --------------------------------------------------------
    # NPM
    # --------------------------------------------------------

    if sales not in (None, 0) and net_profit is not None:
        npm = net_profit / sales * 100
    else:
        npm = safe_num(row.get("net_profit_margin_pct"))

    # --------------------------------------------------------
    # OPM
    # --------------------------------------------------------

    if sales not in (None, 0) and operating_profit is not None:
        opm = operating_profit / sales * 100
    else:
        opm = safe_num(row.get("operating_profit_margin_pct"))

    # --------------------------------------------------------
    # ROE
    # --------------------------------------------------------

    if equity > 0 and net_profit is not None:
        roe_value = net_profit / equity * 100
    else:
        roe_value = safe_num(row.get("return_on_equity_pct"))

    # --------------------------------------------------------
    # ROCE
    # --------------------------------------------------------

    capital_employed = (
        equity
        + (borrowings or 0)
    )

    if capital_employed > 0 and operating_profit is not None:
        roce_value = operating_profit / capital_employed * 100
    else:
        roce_value = None

    # --------------------------------------------------------
    # ROA
    # --------------------------------------------------------

    if total_assets not in (None, 0) and net_profit is not None:
        roa_value = net_profit / total_assets * 100
    else:
        roa_value = None

    # --------------------------------------------------------
    # D/E
    # --------------------------------------------------------

    if borrowings in (None, 0):
        de_value = 0.0
    elif equity > 0:
        de_value = borrowings / equity
    else:
        de_value = None

    # --------------------------------------------------------
    # HIGH LEVERAGE
    # --------------------------------------------------------

    sector = row.get("broad_sector")

    high_leverage = (
        de_value is not None
        and de_value > 5
        and sector != "Financials"
    )

    # --------------------------------------------------------
    # INTEREST COVERAGE
    # --------------------------------------------------------

    if interest in (None, 0):
        icr_value = None
        icr_label_value = "Debt Free"
        icr_warning_value = False
    else:
        icr_value = (
            (operating_profit or 0)
            + (other_income or 0)
        ) / interest

        icr_label_value = None
        icr_warning_value = icr_value < 1.5

    # --------------------------------------------------------
    # NET DEBT
    # --------------------------------------------------------

    if borrowings is None and investments is None:
        net_debt_value = None
    else:
        net_debt_value = (
            (borrowings or 0)
            - (investments or 0)
        )

    # --------------------------------------------------------
    # ASSET TURNOVER
    # --------------------------------------------------------

    if total_assets not in (None, 0) and sales is not None:
        asset_turnover_value = sales / total_assets
    else:
        asset_turnover_value = safe_num(
            row.get("asset_turnover")
        )

    return pd.Series(
        {
            "engine_net_profit_margin_pct": npm,
            "engine_operating_profit_margin_pct": opm,
            "engine_return_on_equity_pct": roe_value,
            "engine_roce_pct": roce_value,
            "engine_roa_pct": roa_value,
            "engine_debt_to_equity": de_value,
            "high_leverage_flag": high_leverage,
            "engine_interest_coverage": icr_value,
            "icr_label": icr_label_value,
            "icr_warning": icr_warning_value,
            "engine_net_debt_cr": net_debt_value,
            "engine_asset_turnover": asset_turnover_value,
        }
    )


engine_values = ratios.apply(
    calculate_engine_row,
    axis=1,
)

ratios = pd.concat(
    [ratios, engine_values],
    axis=1,
)


# ============================================================
# CASH FLOW KPIs
# ============================================================

print("Calculating cash-flow KPIs...")


def get_cf_value(row, field):
    value = row.get(field)
    return safe_num(value)


ratios["cash_from_operations_cr"] = ratios[
    "cash_from_operations_cr"
].combine_first(
    ratios["_panel_cfo"]
    if "_panel_cfo" in ratios.columns
    else pd.Series(index=ratios.index, dtype=float)
)


# Use existing source FCF first, then calculate where possible.
ratios["free_cash_flow_cr"] = ratios[
    "free_cash_flow_cr"
].combine_first(
    ratios.apply(
        lambda r: (
            safe_num(r.get("_panel_cfo") or 0)
            + safe_num(r.get("_panel_cfi") or 0)
            if (
                safe_num(r.get("_panel_cfo")) is not None
                or safe_num(r.get("_panel_cfi")) is not None
            )
            else np.nan
        ),
        axis=1,
    )
)


ratios["capex_cr"] = ratios[
    "capex_cr"
].combine_first(
    ratios.apply(
        lambda r: (
            abs(safe_num(r.get("_panel_cfi")))
            if safe_num(r.get("_panel_cfi")) is not None
            else np.nan
        ),
        axis=1,
    )
)


ratios["capex_intensity_pct"] = ratios.apply(
    lambda r: (
        abs(
            safe_num(r.get("_panel_cfi"))
            or 0
        )
        / safe_num(r.get("_panel_sales"))
        * 100
        if (
            safe_num(r.get("_panel_sales"))
            not in (None, 0)
            and safe_num(r.get("_panel_cfi")) is not None
        )
        else np.nan
    ),
    axis=1,
)


ratios["fcf_conversion_pct"] = ratios.apply(
    lambda r: (
        safe_num(r.get("free_cash_flow_cr"))
        / safe_num(r.get("_panel_operating_profit"))
        * 100
        if (
            safe_num(r.get("free_cash_flow_cr")) is not None
            and safe_num(r.get("_panel_operating_profit"))
            not in (None, 0)
        )
        else np.nan
    ),
    axis=1,
)


ratios["cfo_pat_ratio"] = ratios.apply(
    lambda r: (
        safe_num(r.get("_panel_cfo"))
        / safe_num(r.get("_panel_net_profit"))
        if (
            safe_num(r.get("_panel_cfo")) is not None
            and safe_num(r.get("_panel_net_profit"))
            not in (None, 0)
        )
        else np.nan
    ),
    axis=1,
)


def cfo_quality(value):
    if pd.isna(value):
        return None
    if value > 1:
        return "High Quality"
    if value >= 0.5:
        return "Moderate"
    return "Accrual Risk"


ratios["cfo_quality_label"] = ratios[
    "cfo_pat_ratio"
].apply(cfo_quality)


# ============================================================
# CAPITAL ALLOCATION
# ============================================================

ratios["capital_allocation"] = ratios.apply(
    lambda r: capital_allocation(
        safe_num(r.get("_panel_cfo")),
        safe_num(r.get("_panel_cfi")),
        safe_num(r.get("_panel_cff")),
        safe_num(r.get("cfo_pat_ratio")),
    ),
    axis=1,
)


capital_allocation_output = ratios[
    [
        "company_id",
        "year",
        "broad_sector",
        "capital_allocation",
        "cfo_pat_ratio",
        "free_cash_flow_cr",
        "capex_cr",
    ]
].copy()

capital_allocation_output.to_csv(
    OUTPUT / "capital_allocation.csv",
    index=False,
)

print(
    "Created:",
    OUTPUT / "capital_allocation.csv",
)


# ============================================================
# CAGR ENGINE
# ============================================================

print("Calculating 3Y / 5Y / 10Y CAGR...")


# Build company-year lookup tables.
pl_lookup = (
    pl.drop_duplicates(["company_id", "year"])
    .set_index(["company_id", "year"])
)

ratio_lookup = (
    ratios.drop_duplicates(["company_id", "year"])
    .set_index(["company_id", "year"])
)


def lookup_value(lookup, company_id, year, candidates):
    key = (company_id, year)

    if key not in lookup.index:
        return None

    row = lookup.loc[key]

    # If duplicate rows somehow remain, take first.
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]

    for column in candidates:
        if column in row.index:
            value = safe_num(row[column])
            if value is not None:
                return value

    return None


def calculate_cagr_for_row(row, value_type, years):
    company_id = row["company_id"]
    current_year = safe_num(row["year"])

    if current_year is None:
        return None, "INSUFFICIENT"

    current_year = int(current_year)
    start_year = current_year - years

    if value_type == "revenue":
        current_value = lookup_value(
            pl_lookup,
            company_id,
            current_year,
            ["sales", "revenue"],
        )

        start_value = lookup_value(
            pl_lookup,
            company_id,
            start_year,
            ["sales", "revenue"],
        )

    elif value_type == "pat":
        current_value = lookup_value(
            pl_lookup,
            company_id,
            current_year,
            ["net_profit"],
        )

        start_value = lookup_value(
            pl_lookup,
            company_id,
            start_year,
            ["net_profit"],
        )

    elif value_type == "eps":
        current_value = lookup_value(
            ratio_lookup,
            company_id,
            current_year,
            ["earnings_per_share"],
        )

        start_value = lookup_value(
            ratio_lookup,
            company_id,
            start_year,
            ["earnings_per_share"],
        )

    else:
        return None, "INSUFFICIENT"

    return cagr(start_value, current_value, years)


for metric_name, value_type in [
    ("revenue", "revenue"),
    ("pat", "pat"),
    ("eps", "eps"),
]:
    for years in [3, 5, 10]:

        values = []
        flags = []

        for _, row in ratios.iterrows():
            value, flag = calculate_cagr_for_row(
                row,
                value_type,
                years,
            )

            values.append(value)
            flags.append(flag)

        ratios[
            f"{metric_name}_cagr_{years}yr"
        ] = values

        ratios[
            f"{metric_name}_cagr_{years}yr_flag"
        ] = flags


# Sprint-required aliases.
ratios["revenue_cagr_5yr"] = ratios[
    "revenue_cagr_5yr"
]

ratios["pat_cagr_5yr"] = ratios[
    "pat_cagr_5yr"
]

ratios["eps_cagr_5yr"] = ratios[
    "eps_cagr_5yr"
]


# ============================================================
# COMPOSITE QUALITY SCORE
# ============================================================

print("Calculating composite quality score...")


score_components = pd.DataFrame(index=ratios.index)

score_components["npm"] = percentile_score(
    ratios["engine_net_profit_margin_pct"]
)

score_components["roe"] = percentile_score(
    ratios["engine_return_on_equity_pct"]
)

score_components["roce"] = percentile_score(
    ratios["engine_roce_pct"]
)

score_components["asset_turnover"] = percentile_score(
    ratios["engine_asset_turnover"]
)

score_components["fcf"] = percentile_score(
    ratios["free_cash_flow_cr"]
)

score_components["revenue_cagr"] = percentile_score(
    ratios["revenue_cagr_5yr"]
)

score_components["pat_cagr"] = percentile_score(
    ratios["pat_cagr_5yr"]
)

# Lower D/E is better.
score_components["debt_to_equity"] = percentile_score(
    ratios["engine_debt_to_equity"],
    inverse=True,
)

ratios["composite_quality_score"] = (
    score_components.mean(
        axis=1,
        skipna=True,
    )
)


# ============================================================
# EDGE CASE LOG
# ============================================================

# ============================================================
# DAY 13: COMPANIES REFERENCE ROE / ROCE CROSS-CHECK
# ============================================================

print("Loading companies.xlsx reference ROE/ROCE...")


companies_path = (
    ROOT
    / "data"
    / "raw"
    / "1788501606103-7177b6c2-companies.xlsx"
)

companies_ref = pd.read_excel(
    companies_path,
    header=1,
)

companies_ref["company_id"] = (
    companies_ref["id"]
    .astype(str)
    .str.strip()
    .str.upper()
)

companies_ref["reference_roce_pct"] = pd.to_numeric(
    companies_ref["roce_percentage"],
    errors="coerce",
)

companies_ref["reference_roe_pct"] = pd.to_numeric(
    companies_ref["roe_percentage"],
    errors="coerce",
)

companies_ref = companies_ref[
    [
        "company_id",
        "reference_roce_pct",
        "reference_roe_pct",
    ]
].drop_duplicates("company_id")


# Find latest available engine year for each company.
latest_engine = (
    ratios.dropna(subset=["year"])
    .sort_values(["company_id", "year"])
    .groupby("company_id", as_index=False)
    .tail(1)
    .copy()
)

latest_engine = latest_engine[
    [
        "company_id",
        "year",
        "engine_return_on_equity_pct",
        "engine_roce_pct",
    ]
]

reference_check = latest_engine.merge(
    companies_ref,
    on="company_id",
    how="left",
)

reference_check["roe_difference_pp"] = (
    reference_check["engine_return_on_equity_pct"]
    - reference_check["reference_roe_pct"]
).abs()

reference_check["roce_difference_pp"] = (
    reference_check["engine_roce_pct"]
    - reference_check["reference_roce_pct"]
).abs()


def classify_reference_difference(row, metric):
    if metric == "roe":
        engine_col = "engine_return_on_equity_pct"
        reference_col = "reference_roe_pct"
        difference_col = "roe_difference_pp"
    elif metric == "roce":
        engine_col = "engine_roce_pct"
        reference_col = "reference_roce_pct"
        difference_col = "roce_difference_pp"
    else:
        return "INSUFFICIENT_DATA"

    engine_value = row.get(engine_col)
    reference_value = row.get(reference_col)
    difference = row.get(difference_col)

    if pd.isna(engine_value) or pd.isna(reference_value):
        return "INSUFFICIENT_DATA"

    if pd.isna(difference):
        return "INSUFFICIENT_DATA"

    if difference <= 5:
        return "NO_ANOMALY"

    if metric == "roe" and abs(engine_value) > 200:
         return "SOURCE_DATA_DISCREPANCY"

    return "PERIOD_OR_SOURCE_DISCREPANCY"

reference_check["roe_classification"] = reference_check.apply(
    lambda row: classify_reference_difference(row, "roe"),
    axis=1,
)

reference_check["roce_classification"] = reference_check.apply(
    lambda row: classify_reference_difference(row, "roce"),
    axis=1,
)

reference_check["roe_anomaly_gt_5pp"] = (
    reference_check["roe_difference_pp"] > 5
)

reference_check["roce_anomaly_gt_5pp"] = (
    reference_check["roce_difference_pp"] > 5
)

# Keep the complete cross-check as an audit file.
reference_check_path = (
    OUTPUT / "companies_reference_ratio_crosscheck.csv"
)

reference_check.to_csv(
    reference_check_path,
    index=False,
)

print(
    "Created:",
    reference_check_path,
)

print("Generating edge-case log...")

log_lines = []

log_lines.append(
    "NIFTY100 RATIO ENGINE - EDGE CASE LOG"
)

log_lines.append("=" * 70)
log_lines.append("")

# Variant groups
variant_groups = ratio_key_counts[
    ratio_key_counts["record_count"] > 1
]

log_lines.append(
    f"Variant company-year groups: {len(variant_groups)}"
)

log_lines.append(
    f"Variant rows: {(ratios['record_status'] == 'VARIANT_REVIEW').sum()}"
)

log_lines.append("")

# Negative equity
negative_equity = ratios[
    ratios["_panel_equity_capital"].fillna(0)
    + ratios["_panel_reserves"].fillna(0)
    <= 0
]

log_lines.append(
    f"Negative/non-positive equity records: {len(negative_equity)}"
)

# Debt free
debt_free = ratios[
    ratios["engine_interest_coverage"].isna()
]

log_lines.append(
    f"Debt-free / zero-interest records: {len(debt_free)}"
)

# High leverage
high_leverage = ratios[
    ratios["high_leverage_flag"] == True
]

log_lines.append(
    f"High leverage non-Financial records: {len(high_leverage)}"
)

# CAGR flags
for column in [
    "revenue_cagr_5yr_flag",
    "pat_cagr_5yr_flag",
    "eps_cagr_5yr_flag",
]:
    if column in ratios.columns:
        counts = ratios[column].value_counts(dropna=False)

        log_lines.append("")
        log_lines.append(column)

        for flag, count in counts.items():
            log_lines.append(
                f"  {flag}: {count}"
            )

# Source OPM discrepancy
if "operating_profit_margin_pct" in ratios.columns:
    opm_diff = (
        ratios["engine_operating_profit_margin_pct"]
        - ratios["operating_profit_margin_pct"]
    ).abs()

    opm_anomalies = ratios[
        opm_diff > 5
    ]

    log_lines.append("")
    log_lines.append(
        f"OPM source-vs-engine anomalies >5%: {len(opm_anomalies)}"
    )

# Source ROE discrepancy
if "return_on_equity_pct" in ratios.columns:
    roe_diff = (
        ratios["engine_return_on_equity_pct"]
        - ratios["return_on_equity_pct"]
    ).abs()

    roe_anomalies = ratios[
        roe_diff > 5
    ]

    log_lines.append(
        f"ROE source-vs-engine anomalies >5%: {len(roe_anomalies)}"
    )

log_lines.append("")
log_lines.append(
    "Note: source values are preserved for auditability."
)

# Day 13: companies.xlsx reference ROE / ROCE cross-check
log_lines.append("")
log_lines.append(
    "DAY 13: companies.xlsx reference ROE/ROCE cross-check"
)
log_lines.append("-" * 70)

if "reference_check" in globals():

    roe_ref_anomalies = reference_check[
        reference_check["roe_anomaly_gt_5pp"] == True
    ]

    roce_ref_anomalies = reference_check[
        reference_check["roce_anomaly_gt_5pp"] == True
    ]

    log_lines.append(
        f"Companies reference records: {len(reference_check)}"
    )

    log_lines.append(
        f"ROE anomalies >5 percentage points: "
        f"{len(roe_ref_anomalies)}"
    )

    log_lines.append(
        f"ROCE anomalies >5 percentage points: "
        f"{len(roce_ref_anomalies)}"
    )

    log_lines.append("")

    log_lines.append("ROE reference anomalies:")

    for _, row in roe_ref_anomalies.iterrows():
        log_lines.append(
            f"  {row['company_id']} | "
            f"latest_year={int(row['year'])} | "
            f"engine={row['engine_return_on_equity_pct']:.2f}% | "
            f"reference={row['reference_roe_pct']:.2f}% | "
            f"diff={row['roe_difference_pp']:.2f} pp | "
            f"classification={row['roe_classification']}"
        )

    log_lines.append("")
    log_lines.append("ROCE reference anomalies:")

    for _, row in roce_ref_anomalies.iterrows():

        engine_roce = row["engine_roce_pct"]
        reference_roce = row["reference_roce_pct"]
        difference = row["roce_difference_pp"]

        engine_text = (
            f"{engine_roce:.2f}%"
            if pd.notna(engine_roce)
            else "NA"
        )

        reference_text = (
            f"{reference_roce:.2f}%"
            if pd.notna(reference_roce)
            else "NA"
        )

        difference_text = (
            f"{difference:.2f} pp"
            if pd.notna(difference)
            else "NA"
        )

        log_lines.append(
            f"  {row['company_id']} | "
            f"latest_year={int(row['year'])} | "
            f"engine={engine_text} | "
            f"reference={reference_text} | "
            f"diff={difference_text} | "
            f"classification={row['roce_classification']}"
        )

    log_lines.append("")
    log_lines.append(
        "Classification note: companies.xlsx contains a single "
        "company-level reference ROE/ROCE value, while the ratio "
        "engine is year-specific. Therefore >5 pp differences are "
        "treated as period/source discrepancies unless a formula "
        "problem is independently established."
    )

log_lines.append(
    "Engine-calculated values are used for analytical calculations "
    "where underlying financial inputs are available."
)

log_lines.append(
    "Variant records are retained and explicitly flagged rather "
    "than silently discarded."
)

with open(
    OUTPUT / "ratio_edge_cases.log",
    "w",
    encoding="utf-8",
) as f:
    f.write("\n".join(log_lines))

print(
    "Created:",
    OUTPUT / "ratio_edge_cases.log",
)


# ============================================================
# FINAL OUTPUT COLUMN ORDER
# ============================================================

base_columns = [
    "id",
    "company_id",
    "year",
    "broad_sector",
    "record_status",
    "record_count",

    # Source KPIs
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
    "cash_from_operations_cr",

    # Engine KPIs
    "engine_net_profit_margin_pct",
    "engine_operating_profit_margin_pct",
    "engine_return_on_equity_pct",
    "engine_roce_pct",
    "engine_roa_pct",
    "engine_debt_to_equity",
    "high_leverage_flag",
    "engine_interest_coverage",
    "icr_label",
    "icr_warning",
    "engine_net_debt_cr",
    "engine_asset_turnover",

    # Cash-flow KPIs
    "capex_intensity_pct",
    "fcf_conversion_pct",
    "cfo_pat_ratio",
    "cfo_quality_label",
    "capital_allocation",

    # CAGR
    "revenue_cagr_3yr",
    "revenue_cagr_3yr_flag",
    "revenue_cagr_5yr",
    "revenue_cagr_5yr_flag",
    "revenue_cagr_10yr",
    "revenue_cagr_10yr_flag",

    "pat_cagr_3yr",
    "pat_cagr_3yr_flag",
    "pat_cagr_5yr",
    "pat_cagr_5yr_flag",
    "pat_cagr_10yr",
    "pat_cagr_10yr_flag",

    "eps_cagr_3yr",
    "eps_cagr_3yr_flag",
    "eps_cagr_5yr",
    "eps_cagr_5yr_flag",
    "eps_cagr_10yr",
    "eps_cagr_10yr_flag",

    # Composite
    "composite_quality_score",
]


final_columns = [
    c for c in base_columns
    if c in ratios.columns
]

output_df = ratios[final_columns].copy()


# ============================================================
# WRITE ANALYTICAL CSV
# ============================================================

engine_csv = ANALYTICAL / "financial_ratios_engine.csv"

output_df.to_csv(
    engine_csv,
    index=False,
)

print(
    "Created:",
    engine_csv,
)


# ============================================================
# WRITE SQLITE TABLE
# ============================================================

print("\nUpdating SQLite database...")

with sqlite3.connect(DB_PATH) as conn:

    output_df.to_sql(
        "financial_ratios",
        conn,
        if_exists="replace",
        index=False,
    )

print("SQLite table created: financial_ratios")


# ============================================================
# FINAL VALIDATION
# ============================================================

with sqlite3.connect(DB_PATH) as conn:

    db_count = pd.read_sql_query(
        "SELECT COUNT(*) AS row_count FROM financial_ratios",
        conn,
    ).iloc[0]["row_count"]

    db_columns = pd.read_sql_query(
        "PRAGMA table_info(financial_ratios)",
        conn,
    )


print("\n" + "=" * 70)
print("RATIO ENGINE COMPLETE")
print("=" * 70)

print(f"Input ratio rows:       {len(ratios):,}")
print(f"Output ratio rows:      {len(output_df):,}")
print(f"SQLite ratio rows:      {db_count:,}")
print(
    f"Output columns:         {len(output_df.columns)}"
)

print(
    "\nVariant rows retained:",
    (
        output_df["record_status"]
        .eq("VARIANT_REVIEW")
        .sum()
    ),
)

print(
    "\nRequired KPI columns:"
)

required_kpis = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
    "cash_from_operations_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "composite_quality_score",
]

for column in required_kpis:
    if column in output_df.columns:
        non_null = output_df[column].notna().sum()
        print(
            f"  {column:<35} "
            f"{non_null:>5}/{len(output_df)} populated"
        )
    else:
        print(
            f"  {column:<35} MISSING"
        )

print("\nOutput files:")
print(f"  {engine_csv}")
print(f"  {OUTPUT / 'capital_allocation.csv'}")
print(f"  {OUTPUT / 'ratio_edge_cases.log'}")

print("\nIMPORTANT:")
print(
    "The engine does not manufacture rows to satisfy the "
    "1,100-row target."
)

print(
    "All source/variant records are preserved transparently."
)
