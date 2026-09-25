# V1-0i

## Report for the Current Year only (first financial year)
- New option **3 · Company & Report Data → Report options → Comparative year (PY)**:
  *Automatic* (default: Current Year only when the TB has no Previous Year figures) · *Always show PY* ·
  *Current Year only — first financial year*.
- In Current-Year-only mode: statements, notes and tax computation have a single CY column; the equity
  statement has one block ("Capital and reserves introduced in the year"); controls that compare with the
  previous year are skipped; the cash flow starts from zero (new company).

## Level of detail — balance sheet and P&L (Statements Preview and Word report)
Built on the Excel generator's row grouping (outline levels):
| Level | Shows | Example (current assets) |
|---|---|---|
| **Detailed** — every statement line | all lines, group sub-totals, totals (as before) | Work in progress, Trading goods, Trade receivables, Prepayments, Bank balances… |
| **Summarised** — headings and sub-totals | groups with their totals, main totals | Inventories · Accounts receivables · Loans & advances · Cash |
| **Condensed** — main headings only | one line per main heading, key sub-totals | Current assets (notes 12–14, 16) |
Chosen on Statements Preview (radio at the top) or in Report options; saved with the project and used for the
Word report. Note references are kept (condensed lines show the range of notes, e.g. "12–14, 16").
The statements workbook (Excel) stays detailed.

## Company & Report Data inside the TB file
- If an uploaded TB workbook also contains the Company & Report Data sheets (Company, Report options, Per-year data…),
  the app detects them, and after the TB is loaded proposes them on page 3 (**Apply these data** / **Ignore**) —
  nothing is replaced until you apply.
- TB template tab: option "Also include the Company & Report Data sheets" (pre-filled with the project's data).
