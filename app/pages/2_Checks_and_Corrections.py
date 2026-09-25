"""2 · Checks & Corrections — one tab per kind of check, verdict on top (minimum scrolling)."""
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
from app.style import cy_py_note, info_banner, ok_banner, red_alert, section, warn_banner  # noqa: E402
from engine import code_suggest, guidance, package, tb_io  # noqa: E402

state.init_state()
state.page_setup("🔍 Checks & Corrections")
if not state.require_tb():
    st.stop()

tb = state.tb()
valid = state.valid_codes()
ys = state.years()
PAGE_NAMES = {guidance.TB: "1 · Trial Balance", guidance.CHECKS: "2 · Checks & Corrections",
              guidance.DATA: "3 · Company & Report Data"}

# ----------------------------------------------------------- compute all ----
bal = tb_io.balance(tb)
issues = tb_io.line_issues(tb, valid)
dups = tb_io.duplicate_groups(tb)
todo = tb[~tb["code"].isin(valid)]
dep = tb[(tb["code"] == "BS 1.09") & (tb[[f"debit_{y}" for y in ys]].sum(axis=1) > 0)]
targets = state.report_years() if state.view_all() else [state.active_year()]
models = {y: state.model(y) for y in targets}
models_ok = all(m is not None for m in models.values())
ctl_b = sum(c["level"] == "BLOCKING" for m in models.values() if m for c in m["controls"])
ctl_w = sum(c["level"] == "WARNING" for m in models.values() if m for c in m["controls"])
n_line_b = int((issues["Level"] == "BLOCKING").sum()) if not issues.empty else 0

# ---------------------------------------------------------------- verdict ---
if ctl_b or not bal["ok"] or n_line_b:
    red_alert(f"To correct before the final report: {'TB not balanced · ' if not bal['ok'] else ''}"
              f"{n_line_b} blocking line issue(s) · {ctl_b} blocking report control(s). Open the tabs marked ❌.")
elif ctl_w:
    warn_banner(f"No blocking issue — {ctl_w} warning(s) to review. You can generate the report.")
else:
    ok_banner("All checks passed. You can generate the report.")
if state.view_all():
    cy_py_note(all_years=True)
else:
    cy_py_note(state.active_year())


def mark(n_block, n_warn=0):
    return " ❌" if n_block else (" ⚠️" if n_warn else " ✅")


tabs = st.tabs([
    "⚖️ Balance" + mark(not bal["ok"]),
    f"🧾 Line issues ({len(issues)})" + mark(n_line_b, len(issues)),
    f"👯 Duplicates ({len(dups)})" + mark(len(dups)),
    f"🏷️ CIT codes ({len(todo)} to map)" + mark(len(todo)),
    "🛠️ Quick fixes" + mark(len(dep)),
    f"📋 Report controls ({ctl_b}/{ctl_w})" + mark(ctl_b, ctl_w),
])

# ================================================================ balance ===
with tabs[0]:
    st.dataframe(tb_io.balance_table(tb), hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="localized")
                                for c in ("Total debit", "Total credit", "Difference (debit − credit)")})
    if bal["ok"]:
        ok_banner(f"Debits equal credits for every year ({', '.join(map(str, ys))}).")
    else:
        bad = [str(y) for y in ys if not bal[y]["ok"]]
        red_alert(f"The trial balance does not balance in {', '.join(bad)}. " + guidance.advice("TB_NOT_BALANCED")[0])
        st.page_link(guidance.TB, label="→ Correct the lines in 1 · Trial Balance (✏️ Edit lines)", icon="🧾")

# ============================================================ line issues ===
with tabs[1]:
    if issues.empty:
        ok_banner("No issue found on the TB lines.")
    else:
        lv = st.multiselect("Show", ["BLOCKING", "WARNING", "INFO"], default=["BLOCKING", "WARNING"])
        st.dataframe(issues[issues["Level"].isin(lv)], width="stretch", hide_index=True, height=420)

