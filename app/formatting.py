"""Display formatting — one place to change number styles (accounting brackets)."""
from __future__ import annotations

import pandas as pd

NA = "—"


def fmt(value, decimals: int = 0) -> str:
    """1250000 -> '1,250,000'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return NA


def fmt_acc(value) -> str:
    """Accounting style used in the report: negatives in brackets, zero as '-'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    v = float(value)
    if abs(v) < 0.5:
        return "-"
    s = f"{abs(v):,.0f}"
    return f"({s})" if v < 0 else s


def fmt_date(value) -> str:
    """dd-mmm-yyyy — never an ambiguous numeric format."""
    if value in (None, "") or (not isinstance(value, str) and pd.isna(value)):
        return NA
    try:
        return pd.Timestamp(value).strftime("%d-%b-%Y")
    except (TypeError, ValueError):
        return NA
