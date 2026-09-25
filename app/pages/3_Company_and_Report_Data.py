"""3 · Company & Report Data — everything printed in the report that is not in the TB."""
from __future__ import annotations

import sys
from datetime import date
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.style import cy_py_note, info_banner, ok_banner, section, warn_banner  # noqa: E402
from engine import company_data, multiyear, package, render_report, templates  # noqa: E402
from app.downloads import download_button  # noqa: E402

state.init_state()
state.page_setup("🏢 Company & Report Data")

d = state.project()
m, g = d["meta"], d["general"]
YS = sorted(state.years(), reverse=True)   # most recent first
YD = d.setdefault("years_data", {})

miss = state.missing_general()
if miss:
    warn_banner("Still missing (printed in the report): <b>" + ", ".join(miss) + "</b>.")
else:
    ok_banner("All the information printed in the report is filled in.")
cy_py_note()

pend_cd = st.session_state.get("arg_pending_company")
if pend_cd:
    pg, pm = pend_cd["part"].get("general", {}), pend_cd["part"].get("meta", {})
    with st.container(border=True):
        info_banner(f"<b>Company & Report Data found in the TB file</b> “{pend_cd['source']}”: company "
                    f"<b>{pm.get('company_name') or '—'}</b>, year end <b>{pm.get('period_end') or '—'}</b>, auditor "
                    f"<b>{pg.get('audit_company_name') or '—'}</b>, per-year data for "
                    f"<b>{', '.join(sorted((pend_cd['part'].get('years_data') or {}).keys())) or '—'}</b>. "
                    "Apply them to fill this page, or ignore them.")
        a1, a2 = st.columns(2)
        if a1.button("✅ APPLY THESE DATA", type="primary"):
            done = company_data.apply(d, pend_cd["part"])
            st.session_state["arg_pending_company"] = None
            state.mark_dirty()
            st.success("Applied: " + ", ".join(done) + ". Check the tabs below.")
            st.rerun()
        if a2.button("Ignore"):
            st.session_state["arg_pending_company"] = None
            st.rerun()


def to_date(v):
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def saved():
    state.mark_dirty()
    st.success("Saved.")


tabs = st.tabs(["🏢 Company & auditor", "📅 Period & tax", "📦 Stock & fixed assets", "💶 Equity & cash flow",
                "⚙️ Report options",
                "💾 Save / load"])

# ============================================================== company ======
with tabs[0]:
    with st.form("arg_f_company"):
        section("Company")
        c1, c2 = st.columns(2)
        company = c1.text_input("Company name *", m.get("company_name") or "")
        activity = c2.text_input("Main activity * (completes: 'The principal activity of the company is …')",
                                 g.get("main_activity") or "")
        c1, c2, c3 = st.columns(3)
        office = c1.text_area("Registered office * (one line per row)", g.get("registered_office") or "", height=110)
        directors = c2.text_area("Directors * (one per line)", g.get("directors") or "", height=110)
        bankers = c3.text_area("Principal bankers * (one per line)", (g.get("bankers") or "").strip(), height=110)
        section("Auditor")
        c1, c2 = st.columns(2)
        aud = c1.text_input("Audit firm name *", g.get("audit_company_name") or "")
        aud_addr = c2.text_area("Audit firm address *", g.get("audit_company_address") or "", height=80)
        c1, c2 = st.columns(2)
        fw_aud = c1.text_input("Auditor's report framework *", g.get("auditor_report_framework") or "",
                               help="'…in accordance with {framework}' in the opinion paragraph")
        fw_acc = c2.text_input("Accounting framework *", g.get("accounting_framework") or "",
                               help="Note 2 a): '…in compliance with the {framework} for Small and Medium-sized Entities…'")
        section("Directors' report & signatures")
        c1, c2, c3 = st.columns(3)
        div = c1.number_input("Proposed dividend (Rwf)", value=num(g.get("proposed_dividend")), step=1000.0, format="%.0f")
        rep = c2.text_input("Company representative (directors' statement)", g.get("company_representative") or "",
                            help="Leave empty to print a dotted line to sign by hand")
        sig = c3.date_input("Approval / signature date", value=to_date(g.get("signature_date")), format="DD/MM/YYYY")
        c1, c2 = st.columns(2)
        director = c1.text_input("Director signing the balance sheet", g.get("company_director") or "")
        fs_sig = c2.date_input("Financial statements signing date", value=to_date(g.get("fs_signing_date")),
                               format="DD/MM/YYYY")
        if st.form_submit_button("💾 SAVE", type="primary"):
            m["company_name"] = company.strip()
            g.update({"main_activity": activity.strip(), "registered_office": office.strip(),
                      "directors": directors.strip(), "bankers": bankers.strip(), "audit_company_name": aud.strip(),
                      "audit_company_address": aud_addr.strip(), "auditor_report_framework": fw_aud.strip(),
                      "accounting_framework": fw_acc.strip(), "proposed_dividend": div,
                      "company_representative": rep.strip(), "signature_date": sig.isoformat() if sig else "",
                      "company_director": director.strip(), "fs_signing_date": fs_sig.isoformat() if fs_sig else ""})
            saved()

