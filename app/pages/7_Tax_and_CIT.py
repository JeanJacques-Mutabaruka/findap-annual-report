"""7 · Tax & CIT — taxable income explained, RRA CIT annex (BS / P&L), code <-> RRA mapping, RRA file update check."""
from __future__ import annotations

import json
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
from engine import package, rra, tax_cit  # noqa: E402

state.init_state()
state.page_setup("🏛️ Tax & CIT")

chart = state.chart()
R = rra.load()
company = state.project()["meta"].get("company_name") or "Company"
slug = package.company_slug(company)


def money_view(df: pd.DataFrame, cols: list[str], pct_rows: set[int] | None = None) -> pd.io.formats.style.Styler:
    """Amounts as text in accounting style, negatives red in brackets."""
    out = df.copy()
    for c in cols:
        out[c] = [("" if v is None or (isinstance(v, float) and pd.isna(v)) else
                   (f"{float(v):.2%}" if pct_rows and i in pct_rows else fmt_acc(v))) for i, v in zip(out.index, out[c])]
    return out.style.map(lambda v: "color:#C00000" if isinstance(v, str) and v.startswith("(") else "", subset=cols)


tabs = st.tabs(["🧮 Taxable income", "🏛️ RRA annex (BS / P&L)", "🔗 CIT codes ↔ RRA", "🔄 Check an RRA annexure file"])

# ======================================================== taxable income ===
with tabs[0]:
    if not state.require_tb():
        pass
    else:
        y = state.active_year()
        m = state.model(y)
        if m is None:
            info_banner(st.session_state.get("arg_model_error") or "Statements not computed yet.")
        else:
            det = m["income_tax"]["detail"]
            warns = tax_cit.tax_warnings(m)
            from engine import fixed_assets as fa_
            reg_ = fa_.register_from_records(state.project().get("asset_register"))
            if not reg_.empty:
                s_ = fa_.settings_of(state.project())
                bt_ = fa_.book_vs_tax(fa_.book_schedule(reg_, chart, s_, y), fa_.tax_schedule(reg_, chart, s_, y), [y - 1, y])
                warns = [w_ for w_ in warns if not w_.startswith("Depreciation:")]
                for _, r_ in bt_.iterrows():
                    if abs(r_["Difference (tax − book)"]) > 1:
                        warns.append(f"{int(r_['Year'])}: tax depreciation (RRA pools) {r_['Tax depreciation (RRA pools)']:,.0f} "
                                     f"≠ book depreciation {r_['Book depreciation (straight-line)']:,.0f} (difference "
                                     f"{r_['Difference (tax − book)']:,.0f}) — not yet reflected in the taxable income.")
            explain_box("How the taxable income is calculated", """
<b>1. Profit before tax</b> — from the P&amp;L: every P&amp;L code of the trial balance, credit − debit.<br>
<b>2. Grant received</b> — kept at 0 for the moment (treatment of grants to be designed).<br>
<b>3. Non-admissible expenses</b> (RRA P&amp;L 11) — <i>coefficient × (debit − credit)</i> of each code listed; management
fees: only <i>max(0, fees − 2% × turnover)</i>, turnover = all revenues (codes PL 01… and PL 08…, RRA P&amp;L 1 + 8).<br>
<b>4. Non-taxable income</b> — dividends received (RRA P&amp;L 12) in full; farming and livestock income (RRA P&amp;L 13)
up to 12,000,000.<br>
<b>5. Tax losses</b> (RRA P&amp;L 14) — losses of the previous years (5 by default, or the client's extension), oldest
first, entered per year of origin on <i>3 · Company &amp; Report Data → Period &amp; tax</i>; deducted up to the taxable
income before losses.<br>
<b>6. Tax charge</b> (RRA P&amp;L 16) — companies: tax base × CIT rate if positive; individuals: brackets.<br>
<b>7. Income tax payable</b> = tax charge − quarterly prepayments − withholding tax.<br><br>
All rates, limits and codes are parameters in one place (<i>data/chart_of_accounts.json → income_tax</i>). The Excel
download rebuilds every step with <b>live formulas</b> on a TB sheet; inputs are in blue on yellow, and two check
columns compare each step with the app.""", warns)
            df = tax_cit.taxable_income_df(m)
            pct = set(df.index[df["Step"] == "CIT rate"])
            view = df.drop(columns=["kind"]).rename(columns={"CY": f"CY {m['meta']['year_cy']}", "PY": f"PY {m['meta']['year_py']}"})
            ycols = [c for c in view.columns if c.startswith(("CY", "PY"))]
            view["Coefficient"] = [f"{v:.0%}" if isinstance(v, (int, float)) and not pd.isna(v) else "" for v in view["Coefficient"]]
            st.dataframe(money_view(view, ycols, pct), hide_index=True, width="stretch", height=min(38 * (len(view) + 1), 880),
                         column_config={"How it is computed": st.column_config.TextColumn(width="large")})
            from engine import multiyear
            sched = multiyear.loss_schedule(state.project(), state.tb(), chart)
            sched["years_list"] = sorted(sched["by_year"])
            if sched["origins"]:
                section("Tax losses — by year of origin")
                st.dataframe(pd.DataFrame([{"Year of origin": str(o["year"]), "Tax loss": o["loss"], "Source": o["source"],
                                            "Used before the TB years": o["used_before"],
                                            **{f"Used in {yy}": o["used_by_year"].get(yy, 0.0) for yy in sched["years_list"]},
                                            "Usable until": str(o["expires_after"]), "Remaining": o["remaining"]}
                                           for o in sched["origins"]]), hide_index=True, width="stretch")
            download_button("⬇️ Taxable income — Excel with formulas", tax_cit.tax_workbook(m, state.pair_input(y)["trial_balance"],
                            chart, company, sched), f"{slug}_taxable_income_{y}.xlsx", key="arg_dl_tax", primary=True)

