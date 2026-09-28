"""8 · Long-term Assets Check — register (template / upload / filters), book and tax depreciation, reconciliation with the TB,
RRA Depreciation Table, Excel with formulas."""
from __future__ import annotations

import sys
from datetime import date
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
from engine import fixed_assets as fa  # noqa: E402
from engine import package  # noqa: E402

state.init_state()
state.page_setup("🏗️ Long-term Assets Check")

chart = state.chart()
proj = state.project()
settings = fa.settings_of(proj)
reg = fa.register_from_records(proj.get("asset_register"))
cats = fa.categories(chart, settings)
cat_name = {c["code"]: c["name"] for c in cats}
company = proj["meta"].get("company_name") or "Company"
slug = package.company_slug(company)
years = sorted(state.years()) if state.has_tb() else []
last_year = max(years) if years else date.today().year
limit = float(chart["fixed_assets"].get("small_pool_limit") or 0)


def styled(df: pd.DataFrame, money: list[str]):
    v = df.copy()
    for c in money:
        v[c] = [fmt_acc(x) for x in v[c]]
    return v.style.map(lambda x: "color:#C00000" if isinstance(x, str) and x.startswith("(") else "", subset=money)


missing_rates = [c for c in cats if c["rate"] is None]
used_missing = [c for c in missing_rates if not reg.empty and (reg["category"] == c["code"]).any()]
warns = []
if reg.empty:
    warns.append("No fixed-asset register yet — download the template, fill it (or ask the client) and upload it.")
if used_missing:
    warns.append("No depreciation rate for " + ", ".join(f"{c['code']} {c['name']}" for c in used_missing) +
                 " — these assets are not depreciated. Enter the rate in ⚙️ Rates & options.")
explain_box("How the fixed assets are calculated", f"""
<b>Register</b> — one line per asset: description, DMC/EBM invoice number, acquisition date (the three columns of the RRA
<i>Depreciation Table</i>), category (CIT code), cost, and for sold or scrapped assets the disposal date and proceeds.<br>
<b>Book depreciation (annual report)</b> — <i>straight-line on each asset</i>: cost × category rate every year, a
<b>full year in the acquisition year</b>, <b>{'a full year' if settings['disposal_year_full'] else 'no depreciation'}
in the disposal year</b> (option), residual value 0, until the cost is fully depreciated. Gain/loss on disposal =
proceeds − net book value.<br>
<b>Tax depreciation (RRA Depreciation Table)</b> — <i>reducing balance per category</i> (all assets of a category form a
pool) at the same rates, full year in the acquisition year; a disposal removes the asset's <b>own tax value</b>; when a
pool is worth less than <b>Rwf {limit + 1:,.0f}</b> after the purchases and disposals of the year and before depreciation,
it is written off at <b>100%</b>.<br>
<b>Why the two methods differ</b> — with the RRA reducing balance on a pool, an asset is never fully depreciated as long
as new assets of the same category are bought (the pool never reaches 0); the straight-line on each asset depreciates
each item over its life. The difference between book and tax depreciation is shown per year (📊 Summary) and flagged
in 7 · Tax & CIT and in the assessment report — the tax computation does not replace one by the other yet.<br>
<b>Note 11</b> — built from the register when it <b>reconciles with the TB</b> (cost per category, accumulated
depreciation, charge, disposal result, NBV) for CY and PY; otherwise the TB figures are used and the depreciation is
allocated pro rata to cost (option below to force or refuse the register).""", warns)

tabs = st.tabs(["📄 Template & upload", "🔎 Register", "⚙️ Rates & options", "📈 Depreciation by asset",
                "📊 Summary by year & category", "⚖️ Reconciliation with the TB", "🏛️ RRA Depreciation Table"])

