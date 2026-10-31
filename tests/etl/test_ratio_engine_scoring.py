import numpy as np
import pandas as pd

from src.etl.build_ratio_engine import percentile_score


def test_ineligible_rows_do_not_affect_percentile_ranks():
    values = pd.Series([10.0, 20.0, 30.0], index=["a", "b", "c"])
    eligible = pd.Series([True, True, False], index=values.index)

    scores = percentile_score(values, eligible=eligible)

    assert scores["a"] == 50.0
    assert scores["b"] == 100.0
    assert np.isnan(scores["c"])


def test_inverse_percentile_respects_eligibility():
    values = pd.Series([10.0, 20.0, 999.0], index=["a", "b", "c"])
    eligible = pd.Series([True, True, False], index=values.index)

    scores = percentile_score(
        values,
        inverse=True,
        eligible=eligible,
    )

    assert scores["a"] == 100.0
    assert scores["b"] == 50.0
    assert np.isnan(scores["c"])


def test_missing_eligibility_is_treated_as_ineligible():
    values = pd.Series([10.0, 20.0], index=["a", "b"])
    eligible = pd.Series([True, np.nan], index=values.index)

    scores = percentile_score(values, eligible=eligible)

    assert scores["a"] == 100.0
    assert np.isnan(scores["b"])


def test_no_eligible_values_returns_all_missing_scores():
    values = pd.Series([10.0, 20.0])
    eligible = pd.Series([False, False], index=values.index)

    scores = percentile_score(values, eligible=eligible)

    assert scores.isna().all()