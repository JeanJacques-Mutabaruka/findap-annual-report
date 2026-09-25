# Annual Report Generator — Testers' guide

**Version under test: V1-0i** (shown at the bottom of the left menu) · about **60 minutes** for the 14 scenarios.

Thank you for testing. The tool turns a company's **trial balance** into its audited **annual report**
(Word and PDF): it checks the figures, asks for what is missing, then generates the files.

## Before you start

- **Link and sign-in**: open the link you received and sign in with the **same e-mail address** the
  invitation was sent to (Google sign-in, or a one-time link sent by e-mail).
- **Data**: use **only the demo data** or a trial balance where names and amounts are **anonymised**.
  Never upload a real client file during the test.
- **Your work is not stored online**: to keep it, download the *project file* (page 5) before closing the tab.
- **Vocabulary**: **CY = Current Year** (the year reported) · **PY = Previous Year** (its comparative year).
- **Reporting**: use the **💬 Send feedback** button in the left menu — one report per problem, with the
  page, what you did, what happened, what you expected, and a screenshot if possible.
- The app may take about a minute to "wake up" if nobody used it recently.

## Scenarios

Tick each scenario and note the time it took. "Expected" is what should happen — anything else is worth reporting.

### 1. First look — 3 min
Home → **LOAD DEMO — 2 YEARS**.
**Expected:** progress checklist with ✅/⚠️/❌, key figures (revenue 535.8 m, net profit 89.9 m), sidebar showing
*TEST COMPANY LTD*, *CY 2025 · PY 2024*, *TB balances*.

### 2. The checks and their explanations — 5 min
Page **Checks and Corrections**. Open each tab.
**Expected:** verdict on top in red; tab **👯 Duplicates** shows 4 lines called *ACCUMULATED DEPRECIATION*;
tab **🛠️ Quick fixes** proposes to move accumulated depreciation to the credit side; tab **📋 Report controls**
explains each problem with "👉 what to do" and a link. *Is each message understandable without help?*

### 3. Fix duplicated descriptions — 4 min
Tab **👯 Duplicates** → rename the 4 lines using the "Line above" hint (e.g. *ACCUMULATED DEPRECIATION – COMPUTERS*)
→ **SAVE DESCRIPTIONS**.
**Expected:** the tab turns ✅; the trial balance still balances.

### 4. Download and fill the TB template — 7 min
Page **Trial Balance** → tab **📄 TB template** → 3 years → download. In Excel: on an empty line choose
*Balance sheet* › *Current Assets* › *Cash and Cash equivalents* › *Bank balances*.
**Expected:** each list shows only the choices of the previous one; the CIT-code list then offers only
*BS 3.1.3.2*; typing the same account description twice turns the cell red. *Tell us if a list misbehaves
(and your Excel version).*

### 5. Upload a trial balance — 5 min
Tab **📤 Upload TB** → upload the template you filled (or the demo file you received).
**Expected:** header row and year columns recognised automatically; balance table per year; blank or TOTAL
lines ignored with a message.

### 6. Find a CIT code without knowing it — 4 min
Tab **🔎 Find a code** → type *rent*, then *bank charges*, then filter by Section.
Add a new line with the code found; then apply a code to an existing line.
**Expected:** results narrow as you type; the new line appears in **✏️ Edit lines** with its statement line.

### 7. Company and report data — 5 min
Page **Company and Report Data** → fill the missing *Accounting framework*, save. Tab **📅 Period & tax**: the demo
carries the old Excel rates (29.40% for 2025, 30% for 2024) → set both to **28**, **SAVE TAX DATA**.
**Expected:** the warning "Still missing" disappears; in Checks and Corrections the `CIT_RATE` warning is gone
and the tax / net profit change accordingly.

### 8. Five years — 5 min
Home → **LOAD DEMO — 5 YEARS**. In the sidebar switch **Years shown** between *Two years* and *All years side by side*.
**Expected:** Statements Preview shows 2021–2025 side by side (cash flow from 2022); in *Two years* mode, choosing
another CY changes every page.

### 9. Generate the report — 5 min
Page **Generate and Download** → *Every year pair* → tick *Generate DRAFT(s) anyway* and *PDF* → **GENERATE**.
**Expected:** one tab per year (FY 2025, FY 2024, …) + *Common files*; open a Word file: cover, statements and notes
filled, no `{…}` left; Word asks to update fields — answer **Yes**.

### 10. Save and resume — 2 min
Page 5 → **Download project file**. Close the tab, reopen the app, page **Trial Balance** → tab
**📂 Resume** → upload the project file.
**Expected:** everything is back (TB, codes, company data, years).

### 11. Templates and font — 3 min
Page **Templates** → download the template, then **Prepare a sample with the demo data** (try another font).
Page **Company and Report Data** → Report options → choose a font → generate again.
**Expected:** the sample and the report use the chosen font everywhere (titles, text, tables).

### 12. Save and reload the company data — 3 min
Page **Company and Report Data** → tab **💾 Save / load** → download the Excel file, open it, change the auditor name,
save, load it back.
**Expected:** the new auditor name appears on page 3; the trial balance is unchanged.

### 13. A file with two trial balances — 2 min
Upload a file holding two TB sheets (you received one).
**Expected:** the app lists both sheets with their years and balance status and lets you choose one.

### 14. Level of detail and first financial year — 4 min
Statements Preview → switch **Detailed / Summarised / Condensed**, then generate a report.
Report options → Comparative year → **Current Year only**, generate again.
**Expected:** the balance sheet and P&L follow the level chosen (preview and Word); in CY-only mode every table
has a single year column.

## Final questions (in the feedback form)

1. What was the hardest step to understand?
2. What would you use first in your daily work?
3. What is missing to generate a real client report?
4. Overall score from 1 to 5, and why.

## Known limitations of this version

- The Word report always compares two years (CY vs PY); with 5 years you get one report per pair.
- The cash flow of the earliest year is not computed (it needs the year before).
- On the online version the PDF table of contents may show the template's page numbers — the Word file
  is correct after "Update fields".
- The demo contains deliberate errors so that every check can be seen.