# ============================================================= duplicates ===
with tabs[2]:
    st.caption("A CIT code may be used on several lines (e.g. two bank accounts under BS 3.1.3.2), but each line "
               "needs its own description — the notes list the accounts by name. Merge duplicated lines, or give "
               "each one a clearer description (e.g. 'ACCUMULATED DEPRECIATION — VEHICLES').")
    if not dups:
        ok_banner("Every account description is unique.")
    else:
        red_alert(f"{len(dups)} description(s) used on several lines — blocking until merged or renamed.")
        same = [g for g in dups if g["same_code"]]
        if same and st.button(f"🔗 MERGE ALL {len(same)} GROUP(S) THAT SHARE THE SAME CIT CODE"):
            new = tb.copy()
            for g in sorted(same, key=lambda g: g["rows"][0], reverse=True):
                new = tb_io.merge_lines(new, g["rows"])
            state.set_tb(new)
            st.rerun()
        amts = tb_io.amount_cols(tb)
        for gi, g in enumerate(dups):
            with st.expander(f"“{tb.at[g['rows'][0], 'account']}” — lines {', '.join('#' + str(i + 1) for i in g['rows'])}"
                             f" — code(s) {', '.join(c or '(none)' for c in g['codes'])}", expanded=gi < 3):
                view = tb.loc[g["rows"], ["code", "account"] + amts].copy()
                view.insert(0, "line above", [tb.at[i - 1, "account"] if i > 0 else "" for i in g["rows"]])
                view.index = [i + 1 for i in g["rows"]]
                ed = st.data_editor(view, key=f"arg_dup_{gi}", width="stretch", disabled=["line above", "code"] + amts,
                                    column_config={"line above": st.column_config.TextColumn("Line above (hint)", help="The account just above in the TB — often the asset this line belongs to"),
                                                   "account": st.column_config.TextColumn("Account description (edit to rename)"),
                                                   **{c: st.column_config.NumberColumn(c.replace("_", " "), format="localized") for c in amts}})
                c1, c2 = st.columns(2)
                if c1.button("✏️ SAVE DESCRIPTIONS", key=f"arg_dup_ren_{gi}", type="primary"):
                    new = tb.copy()
                    for line, r in ed.iterrows():
                        new.at[int(line) - 1, "account"] = str(r["account"]).strip()
                    state.set_tb(new)
                    st.rerun()
                if c2.button("🔗 MERGE INTO ONE LINE", key=f"arg_dup_mrg_{gi}", disabled=not g["same_code"],
                             help=None if g["same_code"] else "Lines with different CIT codes cannot be merged — rename them."):
                    state.set_tb(tb_io.merge_lines(tb, g["rows"]))
                    st.rerun()

# ================================================================ mapping ===
with tabs[3]:
    if todo.empty:
        ok_banner("Every TB line has a valid CIT code.")
    else:
        warn_banner(f"{len(todo)} line(s) without a valid CIT code. Suggestions come from the account name: "
                    "<b>check each one, tick CONFIRM and apply</b>. Nothing is applied without confirmation.")
        opts = state.code_options()
        latest = ys[-1]
        rows = []
        for i, r in todo.iterrows():
            sug, why = code_suggest.suggest(r["account"])
            rows.append({"line": i + 1, "account": r["account"] or "(no name)", "current code": r["code"] or "(blank)",
                         f"net {latest}": r[f"debit_{latest}"] - r[f"credit_{latest}"],
                         "code to apply": state.code_label(sug) if sug else "", "why": why, "confirm": False})
        ed = st.data_editor(
            pd.DataFrame(rows), hide_index=True, width="stretch", key="arg_map_editor",
            disabled=["line", "account", "current code", f"net {latest}", "why"],
            column_config={"code to apply": st.column_config.SelectboxColumn("Code to apply", options=opts, width="large"),
                           f"net {latest}": st.column_config.NumberColumn(f"Net {latest} (Dr − Cr)", format="localized"),
                           "confirm": st.column_config.CheckboxColumn("CONFIRM")})
        ca, cb = st.columns([1, 3])
        if ca.button("✅ APPLY CONFIRMED CODES", type="primary"):
            new = tb.copy()
            n = 0
            for _, r in ed.iterrows():
                if r["confirm"] and r["code to apply"]:
                    new.at[int(r["line"]) - 1, "code"] = str(r["code to apply"]).split(" — ")[0]
                    n += 1
            if n:
                state.set_tb(new)
                st.rerun()
            else:
                cb.warning("Tick CONFIRM on the lines to apply (with a code selected).")
        st.caption("Tip: 1 · Trial Balance → 🔎 Find a code searches by keyword, section, group or statement line.")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.popover("👁️ Review the code of every line", width="stretch"):
            st.dataframe(package.account_map_df(tb, state.code_catalogue()), hide_index=True, width="stretch")
    with c2:
        download_button("⬇️ Account ↔ CIT-code map (Excel)", package.account_map_workbook(tb, state.code_catalogue()),
                        package.company_slug(state.project()["meta"].get("company_name")) + "_account_code_map.xlsx",
                        key="arg_dl_accmap")
    with c3:
        download_button("⬇️ Chart of CIT codes (Excel)", package.chart_workbook(state.code_catalogue()),
                        "CIT_codes_chart.xlsx", key="arg_dl_chart")

