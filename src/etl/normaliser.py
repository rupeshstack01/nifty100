"""
Data normalization utilities for the Nifty 100 ETL pipeline.
"""

import re
from typing import Optional

import pandas as pd


def normalize_year(value) -> Optional[int]:
    """
    Convert different year/date representations into a four-digit year.

    Examples:
        'Dec 2012' -> 2012
        'Mar 2014' -> 2014
        'Mar-13'   -> 2013
        '2024'     -> 2024
        2024       -> 2024

    Returns:
        Four-digit year as int, or None if the value cannot be parsed.
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    # Direct four-digit year
    match = re.search(r"(19|20)\d{2}", text)

    if match:
        return int(match.group(0))

    # Two-digit year formats such as:
    # Mar-13
    # Mar/13
    match = re.search(r"[-/](\d{2})\b", text)

    if match:
        year = int(match.group(1))

        if year <= 50:
            return 2000 + year

        return 1900 + year

    # Try pandas date parsing
    try:
        parsed = pd.to_datetime(text, errors="coerce")

        if pd.notna(parsed):
            return int(parsed.year)

    except (ValueError, TypeError):
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

    # Remove spaces, underscores, dots and hyphens
    ticker = re.sub(r"[\s_.-]+", "", ticker)

    # Known source-specific aliases
    aliases = {
        "AGTL": "ATGL",
    }

    ticker = aliases.get(ticker, ticker)

    return ticker
