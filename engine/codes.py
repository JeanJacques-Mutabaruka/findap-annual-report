"""CIT code format and conversion of the old (V11) codes.

Format (from delivery V2026-09-27 2211): prefix BS / PL + the RRA "Serial No" with EVERY level on 2 digits,
e.g. RRA balance sheet 1.10 -> "BS 01.10", RRA P&L 4.1 -> "PL 04.01", 3.1.3.1 -> "BS 03.01.03.01".
Codes the RRA annexure does not have are SUB-CODES of the RRA line they roll up into
(one more level, e.g. "PL 05.08.02" Fines and penalties -> RRA 5.8 Other administration expenses).

Old V11 codes (first level on ONE digit, e.g. "BS 1.09") are recognised and converted with OLD_TO_NEW:
several of them were renumbered (the V11 chart had no RRA 1.7 "IT equipments technologies" line, etc.),
so an old "BS 1.09" (accumulated depreciation) becomes "BS 01.10", never "BS 01.09" (other assets).
"""
from __future__ import annotations

import re

NEW_RE = re.compile(r"^(BS|PL) \d{2}(\.\d{2})*$")
OLD_RE = re.compile(r"^(BS|PL) \d(\.\d{1,2})*$")

OLD_TO_NEW: dict[str, str] = {
    # ---- balance sheet: fixed assets (RRA 1.7 IT equipment inserted -> 1.07..1.10 shift by one)
    "BS 1.01": "BS 01.01", "BS 1.02": "BS 01.02", "BS 1.03": "BS 01.03", "BS 1.04": "BS 01.04",
    "BS 1.05": "BS 01.05", "BS 1.06": "BS 01.06", "BS 1.07": "BS 01.08", "BS 1.08": "BS 01.09",
    "BS 1.09": "BS 01.10", "BS 1.10": "BS 01.11",
    "BS 2.01": "BS 02.01", "BS 2.02": "BS 02.02", "BS 2.03": "BS 02.03", "BS 2.04": "BS 02.04", "BS 2.05": "BS 02.05",
    "BS 3.1.1.1": "BS 03.01.01.01", "BS 3.1.1.2": "BS 03.01.01.02", "BS 3.1.1.3": "BS 03.01.01.03",
    "BS 3.1.1.4": "BS 03.01.01.04", "BS 3.1.2.1": "BS 03.01.02.01", "BS 3.1.2.2": "BS 03.01.02.02",
    "BS 3.1.2.3": "BS 03.01.02.03", "BS 3.1.3.1": "BS 03.01.03.01", "BS 3.1.3.2": "BS 03.01.03.02",
    "BS 3.1.4": "BS 03.01.04",
    "BS 3.2.1": "BS 03.02.01", "BS 3.2.2": "BS 03.02.02", "BS 3.2.3": "BS 03.02.03", "BS 3.2.4": "BS 03.02.04",
    "BS 3.2.5": "BS 03.02.05", "BS 3.2.6": "BS 03.02.06",
    "BS 3.3.1": "BS 03.01.04.01", "BS 3.3.2": "BS 03.01.04.02", "BS 3.3.3": "BS 03.01.04.03",  # -> other current assets
    "BS 5.01": "BS 05.01", "BS 5.02": "BS 05.02", "BS 5.03": "BS 05.03", "BS 5.04": "BS 05.04", "BS 5.05": "BS 05.05",
    "BS 5.06": "BS 05.06", "BS 5.07": "BS 05.07", "BS 5.08": "BS 05.08", "BS 5.09": "BS 05.06.01",  # grants -> 5.6
    "BS 6.1.1": "BS 06.01.01", "BS 6.1.2": "BS 06.01.02", "BS 6.1.3": "BS 06.01.03", "BS 6.1.4": "BS 06.01.04",
    "BS 6.1.5": "BS 06.01.05", "BS 6.2.1": "BS 06.02.01", "BS 6.2.2": "BS 06.02.02", "BS 6.2.3": "BS 06.02.03",
    "BS 6.2.4": "BS 06.02.04", "BS 6.2.5": "BS 06.02.05",
    "BS 7.01": "BS 07.01", "BS 7.02": "BS 07.02",
    "BS 8.1.1": "BS 08.01.01", "BS 8.1.2": "BS 08.01.02", "BS 8.1.3": "BS 08.01.03", "BS 8.1.4": "BS 08.01.04",
    "BS 8.1.5": "BS 08.01.05", "BS 8.1.6": "BS 08.01.06", "BS 8.2.1": "BS 08.02.01", "BS 8.2.2": "BS 08.02.02",
    "BS 8.2.3": "BS 08.02.03",
    # ---- P&L
    "PL 1.1": "PL 01.01", "PL 1.2": "PL 01.02", "PL 1.3": "PL 01.03",
    "PL 2.1.1": "PL 02.01.01", "PL 2.1.2": "PL 02.01.02", "PL 2.1.3": "PL 02.01.03",
    "PL 2.2.1": "PL 02.02.01", "PL 2.2.2": "PL 02.02.01.01",  # import -> 2.2.1
    "PL 2.3.1": "PL 02.03.01", "PL 2.3.2": "PL 02.03.02",
    **{f"PL 2.4.{i}": f"PL 02.04.{i:02d}" for i in range(1, 8)},
    "PL 2.5.1": "PL 02.05.01", "PL 2.5.2": "PL 02.05.02", "PL 2.5.3": "PL 02.05.03",
    **{f"PL 4.{i:02d}": f"PL 04.{i:02d}" for i in range(1, 28)},
    "PL 4.28": "PL 04.27.01",                                             # subcontractors -> other operating expenses
    **{f"PL 5.{i:02d}": f"PL 05.{i:02d}" for i in range(1, 9)},
    "PL 5.09": "PL 05.08.01", "PL 5.10": "PL 05.08.02", "PL 5.11": "PL 05.08.03", "PL 5.12": "PL 05.08.04",
    "PL 5.13": "PL 05.08.05",                                             # -> other administration expenses
    "PL 6.01": "PL 06.01", "PL 6.02": "PL 06.02", "PL 6.03": "PL 06.03",
    "PL 6.04": "PL 06.01.01", "PL 6.05": "PL 06.01.02",                   # leave pay, non-permanent wages -> 6.1
    "PL 6.06": "PL 06.04", "PL 6.07": "PL 06.05", "PL 6.08": "PL 06.06", "PL 6.09": "PL 06.07", "PL 6.10": "PL 06.08",
    **{f"PL 7.{i:02d}": f"PL 07.{i:02d}" for i in range(1, 8)},
    "PL 7.08": "PL 07.01.01",                                             # interest to related parties -> 7.1
    **{f"PL 8.{i:02d}": f"PL 08.{i:02d}" for i in range(1, 11)},
    "PL 8.11": "PL 08.13.01",                                             # commissions received -> 8.13 other income
    "PL 8.12": "PL 08.11", "PL 8.13": "PL 08.12", "PL 8.14": "PL 08.13",
}
def _old_serial(code: str) -> str:
    return ".".join(str(int(x)) for x in code.split(" ")[1].split("."))


