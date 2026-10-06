from typing import Optional


def free_cash_flow(
    operating_activity,
    investing_activity,
) -> Optional[float]:
    if operating_activity is None and investing_activity is None:
        return None

    return (operating_activity or 0) + (investing_activity or 0)


def cfo_pat_ratio(cfo, pat) -> Optional[float]:
    if pat in (None, 0):
        return None

    return cfo / pat


def cfo_quality_label(ratio) -> Optional[str]:
    if ratio is None:
        return None

    if ratio > 1.0:
        return "High Quality"

    if ratio >= 0.5:
        return "Moderate"

    return "Accrual Risk"


def capex_intensity(
    investing_activity,
    sales,
) -> Optional[float]:
    if sales in (None, 0):
        return None

    return abs(investing_activity or 0) / sales * 100


def capex_intensity_label(value) -> Optional[str]:
    if value is None:
        return None

    if value < 3:
        return "Asset Light"

    if value <= 8:
        return "Moderate"

    return "Capital Intensive"


def fcf_conversion_rate(
    free_cash_flow_value,
    operating_profit,
) -> Optional[float]:
    if operating_profit in (None, 0):
        return None

    return (free_cash_flow_value / operating_profit) * 100


def sign(value) -> str:
    if value is None:
        return "0"

    if value > 0:
        return "+"

    if value < 0:
        return "-"

    return "0"


def classify_capital_allocation(
    cfo,
    cfi,
    cff,
    cfo_pat_ratio_value=None,
) -> str:

    cfo_sign = sign(cfo)
    cfi_sign = sign(cfi)
    cff_sign = sign(cff)

    pattern = (cfo_sign, cfi_sign, cff_sign)

    if pattern == ("+", "-", "-"):
        if (
            cfo_pat_ratio_value is not None
            and cfo_pat_ratio_value > 1.0
        ):
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