# ============================================================ quick fixes ===
with tabs[4]:
    if dep.empty:
        ok_banner("No quick fix needed.")
    else:
        section("Accumulated depreciation entered as a debit")
        warn_banner(guidance.advice("ACCDEP_DEBIT")[0])
        st.dataframe(dep[["account"] + tb_io.amount_cols(tb)], width="stretch")
        if st.button("↔️ MOVE BS 1.09 DEBITS TO THE CREDIT COLUMN (every year)"):
            new = tb.copy()
            for i in dep.index:
                for y in ys:
                    d = new.at[i, f"debit_{y}"]
                    if d > 0:
                        new.at[i, f"credit_{y}"] += d
                        new.at[i, f"debit_{y}"] = 0.0
            state.set_tb(new)
            st.rerun()

# ======================================================== report controls ===
with tabs[5]:
    if not models_ok:
        info_banner(st.session_state.get("arg_model_error") or "Statements not computed yet.")
        st.page_link(guidance.DATA, label="→ 3 · Company & Report Data", icon="🏢")
    else:
        def show(items, box):
            seen = set()
            for c_ in items:
                text, page = guidance.advice(c_["id"])
                box(f"<b>{c_['id']}</b> — {c_['message']}" + (f"<br><span style='font-weight:400'>👉 {text}</span>" if text else ""))
                if page and (c_["id"], page) not in seen:
                    seen.add((c_["id"], page))
                    st.page_link(page, label=f"Go to {PAGE_NAMES.get(page, page)}", icon="➡️")

        ytabs = st.tabs([f"CY {y} vs PY {y - 1}" for y in models]) if len(models) > 1 else [st.container()]
        for yt, (y, m) in zip(ytabs, models.items()):
            with yt:
                groups = {lvl: [c_ for c_ in m["controls"] if c_["level"] == lvl] for lvl in ("BLOCKING", "WARNING", "INFO")}
                m1, m2, m3 = st.columns(3)
                m1.metric("Blocking", len(groups["BLOCKING"]))
                m2.metric("Warnings", len(groups["WARNING"]))
                m3.metric("Information", len(groups["INFO"]))
                if groups["BLOCKING"]:
                    with st.expander(f"❌ Must be corrected ({len(groups['BLOCKING'])})", expanded=True):
                        show(groups["BLOCKING"], red_alert)
                if groups["WARNING"]:
                    with st.expander(f"⚠️ To review ({len(groups['WARNING'])})", expanded=not groups["BLOCKING"]):
                        show(groups["WARNING"], warn_banner)
                with st.expander(f"ℹ️ Information ({len(groups['INFO'])})"):
                    for c_ in groups["INFO"]:
                        st.markdown(f"- `{c_['id']}` {c_['message']}")
        if not ctl_b:
            st.page_link("pages/5_Generate_and_Download.py", label="→ 5 · Generate & Download", icon="📦")
