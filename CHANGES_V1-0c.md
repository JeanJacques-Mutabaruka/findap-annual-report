# V1-0c

## Generate & Download
- Files are grouped **one tab per financial year** (📅 FY 2025, FY 2024, …; ⚠️ marks a DRAFT), plus a
  **📁 Common files** tab (project file, multi-year workbook). Each year tab has its own ZIP; the global ZIP stays.

## TB template (1 · Trial Balance → 📄 TB template)
- New columns **Statement · Section · Group · Statement line** before CIT code and Account name.
- **Cascading drop-downs**: a Statement limits the Sections, a Section the Groups, a Group the Statement lines;
  the **CIT-code list follows the most precise choice** (all codes when nothing is chosen). Standard Excel
  formulas (INDIRECT) on a hidden sheet "Lists" — works in every Excel version.
- **Check column**: shows the statement line of the CIT code entered and warns when it contradicts the line chosen.
- On upload, a blank CIT code is **derived from Group + Statement line**.
- Sheet "CIT codes" with filters on every column for keyword search.

## Edit TB (1 · Trial Balance → ✏️ Edit TB)
- **🔎 Find a CIT code**: keyword search (accent-insensitive, several words) across code, section, group and
  statement line, with Statement › Section › Group filters. Then **➕ add a new TB line** with the code found
  (amounts per year) or **🎯 apply it to an existing line** (lines without a valid code listed first).
- Editor: CIT-code cell shows "code — statement line" (type part of the line to search); read-only
  Statement line, Group and Section columns; **filter box** to show only matching lines.

## Fixed
- A stray "None" printed under the CY/PY banner on pages 2 and 5.
