from typing import Optional, Tuple


def calculate_cagr(
    start_value,
    end_value,
    years: int,
) -> Tuple[Optional[float], str]:
    """
    Calculate CAGR with explicit handling of financial edge cases.

    Returns:
        (cagr_value, flag)
    """

    if start_value is None or end_value is None:
        return None, "INSUFFICIENT"

    if years is None or years <= 0:
        return None, "INSUFFICIENT"

    if start_value == 0:
        return None, "ZERO_BASE"

    # Positive -> Positive
    if start_value > 0 and end_value > 0:
        cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
        return cagr, "NORMAL"

    # Positive -> Negative
    if start_value > 0 and end_value < 0:
        return None, "DECLINE_TO_LOSS"

    # Negative -> Positive
    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"

    # Negative -> Negative
    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    # End value exactly zero
    if end_value == 0:
        return None, "DECLINE_TO_LOSS"

    return None, "INSUFFICIENT"


def revenue_cagr(start_value, end_value, years):
    return calculate_cagr(start_value, end_value, years)


def pat_cagr(start_value, end_value, years):
    return calculate_cagr(start_value, end_value, years)


def eps_cagr(start_value, end_value, years):
    return calculate_cagr(start_value, end_value, years)