# ============================================================== RRA annex ===
with tabs[1]:
    if state.require_tb():
        y = state.active_year()
        m = state.model(y)
        if m is None:
            info_banner(st.session_state.get("arg_model_error") or "Statements not computed yet.")
        else:
            rows = state.pair_input(y)["trial_balance"]
            table = tax_cit.rra_df(chart, R, rows, m)
            rec = tax_cit.reconciliation_df(table, m)
            bad = rec[rec["Difference"].abs() > 1]
            unlinked = [ln["code"] for ln in tax_cit.chart_lines(chart) if not ln.get("rra")]
            used_unlinked = sorted({r["code"] for r in rows if r.get("code") in unlinked and
                                    (abs(float(r.get("debit_cy") or 0)) + abs(float(r.get("credit_cy") or 0))) > 1})
            w = []
            if used_unlinked:
                w.append(f"The TB uses code(s) with no RRA line yet ({', '.join(used_unlinked)}) — their amounts are NOT in the "
                         "RRA annex. Their RRA line is to be decided (tab 🔗 CIT codes ↔ RRA).")
            w.append("Lines 12, 13, 17, 18, 19, 20 and 21 of the RRA P&L are not computed by the app (not in the V11 tool) — "
                     "they stay empty.")
            rra_tabs = st.tabs(["ℹ️ How it's built & reconciliation", "🏛️ RRA Balance sheet", "🏛️ RRA Profit and loss"])
            with rra_tabs[0]:
                explain_box("How the RRA annex is built", f"""
Every CIT code of the app is linked to one line of the RRA annexure (<i>{R.get('source', '')}</i>). A code that the
RRA file does not have is a <b>sub-code</b> (one more level, e.g. <i>PL 05.08.02</i>) and is added to the RRA line
above it (<i>5.8</i>).<br>
<b>Lines</b>: sum of the TB lines linked to them, shown on their usual side (assets and expenses as debit − credit;
liabilities, equity, revenues, closing stock and accumulated depreciation as credit − debit).<br>
<b>Totals</b>: the formula written in the RRA description (e.g. <i>1 = 1.1 to 1.9 − 1.10 + 1.11</i>, <i>10 = 4 − 9</i>);
without a formula, the sum of the lines below. Cost of sales (P&amp;L 2) = 2.1 + 2.2 + 2.3 + 2.4 − 2.5 (app
assumption: the RRA file gives no formula).<br>
<b>From the app</b>: profit of the year (BS 5.8), income-tax provision (BS 8.2.1), added back (P&amp;L 11), loss carried
forward (P&amp;L 14), income tax (P&amp;L 16). P&amp;L 15 follows the RRA formula (10 + 11 − 12 − 13) — it does not
deduct the loss carried forward, unlike the tax base of the annual report.<br>
<b>Check</b>: the key figures are compared with the annual report below; RRA BS 10 (assets − (equity + liabilities))
must be 0.""", w)
                if bad.empty:
                    ok_banner("The RRA annex and the annual report give the same total assets, gross profit, profit before "
                              "tax and income tax.")
                else:
                    red_alert(f"{len(bad)} difference(s) between the RRA annex and the annual report — see the table below.")
                st.dataframe(money_view(rec, ["Annual report", "RRA annex", "Difference"]), hide_index=True, width="stretch")
                download_button("⬇️ RRA annex (BS + P&L) — Excel with formulas",
                                tax_cit.rra_workbook(chart, R, rows, m, company), f"{slug}_RRA_CIT_annex_{y}.xlsx",
                                key="arg_dl_rra", primary=True)
            for tab, sh, lab in ((rra_tabs[1], "BS", "Balance sheet"), (rra_tabs[2], "PL", "Profit and loss")):
                with tab:
                    v = table[table["Sheet"] == sh].drop(columns=["Sheet"]).rename(
                        columns={"CY": f"CY {m['meta']['year_cy']}", "PY": f"PY {m['meta']['year_py']}"})
                    ycols = [c for c in v.columns if c.startswith(("CY", "PY"))]
                    st.dataframe(money_view(v, ycols).apply(
                        lambda r: ["font-weight:700;background:#EAF1F8" if r["Kind"] == "total" else "" for _ in r], axis=1),
                        hide_index=True, width="stretch", height=620)