# =============================================================== period =====


def year_grid(fields: list[str], key: str, pct: tuple = ()):
    """Editable grid: one row per year (most recent first), one column per field of years_data."""
    rows = []
    for y in YS:
        v = multiyear.yd(d, y)
        rows.append({"Year": str(y), **{f: (float(v[f]) * 100 if f in pct else float(v[f] or 0)) for f in fields}})
    cfg = {"Year": st.column_config.TextColumn("Year", disabled=True)}
    for f in fields:
        lab, hlp = multiyear.YEAR_FIELDS[f]
        cfg[f] = st.column_config.NumberColumn(lab, help=hlp, format="%.2f" if f in pct else "localized")
    return st.data_editor(pd.DataFrame(rows), hide_index=True, width="stretch", key=key, column_config=cfg,
                          disabled=["Year"])


def save_grid(ed, fields, pct=()):
    for r in ed.to_dict("records"):
        yd_ = YD.setdefault(str(r["Year"]), {})
        for f in fields:
            val = float(r[f] or 0)
            yd_[f] = val / 100 if f in pct else val
    saved()


with tabs[1]:
    with st.form("arg_f_period"):
        section("Financial year")
        c1, c2, c3 = st.columns(3)
        pend = c1.date_input("Financial year end (of the most recent year) *", value=to_date(m.get("period_end")),
                             format="DD/MM/YYYY",
                             help="Day and month apply to every year of the TB (e.g. 31/12). The year of each "
                                  "report is the Current Year (CY) chosen in the sidebar.")
        cur = c2.text_input("Currency", m.get("currency") or "Rwf")
        ctype = c3.selectbox("Taxpayer type", ["CORPORATE", "INDIVIDUAL"],
                             index=0 if (m.get("company_type") or "CORPORATE") == "CORPORATE" else 1)
        if st.form_submit_button("💾 SAVE", type="primary"):
            m.update({"period_end": pend.isoformat() if pend else "", "currency": cur.strip() or "Rwf", "company_type": ctype})
            saved()
    section("Corporate income tax — one line per year")
    if not YS:
        info_banner("Load a trial balance first: the years come from the TB.")
    else:
        st.caption("Rwanda CIT: 30% up to 2023, 28% from 2024 (Law 051/2023) — pre-filled; change only for an "
                   "incentive rate. The report of CY uses the CY line and the PY line (CY − 1).")
        tf = ["cit_rate", "prepayments", "wht", "grants", "loss_brought_forward"]
        ted = year_grid(tf, "arg_tax_grid", pct=("cit_rate",))
        if st.button("💾 SAVE TAX DATA", type="primary"):
            save_grid(ted, tf, pct=("cit_rate",))