RENUMBERED = {o: n for o, n in OLD_TO_NEW.items()
              if ".".join(str(int(x)) for x in n.split(" ")[1].split(".")) != _old_serial(o)}


# Codes of the delivery V2026-09-27 2211 that were replaced once their RRA line was decided (28-09-2026).
RETIRED: dict[str, str] = {"BS 05.09": "BS 05.06.01", "PL 02.02.02": "PL 02.02.01.01", "PL 08.14": "PL 08.13.01"}


def is_old(code: str) -> bool:
    return bool(OLD_RE.match(code or ""))


def to_new(code: str) -> str:
    """Old V11 code -> new code; any other code unchanged."""
    return OLD_TO_NEW.get(code, code) if is_old(code) else RETIRED.get(code, code)


def from_serial(prefix: str, serial: str) -> str:
    """RRA serial ('1.10', '4.1', '3.1.3.1') -> app code ('BS 01.10', 'PL 04.01', 'BS 03.01.03.01')."""
    return f"{prefix} " + ".".join(f"{int(x):02d}" for x in str(serial).split("."))


def to_serial(code: str) -> str:
    """App code -> RRA-style serial ('BS 01.10' -> '1.10')."""
    return ".".join(str(int(x)) for x in code.split(" ")[1].split("."))


def parent(code: str) -> str | None:
    """'PL 05.08.02' -> 'PL 05.08'; top level -> None."""
    p, n = code.split(" ")
    parts = n.split(".")
    return f"{p} {'.'.join(parts[:-1])}" if len(parts) > 1 else None


def convert_codes(codes) -> tuple[list[str], list[tuple[str, str]]]:
    """Convert a sequence of codes. Returns (new codes, [(old, new) for every code that changed])."""
    out, changed = [], []
    for c in codes:
        n = to_new(c)
        out.append(n)
        if n != c:
            changed.append((c, n))
    return out, changed


def conversion_note(changed: list[tuple[str, str]]) -> str | None:
    if not changed:
        return None
    moved = sorted({(o, n) for o, n in changed if o in RENUMBERED or o in RETIRED})
    txt = (f"{len(changed)} CIT code(s) in the old V11 numbering were converted to the RRA-based format "
           f"(e.g. {changed[0][0]} → {changed[0][1]}).")
    if moved:
        txt += " Renumbered lines — check them: " + ", ".join(f"{o} → {n}" for o, n in moved[:10]) + \
               ("…" if len(moved) > 10 else "") + "."
    return txt
