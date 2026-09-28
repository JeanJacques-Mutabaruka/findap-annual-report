"""9 · Stock Control — stock form per year (template / upload), movement by item and category, losses, reconciliation with
the TB, Excel with formulas."""
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
from engine import package, stock  # noqa: E402

state.init_state()
state.page_setup("📦 Stock Control")
if not state.require_tb():
    st.stop()

chart = state.chart()
proj = state.project()
company = proj["meta"].get("company_name") or "Company"
slug = package.company_slug(company)
ys = sorted(state.years(), reverse=True)
year = st.selectbox("Financial year of the stock form", ys, index=ys.index(state.active_year()) if state.active_year() in ys else 0,
                    key="arg_stock_year")
forms = proj.setdefault("stock", {})
form = forms.get(str(year)) or {}
tb = state.tb()
tb_stock = sum(float(tb[tb["code"] == c["code"]][f"debit_{year}"].sum() - tb[tb["code"] == c["code"]][f"credit_{year}"].sum())
               for c in stock.cats(chart))


def styled(df, money):
    v = df.copy()
    for c in money:
        v[c] = [fmt_acc(x) if x is not None and not (isinstance(x, float) and pd.isna(x)) else "" for x in v[c]]
    return v.style.map(lambda x: "color:#C00000" if isinstance(x, str) and x.startswith("(") else "", subset=money)


warns = []
if not form.get("items"):
    if abs(tb_stock) > 1:
        warns.append(f"The TB shows inventories of {fmt_acc(tb_stock)} for {year} but no stock form is loaded — the figure "
                     "is not explained. Send the template to the client.")
    else:
        warns.append(f"No stock form for {year}.")
explain_box("How the stock is checked", f"""
<b>Stock form</b> (one per year, item level, grouped by the RRA inventory categories 3.1.1.1–3.1.1.4): items, opening stock,
movements IN (purchases), movements OUT — <b>sales at cost</b> and <b>losses / damages</b> (theft, damage, expiry, fire or
other unforeseen event, each with its <b>date</b>, <b>supporting document number</b> and a comment) — and the closing stock
<b>counted</b>.<br>
<b>Per item</b>: expected closing = opening + in − sales − losses, compared with the count (quantities and values). A
difference is a stock gain / loss not explained by the losses sheet.<br>
<b>Reconciliation with the TB</b>: closing stock per category = inventories of the balance sheet of {year}; opening stock =
inventories of {year - 1}; purchases = PL 02.02.01 (+ imports PL 02.02.01.01); when the TB uses the P&amp;L stock lines
(PL 02.01 opening / PL 02.05 closing), they are checked too.<br>
<b>Note 12</b> (inventory movement) is built from the form when its closing stock equals the TB inventories:
opening, purchases, cost of sales (sales at cost) and gain/(loss) = losses + count differences.""", warns)

tabs = st.tabs(["📄 Template & upload", "📊 Movement by item & category", "🚨 Losses & damages", "⚖️ Reconciliation with the TB"])

with tabs[0]:
    section(f"Template {year}")
    st.markdown("Excel form with the sheets **Items**, **Opening stock**, **IN - Purchases**, **OUT - Sales**, "
                "**OUT - Losses & damages** and **Closing stock**, drop-down lists for the categories and the loss events, "
                "and the instructions. Pre-filled when a form is already loaded for the year.")
    download_button(f"⬇️ Download the stock form {year} (Excel)", stock.template_workbook(chart, year, form),
                    f"{slug}_stock_form_{year}.xlsx", key="arg_dl_stock_tpl", primary=True)
    section("Upload the filled form")
    f = st.file_uploader("Stock form (.xlsx)", type=["xlsx", "xlsm"], key=f"arg_stock_up_{year}")
    if f is not None:
        try:
            new = stock.parse_workbook(f.getvalue())
            iss = stock.issues(new, chart)
            st.caption(f"{len(new['items'])} item(s), {len(new['in'])} purchase line(s), {len(new['sales'])} sale line(s), "
                       f"{len(new['losses'])} loss line(s) read from {f.name}.")
            if len(iss):
                st.dataframe(iss, hide_index=True, width="stretch", height=min(38 * (len(iss) + 1), 300))
            if st.button(f"✅ USE THIS FORM FOR {year}", type="primary"):
                forms[str(year)] = new
                state.mark_dirty()
                st.rerun()
        except Exception as e:  # noqa: BLE001
            red_alert(f"This file cannot be read as a stock form: {e}")
    if form.get("items"):
        iss = stock.issues(form, chart)
        (ok_banner if iss.empty else warn_banner)(f"Stock form {year}: {len(form['items'])} item(s)" +
                                                  ("" if iss.empty else f" — {len(iss)} issue(s)"))
        if len(iss):
            st.dataframe(iss, hide_index=True, width="stretch", height=min(38 * (len(iss) + 1), 300))
        if st.button(f"🗑️ REMOVE THE STOCK FORM OF {year}"):
            forms.pop(str(year), None)
            state.mark_dirty()
            st.rerun()

