import pandas as pd
import pytest

from src.etl.validator import dq05_opm_crosscheck, dq11_ratio_sanity


def run_dq05(frame):
    failures = []
    dq05_opm_crosscheck({"profitandloss": frame.copy()}, failures)
    return failures


def run_dq11(frame):
    failures = []
    dq11_ratio_sanity({"financial_ratios": frame.copy()}, failures)
    return failures


def test_dq05_matching_opm_has_no_failure():
    df = pd.DataFrame([{
        "company_id": "TEST",
        "year": 2024,
        "sales": 200,
        "operating_profit": 50,
        "opm_percentage": 25,
    }])

    assert run_dq05(df) == []


def test_dq05_flags_difference_over_one_percentage_point():
    df = pd.DataFrame([{
        "company_id": "TEST",
        "year": 2024,
        "sales": 200,
        "operating_profit": 50,
        "opm_percentage": 23,
    }])

    failures = run_dq05(df)

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-05"
    assert failures[0]["severity"] == "WARNING"
    assert "calculated=25.00%" in failures[0]["message"]


def test_dq05_ignores_zero_sales():
    df = pd.DataFrame([{
        "company_id": "TEST",
        "year": 2024,
        "sales": 0,
        "operating_profit": 50,
        "opm_percentage": 25,
    }])

    assert run_dq05(df) == []


def test_dq05_ignores_missing_inputs():
    df = pd.DataFrame([{
        "company_id": "TEST",
        "year": 2024,
        "sales": None,
        "operating_profit": 50,
        "opm_percentage": 25,
    }])

    assert run_dq05(df) == []


@pytest.mark.parametrize("value", [-1001, 1001, -50971, 13857])
def test_dq11_flags_extreme_opm(value):
    df = pd.DataFrame([{
        "company_id": "TEST",
        "year": 2024,
        "operating_profit_margin_pct": value,
    }])

    failures = run_dq11(df)

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-11"
    assert "operating_profit_margin_pct" in failures[0]["message"]


def test_dq11_does_not_flag_opm_inside_existing_limits():
    df = pd.DataFrame([{
        "company_id": "TEST",
        "year": 2024,
        "operating_profit_margin_pct": 100,
    }])

    assert run_dq11(df) == []