# ========================================================== stock / PPE =====
with tabs[2]:
    section("Inventory movement (note 12) — one column per year")
    if not YS:
        info_banner("Load a trial balance first: the years come from the TB.")
    else:
        has_im = any(multiyear.yd(d, y).get("inventory_movement") for y in YS)
        use_im = st.toggle("Provide the inventory movement", value=has_im)
        if use_im:
            base = pd.DataFrame({"item": [lab for _, lab in multiyear.INV_KEYS],
                                 **{str(y): [float((multiyear.yd(d, y).get("inventory_movement") or {}).get(k, 0))
                                             for k, _ in multiyear.INV_KEYS] for y in YS}})
            ied = st.data_editor(base, hide_index=True, disabled=["item"], key="arg_im_editor", width="stretch",
                                 column_config={str(y): st.column_config.NumberColumn(str(y), format="localized") for y in YS})
            st.caption("Closing stock: " + " · ".join(f"{y}: {ied[str(y)].sum():,.0f}" for y in YS) +
                       " — must equal balance-sheet inventories.")
        if st.button("💾 SAVE INVENTORY MOVEMENT", type="primary"):
            for y in YS:
                YD.setdefault(str(y), {})["inventory_movement"] = (
                    {k: float(ied.iloc[i][str(y)]) for i, (k, _) in enumerate(multiyear.INV_KEYS)} if use_im else None)
            saved()

        section("Fixed-asset register (note 11)")
        fy = st.selectbox("Register of the year", YS, format_func=lambda y: f"{y}",
                          help="The register of a year is used in the report whose Current Year (CY) is that year.")
        fa = multiyear.yd(d, fy).get("fixed_assets")
        use_fa = st.toggle(f"Provide the fixed-asset register for {fy} (otherwise depreciation is allocated pro rata)",
                           value=bool(fa), key=f"arg_use_fa_{fy}")
        cols = ["name", "rate", "cost_opening", "additions", "disposals", "dep_opening", "charge", "dep_on_disposals"]
        if use_fa:
            base = pd.DataFrame(fa or [{"name": "Motor vehicles", "rate": 0.25}, {"name": "Furniture", "rate": 0.25},
                                       {"name": "Computers & other", "rate": 0.5}])
            for c in cols:
                if c not in base.columns:
                    base[c] = 0.0
            fed = st.data_editor(base[cols], num_rows="dynamic", key=f"arg_fa_editor_{fy}", width="stretch", hide_index=True,
                                 column_config={"name": "Category", "rate": st.column_config.NumberColumn("Rate", format="%.2f"),
                                                **{c: st.column_config.NumberColumn(c.replace("_", " "), format="localized")
                                                   for c in cols[2:]}})
            st.caption("Depreciation columns as positive amounts; disposals of cost as negative amounts.")
        if st.button("💾 SAVE FIXED-ASSET REGISTER", type="primary"):
            YD.setdefault(str(fy), {})["fixed_assets"] = fed.fillna(0).to_dict("records") if use_fa else None
            saved()

# ======================================================= equity / cash ======
with tabs[3]:
    section("Equity movements and cash-flow information — one line per year")
    if not YS:
        info_banner("Load a trial balance first: the years come from the TB.")
    else:
        ef = ["drawings", "adjustments", "income_tax_paid", "disposal_proceeds", "additional_loans_from_directors",
              "short_term_borrowings"]
        eed = year_grid(ef, "arg_eq_grid")
        if st.button("💾 SAVE EQUITY & CASH-FLOW DATA", type="primary"):
            save_grid(eed, ef)

