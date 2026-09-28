# Annual Report Generator

**Version V2026-09-28 0153**

A Streamlit tool that turns a **trial balance** into the audited **annual report** (Word + PDF) of a
Rwandan company, using the firm's Word template (cover, directors' report, auditor's report, P&L,
balance sheet, changes in equity, cash flow, notes).

It replaces the Excel/VBA tool `Template__Tool_Annualreport_Generator_COMPANY_Ltd__V11.xlsm` and uses
the same engine as the `annual-report-generator` AI skill.

---

## Run it locally — one click

*(The launchers `run.bat` / `run.sh` are in the LOCAL package; this GitHub package is what runs on Streamlit Cloud.)*

**Windows** — double-click `run.bat`

**macOS / Linux**

```bash
./run.sh
```

The script creates a virtual environment, installs the dependencies (first run only, 1–2 minutes)
and opens the app at <http://localhost:8501>. Close the window to stop the app.

If `run.sh` will not start: `chmod +x run.sh`.

**Manual alternative**

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m streamlit run app/Home.py
```

Requires **Python 3.10 or newer** (tick "Add python.exe to PATH" when installing on Windows).

**PDF output (optional):** install LibreOffice (<https://www.libreoffice.org>). Without it the app
produces the Word report only — open it in Word and *Save as PDF*.

### Vocabulary

**CY = Current Year** — the financial year being reported. **PY = Previous Year** — the comparative year
just before it (CY − 1). The sidebar always shows which pair is active.

### First thing to try

Press **🧪 LOAD DEMO — 2 YEARS** (or **5 YEARS**) on the Home page. It loads TEST COMPANY LTD (FY 2025) from the V11 Excel
generator, errors included (accumulated depreciation entered as debit, a balancing plug), so that every
check and correction screen can be seen.

To try the upload screen, use `data/demo/demo_trial_balance.xlsx` (2 years) or
`data/demo/demo_trial_balance_5years.xlsx` (5 years, un-labelled total line). No TB yet? Download the blank
template on **1 · Trial Balance → 📄 TB template**.

### Several years

A TB can hold any number of years. In the sidebar choose **Years shown**:
- **Two years (CY vs PY)** — pick the Current Year; checks, preview and report work on that pair;
- **All years side by side** — balance per year, controls for every pair, statements and notes with one column
  per year, multi-year Excel workbook. Word reports are produced for each pair (the template compares CY with PY).

---

## Workflow

| Page | What it does |
|---|---|
| **Home** | Progress checklist, key figures, demo data |
| **1 · Trial Balance** | Blank TB template (1–10 years, cascading Statement › Section › Group › Statement line › CIT code drop-downs). Upload the TB (xlsx / xls / xlsm / csv, any number of years): header row detection, column mapping per year (debit/credit or signed balance), balance check. Resume a saved project. Import a V11 Excel generator workbook. Download the **AI mapping prompt** (map a TB without CIT codes with any AI assistant). Find a CIT code by keyword / section / group and add or apply it; edit lines (searchable); **delete lines** (lines with 0 in every year in one click, any line on request, with undo); add / remove years. |
| **2 · Checks & Corrections** | One tab per check: balance per year, duplicated account descriptions (merge / rename), issues on individual lines, CIT-code mapping with suggestions to confirm (name + balance direction, confidence 🟢/🟡/🔴, alternative code, doubts written in the comments, pre-tick of high-confidence lines), download of the account ↔ code map and of the chart of codes, quick fixes (accumulated depreciation, lines with 0 in every year), every report control with **what to do** and a link to the page where it is corrected |
| **3 · Company & Report Data** | Save / load all these data (Excel or JSON). Company, auditor, directors, bankers, frameworks, signatures; year end; per-year grids for tax, equity and cash-flow data; inventory movement per year; fixed-asset register per year; report options (font size, colour, zero lines, custom template, notes) |
| **4 · Statements Preview** | Level of detail (Detailed / Summarised / Condensed). CY vs PY (or CY only for a first financial year): P&L, balance sheet, cash flow, equity, income tax, fixed assets and notes as printed. All years: the same statements with one column per year + multi-year workbook |
| **7 · Tax & CIT** | Taxable income step by step (how each amount is obtained, add-back rules, warnings on missing inputs) + Excel with live formulas; RRA CIT annex (balance sheet and P&L in the RRA layout, RRA totals, reconciliation with the annual report) + Excel with formulas; CIT codes ↔ RRA mapping; check of a new RRA annexure file (differences and proposed updates) |
| **8 · Long-term Assets Check** | Asset-register template (RRA Depreciation Table columns + category, cost, disposal) and upload; register with filters (keywords, category, status, date and cost ranges); rates & options (disposal year, note 11 source); book depreciation straight-line per asset (life schedule per asset); tax depreciation RRA reducing balance per category with the Rwf 500,001 rule; summaries per year and category; book vs tax; reconciliation with the TB; RRA Depreciation Table; Excel with live formulas |
| **9 · Stock Control** | Stock form per year (items by RRA category, opening, purchases, sales at cost, losses & damages with date / document / comment, closing count) and upload; movement by item and category; losses; reconciliation with the TB; note 12 from the form; Excel with formulas |
| **10 · Global Assessment** | Global review: status per area, key figures, missing elements, key events, all controls, details; Word / PDF report (summary or detailed) stamped with the date and time |
| **6 · Templates** | Preview (4 pages with demo data), see, download and choose the Word templates (managed by the administrator in `templates/`), prepare a sample filled with the demo data, choose the report font |
| **5 · Generate & Download** | One report (selected CY) or every year pair, downloads grouped in one tab per year: project file, skill input, model, controls, statements workbook, Word, PDF, multi-year workbook — individually or as a ZIP |

### What the checks do

- **Blocking** (the final report is refused; a DRAFT can be forced for internal review): TB does not
  balance, missing or unknown CIT code, the same account description on several lines (a CIT code may repeat, a description may not), balance sheet does not balance, cash flow does not reconcile to
  cash, accumulated depreciation with a debit balance, non-consecutive note numbers.
- **Warnings** (report allowed, review advised): CIT rate different from the statutory rate, balancing
  or suspense accounts, retained earnings roll-forward, depreciation mismatch, missing stock movement or
  fixed-asset register, missing company data.
- **Nothing is changed without you**: suggested CIT codes are applied only after you tick CONFIRM.

Full catalogue and formulas: `engine/build_model.py` and the skill's `references/computation-rules.md`.

---

## How persistence works — read this

**Nothing is stored on the server.** Everything lives in your browser session.

To keep your work, download the **project file** (`…_project.json`) on **5 · Generate & Download**,
and reload it on **1 · Trial Balance → Resume project**. The sidebar reminds you when there is unsaved work.

---

## Putting it online for testers

See **DEPLOYMENT.md** (GitHub + Streamlit Community Cloud, step by step) and give testers **TESTERS_GUIDE.md**.
Windows helpers: `github_first_push.bat` (once) and `github_update.bat` (each change, tests run first).

## Project structure

```
annual-report-app/
├── run.bat / run.sh            one-click launchers
├── github_first_push.bat       first upload to GitHub (once)
├── github_update.bat           tests + upload of changes (Streamlit Cloud redeploys)
├── DEPLOYMENT.md / TESTERS_GUIDE.md
├── requirements.txt            Python dependencies
├── packages.txt                system packages for Streamlit Cloud (LibreOffice, for PDF)
├── .streamlit/config.toml      theme and upload limit
├── app/
│   ├── Home.py                 entry point
│   ├── pages/1_… to 5_…        the five workflow pages
│   ├── state.py                session state (keys arg_*), rebuild pipeline, progress
│   ├── style.py                CSS and banners — colours in THEME only
│   ├── formatting.py           number / date formats
│   └── downloads.py            download buttons
├── engine/                     no Streamlit code — testable, shared with the AI skill
│   ├── tb_io.py                TB reading (any number of years), mapping, balance and line checks
│   ├── multiyear.py            project format, CY/PY pairs, multi-year tables
│   ├── code_suggest.py         CIT-code suggestions: account name (EN / FR) + balance direction, confidence
│   ├── ai_prompt.py            AI mapping prompt (.md) built from the chart of codes
│   ├── codes.py                CIT code format (RRA serial, 2-digit levels) and conversion of old V11 codes
│   ├── rra.py                  RRA CIT annexure: lines, RRA totals, update check of a new RRA file
│   ├── tax_cit.py              taxable income detail, RRA annex, mapping, Excel files with formulas
│   ├── fixed_assets.py         asset register, book (straight-line) and tax (RRA pools) depreciation, reconciliation, Excel
│   ├── stock.py                stock form, movement by item / category, reconciliation, note 12, Excel
│   ├── assessment.py           global assessment and its Word / PDF report
│   ├── build_model.py          statements, tax, PPE, equity, cash flow, notes, controls
│   ├── render_report.py        fills the Word template (bookmarks, tables, notes)
│   ├── export_pdf.py           PDF via LibreOffice (TOC refreshed when possible)
│   ├── xlsm_import.py          V11 Excel generator → project
│   ├── package.py              TB template, code maps, workbooks, file names, ZIP
│   └── guidance.py             "what to do" text for every control
├── templates/                  Word templates — one folder per template (admin only, see templates/README.md)
├── scripts/make_previews.py    (administrator) rebuild templates/<id>/preview.png
├── data/
│   ├── chart_of_accounts.json  CIT codes → statement lines, groups, notes, signs, RRA line of each code
│   ├── rra_annexure.json       lines and formulas of the RRA CIT annexure the codes are mapped to
│   ├── notes_default.json      explanatory notes 5–25
│   └── demo/                   demo projects (2 and 5 years) + demo TB files
└── tests/                      pytest: engine regression + page smoke tests
```

## Customising

- **Colours** — `app/style.py` (`THEME`) and `.streamlit/config.toml`.
- **Statement layout / new CIT codes** — `data/chart_of_accounts.json`.
- **Notes titles and standard texts** — `data/notes_default.json` (or per project on page 3).
- **Templates** — add a folder in `templates/` (see `templates/README.md`); users choose it on page 3 or 6. The `annual-report-template-builder` skill helps prepare new templates.
- **Font** — users choose it on page 3 (Report options) from a list of common fonts.

## Tests

```bash
pip install pytest
pytest -q
```

42 tests: figures identical to the V11 Excel tool, blocking controls, upload/mapping (2 and 5 years,
un-labelled total line, missing account names), signed balances, code suggestions (balance direction, confidence), zero-line deletion, AI prompt and
re-upload of an AI-mapped TB, multi-year alignment,
TB template round-trip, Word rendering without leftover placeholders, statements workbook, and headless
runs of every page including full 2-year and 5-year generations.
