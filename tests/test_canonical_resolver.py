import pandas as pd
from pandas.testing import assert_frame_equal

from src.etl.canonical_resolver import (
    canonical_period,
    normalize_keys,
    remove_exact_duplicates,
    build_variant_review,
)


def test_period_aliases_share_a_canonical_key():
    assert canonical_period("Mar-13") == "Mar 2013"
    assert canonical_period("Mar 2013") == "Mar 2013"
    assert canonical_period("MAR/2013") == "Mar 2013"


def test_ttm_and_unusual_periods_remain_distinct():
    assert canonical_period("TTM") == "ttm"
    assert canonical_period("2024.5") == "2024.5"
    assert canonical_period("TTM") != canonical_period("Mar 2024")
    assert canonical_period("2024.5") != canonical_period("Mar 2024")


def test_normalize_keys_does_not_modify_input():
    source = pd.DataFrame({
        "id": [1],
        "company_id": [" tcs "],
        "year": [2013],
        "reporting_period": ["Mar-13"],
        "operating_activity": [100],
    })
    original = source.copy(deep=True)

    normalized = normalize_keys(source)

    assert_frame_equal(source, original)
    assert normalized.loc[0, "_canonical_period_key"] == "Mar 2013"


def test_exact_duplicates_are_removed():
    source = pd.DataFrame({
        "id": [1, 2],
        "company_id": ["TCS", "TCS"],
        "year": [2013, 2013],
        "reporting_period": ["Mar-13", "Mar 2013"],
        "operating_activity": [100, 100],
    })

    cleaned, audit = remove_exact_duplicates(source)

    assert len(cleaned) == 1
    assert len(audit) == 1
    assert audit.iloc[0]["duplicate_type"] == "EXACT_DUPLICATE"


def test_conflicting_financial_values_are_preserved_and_flagged():
    source = pd.DataFrame({
        "id": [1, 2],
        "company_id": ["ABB", "ABB"],
        "year": [2024, 2024],
        "reporting_period": ["Mar 2024", "Mar-24"],
        "operating_activity": [100, 120],
    })

    cleaned, audit = remove_exact_duplicates(source)
    review = build_variant_review(cleaned)

    assert len(cleaned) == 2
    assert len(audit) == 1
    assert audit.iloc[0]["duplicate_type"] == "VARIANT_DUPLICATE"
    assert len(review) == 1
    assert review.iloc[0]["resolution"] == "REVIEW_REQUIRED"
    assert "operating_activity" in review.iloc[0]["differing_columns"]


def test_different_periods_in_same_year_are_not_merged():
    source = pd.DataFrame({
        "id": [1, 2],
        "company_id": ["ABC", "ABC"],
        "year": [2024, 2024],
        "reporting_period": ["Mar 2024", "Sep 2024"],
        "sales": [100, 150],
    })

    cleaned, _ = remove_exact_duplicates(source)

    assert len(cleaned) == 2
    assert set(cleaned["reporting_period"]) == {"Mar 2024", "Sep 2024"}


def test_ttm_duplicates_only_deduplicate_when_values_match():
    source = pd.DataFrame({
        "id": [1, 2, 3],
        "company_id": ["ABC", "ABC", "XYZ"],
        "year": [None, None, None],
        "reporting_period": ["TTM", "TTM", "TTM"],
        "net_profit": [50, 50, 75],
    })

    cleaned, _ = remove_exact_duplicates(source)

    assert len(cleaned) == 2
    assert set(cleaned["company_id"]) == {"ABC", "XYZ"}
    assert cleaned.loc[cleaned["company_id"] == "ABC", "net_profit"].iloc[0] == 50
