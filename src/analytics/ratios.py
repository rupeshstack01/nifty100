from typing import Optional


def net_profit_margin(net_profit, sales) -> Optional[float]:
    if sales in (None, 0):
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(operating_profit, sales) -> Optional[float]:
    if sales in (None, 0):
        return None
    return (operating_profit / sales) * 100


def roe(net_profit, equity_capital, reserves) -> Optional[float]:
    equity = (equity_capital or 0) + (reserves or 0)
    if equity <= 0:
        return None
    return (net_profit / equity) * 100


def roce(ebit, equity_capital, reserves, borrowings) -> Optional[float]:
    capital_employed = (
        (equity_capital or 0)
        + (reserves or 0)
        + (borrowings or 0)
    )
    if capital_employed <= 0:
        return None
    return (ebit / capital_employed) * 100


def roa(net_profit, total_assets) -> Optional[float]:
    if total_assets in (None, 0):
        return None
    return (net_profit / total_assets) * 100


def debt_to_equity(borrowings, equity_capital, reserves) -> Optional[float]:
    equity = (equity_capital or 0) + (reserves or 0)

    if borrowings in (None, 0):
        return 0.0

    if equity <= 0:
        return None

    return borrowings / equity


def high_leverage_flag(debt_equity, broad_sector) -> bool:
    if debt_equity is None:
        return False

    if broad_sector == "Financials":
        return False

    return debt_equity > 5


def interest_coverage(
    operating_profit,
    other_income,
    interest,
) -> Optional[float]:
    if interest in (None, 0):
        return None

    return ((operating_profit or 0) + (other_income or 0)) / interest


def icr_label(icr) -> Optional[str]:
    if icr is None:
        return "Debt Free"
    return None


def icr_warning(icr) -> bool:
    if icr is None:
        return False
    return icr < 1.5


def net_debt(borrowings, investments) -> Optional[float]:
    if borrowings is None and investments is None:
        return None

    return (borrowings or 0) - (investments or 0)


def asset_turnover(sales, total_assets) -> Optional[float]:
    if total_assets in (None, 0):
        return None

    return sales / total_assets


def return_on_assets(net_profit, total_assets) -> Optional[float]:
    return roa(net_profit, total_assets)


def fcf(operating_activity, investing_activity) -> Optional[float]:
    if operating_activity is None and investing_activity is None:
        return None

    return (operating_activity or 0) + (investing_activity or 0)


def capex_intensity(investing_activity, sales) -> Optional[float]:
    if sales in (None, 0):
        return None

    return abs(investing_activity or 0) / sales * 100


def fcf_conversion_rate(free_cash_flow, operating_profit) -> Optional[float]:
    if operating_profit in (None, 0):
        return None

    return (free_cash_flow / operating_profit) * 100