# ---------------------------------------------------------------- template ---
with tabs[0]:
    section("Template")
    st.markdown("Excel template with the columns of the RRA **Depreciation Table** (green) and the columns the app needs "
                "(category, cost, disposal), the list of categories and rates, a drop-down for the category and the "
                "instructions. When a register is already loaded, the template is pre-filled with it (to update it).")
    download_button("⬇️ Download the asset-register template (Excel)", fa.template_workbook(chart, settings, reg),
                    f"{slug}_asset_register_template.xlsx", key="arg_dl_fa_tpl", primary=True)
    section("Upload the register")
    f = st.file_uploader("Asset register (.xlsx)", type=["xlsx", "xlsm"], key="arg_fa_up")
    if f is not None:
        try:
            new = fa.parse_workbook(f.getvalue())
            iss = fa.issues(new, chart, settings)
            nb = int((iss["Level"] == "BLOCKING").sum()) if not iss.empty else 0
            st.caption(f"{len(new)} asset(s) read from {f.name} — {nb} blocking issue(s), "
                       f"{len(iss) - nb} warning(s).")
            if len(iss):
                st.dataframe(iss, hide_index=True, width="stretch", height=min(38 * (len(iss) + 1), 300))
            c1, c2 = st.columns(2)
            if c1.button("✅ REPLACE THE REGISTER WITH THIS FILE", type="primary"):
                proj["asset_register"] = fa.register_to_records(new)
                state.mark_dirty()
                st.rerun()
            if not reg.empty and c2.button("➕ ADD THESE ASSETS TO THE CURRENT REGISTER"):
                proj["asset_register"] = fa.register_to_records(pd.concat([reg, new], ignore_index=True))
                state.mark_dirty()
                st.rerun()
        except Exception as e:  # noqa: BLE001
            red_alert(f"This file cannot be read as an asset register: {e}")
    if not reg.empty:
        iss = fa.issues(reg, chart, settings)
        if iss.empty:
            ok_banner(f"{len(reg)} asset(s) in the register — no issue.")
        else:
            nb = int((iss["Level"] == "BLOCKING").sum())
            (red_alert if nb else warn_banner)(f"{len(reg)} asset(s) in the register — {nb} blocking issue(s) (not "
                                               f"computed), {len(iss) - nb} warning(s).")
            st.dataframe(iss, hide_index=True, width="stretch", height=min(38 * (len(iss) + 1), 300))
        if st.button("🗑️ CLEAR THE REGISTER"):
            proj["asset_register"] = []
            state.mark_dirty()
            st.rerun()

# ---------------------------------------------------------------- register ---
with tabs[1]:
    if reg.empty:
        info_banner("No register loaded yet (📄 Template & upload).")
    else:
        c1, c2, c3 = st.columns([2, 2, 1])
        q = c1.text_input("Keywords (name, asset ID, invoice number, comment)", key="arg_fa_q")
        sel = c2.multiselect("Categories", list(cat_name), format_func=lambda c: f"{c} {cat_name[c]}", key="arg_fa_cat")
        status = c3.selectbox("Status", ["All", "In use", "Disposed"], key="arg_fa_status")
        dmin = min(d for d in reg["acq_date"] if d) if reg["acq_date"].notna().any() else date(2000, 1, 1)
        dmax = max(d for d in reg["acq_date"] if d) if reg["acq_date"].notna().any() else date.today()
        c1, c2 = st.columns(2)
        dr = c1.date_input("Acquisition date between", value=(dmin, dmax), format="DD/MM/YYYY", key="arg_fa_dates")
        cmax = float(reg["cost"].fillna(0).max() or 0)
        cr = c2.slider("Cost between (Rwf)", 0.0, max(cmax, 1.0), (0.0, max(cmax, 1.0)), key="arg_fa_cost")
        v = reg.copy()
        if q.strip():
            hay = (v["description"] + " " + v["asset_id"] + " " + v["doc_no"] + " " + v["comment"]).str.lower()
            v = v[hay.apply(lambda h: all(w in h for w in q.lower().split()))]
        if sel:
            v = v[v["category"].isin(sel)]
        if status != "All":
            v = v[v["disp_date"].isna() == (status == "In use")]
        if isinstance(dr, tuple) and len(dr) == 2:
            v = v[v["acq_date"].apply(lambda d: d is not None and dr[0] <= d <= dr[1])]
        v = v[v["cost"].fillna(0).between(cr[0], cr[1])]
        book = fa.book_schedule(v, chart, settings, last_year)
        nbv = book[book["year"] == last_year].groupby("asset")["nbv"].sum() if not book.empty else pd.Series(dtype=float)
        view = pd.DataFrame({"Asset ID": v["asset_id"], "Description": v["description"],
                             "Category": v["category"].map(lambda c: f"{c} {cat_name.get(c, '?')}"),
                             "DMC/EBM invoice": v["doc_no"], "Acquired": v["acq_date"], "Cost": v["cost"],
                             "Disposed": v["disp_date"], "Proceeds": v["disp_proceeds"]})
        st.caption(f"{len(v)} of {len(reg)} assets · cost {fmt_acc(v['cost'].fillna(0).sum())}")
        st.dataframe(view, hide_index=True, width="stretch", height=460,
                     column_config={c: st.column_config.NumberColumn(format="localized") for c in ("Cost", "Proceeds")} |
                     {c: st.column_config.DateColumn(format="DD/MM/YYYY") for c in ("Acquired", "Disposed")})
        download_button("⬇️ These assets (Excel)", package.workbook({"Assets": view}), f"{slug}_assets_filtered.xlsx",
                        key="arg_dl_fa_filtered")

