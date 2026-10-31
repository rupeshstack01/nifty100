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


def percentile_score(series, inverse=False, eligible=None):
    """
    Convert a KPI into a 0-100 percentile score.

    Only eligible rows participate in peer ranking.
    Ineligible rows retain NaN scores.
    """
    result = pd.Series(np.nan, index=series.index, dtype=float)

    valid = series.notna()

    if eligible is not None:
        eligible = eligible.reindex(series.index).fillna(False).astype(bool)
        valid = valid & eligible

    if valid.sum() == 0:
        return result

    ranked = series[valid].rank(
        pct=True,
        ascending=not inverse,
    ) * 100

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
    Classify capital allocation only when all three cash-flow
    inputs are available and trustworthy.
    """
    if cfo is None or cfi is None or cff is None:
        return "Insufficient Data"

    if any(pd.isna(value) for value in (cfo, cfi, cff)):
        return "Insufficient Data"

    pattern = (
        sign(cfo),
        sign(cfi),
        sign(cff),
    )

    if pattern == ("+", "-", "-"):
        if cfo_pat_ratio is not None and not pd.isna(cfo_pat_ratio):
            if cfo_pat_ratio > 1:
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
# JOIN FINANCIAL PANEL WITH DATA-QUALITY FLAGS
# ============================================================

panel_lookup = panel.copy()

# The panel should contain exactly one row per company-year.
if panel_lookup.duplicated(["company_id", "year"]).any():
    raise ValueError(
        "financial_panel.csv contains duplicate company-year keys."
    )

panel_lookup = panel_lookup.rename(
    columns={
        "profitandloss_sales": "_panel_sales",
        "profitandloss_net_profit": "_panel_net_profit",
        "profitandloss_operating_profit": "_panel_operating_profit",
        "profitandloss_other_income": "_panel_other_income",
        "profitandloss_interest": "_panel_interest",
        "balancesheet_equity_capital": "_panel_equity_capital",
        "balancesheet_reserves": "_panel_reserves",
        "balancesheet_borrowings": "_panel_borrowings",
        "balancesheet_investments": "_panel_investments",
        "balancesheet_total_assets": "_panel_total_assets",
        "cashflow_operating_activity": "_panel_cfo",
        "cashflow_investing_activity": "_panel_cfi",
        "cashflow_financing_activity": "_panel_cff",
        "cashflow_net_cash_flow": "_panel_net_cash_flow",
        "profitandloss_ambiguous": "_pl_ambiguous",
        "balancesheet_ambiguous": "_bs_ambiguous",
        "cashflow_ambiguous": "_cf_ambiguous",
        "financial_ratios_ambiguous": "_ratios_ambiguous",
    }
)

panel_fields = [
    "company_id",
    "year",
    "_panel_sales",
    "_panel_net_profit",
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
    "_panel_net_cash_flow",
    "_pl_ambiguous",
    "_bs_ambiguous",
    "_cf_ambiguous",
    "_ratios_ambiguous",
]

panel_fields = [
    column for column in panel_fields
    if column in panel_lookup.columns
]

ratios = ratios.merge(
    panel_lookup[panel_fields],
    on=["company_id", "year"],
    how="left",
    validate="many_to_one",
)

# Expose the data-quality flags in the output.
# Use the authoritative panel review file, including missing records.
review_path = ANALYTICAL / "financial_panel_review.csv"

if not review_path.exists():
    raise FileNotFoundError(
        f"Required panel review file is missing: {review_path}"
    )

review = pd.read_csv(review_path)

required_review_columns = [
    "company_id",
    "year",
    "needs_review",
]

missing_review_columns = [
    column for column in required_review_columns
    if column not in review.columns
]

if missing_review_columns:
    raise ValueError(
        f"Panel review file is missing columns: {missing_review_columns}"
    )

if review.duplicated(["company_id", "year"]).any():
    raise ValueError(
        "Panel review file has duplicate company-year keys."
    )

review["needs_review"] = (
    review["needs_review"].fillna(True).astype(bool)
)

ratios = ratios.merge(
    review[["company_id", "year", "needs_review"]].rename(
        columns={"needs_review": "_authoritative_needs_review"}
    ),
    on=["company_id", "year"],
    how="left",
    validate="many_to_one",
)

# Unmatched keys are conservatively marked for review.
ratios["panel_needs_review"] = (
    ratios["_authoritative_needs_review"].fillna(True).astype(bool)
)


# ============================================================
# CALCULATE ENGINE KPIs
# ============================================================

print("\nCalculating ratio KPIs...")


def calculate_engine_row(row):
    if bool(row.get("panel_needs_review", True)):
        return pd.Series({
            "engine_net_profit_margin_pct": np.nan,
            "engine_operating_profit_margin_pct": np.nan,
            "engine_return_on_equity_pct": np.nan,
            "engine_roce_pct": np.nan,
            "engine_roa_pct": np.nan,
            "engine_debt_to_equity": np.nan,
            "high_leverage_flag": False,
            "engine_interest_coverage": np.nan,
            "icr_label": None,
            "icr_warning": None,
            "engine_net_debt_cr": np.nan,
            "engine_asset_turnover": np.nan,
        })

    pl_ambiguous = bool(row.get("_pl_ambiguous", True))
    bs_ambiguous = bool(row.get("_bs_ambiguous", True))
    ratio_ambiguous = bool(row.get("_ratios_ambiguous", True))

    # P&L inputs are only trusted when that source is unambiguous.
    sales = safe_num(row.get("_panel_sales")) if not pl_ambiguous else None
    net_profit = safe_num(row.get("_panel_net_profit")) if not pl_ambiguous else None
    operating_profit = (
        safe_num(row.get("_panel_operating_profit"))
        if not pl_ambiguous else None
    )
    other_income = (
        safe_num(row.get("_panel_other_income"))
        if not pl_ambiguous else None
    )
    interest = safe_num(row.get("_panel_interest")) if not pl_ambiguous else None

    # Balance-sheet inputs are only trusted when that source is unambiguous.
    equity_capital = (
        safe_num(row.get("_panel_equity_capital"))
        if not bs_ambiguous else None
    )
    reserves = safe_num(row.get("_panel_reserves")) if not bs_ambiguous else None
    borrowings = (
        safe_num(row.get("_panel_borrowings"))
        if not bs_ambiguous else None
    )
    investments = (
        safe_num(row.get("_panel_investments"))
        if not bs_ambiguous else None
    )
    total_assets = (
        safe_num(row.get("_panel_total_assets"))
        if not bs_ambiguous else None
    )

    # Require both equity components; do not assume missing means zero.
    equity = (
        equity_capital + reserves
        if equity_capital is not None and reserves is not None
        else None
    )

    npm = (
        net_profit / sales * 100
        if sales not in (None, 0) and net_profit is not None
        else None
    )
    opm = (
        operating_profit / sales * 100
        if sales not in (None, 0) and operating_profit is not None
        else None
    )
    roe_value = (
        net_profit / equity * 100
        if net_profit is not None and equity not in (None, 0) and equity > 0
        else None
    )

    capital_employed = (
        equity + borrowings
        if equity is not None and borrowings is not None
        else None
    )
    roce_value = (
        operating_profit / capital_employed * 100
        if operating_profit is not None
        and capital_employed not in (None, 0)
        and capital_employed > 0
        else None
    )
    roa_value = (
        net_profit / total_assets * 100
        if net_profit is not None and total_assets not in (None, 0)
        else None
    )

    if borrowings is None or equity is None or equity <= 0:
        de_value = None
    else:
        de_value = borrowings / equity

    sector = row.get("broad_sector")
    high_leverage = (
        de_value is not None
        and de_value > 5
        and sector != "Financials"
    )



    if (
        interest is None
        or interest <= 0
        or operating_profit is None
        or other_income is None
    ):
        icr_value = None
        icr_label_value = None
        icr_warning_value = None
    else:
        icr_value = (operating_profit + other_income) / interest
        icr_label_value = None
        icr_warning_value = icr_value < 1.5

    net_debt_value = (
        borrowings - investments
        if borrowings is not None and investments is not None
        else None
    )

    asset_turnover_value = (
        sales / total_assets
        if sales is not None and total_assets not in (None, 0)
        else None
    )

    return pd.Series({
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
    })


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


def trusted_num(row, field, ambiguous_flag=None):
    """Return a numeric value only when its source is trustworthy."""
    if ambiguous_flag and bool(row.get(ambiguous_flag, True)):
        return None

    return safe_num(row.get(field))


# Trust panel cash-flow values only when the cash-flow source
# is unambiguous. Never infer FCF or capex from total investing cash flow.
ratios["cash_from_operations_cr"] = ratios.apply(
    lambda r: trusted_num(r, "_panel_cfo", "_cf_ambiguous"),
    axis=1,
)

# Preserve source-provided ratio-table values only when that source
# is unambiguous. Missing values remain missing.
if "_ratios_ambiguous" in ratios.columns:
    trusted_ratio_source = ~ratios["_ratios_ambiguous"].fillna(True).astype(bool)
else:
    trusted_ratio_source = pd.Series(False, index=ratios.index)

ratios["free_cash_flow_cr"] = ratios["free_cash_flow_cr"].where(
    trusted_ratio_source
)

ratios["capex_cr"] = ratios["capex_cr"].where(
    trusted_ratio_source
)

# Capex intensity requires a trusted capex value and trusted revenue.
ratios["capex_intensity_pct"] = ratios.apply(
    lambda r: (
        safe_num(r.get("capex_cr"))
        / trusted_num(r, "_panel_sales", "_pl_ambiguous")
        * 100
        if (
            safe_num(r.get("capex_cr")) is not None
            and trusted_num(r, "_panel_sales", "_pl_ambiguous")
            not in (None, 0)
        )
        else np.nan
    ),
    axis=1,
)

# FCF conversion requires trusted FCF and operating profit.
ratios["fcf_conversion_pct"] = ratios.apply(
    lambda r: (
        safe_num(r.get("free_cash_flow_cr"))
        / trusted_num(r, "_panel_operating_profit", "_pl_ambiguous")
        * 100
        if (
            safe_num(r.get("free_cash_flow_cr")) is not None
            and trusted_num(
                r, "_panel_operating_profit", "_pl_ambiguous"
            ) not in (None, 0)
        )
        else np.nan
    ),
    axis=1,
)

# CFO/PAT requires trusted operating cash flow and net profit.
ratios["cfo_pat_ratio"] = ratios.apply(
    lambda r: (
        trusted_num(r, "_panel_cfo", "_cf_ambiguous")
        / trusted_num(r, "_panel_net_profit", "_pl_ambiguous")
        if (
            trusted_num(r, "_panel_cfo", "_cf_ambiguous") is not None
            and trusted_num(r, "_panel_net_profit", "_pl_ambiguous")
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


ratios["cfo_quality_label"] = ratios["cfo_pat_ratio"].apply(cfo_quality)

# ============================================================
# CAPITAL ALLOCATION
# ============================================================

ratios["capital_allocation"] = ratios.apply(
    lambda r: capital_allocation(
        safe_num(r.get("_panel_cfo"))
        if not bool(r.get("_cf_ambiguous", True))
        else None,
        safe_num(r.get("_panel_cfi"))
        if not bool(r.get("_cf_ambiguous", True))
        else None,
        safe_num(r.get("_panel_cff"))
        if not bool(r.get("_cf_ambiguous", True))
        else None,
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



# ============================================================
# CAGR ENGINE
# ============================================================

print("Calculating 3Y / 5Y / 10Y CAGR...")


# Build lookups without silently resolving duplicate company-year keys.
def build_cagr_lookup(df, value_columns, ambiguous_column=None):
    lookup = {}

    for _, source_row in df.iterrows():
        company_id = source_row.get("company_id")
        year_value = safe_num(source_row.get("year"))

        if pd.isna(company_id) or year_value is None:
            continue

        key = (company_id, int(year_value))

        # Any repeated key is ambiguous for CAGR purposes.
        if key in lookup:
            lookup[key] = None
            continue

        if ambiguous_column and bool(
            source_row.get(ambiguous_column, True)
        ):
            lookup[key] = None
            continue

        values = {}
        for column in value_columns:
            values[column] = (
                safe_num(source_row.get(column))
                if column in source_row.index
                else None
            )

        lookup[key] = values

    return lookup


# Apply P&L ambiguity flags to CAGR source records.
pl_for_cagr = pl.copy()

if "_pl_ambiguous" not in pl_for_cagr.columns:
    pl_for_cagr = pl_for_cagr.merge(
        panel_lookup[["company_id", "year", "_pl_ambiguous"]],
        on=["company_id", "year"],
        how="left",
        validate="many_to_one",
    )

pl_lookup = build_cagr_lookup(
    pl_for_cagr,
    ["sales", "revenue", "net_profit"],
    ambiguous_column="_pl_ambiguous",
)

ratio_lookup = build_cagr_lookup(
    ratios,
    ["earnings_per_share"],
    ambiguous_column="_ratios_ambiguous",
)


def lookup_value(lookup, company_id, year, candidates):
    key = (company_id, year)

    if key not in lookup or lookup[key] is None:
        return None

    values = lookup[key]

    for column in candidates:
        value = values.get(column)
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

    if value_type in ("revenue", "pat"):
        lookup = pl_lookup
        candidates = (
            ["sales", "revenue"]
            if value_type == "revenue"
            else ["net_profit"]
        )
    elif value_type == "eps":
        lookup = ratio_lookup
        candidates = ["earnings_per_share"]
    else:
        return None, "INSUFFICIENT"

    current_value = lookup_value(
        lookup, company_id, current_year, candidates
    )
    start_value = lookup_value(
        lookup, company_id, start_year, candidates
    )

    if current_value is None or start_value is None:
        return None, "INSUFFICIENT_OR_AMBIGUOUS"

    return cagr(start_value, current_value, years)


for metric_name, value_type in [
    ("revenue", "revenue"),
    ("pat", "pat"),
    ("eps", "eps"),
]:
    for years in [3, 5, 10]:
        results = [
            calculate_cagr_for_row(row, value_type, years)
            for _, row in ratios.iterrows()
        ]

        ratios[f"{metric_name}_cagr_{years}yr"] = [
            value for value, flag in results
        ]

        ratios[f"{metric_name}_cagr_{years}yr_flag"] = [
            flag for value, flag in results
        ]




# ============================================================
# COMPOSITE QUALITY SCORE
# ============================================================

print("Calculating composite quality score...")

# Exclude rows with missing or ambiguous source data from peer rankings.
review_mask = (
    ratios["panel_needs_review"]
    .fillna(True)
    .astype(bool)
)
eligible_mask = ~review_mask

score_components = pd.DataFrame(index=ratios.index)

score_components["npm"] = percentile_score(
    ratios["engine_net_profit_margin_pct"],
    eligible=eligible_mask,
)

score_components["roe"] = percentile_score(
    ratios["engine_return_on_equity_pct"],
    eligible=eligible_mask,
)

score_components["roce"] = percentile_score(
    ratios["engine_roce_pct"],
    eligible=eligible_mask,
)

score_components["asset_turnover"] = percentile_score(
    ratios["engine_asset_turnover"],
    eligible=eligible_mask,
)

score_components["fcf"] = percentile_score(
    ratios["free_cash_flow_cr"],
    eligible=eligible_mask,
)

score_components["revenue_cagr"] = percentile_score(
    ratios["revenue_cagr_5yr"],
    eligible=eligible_mask,
)

score_components["pat_cagr"] = percentile_score(
    ratios["pat_cagr_5yr"],
    eligible=eligible_mask,
)

# Lower debt-to-equity is better.
score_components["debt_to_equity"] = percentile_score(
    ratios["engine_debt_to_equity"],
    inverse=True,
    eligible=eligible_mask,
)

# Track score coverage so incomplete scores are visible.
ratios["quality_score_components_available"] = (
    score_components.notna().sum(axis=1)
)

ratios["quality_score_components_total"] = len(score_components.columns)

MIN_SCORE_COMPONENTS = 6

# Review-required rows must not receive a composite score.
ratios.loc[review_mask, "quality_score_components_available"] = 0

# Calculate the composite score only when enough components are available.
ratios["composite_quality_score"] = score_components.mean(
    axis=1,
    skipna=True,
).where(
    (ratios["quality_score_components_available"] >= MIN_SCORE_COMPONENTS)
    & ~review_mask
)

# Explain why a score is unavailable.
ratios["quality_score_status"] = np.select(
    [
        review_mask,
        ratios["quality_score_components_available"] < MIN_SCORE_COMPONENTS,
    ],
    [
        "NEEDS_REVIEW",
        "INSUFFICIENT_COMPONENTS",
    ],
    default="OK",
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
"quality_score_components_available",
"quality_score_components_total",
"quality_score_status",

# Data quality
"panel_needs_review",
]


final_columns = [
    c for c in base_columns
    if c in ratios.columns
]

output_df = ratios[final_columns].copy()

# ============================================================
# PRE-WRITE VALIDATION
# ============================================================

required_output_columns = [
    "company_id",
    "year",
    "record_status",
    "composite_quality_score",
    "quality_score_components_available",
    "quality_score_components_total",
    "quality_score_status",
]

missing_required = [
    column for column in required_output_columns
    if column not in output_df.columns
]

if missing_required:
    raise ValueError(
        f"Missing required output columns: {missing_required}"
    )

if output_df[["company_id", "year"]].isna().any().any():
    raise ValueError("Output contains missing company_id/year keys.")

if output_df.empty:
    raise ValueError("Refusing to write an empty ratio-engine output.")


if len(output_df) != len(ratios):
    raise ValueError(
        "Output row count differs from input ratio row count."
    )

# Verify that variant records have not been lost.
input_variant_rows = (
    ratios["record_status"].eq("VARIANT_REVIEW").sum()
)

output_variant_rows = (
    output_df["record_status"].eq("VARIANT_REVIEW").sum()
)

if input_variant_rows != output_variant_rows:
    raise ValueError(
        "Variant-preservation check failed: "
        f"input has {input_variant_rows} variant rows, "
        f"output has {output_variant_rows}."
    )

print(f"Variant-preservation check passed: {output_variant_rows} rows.")

print("Pre-write validation passed.")



# ============================================================
# WRITE SQLITE TABLE WITH BACKUP AND VALIDATION
# ============================================================

print("\nUpdating SQLite database...")

import shutil
from datetime import datetime

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database does not exist; refusing to create a replacement: {DB_PATH}"
    )

backup_dir = ROOT / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
db_backup_path = backup_dir / f"nifty100_before_ratio_engine_{timestamp}.db"

# Preserve the current database before modifying it.
shutil.copy2(DB_PATH, db_backup_path)
print(f"Database backup created: {db_backup_path}")

# Write transactionally so a failed SQL operation rolls back.
with sqlite3.connect(DB_PATH) as conn:
    try:
        conn.execute("BEGIN")

        output_df.to_sql(
            "financial_ratios",
            conn,
            if_exists="replace",
            index=False,
        )

        db_count = pd.read_sql_query(
            "SELECT COUNT(*) AS row_count FROM financial_ratios",
            conn,
        ).iloc[0]["row_count"]

        if db_count != len(output_df):
            raise RuntimeError(
                f"SQLite row-count mismatch: expected {len(output_df)}, "
                f"found {db_count}."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

with sqlite3.connect(DB_PATH) as conn:
    db_columns = pd.read_sql_query(
        "PRAGMA table_info(financial_ratios)",
        conn,
    )

print("SQLite table created and row-count check passed.")
print(f"Verified SQLite rows: {db_count:,}")
print(f"Verified SQLite columns: {len(db_columns)}")
print(f"Backup: {db_backup_path}")



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

# ============================================================
# RESTORE OUTPUT FILES AFTER VALIDATION
# ============================================================

import os
import tempfile

engine_csv = ANALYTICAL / "financial_ratios_engine.csv"
capital_allocation_path = OUTPUT / "capital_allocation.csv"
reference_check_path = OUTPUT / "companies_reference_ratio_crosscheck.csv"
edge_cases_path = OUTPUT / "ratio_edge_cases.log"

# Prepare all output files before replacing existing files.
dataframes_to_write = [
    (engine_csv, output_df),
    (capital_allocation_path, capital_allocation_output),
    (reference_check_path, reference_check),
]

staged_files = []

try:
    # Stage and verify each CSV.
    for final_path, dataframe in dataframes_to_write:
        final_path.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{final_path.stem}_",
            suffix=".tmp",
            dir=final_path.parent,
        )
        os.close(fd)

        temp_path = Path(temp_name)
        dataframe.to_csv(temp_path, index=False)

        staged_check = pd.read_csv(temp_path)

        if len(staged_check) != len(dataframe):
            raise RuntimeError(
                f"Staged CSV row-count mismatch: {final_path}"
            )

        staged_files.append((temp_path, final_path))

    # Stage and verify the edge-case log.
    edge_cases_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=".ratio_edge_cases_",
        suffix=".tmp",
        dir=edge_cases_path.parent,
    )
    os.close(fd)

    edge_temp_path = Path(temp_name)
    edge_temp_path.write_text(
        "\n".join(log_lines),
        encoding="utf-8",
    )
    staged_files.append((edge_temp_path, edge_cases_path))

    # Publish the staged files.
    for temp_path, final_path in staged_files:
        os.replace(temp_path, final_path)

except Exception:
    for temp_path, _ in staged_files:
        if temp_path.exists():
            temp_path.unlink()
    raise

print("\nOutput files written and verified:")
print(f"  {engine_csv}")
print(f"  {capital_allocation_path}")
print(f"  {reference_check_path}")
print(f"  {edge_cases_path}")

print("\nIMPORTANT:")
print(
    "The engine does not manufacture rows to satisfy the "
    "1,100-row target."
)
print("All source/variant records are preserved transparently.")