"""5 · Generate & Download — the set of files for the annual report(s)."""
from __future__ import annotations

import io
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.style import cy_py_note, info_banner, ok_banner, red_alert, section, status_list, warn_banner  # noqa: E402
from engine import build_model, export_pdf, multiyear, package, render_report, tb_io  # noqa: E402

state.init_state()
state.page_setup("📦 Generate & Download")
m = state.project()["meta"]

# ------------------------------------------------------------ project file --
section("Save your work")
st.caption("The project file holds the TB of every year, the CIT codes and all company / report data. "
           "Reload it on 1 · Trial Balance → Resume project.")
if state.has_tb():
    if st.download_button("💾 Download project file (…_project.json)", data=package.to_json_bytes(state.full_project()),
                          file_name=package.stem(m.get("company_name"), kind="Project") + "_project.json",
                          mime="application/json", key="arg_dl_project"):
        st.session_state["arg_dirty"] = False
if not state.require_tb():
    st.stop()

# ------------------------------------------------------------------ scope ----
section("Which report(s)?")
ry = state.report_years()
ay = state.active_year()
scope_opts = [f"Current Year selected: CY {ay} vs PY {ay - 1}"]
if len(ry) > 1:
    scope_opts.append(f"Every year pair: {', '.join(f'{y}/{y - 1}' for y in ry)} ({len(ry)} reports)")
scope = st.radio("Reports to generate", scope_opts, index=1 if state.view_all() and len(scope_opts) > 1 else 0,
                 help="Each Word report compares one Current Year (CY) with its Previous Year (PY). "
                      "Change the selected CY in the sidebar.")
targets = ry if scope.startswith("Every") else [ay]
if len(targets) > 1:
    cy_py_note(all_years=True)
else:
    cy_py_note(ay)

# ------------------------------------------------------------------ gate ----
section("Before generating")
_steps = state.steps()[:-1]
with st.expander("Checklist — " + " ".join({"ok": "✅", "warn": "⚠️", "fail": "❌", "todo": "⏳"}[x[0]] for x in _steps),
                 expanded=any(x[0] == "fail" for x in _steps)):
    status_list(_steps)
models = {y: state.model(y) for y in targets}
if any(v is None for v in models.values()):
    red_alert(st.session_state.get("arg_model_error") or "Statements cannot be computed yet.")
    st.stop()
blocking = {y: [c for c in mm["controls"] if c["level"] == "BLOCKING"] for y, mm in models.items()}
n_block = sum(len(v) for v in blocking.values())
n_warn = sum(c["level"] == "WARNING" for mm in models.values() for c in mm["controls"])
draft = False
if n_block:
    red_alert(f"<b>{n_block} blocking issue(s)</b> — the final report(s) cannot be issued.")
    with st.expander("See the blocking issues"):
        for y, v in blocking.items():
            for c in v:
                st.markdown(f"- **CY {y}** — {c['message']}")
    st.page_link("pages/2_Checks_and_Corrections.py", label="→ Correct them in 2 · Checks & Corrections", icon="🔍")
    draft = st.checkbox("Generate DRAFT(s) anyway (file names end with _DRAFT) — for internal review only")
elif n_warn:
    warn_banner(f"{n_warn} warning(s) to review (listed in the controls reports). No blocking issue.")
else:
    ok_banner("All controls passed.")
missing = state.missing_general()
if missing:
    warn_banner("Missing data will print as blank or dotted lines: " + ", ".join(missing))

soffice = export_pdf.find_soffice()
want_pdf = st.checkbox("Also produce the PDF(s)", value=bool(soffice), disabled=not soffice,
                       help=None if soffice else "LibreOffice not found on this computer — open the .docx in Word and "
                                                  "save as PDF (Word also refreshes the table of contents).")
want_multi = st.checkbox("Also produce the multi-year statements workbook (all years side by side)",
                         value=len(ry) > 1, disabled=len(ry) < 2)
tpl = state.current_template()
font = state.project()["meta"].get("font_name") or (tpl or {}).get("default_font") or None
if tpl is None:
    red_alert("No Word template available — the administrator must add one in the templates/ folder.")
    st.stop()
lvl_lab = render_report.DETAIL_LEVELS[state.project()["meta"].get("detail_level") or "detailed"][1].split(" — ")[0]
st.caption(f"Word template: **{tpl['alias']}** · font: **{font or 'template fonts'}** · level of detail: **{lvl_lab}** · "
           f"comparative: **{'CY only' if any(mm['meta'].get('single_year') for mm in models.values()) else 'CY and PY'}** "
           "— change them in 3 · Company & Report Data → Report options.")