# ========================================================== codes <-> RRA ===
with tabs[2]:
    mp = tax_cit.mapping_df(chart, R)
    todo = mp[mp["Link"].str.startswith("⚠️")]
    explain_box("CIT code format and link to the RRA annexure", """
<b>Format</b>: <i>BS</i> or <i>PL</i> + the RRA <i>Serial No</i> with every level on 2 digits — RRA 1.10 → <b>BS 01.10</b>,
RRA 4.1 → <b>PL 04.01</b>, RRA 3.1.3.1 → <b>BS 03.01.03.01</b>. Codes are text, sort correctly and cannot be confused
with a number in Excel (4.1 vs 4.10).<br>
<b>Sub-codes</b>: a line the RRA file does not have gets one more level under the RRA line it is reported in —
e.g. <i>PL 05.08.02 Fines and penalties</i> → RRA 5.8; <i>BS 03.01.04.01 VAT receivables</i> → RRA 3.1.4. The annual
report keeps them as separate lines; the RRA annex adds them to their parent.<br>
<b>Old codes</b> (V11 format, one digit before the first dot, e.g. <i>BS 1.09</i>) are converted automatically when a TB,
a project or a V11 workbook is loaded — with a message listing the renumbered lines (V11 had no RRA 1.7 IT
equipment line, so BS 1.07–1.10 moved by one; PL 6.06–6.10 and 8.11–8.14 were renumbered too).<br>
<b>RRA file</b>: the RRA serial is identified by its <i>row</i> in the annexure, because the P&amp;L sheet stores serials
as numbers (4.10 reads 4.1) and the balance sheet gives 3.1.3.1 to both cash and bank balances.""",
                [f"{len(todo)} code(s) have no RRA line yet: " + ", ".join(f"{r['CIT code']} {r['Statement line (report)']}"
                                                                         for _, r in todo.iterrows())] if len(todo) else None)
    q = st.text_input("Filter (code, line, RRA serial or description)", key="arg_map_q")
    v = mp
    if q.strip():
        hay = mp.astype(str).agg(" ".join, axis=1).str.lower()
        v = mp[hay.apply(lambda h: all(w in h for w in q.lower().split()))]
    st.dataframe(v.style.apply(lambda r: ["color:#C00000;font-weight:700" if str(r["Link"]).startswith("⚠️") else
                                          ("background:#FFF8E1" if "sub-code" in str(r["Link"]) else "") for _ in r], axis=1),
                 hide_index=True, width="stretch", height=520)
    st.caption(f"{len(v)} of {len(mp)} codes · yellow = sub-code (rolls up into its RRA line) · red = RRA line to decide")
    download_button("⬇️ CIT codes ↔ RRA mapping (Excel)", tax_cit.mapping_workbook(chart, R), "CIT_codes_RRA_mapping.xlsx",
                    key="arg_dl_map")