# ------------------------------------------------------------------- rates ---
with tabs[2]:
    section("Depreciation rates (book and tax)")
    st.caption("Defaults from the accounting policy (data/chart_of_accounts.json → fixed_assets). A change here applies to "
               "this project only.")
    rv = pd.DataFrame([{"CIT code": c["code"], "Category": c["name"],
                        "Rate (%)": None if c["rate"] is None else c["rate"] * 100} for c in cats])
    ed = st.data_editor(rv, hide_index=True, width="stretch", disabled=["CIT code", "Category"], key="arg_fa_rates",
                        column_config={"Rate (%)": st.column_config.NumberColumn(format="%.2f", min_value=0, max_value=100)})
    section("Options")
    c1, c2 = st.columns(2)
    dfull = c1.radio("Book depreciation in the disposal year", ["No depreciation (default)", "Full year"],
                     index=1 if settings["disposal_year_full"] else 0, key="arg_fa_dfull")
    n11 = c2.radio("Note 11 from the register", ["auto", "always", "never"], index=["auto", "always", "never"].index(
        settings["note11"]), format_func={"auto": "Only when it reconciles with the TB (default)",
                                          "always": "Always, even with differences", "never": "Never (TB, pro rata)"}.get,
                   key="arg_fa_n11")
    if st.button("💾 SAVE RATES & OPTIONS", type="primary"):
        defaults = {c["code"]: c["rate"] for c in chart["fixed_assets"]["categories"]}
        rates = {}
        for r in ed.to_dict("records"):
            val = None if pd.isna(r["Rate (%)"]) else float(r["Rate (%)"]) / 100
            if val != defaults.get(r["CIT code"]):
                rates[r["CIT code"]] = val
        proj["asset_settings"] = {"rates": rates, "disposal_year_full": dfull == "Full year", "note11": n11}
        state.mark_dirty()
        st.rerun()
    if missing_rates:
        warn_banner("No rate yet for " + ", ".join(f"{c['code']} {c['name']}" for c in missing_rates) +
                    " (not in the accounting policy).")

book = fa.book_schedule(reg, chart, settings, last_year) if not reg.empty else pd.DataFrame()
tax = fa.tax_schedule(reg, chart, settings, last_year) if not reg.empty else pd.DataFrame()

