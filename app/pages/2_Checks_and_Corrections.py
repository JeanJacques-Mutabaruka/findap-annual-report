"""2 · Checks & Corrections — one tab per kind of check, verdict on top (minimum scrolling)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import line_tools, state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.style import cy_py_note, info_banner, ok_banner, red_alert, section, warn_banner  # noqa: E402
from engine import ai_prompt, code_suggest, guidance, package, tb_io  # noqa: E402

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
dep = tb[(tb["code"] == "BS 01.10") & (tb[[f"debit_{y}" for y in ys]].sum(axis=1) > 0)]
zeros = tb_io.zero_lines(tb)
negs = [i for i in tb.index for y in ys for s_ in ("debit", "credit") if float(tb.at[i, f"{s_}_{y}"] or 0) < -1]
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
    "🛠️ Quick fixes" + (f" · 🧹 {len(zeros)} zero line(s)" if zeros else "") + mark(len(dep) + len(set(negs))),
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
        if zeros:
            st.caption(f"🧹 {len(zeros)} line(s) have 0 in every year — delete them in one click in the 🛠️ Quick fixes tab.")

# ============================================================= duplicates ===
with tabs[2]:
    st.caption("A CIT code may be used on several lines (e.g. two bank accounts under BS 03.01.03.02), but each line "
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
        warn_banner(f"{len(todo)} line(s) without a valid CIT code. Suggestions come from the account name <b>and the "
                    "direction of the balance</b> (e.g. a bank account in credit → overdraft): <b>check each one, tick "
                    "CONFIRM and apply</b>. Nothing is applied without confirmation.")
        opts = state.code_options()
        cat_ = state.code_catalogue()
        latest = ys[-1]
        ICON = {"High": "🟢 High", "Medium": "🟡 Medium", "Low": "🔴 Low"}
        rows, props = [], {}
        for i, r in todo.iterrows():
            p_ = code_suggest.propose(r["account"], tb_io.line_net(tb, i), cat_)
            props[i + 1] = p_
            rows.append({"line": i + 1, "account": r["account"] or "(no name)", "current code": r["code"] or "(blank)",
                         f"net {latest}": r[f"debit_{latest}"] - r[f"credit_{latest}"],
                         "code to apply": state.code_label(p_["code"]) if p_["code"] else "",
                         "confidence": ICON[p_["confidence"]] if p_["code"] else "⚪ none",
                         "why": p_["reason"], "alternative": state.code_label(p_["alternative"]) if p_["alternative"] else "",
                         "confirm": False})
        n_conf = {k: sum(1 for p_ in props.values() if p_["code"] and p_["confidence"] == k) for k in ICON}
        n_none = sum(1 for p_ in props.values() if not p_["code"])
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🟢 High", n_conf["High"], help="Name and balance direction point to one code")
        k2.metric("🟡 Medium", n_conf["Medium"], help="Likely code — another one is possible (see Alternative)")
        k3.metric("🔴 Low", n_conf["Low"], help="Unusual balance or generic name — check carefully")
        k4.metric("⚪ No suggestion", n_none, help="Choose the code in the list, or use 1 · Trial Balance → 🔎 Find a code")
        o1, o2, o3 = st.columns(3)
        pre_hi = o1.toggle("Pre-tick CONFIRM on 🟢 High suggestions", value=False, key="arg_map_pretick",
                           help="Ticks CONFIRM for the high-confidence lines — review them, then APPLY.")
        only_doubt = o2.toggle("Show only the lines to review (Medium / Low / none)", value=False, key="arg_map_doubts")
        write_com = o3.toggle("Write the doubts in the Comments column", value=True, key="arg_map_comments",
                              help="For Medium / Low lines, the proposal, its reason and the alternative are added to "
                                   "the line's comment when the code is applied — you keep a trace for the review.")
        df_map = pd.DataFrame(rows)
        if pre_hi:
            df_map["confirm"] = df_map["confidence"].eq(ICON["High"])
        if only_doubt:
            df_map = df_map[~df_map["confidence"].eq(ICON["High"])]
        ed = st.data_editor(
            df_map, hide_index=True, width="stretch", key=f"arg_map_editor_{int(pre_hi)}{int(only_doubt)}",
            height=min(38 * (len(df_map) + 1), 420),
            disabled=["line", "account", "current code", f"net {latest}", "confidence", "why", "alternative"],
            column_config={"code to apply": st.column_config.SelectboxColumn("Code to apply", options=opts, width="large"),
                           f"net {latest}": st.column_config.NumberColumn(f"Net {latest} (Dr − Cr)", format="localized"),
                           "confidence": st.column_config.TextColumn("Confidence"),
                           "why": st.column_config.TextColumn("Why", width="large"),
                           "alternative": st.column_config.TextColumn("Alternative"),
                           "confirm": st.column_config.CheckboxColumn("CONFIRM")})
        ca, cb = st.columns([1, 3])
        if ca.button("✅ APPLY CONFIRMED CODES", type="primary"):
            new = tb.copy()
            n = 0
            for _, r in ed.iterrows():
                if r["confirm"] and r["code to apply"]:
                    i = int(r["line"]) - 1
                    code = str(r["code to apply"]).split(" — ")[0]
                    new.at[i, "code"] = code
                    p_ = props.get(int(r["line"]), {})
                    if write_com and p_.get("comment") and code == p_.get("code"):
                        old_c = tb_io.clean_text(new.at[i, "comment"])
                        if p_["comment"] not in old_c:
                            new.at[i, "comment"] = (old_c + " | " if old_c else "") + p_["comment"]
                    n += 1
            if n:
                state.set_tb(new)
                st.rerun()
            else:
                cb.warning("Tick CONFIRM on the lines to apply (with a code selected).")
        st.caption("Tip: 1 · Trial Balance → 🔎 Find a code searches by keyword, section, group or statement line. "
                   "Many lines to map? Use the AI mapping prompt (button below) with any AI assistant, then re-upload the TB.")
    c1, c2, c3, c4 = st.columns(4)
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
    with c4:
        with st.popover("🤖 AI mapping prompt", width="stretch"):
            st.markdown("Attach **your TB (Excel)** and **this file** in any AI assistant and ask it to follow the prompt. "
                        "You get back the TB with a CIT code, a confidence level and comments on every doubtful line — "
                        "upload it on 1 · Trial Balance.")
            warn_banner("<b>Confidentiality</b> — the TB is sent to the AI provider you choose. Check that your firm "
                        "and your client allow it.")
            download_button("⬇️ Download the prompt (.md)", ai_prompt.build_bytes(state.code_catalogue()),
                            ai_prompt.FILE_NAME, key="arg_dl_prompt_p2")

# ============================================================ quick fixes ===
with tabs[4]:
    line_tools.undo_box("arg_del_p2")
    if dep.empty and not zeros and not negs:
        ok_banner("No quick fix needed.")
    if negs:
        section("Negative amounts")
        warn_banner(f"<b>{len(set(negs))} line(s)</b> have a negative debit or credit — accepted as exceptions, but a "
                    "negative debit is normally a credit (and vice versa). Moving them keeps every balance unchanged.")
        if st.button("↔️ MOVE THE NEGATIVE AMOUNTS TO THE OTHER SIDE (every year)", key="arg_fix_negs"):
            new_tb, n_ = tb_io.move_negatives(tb)
            state.set_tb(new_tb)
            st.rerun()
    if zeros:
        section("Lines with 0 in every year")
        line_tools.zero_lines_panel("arg_del_p2")
        st.caption("To delete other lines: 1 · Trial Balance → 🗑️ Delete lines.")
    if not dep.empty:
        section("Accumulated depreciation entered as a debit")
        warn_banner(guidance.advice("ACCDEP_DEBIT")[0])
        st.dataframe(dep[["account"] + tb_io.amount_cols(tb)], width="stretch")
        if st.button("↔️ MOVE BS 01.10 DEBITS TO THE CREDIT COLUMN (every year)"):
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
