# V1-0a — first version (local test)

## Scope
1. Trial balance input: Excel / CSV upload with header-row detection and column mapping (debit/credit or
   signed balance), V11 Excel generator import, project file resume, line editor.
2. Balance check per year (debit, credit, difference) — on page 1, page 2, the sidebar and the Home checklist.
3. File set: project file, computed model, controls report, statements workbook, Word report, PDF (if
   LibreOffice), ZIP. Naming: `<Company>_Annual_Report_FS__V<yyyy-mm-dd> <hhmm>` (+ `_DRAFT`).
4. Messages before generation: TB line issues, CIT-code mapping with suggestions to confirm, report
   controls (blocking / warning / info) with "what to do" and links; generation refused while blocking
   issues remain (DRAFT possible on explicit request).

## Engine (shared with the annual-report-generator skill)
- Figures identical to the V11 Excel tool on its demo data.
- Deliberate differences from V11 are listed in the skill's references/computation-rules.md §10.

## Known limits / next versions
- Colours provisional (THEME in app/style.py).
- Checklist-and-dialogue assistant (missing data, key points of the report) — planned.
- French template and notes — planned.
- Cash-flow statement shows the current year only (V11 layout).