# --------------------------------------------------------------- by asset ---
with tabs[3]:
    if reg.empty:
        info_banner("No register loaded yet.")
    else:
        ok_assets = fa.valid(reg, chart, settings)
        labels = [f"{r['asset_id'] + ' — ' if r['asset_id'] else ''}{r['description']} ({r['category']}, "
                  f"{r['acq_date']:%d/%m/%Y})" for _, r in ok_assets.iterrows()]
        pick = st.selectbox("Asset", range(len(labels)), format_func=lambda i: labels[i], key="arg_fa_pick")
        life = fa.book_schedule(ok_assets.iloc[[pick]], chart, settings, last_year, full_life=True)
        section("Book depreciation — from the acquisition to the end of the depreciation")
        cols = ["cost_open", "additions", "disposals", "cost_close", "dep_open", "charge", "dep_disposals", "dep_close",
                "nbv", "gain_loss"]
        lv = life[["year"] + cols].rename(columns={"year": "Year", "cost_open": "Cost 1 Jan", "additions": "Additions",
                                                   "disposals": "Disposals", "cost_close": "Cost 31 Dec",
                                                   "dep_open": "Acc. dep. 1 Jan", "charge": "Charge",
                                                   "dep_disposals": "Dep. on disposal", "dep_close": "Acc. dep. 31 Dec",
                                                   "nbv": "NBV 31 Dec", "gain_loss": "Gain / (loss)"})
        lv["Year"] = lv["Year"].astype(str)
        st.dataframe(styled(lv, [c for c in lv.columns if c != "Year"]), hide_index=True, width="stretch")
        section("Tax value (RRA pool of the category)")
        tt = fa.tax_schedule(reg, chart, settings, last_year)
        tt = tt[tt["asset"] == fa.valid(reg, chart, settings).index[pick]] if not tt.empty else tt
        if not tt.empty:
            tv = tt[["year", "tax_open", "acquisition", "disposition", "before_dep", "rate", "allowance", "tax_close",
                     "pool_written_off"]].rename(columns={"year": "Year", "tax_open": "Tax value 1 Jan",
                                                          "acquisition": "Acquisition", "disposition": "Disposition",
                                                          "before_dep": "Before depreciation", "rate": "Rate",
                                                          "allowance": "Allowance", "tax_close": "Tax value 31 Dec",
                                                          "pool_written_off": "Pool < limit (100%)"})
            tv["Year"] = tv["Year"].astype(str)
            tv["Rate"] = tv["Rate"].map(lambda x: "" if x is None or pd.isna(x) else f"{x:.0%}")
            st.dataframe(styled(tv, ["Tax value 1 Jan", "Acquisition", "Disposition", "Before depreciation", "Allowance",
                                     "Tax value 31 Dec"]), hide_index=True, width="stretch")

# ----------------------------------------------------------------- summary ---
with tabs[4]:
    if book.empty:
        info_banner("No register loaded yet.")
    else:
        sm = fa.summary(book, chart)
        sum_tabs = st.tabs(["📅 By category (one year)", "📈 Charge per year", "🏛️ Tax allowance per year",
                           "⚖️ Book vs tax"])
        with sum_tabs[0]:
            ysel = st.selectbox("Year", sorted(sm["year"].unique(), reverse=True), key="arg_fa_sy")
            s1 = sm[sm["year"] == ysel].drop(columns=["year"]).rename(columns={
                "category": "Code", "name": "Category", "cost_open": "Cost 1 Jan", "additions": "Additions",
                "disposals": "Disposals", "cost_close": "Cost 31 Dec", "dep_open": "Acc. dep. 1 Jan", "charge": "Charge",
                "dep_disposals": "Dep. on disposals", "dep_close": "Acc. dep. 31 Dec", "nbv": "NBV",
                "gain_loss": "Gain / (loss)"})
            tot = s1.select_dtypes("number").sum()
            s1 = pd.concat([s1, pd.DataFrame([{"Code": "", "Category": "TOTAL", **tot.to_dict()}])], ignore_index=True)
            st.dataframe(styled(s1, [c for c in s1.columns if c not in ("Code", "Category")]), hide_index=True,
                        width="stretch")
        with sum_tabs[1]:
            pv = sm.pivot_table(index="name", columns="year", values="charge", aggfunc="sum", fill_value=0)
            pv.columns = [str(c) for c in pv.columns]
            pv.loc["TOTAL"] = pv.sum()
            st.dataframe(styled(pv.reset_index().rename(columns={"name": "Category"}), list(pv.columns)), hide_index=True,
                        width="stretch")
        with sum_tabs[2]:
            ts = fa.tax_summary(tax, chart)
            if not ts.empty:
                tp = ts.pivot_table(index="name", columns="year", values="allowance", aggfunc="sum", fill_value=0)
                tp.columns = [str(c) for c in tp.columns]
                tp.loc["TOTAL"] = tp.sum()
                st.dataframe(styled(tp.reset_index().rename(columns={"name": "Category"}), list(tp.columns)), hide_index=True,
                            width="stretch")
                wo = ts[ts["written_off"]]
                if len(wo):
                    info_banner("Pools written off at 100% (below Rwf " + f"{limit + 1:,.0f}): " +
                                ", ".join(f"{r['name']} {r['year']}" for _, r in wo.iterrows()))
        with sum_tabs[3]:
            bt = fa.book_vs_tax(book, tax, years or [last_year])
            bt["Year"] = bt["Year"].astype(str)
            st.dataframe(styled(bt, [c for c in bt.columns if c != "Year"]), hide_index=True, width="stretch")
            if (bt["Difference (tax − book)"].abs() > 1).any():
                warn_banner("Book and tax depreciation differ — the tax computation still uses the book depreciation of "
                            "the accounts (7 · Tax & CIT). To be decided how to adjust the taxable income.")
        download_button("⬇️ Fixed assets — Excel with formulas (register, grids, summaries, reconciliation, RRA table)",
                        fa.export_workbook(reg, chart, settings, years or [last_year], state.tb() if state.has_tb() else None,
                                           company), f"{slug}_fixed_assets_{last_year}.xlsx", key="arg_dl_fa_x", primary=True)