# -------------------------------------------------------------- generate ----
section("Generate")
if st.button("⚙️ GENERATE THE FILES", type="primary", disabled=bool(n_block) and not draft):
    now = datetime.now()
    files: dict[str, bytes] = {}
    with st.status("Generating…", expanded=True) as s:
        files[package.stem(m.get("company_name"), now, kind="Project") + "_project.json"] = \
            package.to_json_bytes(state.full_project())
        reps = {}
        for y, mm in models.items():
            stem = package.stem(m.get("company_name"), now, year=y) + ("_DRAFT" if blocking[y] else "")
            st.write(f"Report CY {y} vs PY {y - 1}")
            files[f"{stem}_input.json"] = package.to_json_bytes(state.pair_input(y))
            files[f"{stem}_model.json"] = package.to_json_bytes(mm)
            files[f"{stem}_controls.md"] = build_model.controls_md(mm).encode("utf-8")
            files[f"{stem}_statements.xlsx"] = package.statements_workbook(mm, state.tb())
            out = io.BytesIO()
            reps[y] = render_report.render(str(tpl["docx"]), mm, out, allow_blocking=bool(blocking[y]), font_name=font)
            files[f"{stem}.docx"] = out.getvalue()
            if reps[y]["missing"]:
                st.write(f"⚠️ Not found in the template: {', '.join(reps[y]['missing'])}")
            if want_pdf:
                st.write(f"PDF CY {y} (LibreOffice — can take a minute)")
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        dx, pdf = Path(tmp) / "report.docx", Path(tmp) / "report.pdf"
                        dx.write_bytes(files[f"{stem}.docx"])
                        export_pdf.export(dx, pdf)
                        files[f"{stem}.pdf"] = pdf.read_bytes()
                except Exception as e:  # noqa: BLE001
                    st.write(f"⚠️ PDF not produced: {e}")
        if want_multi and len(ry) > 1:
            st.write("Multi-year statements workbook")
            allm = state.all_models()
            sheets = {t: multiyear.multi_statement(allm, k) for k, t in
                      (("pnl", "P&L"), ("bs", "Balance sheet"), ("cashflow", "Cash flow"), ("income_tax", "Income tax"))}
            files[package.stem(m.get("company_name"), now, kind="Statements_multi-year") + ".xlsx"] = \
                package.multi_year_workbook(sheets, tb_io.balance_table(state.tb()))
        st.session_state["arg_outputs"] = {"files": files, "renders": reps,
                                           "zip": package.stem(m.get("company_name"), now, kind="Annual_Report_files")}
        s.update(label=f"{len(files)} files generated", state="complete")

out = st.session_state.get("arg_outputs")
if out:
    section("Download")
    files = out["files"]
    labels = [(".docx", "📄 Report (Word)"), (".pdf", "📕 Report (PDF)"), ("_statements.xlsx", "📊 Statements (Excel)"),
              ("_controls.md", "🧪 Controls report"), ("_model.json", "🧮 Model (JSON)"),
              ("_input.json", "🤖 Skill input (JSON)")]

    def file_row(name, data):
        lab = next((l for suf, l in labels if name.endswith(suf)), name)
        c1, c2 = st.columns([1, 3])
        with c1:
            download_button(lab, data, name, key=f"arg_dl_{name}", primary=name.endswith((".docx", ".pdf")))
        c2.caption(name)

    years_out = sorted(out["renders"], reverse=True)
    common = {n: d for n, d in files.items() if not any(f"_FY{y}_" in n for y in years_out)}
    tab_names = [f"📅 FY {y}" + (" ⚠️" if out["renders"][y].get("draft") else "") for y in years_out] + ["📁 Common files"]
    tabs = st.tabs(tab_names)
    for tab, y in zip(tabs, years_out):
        with tab:
            rep = out["renders"][y]
            st.caption(f"Report of the year ended in {y}: CY (Current Year) {y} compared with PY (Previous Year) {y - 1}.")
            if rep.get("draft"):
                warn_banner(f"CY {y}: DRAFT — generated with blocking issues. Not for issue.")
            for w in rep.get("warnings", []):
                if not w.startswith("INFO"):
                    warn_banner(w)
            fy = {n: d for n, d in files.items() if f"_FY{y}_" in n}
            order = {suf: i for i, (suf, _) in enumerate(labels)}
            for name in sorted(fy, key=lambda n: next((order[s_] for s_ in order if n.endswith(s_)), 99)):
                file_row(name, fy[name])
            download_button(f"🗜️ All files of FY {y} (ZIP)", package.bundle(fy), f"{out['zip']}_FY{y}.zip",
                            key=f"arg_dl_zip_{y}")
    with tabs[-1]:
        st.caption("Files that cover the whole project (all years).")
        for name, data in sorted(common.items()):
            lab = "💾 Project file" if name.endswith("_project.json") else "📈 Multi-year workbook"
            c1, c2 = st.columns([1, 3])
            with c1:
                download_button(lab, data, name, key=f"arg_dl_{name}")
            c2.caption(name)
    st.divider()
    download_button(f"🗜️ Everything — {len(files)} files (ZIP)", package.bundle(files), out["zip"] + ".zip",
                    key="arg_dl_zip", primary=True)
    info_banner("Opening a .docx, Word asks to <b>update the fields</b> — answer <b>Yes</b> to refresh the table of "
                "contents and page numbers. The skill input (JSON) can be given to the annual-report-generator AI skill.")