# ============================================================= options ======
with tabs[4]:
    with st.form("arg_f_options"):
        section("Report layout")
        c1, c2, c3 = st.columns(3)
        fs = c1.number_input("Table font size (pt)", min_value=6, max_value=11, value=int(m.get("tables_font_size") or 8))
        col = c2.color_picker("Colour of inserted data", "#" + (m.get("variables_color") or "000000").lstrip("#"),
                              help="V11 used blue (#0070C0) to spot inserted data; black for the final report")
        hz = c3.checkbox("Hide lines that are zero in both years", value=bool(m.get("hide_zero_lines", True)))
        c1, c2 = st.columns(2)
        lv_keys = list(render_report.DETAIL_LEVELS)
        lv = c1.radio("Level of detail — balance sheet and P&L", lv_keys,
                      index=lv_keys.index(m.get("detail_level") or "detailed"),
                      format_func=lambda k: render_report.DETAIL_LEVELS[k][1],
                      help="Detailed: every statement line (as the Excel generator). Summarised: main headings with "
                           "their sub-totals (e.g. Current assets → Inventories, Receivables, Cash). Condensed: main "
                           "headings only (e.g. Current assets, Total assets). Also changeable on Statements Preview.")
        cp_keys = list(multiyear.COMPARATIVE)
        cp = c2.radio("Comparative year (PY)", cp_keys, index=cp_keys.index(m.get("comparative") or "auto"),
                      format_func=lambda k: multiyear.COMPARATIVE[k],
                      help="A company in its first financial year has no Previous Year: its report shows the Current "
                           "Year (CY) only.")
        if st.form_submit_button("💾 SAVE", type="primary"):
            m.update({"tables_font_size": int(fs), "variables_color": col.lstrip("#").upper(), "hide_zero_lines": hz,
                      "detail_level": lv, "comparative": cp})
            saved()

    section("Word template and font")
    tlist = [t for t in templates.list_templates() if not t["error"]]
    if not tlist:
        warn_banner("No Word template available — the administrator must add one in the templates/ folder.")
    else:
        cur = state.current_template()
        ids = [t["id"] for t in tlist]
        c1, c2 = st.columns([3, 2])
        tid = c1.selectbox("Annual report template", ids, index=ids.index(cur["id"]) if cur else 0,
                           format_func=lambda i: next(t["alias"] for t in tlist if t["id"] == i),
                           help="Templates are managed by the administrator. See and download them on the Templates page.")
        chosen = next(t for t in tlist if t["id"] == tid)
        default_label = f"Template default ({chosen.get('default_font') or 'fonts of the Word file'})"
        fonts = [default_label] + templates.FONTS
        cur_font = m.get("font_name") or default_label
        font = c2.selectbox("Font of the report", fonts, index=fonts.index(cur_font) if cur_font in fonts else 0,
                            help="'Template default' follows the font set for each template by the administrator. "
                                 "Another choice replaces every text font of the report (titles, text, tables). The "
                                 "Word file shows it on any PC where the font is installed; online PDFs use a close "
                                 "substitute if the server does not have it.")
        st.caption(chosen["description"])
        if st.button("💾 SAVE TEMPLATE AND FONT", type="primary"):
            m["template_id"] = tid
            m["font_name"] = "" if font == default_label else font
            saved()
        st.page_link("pages/6_Templates.py", label="See and download the templates", icon="🗂️")

    section("Explanatory notes (advanced)")
    st.caption("Titles, sign ('D' debit − credit / 'C' credit − debit), content sources (tb, income_tax, ppe, "
               "inventory) and standard texts ({period_end} is replaced by the date). Keep ids consecutive — Word "
               "numbers the notes automatically and the first injected note is 5.")
    notes = d.get("notes") or state.current_notes()["notes"]
    ndf = pd.DataFrame([{"id": n["id"], "title": n["title"], "way": n.get("way") or "",
                         "tables": ", ".join(n.get("tables", [])), "text": n.get("text") or ""} for n in notes])
    ned = st.data_editor(ndf, num_rows="dynamic", hide_index=True, width="stretch", key="arg_notes_editor",
                         column_config={"text": st.column_config.TextColumn(width="large"),
                                        "way": st.column_config.SelectboxColumn(options=["", "D", "C"])})
    c1, c2 = st.columns(2)
    if c1.button("💾 SAVE NOTES", type="primary"):
        old = {n["id"]: n for n in notes}
        new = []
        for r in ned.fillna("").to_dict("records"):
            if not str(r["id"]).strip():
                continue
            n = dict(old.get(str(r["id"]), {}))
            n.update({"id": str(r["id"]).zfill(2), "title": r["title"], "way": r["way"] or None,
                      "tables": [x.strip() for x in str(r["tables"]).split(",") if x.strip()]})
            if str(r["text"]).strip():
                n["text"] = r["text"]
            else:
                n.pop("text", None)
            new.append(n)
        d["notes"] = new
        saved()
    if c2.button("Reset notes to default"):
        d["notes"] = None
        saved()

# ============================================================ save / load ===
with tabs[5]:
    section("Save these data")
    st.caption("Everything on this page — company, auditor, signatures, per-year tax / equity / cash-flow data, "
               "inventory movement, fixed-asset registers, report options and notes — but not the trial balance. "
               "Reload the file next year or for another report of the same company instead of typing again.")
    slug = package.company_slug(m.get("company_name"))
    stamp = datetime.now().strftime("%Y-%m-%d %H%M")
    c1, c2 = st.columns(2)
    with c1:
        download_button("⬇️ Excel (.xlsx) — easy to read and edit", company_data.to_excel(d, state.years()),
                        f"{slug}_Company_Report_Data__V{stamp}.xlsx", key="arg_cd_xlsx", primary=True)
    with c2:
        download_button("⬇️ JSON (.json) — exact copy", company_data.to_json(d),
                        f"{slug}_Company_Report_Data__V{stamp}.json", key="arg_cd_json")
    section("Load previously saved data")
    st.caption("An Excel or JSON file saved here (a project file …_project.json is accepted too). Only the sections "
               "present in the file are replaced; the trial balance is not touched.")
    up = st.file_uploader("Company & Report Data file", type=["xlsx", "json"], key="arg_cd_file")
    if up is not None:
        try:
            part = company_data.from_file(up.getvalue(), up.name)
            g_ = part.get("general", {})
            m_ = part.get("meta", {})
            info_banner(f"File read: company <b>{m_.get('company_name') or '—'}</b>, year end <b>{m_.get('period_end') or '—'}</b>, "
                        f"auditor <b>{g_.get('audit_company_name') or '—'}</b>, per-year data for "
                        f"<b>{', '.join(sorted((part.get('years_data') or {}).keys())) or '—'}</b>.")
            if st.button("📥 LOAD THESE DATA (replaces the current values)", type="primary"):
                done = company_data.apply(d, part)
                state.mark_dirty()
                st.success("Loaded: " + ", ".join(done) + ".")
        except Exception as e:  # noqa: BLE001
            warn_banner(f"This file cannot be read: {e}")
