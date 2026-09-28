"""Plain-language guidance for every control id: what it means and how to correct it.

PAGE keys point to the app page where the correction is made.
"""
from __future__ import annotations

TB = "pages/1_Trial_Balance.py"
CHECKS = "pages/2_Checks_and_Corrections.py"
DATA = "pages/3_Company_and_Report_Data.py"

GUIDE: dict[str, tuple[str, str]] = {
    "TB_NOT_BALANCED": ("Total debits must equal total credits for each year. Look for a missing line, an amount "
                        "typed in the wrong column, or a line excluded by the import (totals, subtotals). Correct the "
                        "lines in 1 · Trial Balance → Edit TB, or re-export the TB from the accounting system.", TB),
    "TB_UNMAPPED": ("Every TB line needs a CIT code from the chart. Assign it in the ACCOUNT MAPPING section of this "
                    "page (suggestions are pre-filled — confirm each one).", CHECKS),
    "BS_NOT_BALANCED": ("Assets differ from equity + liabilities. Usually caused by unmapped lines, a TB that does not "
                        "balance, or tax/profit accounts (PL CIT, BS 05.08, BS 08.02.01) already booked in the TB. Fix the "
                        "TB first; this check clears by itself.", CHECKS),
    "CF_CASH": ("The cash-flow statement does not end on the balance-sheet cash. Check that all cash and bank accounts "
                "use BS 03.01.03.01 / BS 03.01.03.02 and that the previous-year column is complete.", TB),
    "ACCDEP_DEBIT": ("Accumulated depreciation (BS 01.10) must be a CREDIT balance; as a debit it is added to fixed "
                     "assets. Move the amounts to the credit column (quick fix below or Edit TB). If the TB then no "
                     "longer balances, the original TB was balanced by a compensating error to be found.", CHECKS),
    "DUPLICATE_ACCOUNT": ("Several TB lines carry the same account description. A CIT code may be repeated, but "
                          "each line must have its own description (the notes list accounts by name). Merge the lines "
                          "or rename them in the 👯 Duplicates tab of this page.", CHECKS),
    "NOTE_SEQUENCE": ("Note numbers must follow each other (Word numbers the notes automatically).", DATA),
    "TB_COMPUTED_CODE": ("PL CIT, BS 05.08 and BS 08.02.01 are computed by the generator (tax charge, profit of the year, "
                         "tax provision). Remove these lines from the TB or re-code them.", TB),
    "TB_PLUG_COMMENT": ("A balancing (plug) figure has no accounting meaning — analyse it and replace it by the real "
                        "accounts before issuing the report.", TB),
    "TB_SUSPENSE": ("Suspense / to-be-allocated accounts should be cleared before issuing the report.", TB),
    "PY_EQUALS_CY": ("Previous-year balances are identical to the current year: the comparative column may be a copy. "
                     "Load the audited previous-year balances.", TB),
    "DEP_MISMATCH": ("Depreciation in the P&L differs from the movement of accumulated depreciation. Explain it "
                     "(disposals, reclassification) or correct the TB; entering the fixed-asset register helps.", DATA),
    "RE_ROLLFORWARD": ("Opening retained earnings should equal last year's retained earnings + last year's profit ± "
                       "dividends/adjustments. Check BS 05.07 and enter dividends or prior-year adjustments.", DATA),
    "EQ_STATEMENT": ("The equity statement does not end on balance-sheet equity. Enter drawings/dividends and "
                     "adjustments, or check the equity codes (BS 5.xx).", DATA),
    "CIT_RATE": ("The CIT rate differs from the statutory rate (30% up to 2023, 28% from 2024). Confirm or correct it "
                 "in Period & tax.", DATA),
    "PPE_ALLOCATED": ("Without a fixed-asset register, depreciation by category is estimated pro rata. Enter the "
                      "register (cost, additions, disposals, depreciation by category) for an exact note 11.", DATA),
    "PPE_CHARGE": ("The depreciation charge of the fixed-asset register differs from the P&L depreciation.", DATA),
    "INV_MISSING": ("Inventories exist but the stock movement (opening, purchases, cost of sales) is missing — "
                    "enter it for the inventory note.", DATA),
    "INV_CLOSING": ("The closing stock of the movement table differs from balance-sheet inventories.", DATA),
    "NOTE_ORPHAN": ("Some accounts point to a note that is not in the notes list.", DATA),
    "MISSING_DATA": ("Information printed in the report is missing or still a placeholder. Complete it in "
                     "3 · Company & Report Data.", DATA),
    "NOTE_EMPTY": ("This note has no balance and will print 'Nil for the years presented.'", DATA),
    "CF_TAXPAID": ("Enter the income tax actually paid during the year if it should appear in the cash flow.", DATA),
}


def advice(cid: str) -> tuple[str, str | None]:
    return GUIDE.get(cid, ("", None))
