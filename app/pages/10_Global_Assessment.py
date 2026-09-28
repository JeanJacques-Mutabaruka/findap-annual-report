"""10 · Global Assessment — global assessment of the calculations made for the annual report: status per area, key
figures, missing elements, key events, all controls; Word / PDF report (summary or detailed) stamped with the date
and time."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.formatting import fmt_acc  # noqa: E402
from app.style import explain_box, info_banner, ok_banner, red_alert, section, warn_banner  # noqa: E402
from engine import VERSION, assessment, package  # noqa: E402

state.init_state()
state.page_setup("🧭 Global Assessment")
if not state.require_tb():
    st.stop()

proj = state.project()
models = state.all_models()
a = assessment.build(proj, state.tb(), state.chart(), models, state.valid_codes(),
                     st.session_state.get("arg_import_notes"), bool(st.session_state.get("arg_outputs")), VERSION)
slug = package.company_slug(proj["meta"].get("company_name") or "Company")
stamp = a["now"].strftime("%Y-%m-%d_%H%M")

explain_box("What this page shows", """
A global review of the production of the annual report, for the <b>audit file</b> and for the <b>client</b>: the status of
every area (trial balance, CIT codes, checks, company data, statements and controls, taxable income, RRA annex, fixed
assets, stock, files), the key figures of each report year, the elements that are <b>missing</b> for a complete
calculation, the key events to highlight (tax losses used, add-backs, deductions, disposals, stock losses, differences
between book and tax depreciation…) and every control of the statements.<br>
The <b>report</b> (Word, and PDF when LibreOffice is available) is stamped with the date and time of its generation:
<i>summary</i> = status, figures, missing elements, events, blocking controls and warnings; <i>detailed</i> = everything,
with the reconciliation tables and the TB line issues.""", [f"Missing: {m}" for m in a["missing"]])

n = {s: sum(1 for x in a["areas"] if x["Status"] == s) for s in ("ok", "warn", "fail", "todo")}
k1, k2, k3, k4 = st.columns(4)
k1.metric("✅ OK", n["ok"])
k2.metric("⚠️ To check", n["warn"])
k3.metric("❌ Blocking", n["fail"])
k4.metric("⏳ Missing", n["todo"])
if n["fail"]:
    red_alert(f"{n['fail']} area(s) blocking — see below.")
elif n["warn"] or n["todo"]:
    warn_banner("No blocking area — some points to check or complete.")
else:
    ok_banner("Every area is complete and consistent.")

tabs = st.tabs(["📋 Status & figures", "⚠️ Missing & key events", "🔍 Controls & details", "📄 Report"])

with tabs[0]:
    section("Status by area")
    ar = pd.DataFrame(a["areas"])
    ar.insert(0, " ", ar["Status"].map(assessment.ICON))
    ar["Status"] = ar["Status"].map(assessment.WORD)
    st.dataframe(ar, hide_index=True, width="stretch")
    section("Key figures")
    if a["figures"].empty:
        info_banner("Statements not computed yet.")
    else:
        f = a["figures"].copy()
        f["Year"] = f["Year"].astype(str)
        money = [c for c in f.columns if c != "Year"]
        for c in money:
            f[c] = f[c].map(fmt_acc)
        st.dataframe(f.style.map(lambda x: "color:#C00000" if isinstance(x, str) and x.startswith("(") else "", subset=money),
                     hide_index=True, width="stretch")

with tabs[1]:
    section("Missing elements")
    if a["missing"]:
        for m in a["missing"]:
            st.markdown(f"<div style='color:#C00000;font-weight:600'>⚠️ {m}</div>", unsafe_allow_html=True)
    else:
        ok_banner("Nothing missing.")
    section("Key events to highlight")
    for e in a["events"] or ["None."]:
        st.markdown(f"• {e}")

with tabs[2]:
    section(f"All controls ({len(a['controls'])})")
    lv = st.multiselect("Levels", ["BLOCKING", "WARNING", "INFO"], default=["BLOCKING", "WARNING"], key="arg_as_lv")
    st.dataframe(a["controls"][a["controls"]["Level"].isin(lv)], hide_index=True, width="stretch", height=380)
    if a["details"]:
        section("Details")
        pick = st.selectbox("Table", list(a["details"]), key="arg_as_detail")
        st.dataframe(a["details"][pick], hide_index=True, width="stretch", height=420)

with tabs[3]:
    section("Assessment report")
    st.caption(f"Stamped {a['now']:%d-%m-%Y %H:%M} — the stamp is the moment this page was computed.")
    c1, c2 = st.columns(2)
    for col, detailed, lab in ((c1, False, "summary"), (c2, True, "detailed")):
        with col:
            docx = assessment.to_docx(a, detailed)
            download_button(f"⬇️ Word — {lab}", docx, f"{slug}_assessment_{lab}_{stamp}.docx", key=f"arg_dl_as_{lab}",
                            primary=not detailed)
            if st.button(f"📄 PREPARE THE PDF — {lab}", key=f"arg_as_pdf_{lab}"):
                with st.spinner("Converting with LibreOffice…"):
                    try:
                        pdf = assessment.to_pdf(docx)
                    except Exception as e:  # noqa: BLE001
                        pdf = None
                        warn_banner(f"PDF conversion failed: {e}")
                if pdf:
                    st.session_state[f"arg_as_pdf_bytes_{lab}"] = pdf
                else:
                    warn_banner("LibreOffice is not available here — open the Word file and save it as PDF.")
            if st.session_state.get(f"arg_as_pdf_bytes_{lab}"):
                download_button(f"⬇️ PDF — {lab}", st.session_state[f"arg_as_pdf_bytes_{lab}"],
                                f"{slug}_assessment_{lab}_{stamp}.pdf", key=f"arg_dl_as_pdf_{lab}")