with tabs[1]:
    if not form.get("items"):
        info_banner("No stock form loaded for this year.")
    else:
        mv = stock.movement(form, chart)
        section("By category")
        bc = stock.by_category(mv, chart)
        st.dataframe(styled(bc, [c for c in bc.columns if c not in ("Code", "Category")]), hide_index=True, width="stretch")
        diffs = mv[mv["Qty difference"].abs() > 1e-9]
        if len(diffs):
            warn_banner(f"{len(diffs)} item(s) where the count differs from the expected closing stock — unexplained gain/"
                        f"(loss) of {fmt_acc(mv['Value difference'].sum())}.")
        section("By item")
        q = st.text_input("Filter (item code or name)", key="arg_stock_q")
        cs = st.multiselect("Categories", [c["code"] for c in stock.cats(chart)], key="arg_stock_cats")
        v = mv
        if q.strip():
            v = v[(v["Item"] + " " + v["Name"]).str.lower().str.contains(q.lower().strip(), regex=False)]
        if cs:
            v = v[v["Category"].isin(cs)]
        money = [c for c in v.columns if "value" in c.lower() or c == "Value difference"]
        st.dataframe(styled(v, money), hide_index=True, width="stretch", height=440)
        download_button(f"⬇️ Stock {year} — Excel with formulas (form, movement by item and category, reconciliation)",
                        stock.export_workbook(form, chart, year, tb, company), f"{slug}_stock_{year}.xlsx",
                        key="arg_dl_stock_x", primary=True)

with tabs[2]:
    losses = pd.DataFrame(form.get("losses") or [])
    if losses.empty:
        info_banner("No losses or damages declared for this year.")
    else:
        items = {r["item"]: r for r in form.get("items", [])}
        losses["name"] = losses["item"].map(lambda i: (items.get(i) or {}).get("name", ""))
        view = losses[["date", "item", "name", "qty", "unit_cost", "value", "event", "doc_no", "comment"]].rename(
            columns={"date": "Date", "item": "Item", "name": "Name", "qty": "Quantity", "unit_cost": "Unit cost",
                     "value": "Value", "event": "Event", "doc_no": "Supporting document", "comment": "Comments"})
        st.caption(f"{len(view)} loss(es) — total {fmt_acc(view['Value'].fillna(0).sum())}")
        miss = view[(view["Supporting document"] == "") | view["Date"].isna()]
        if len(miss):
            red_alert(f"{len(miss)} loss(es) without date or supporting document — they cannot be justified to the tax "
                      "authority or the auditor.")
        st.dataframe(styled(view, ["Value"]), hide_index=True, width="stretch")
        by_ev = view.groupby("Event", dropna=False)["Value"].sum().reset_index()
        st.dataframe(styled(by_ev, ["Value"]), hide_index=True)

with tabs[3]:
    if not form.get("items"):
        info_banner("No stock form loaded for this year.")
    else:
        rec = stock.reconcile(form, tb, chart, year)
        bad = rec[~rec["OK"]]
        if bad.empty:
            ok_banner("The stock form reconciles with the trial balance.")
        else:
            red_alert(f"{len(bad)} difference(s) between the stock form and the TB (red lines).")
        st.dataframe(styled(rec, ["Stock form", "Trial balance", "Difference"]).apply(
            lambda r: ["color:#C00000;font-weight:700" if not r["OK"] else "" for _ in r], axis=1),
            hide_index=True, width="stretch")
        im, why = stock.note12_from_project(proj, tb, chart, year)
        (ok_banner if im else warn_banner)(f"Note 12 for {year}: {why}.")