# ======================================================= RRA file check ===
with tabs[3]:
    explain_box("Why check a new RRA annexure file", f"""
RRA updates its CIT annexure from time to time: new lines, lines removed, wording or numbering changed. The app's codes
are mapped to <i>{R.get('source', '')}</i>. Upload the latest annexure (.xlsm / .xlsx, as downloaded from e-tax): the app
reads the <b>BALANCE_SHEET</b> and <b>PROFIT_AND_LOSS</b> sheets and compares every line with the mapping.<br>
<b>Nothing changes by itself.</b> You get the list of differences and the updates the app proposes (new codes in the
same format, codes to re-link, labels to check). Lines that only moved to another row are updated in the files
offered for download.<br>
<b>To apply the update</b> (administrator): download the two data files and replace <i>data/rra_annexure.json</i> and
<i>data/chart_of_accounts.json</i> in the GitHub repository (Add file → Upload files → Commit); the app restarts with
the new mapping. New codes still need their place in the statements (group, note) — check the proposals first.""")
    f = st.file_uploader("RRA CIT annexure (.xlsm / .xlsx)", type=["xlsm", "xlsx"], key="arg_rra_file")
    if f is not None:
        try:
            new = rra.parse_workbook(f.getvalue())
            new["source"] = f.name
        except Exception as e:  # noqa: BLE001
            red_alert(f"This file cannot be read as an RRA annexure: {e}")
            new = None
        if new:
            links: dict[str, list[str]] = {}
            for ln in tax_cit.chart_lines(chart):
                if ln.get("rra"):
                    links.setdefault(f"{ln['rra']['sheet']}:{ln['rra']['row']}", []).append(ln["code"])
            res = rra.compare(R, new, links)
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Unchanged", res["same"])
            k2.metric("New in RRA", len(res["added"]))
            k3.metric("Removed", len(res["removed"]))
            k4.metric("Wording changed", len(res["changed"]))
            k5.metric("Moved rows", len(res["moved"]))
            if not (res["added"] or res["removed"] or res["changed"] or res["moved"]):
                ok_banner(f"<b>{f.name}</b> has the same balance-sheet and P&amp;L lines as the mapping — nothing to update.")
            else:
                red_alert("The uploaded RRA file differs from the app's mapping. Review the proposals below and send them to "
                          "the administrator — the mapping is not updated automatically.")
                st.dataframe(pd.DataFrame(res["proposals"]), hide_index=True, width="stretch")
                c1, c2, c3 = st.columns(3)
                with c1:
                    download_button("⬇️ Change report (Excel)", tax_cit.compare_workbook(res), "RRA_annexure_changes.xlsx",
                                    key="arg_dl_rra_cmp", primary=True)
                with c2:
                    download_button("⬇️ New data/rra_annexure.json", json.dumps(new, indent=1, ensure_ascii=False).encode("utf-8"),
                                    "rra_annexure.json", key="arg_dl_rra_json")
                with c3:
                    download_button("⬇️ data/chart_of_accounts.json (moved rows updated)",
                                    json.dumps(rra.relinked_chart(chart, R, new), indent=1, ensure_ascii=False).encode("utf-8"),
                                    "chart_of_accounts.json", key="arg_dl_chart_json")
                if res["added"] or res["removed"] or res["changed"]:
                    warn_banner("New, removed or re-worded lines need a decision (code, group, note in the statements) before "
                                "the chart file is replaced — see the <b>Proposals</b> sheet of the change report.")
