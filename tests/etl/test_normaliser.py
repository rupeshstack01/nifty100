import pytest

from src.etl.normaliser import normalize_year, normalize_ticker


# ============================================================
# normalize_year() — 20 tests
# ============================================================

@pytest.mark.parametrize(
    "value, expected",
    [
        ("2024", 2024),
        ("2023", 2023),
        ("2012", 2012),
        ("1999", 1999),
        ("Dec 2012", 2012),
        ("Mar 2014", 2014),
        ("Mar-13", 2013),
        ("Jan-20", 2020),
        ("Dec-24", 2024),
        ("2020-03-31", 2020),
        ("31-03-2020", 2020),
        ("03/31/2020", 2020),
        (2024, 2024),
        (2020.0, 2020),
        (" 2024 ", 2024),
        ("FY2024", 2024),
        ("FY 2023", 2023),
        ("March 2021", 2021),
        ("December 2019", 2019),
        ("Apr-18", 2018),
    ],
)
def test_normalize_year_valid(value, expected):
    assert normalize_year(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "not-a-year",
        "ABC",
    ],
)
def test_normalize_year_invalid(value):
    assert normalize_year(value) is None


# ============================================================
# normalize_ticker() — 15 tests
# ============================================================

@pytest.mark.parametrize(
    "value, expected",
    [
        ("ABB", "ABB"),
        ("abb", "ABB"),
        (" Abb ", "ABB"),
        ("TCS", "TCS"),
        ("tcs", "TCS"),
        (" HDFCBANK ", "HDFCBANK"),
        ("hdfc-bank", "HDFCBANK"),
        ("ADANI-ENSOL", "ADANIENSOL"),
        ("ADANI_ENSOL", "ADANIENSOL"),
        ("ADANI.ENSOL", "ADANIENSOL"),
        ("RELIANCE ", "RELIANCE"),
        (" INFY", "INFY"),
        ("M&M", "M&M"),
        ("ICICI BANK", "ICICIBANK"),
        ("  LT  ", "LT"),
    ],
)
def test_normalize_ticker_valid(value, expected):
    assert normalize_ticker(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
    ],
)
def test_normalize_ticker_invalid(value):
    assert normalize_ticker(value) is None
