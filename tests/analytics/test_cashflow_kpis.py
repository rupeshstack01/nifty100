import numpy as np
import pytest

from src.analytics.cashflow_kpis import (
    free_cash_flow,
    cfo_pat_ratio,
    cfo_quality_label,
    capex_intensity,
    capex_intensity_label,
    fcf_conversion_rate,
    sign,
    classify_capital_allocation,
)


def test_free_cash_flow_normal():
    assert free_cash_flow(100, -40) == 60


def test_free_cash_flow_both_missing():
    assert free_cash_flow(None, None) is None


def test_cfo_pat_ratio_normal():
    assert cfo_pat_ratio(120, 100) == pytest.approx(1.2)


def test_cfo_pat_ratio_zero_pat():
    assert cfo_pat_ratio(120, 0) is None


@pytest.mark.parametrize(
    "ratio, expected",
    [
        (1.2, "High Quality"),
        (0.75, "Moderate"),
        (0.3, "Accrual Risk"),
        (None, None),
        (np.nan, None),
    ],
)
def test_cfo_quality_label(ratio, expected):
    assert cfo_quality_label(ratio) == expected


def test_capex_intensity_normal():
    assert capex_intensity(-20, 100) == pytest.approx(20.0)


def test_capex_intensity_zero_sales():
    assert capex_intensity(-20, 0) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (2.0, "Asset Light"),
        (5.0, "Moderate"),
        (10.0, "Capital Intensive"),
        (None, None),
        (np.nan, None),
    ],
)
def test_capex_intensity_label(value, expected):
    assert capex_intensity_label(value) == expected


def test_fcf_conversion_rate_normal():
    assert fcf_conversion_rate(50, 100) == pytest.approx(50.0)


def test_fcf_conversion_rate_zero_operating_profit():
    assert fcf_conversion_rate(50, 0) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (10, "+"),
        (-10, "-"),
        (0, "0"),
        (None, "0"),
        (np.nan, "0"),
    ],
)
def test_sign(value, expected):
    assert sign(value) == expected


def test_capital_allocation_growth_investment():
    row = {
        "operating_activity": 100,
        "investing_activity": -40,
        "financing_activity": 20,
    }
    assert classify_capital_allocation(row) == "Growth Investment"


def test_capital_allocation_distress_signal():
    row = {
        "operating_activity": -50,
        "investing_activity": -10,
        "financing_activity": 80,
    }
    assert classify_capital_allocation(row) == "Distress Signal"


def test_capital_allocation_missing_data():
    row = {
        "operating_activity": 100,
        "investing_activity": np.nan,
        "financing_activity": -20,
    }
    assert classify_capital_allocation(row) == "Unclassified"
