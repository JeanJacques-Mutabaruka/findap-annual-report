"""Annual Report Generator — entry point."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Annual Report Generator", page_icon="📊", layout="wide")

from app import state  # noqa: E402
from app.formatting import fmt_acc  # noqa: E402
from app.style import info_banner, inject_css, section, status_list, warn_banner  # noqa: E402
from engine import VERSION  # noqa: E402

inject_css()
state.init_state()
st.title("📊 Annual Report Generator")
state.sidebar()

if st.session_state.get("arg_demo"):
    info_banner("<b>DEMO MODE</b> — TEST COMPANY LTD, the test data of the Excel generator V11. "
                "It deliberately contains errors (accumulated depreciation as debit, a balancing plug) "
                "so that every check and correction screen can be seen.")

st.markdown(
    "Turns a **trial balance** into the audited **annual report** (Word + PDF) of a Rwandan company, "
    "using the firm's Word template. The app checks that the TB balances, maps every account to its "
    "CIT code, computes the statements and notes, **lists what must be corrected or completed**, "
    "and only then generates the files.\n\n"
    "A TB can hold **several years** (e.g. 5): choose in the sidebar to see **all years side by side** or to "
    "work **two by two** — **CY** (Current Year, the year reported) vs **PY** (Previous Year, its comparative)."
)

# ------------------------------------------------------------------ progress --
section("Progress")
status_list(state.steps())

if state.has_tb() and state.view_all():
    import pandas as pd
    models = state.all_models()
    if models:
        rows = []
        for y, mdl in sorted(models.items()):
            k = mdl["key_figures"]
            rows.append({"Year": str(y), **{lab: k[key]["cy"] for lab, key in
                         [("Revenue", "revenue"), ("Gross profit", "gross_profit"), ("Profit before tax", "pbt"),
                          ("Net profit", "net_profit"), ("Total assets", "total_assets"), ("Equity", "total_equity")]}})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="localized") for c in
                                    ("Revenue", "Gross profit", "Profit before tax", "Net profit", "Total assets", "Equity")})
else:
    model = state.rebuild() if state.has_tb() else None
    if model:
        k = model["key_figures"]
        y, p = model["meta"]["year_cy"], model["meta"]["year_py"]
        st.caption(f"Key figures — CY (Current Year) {y}, compared with PY (Previous Year) {p}, in millions of Rwf")
        c = st.columns(5)
        for col, (lab, key) in zip(c, [("Revenue", "revenue"), ("Gross profit", "gross_profit"),
                                       ("Profit before tax", "pbt"), ("Net profit", "net_profit"),
                                       ("Total assets", "total_assets")]):
            col.metric(f"{lab} (m)", f"{k[key]['cy'] / 1e6:,.1f}",
                       delta=f"{(k[key]['cy'] - k[key]['py']) / 1e6:,.1f} vs PY {p}",
                       help=f"CY {y}: {fmt_acc(k[key]['cy'])} · PY {p}: {fmt_acc(k[key]['py'])}")

# ---------------------------------------------------------------- demo data --
section("Demo data")
a, b = st.columns([1, 3])
with a:
    if st.button("🧪 LOAD DEMO — 2 YEARS", type="primary", width="stretch"):
        state.load_demo()
        st.rerun()
    if st.button("🧪 LOAD DEMO — 5 YEARS", type="primary", width="stretch"):
        state.load_demo(five_years=True)
        st.rerun()
with b:
    st.caption("2 years: TEST COMPANY LTD (FY 2025 / 2024) from the V11 Excel generator — 42 TB lines with CIT codes "
               "and general data, errors included, to see every check and correction screen.")
    st.caption("5 years: the same company for 2021–2025 (2021–2023 are synthetic, scaled from 2024) — to try the "
               "multi-year views (sidebar: 'All years side by side' or two by two).")
if st.session_state.get("arg_demo") and st.button("Clear demo data"):
    for k_ in [k_ for k_ in st.session_state if k_.startswith("arg_")]:
        del st.session_state[k_]
    st.rerun()

# -------------------------------------------------------------------- pages --
section("Workflow")
left, right = st.columns(2)
with left:
    st.markdown(
        "**1 · Trial Balance** — download a blank TB template, upload the TB (Excel / CSV, any number of "
        "years) and map its columns, resume a saved project, or import an Excel generator V11 workbook. "
        "Edit lines directly.\n\n"
        "**2 · Checks & Corrections** — balance check per year, line issues, CIT-code mapping with "
        "suggestions to confirm, and every report control with what to do.\n\n"
        "**3 · Company & Report Data** — company, auditor, directors, period, tax, stock, fixed assets, "
        "equity movements and report options."
    )
with right:
    st.markdown(
        "**4 · Statements Preview** — P&L, balance sheet, cash flow, equity, income tax, fixed assets "
        "and notes exactly as they will be printed.\n\n"
        "**5 · Generate & Download** — project file, statements workbook, controls report, Word report "
        "(and PDF when LibreOffice is installed), individually or as one ZIP."
    )
warn_banner("<b>Nothing is stored on the server.</b> Download the project file (input.json) on "
            "5 · Generate & Download to keep your work, and reload it on 1 · Trial Balance.")
st.divider()
st.caption(f"Tool version {VERSION} · Figures are computed by the engine only — the same engine as the "
           "annual-report-generator AI skill.")