# ----------------------------------------------------------- reconciliation ---
with tabs[5]:
    if book.empty or not state.has_tb():
        info_banner("Needs a register and a trial balance.")
    else:
        rec = fa.reconcile(book, state.tb(), chart, years)
        bad = rec[~rec["OK"]]
        if bad.empty:
            ok_banner("The register reconciles with the trial balance for every year.")
        else:
            red_alert(f"{len(bad)} difference(s) between the register and the TB — see the red lines. Common causes: "
                      "assets missing from the register, a different depreciation method in the books, disposals not "
                      "recorded, accumulated depreciation not split by category.")
        for y in sorted(years, reverse=True):
            section(f"{y}")
            r = rec[rec["Year"] == y].drop(columns=["Year"])
            st.dataframe(styled(r, ["Register", "Trial balance", "Difference"]).apply(
                lambda row: ["color:#C00000;font-weight:700" if not row["OK"] else "" for _ in row], axis=1),
                hide_index=True, width="stretch")
        ay = state.active_year()
        if ay:
            cats11, why = fa.note11_from_project(proj, state.tb(), chart, ay)
            (ok_banner if cats11 else warn_banner)(f"Note 11 for {ay}: {why}.")

# -------------------------------------------------------------- RRA table ---
with tabs[6]:
    if tax.empty:
        info_banner("No register loaded yet.")
    else:
        ry = st.selectbox("Year of the CIT declaration", sorted(set(tax["year"]), reverse=True), key="arg_fa_ry")
        t = fa.rra_table(tax, ry)
        explain_box("RRA Depreciation Table", f"""The 9 columns of the RRA annexure sheet <i>Depreciation Table</i>,
one line per asset, with the TAX values (reducing balance per category). <i>Rate</i> shows 100% when the pool of the
category is below Rwf {limit + 1:,.0f} and written off. Copy the lines into the RRA file with <i>Paste special → Values</i>
(RRA instruction 5), then validate the sheet in the RRA file.""")
        st.dataframe(styled(t.assign(Rate=t["Rate"].map(lambda x: f"{x:.0%}" if x is not None and not pd.isna(x) else "")),
                            [c for c in fa.RRA_COLUMNS[3:] if c != "Rate"]), hide_index=True, width="stretch", height=420)
        download_button(f"⬇️ RRA Depreciation Table {ry} (Excel)", package.workbook({"Depreciation Table": t}),
                        f"{slug}_RRA_depreciation_table_{ry}.xlsx", key="arg_dl_fa_rra")
