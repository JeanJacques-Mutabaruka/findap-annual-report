# V1-0b

## Fixed
- **Crash on 2 · Checks & Corrections** (`AttributeError: 'float' object has no attribute 'strip'`) when a TB
  line had no account name. Causes and fixes:
  - the un-labelled TOTAL line of a TB (V11 TrialBalance sheet, most accounting exports) was imported as an
    account → it is now recognised (no name + amounts equal to the sum of all other lines) and ignored;
  - blank account names are now stored as empty text everywhere; the code suggester accepts empty / missing names;
  - the V11 importer skips lines without an account name.

## New
- **TB template** (1 · Trial Balance → 📄 TB template): Excel file with 1–10 years, Debit/Credit per year (most
  recent first), CIT-code drop-down, full list of codes, instructions, TOTAL line. Re-uploaded, it maps automatically.
- **CY / PY made explicit**: CY = Current Year (year reported), PY = Previous Year (comparative). Permanent
  reminder in the sidebar, banner with the actual years on every page, tooltips on columns and fields,
  year labels such as "2025 (CY)" / "2024 (PY)".
- **Multi-year trial balances** (any number of years, e.g. 5):
  - upload with one Debit/Credit (or balance) column pair per year — years read from the headers;
  - sidebar **Years shown**: *Two years (CY vs PY)* — choose the CY, everything works on that pair — or
    *All years side by side* — balance check, controls per pair, P&L, balance sheet, cash flow, income tax and
    notes with one column per year, multi-year Excel workbook;
  - per-year data (CIT rate, prepayments, WHT, grants, tax losses, drawings, adjustments, cash-flow items,
    inventory movement, fixed-asset register) entered in one grid, one line per year;
  - generation of one report (CY/PY) or of every year pair at once;
  - add / remove a year in ✏️ Edit TB.
- **Code maps download** (2 · Checks & Corrections): the account ↔ CIT-code map of the TB (with statement line
  and note) and the full chart of CIT codes, both in Excel.
- **5-year demo** (Home) and `data/demo/demo_trial_balance_5years.xlsx` to test the multi-year upload.

## Changed
- Project file is now `…_project.json` (multi-year). V1-0a `…_input.json` files still load.
- Each report also exports its 2-year `…_input.json`, ready for the annual-report-generator AI skill.
- File names carry the financial year: `<Company>_Annual_Report_FS_FY2025__V<date> <time>`.
