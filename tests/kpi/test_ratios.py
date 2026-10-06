import math

from src.analytics.ratios import (
    net_profit_margin,
    operating_profit_margin,
    roe,
    roce,
    roa,
    debt_to_equity,
    high_leverage_flag,
    interest_coverage,
    icr_label,
    icr_warning,
    net_debt,
    asset_turnover,
)

from src.analytics.cagr import calculate_cagr

from src.analytics.cashflow_kpis import (
    free_cash_flow,
    cfo_pat_ratio,
    cfo_quality_label,
    capex_intensity,
    capex_intensity_label,
    fcf_conversion_rate,
    classify_capital_allocation,
)


# -----------------------------
# Profitability: 8 tests
# -----------------------------

def test_net_profit_margin_normal():
    assert net_profit_margin(20, 100) == 20


def test_net_profit_margin_zero_sales():
    assert net_profit_margin(20, 0) is None


def test_operating_profit_margin_normal():
    assert operating_profit_margin(30, 100) == 30


def test_roe_normal():
    assert roe(20, 50, 50) == 20


def test_roe_negative_equity():
    assert roe(20, -60, 20) is None


def test_roce_normal():
    assert roce(30, 50, 50, 50) == 20


def test_roa_normal():
    assert roa(20, 100) == 20


def test_roa_zero_assets():
    assert roa(20, 0) is None


# -----------------------------
# Leverage / Efficiency: 8 tests
# -----------------------------

def test_debt_to_equity_debt_free():
    assert debt_to_equity(0, 100, 50) == 0


def test_debt_to_equity_normal():
    assert debt_to_equity(50, 50, 50) == 0.5


def test_high_leverage_non_financial():
    assert high_leverage_flag(6, "Energy") is True


def test_high_leverage_financial():
    assert high_leverage_flag(6, "Financials") is False


def test_interest_coverage_zero_interest():
    assert interest_coverage(100, 10, 0) is None


def test_icr_debt_free_label():
    assert icr_label(None) == "Debt Free"


def test_icr_warning():
    assert icr_warning(1.2) is True


def test_asset_turnover_zero_assets():
    assert asset_turnover(100, 0) is None


# -----------------------------
# CAGR + Cash Flow: 4 tests
# -----------------------------

def test_cagr_normal():
    value, flag = calculate_cagr(100, 121, 2)
    assert round(value, 2) == 10.0
    assert flag == "NORMAL"


def test_cagr_turnaround():
    value, flag = calculate_cagr(-100, 200, 5)
    assert value is None
    assert flag == "TURNAROUND"


def test_cagr_decline_to_loss():
    value, flag = calculate_cagr(100, -20, 5)
    assert value is None
    assert flag == "DECLINE_TO_LOSS"


def test_cagr_zero_base():
    value, flag = calculate_cagr(0, 100, 5)
    assert value is None
    assert flag == "ZERO_BASE"
