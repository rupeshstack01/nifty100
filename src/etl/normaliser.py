
"""
Data normalization utilities for the Nifty 100 ETL pipeline.
"""

import re
from typing import Optional

import pandas as pd


def normalize_year(value) -> Optional[int]:
    """
    Convert supported reporting-period labels into a four-digit year.

    Examples:
        'Dec 2012' -> 2012
        'Mar 2014' -> 2014
        'Mar-13' -> 2013
        '2024' -> 2024
        '2024.0' -> 2024
        '2024.5' -> None
        'TTM' -> None

    Returns:
        Four-digit year as int, or None if the value cannot be parsed.
    """
    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    # Accept fiscal-year labels such as FY2024 and FY 2023.
    fy_match = re.fullmatch(r"(?i)FY\s*((?:19|20)\d{2})", text)
    if fy_match:
        return int(fy_match.group(1))

    # Accept a plain four-digit year or Excel-style year ending in .0.
    match = re.fullmatch(r"((?:19|20)\d{2})(?:\.0+)?", text)
    if match:
        return int(match.group(1))

    # Accept month/year labels, including Mar-13 and Mar 2013.
    # Optional suffixes such as "9m" are retained separately by the loader.
    match = re.fullmatch(
        r"(?i)(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[ -/]((?:19|20)\d{2}|\d{2})(?:\s+\w+)?",
        text,
    )
    if match:
        year_text = match.group(1)
        year = int(year_text)

        if len(year_text) == 2:
            return 2000 + year if year <= 50 else 1900 + year

        return year

    # Do not interpret numeric-like labels such as 2024.5 as dates.
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None

    # Fallback for other recognizable date strings.
    try:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.notna(parsed):
            return int(parsed.year)
    except (ValueError, TypeError, OverflowError):
        pass

    return None


def normalize_ticker(value) -> Optional[str]:
    """
    Normalize a company ticker/company_id.

    Performs:
    1. Basic formatting normalization
    2. Known source-specific ticker alias correction
    """
    if pd.isna(value):
        return None

    ticker = str(value).strip().upper()

    if not ticker:
        return None

    # Remove spaces, underscores, dots and hyphens.
    ticker = re.sub(r"[\s\_.-]+", "", ticker)

    # Known source-specific ticker aliases.
    aliases = {
        "AGTL": "ATGL",
    }

    ticker = aliases.get(ticker, ticker)

    return ticker
