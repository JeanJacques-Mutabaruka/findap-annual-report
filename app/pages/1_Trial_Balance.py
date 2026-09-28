"""1 · Trial Balance — template, upload & map (any number of years), resume a project, V11 import, edit lines."""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import line_tools, state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.formatting import fmt  # noqa: E402
from app.style import cy_py_note, info_banner, ok_banner, red_alert, section, warn_banner  # noqa: E402
from engine import ai_prompt, company_data, package, tb_io, xlsm_import  # noqa: E402

state.init_state()
state.page_setup("🧾 Trial Balance")


def balance_summary() -> None:
    bt = tb_io.balance_table(state.tb())
    st.dataframe(bt, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="localized")
                                for c in ("Total debit", "Total credit", "Difference (debit − credit)")})
    if tb_io.balance(state.tb())["ok"]:
        ok_banner("The trial balance balances for every year.")
    else:
        red_alert("The trial balance does <b>not</b> balance for every year (see ❌ above). Correct it in the "
                  "<b>✏️ Edit TB</b> tab or re-export it, then go to <b>2 · Checks & Corrections</b>.")


def ai_prompt_block(key: str) -> None:
    st.markdown("Your TB has no CIT codes? Download this prompt, then in **any AI assistant** attach **your TB (Excel)** "
                "and **the prompt file**, and ask it to *follow the prompt*. You get back the same TB with a **CIT code** "
                "for every line, a **confidence** level and, where there is a doubt, a proposal and an explanation in "
                "the **Comments** column. Upload that file here (📤 Upload TB) and review the Medium / Low lines.")
    warn_banner("<b>Confidentiality</b> — the trial balance is sent to the AI provider you choose. Check that your firm "
                "and your client allow it.")
    st.caption("Without an AI: upload the TB as it is — page 2 · Checks & Corrections → 🏷️ CIT codes suggests a code "
               "for every line from its name and balance, with a confidence level.")
    download_button("⬇️ Download the AI mapping prompt (.md)", ai_prompt.build_bytes(state.code_catalogue()),
                    ai_prompt.FILE_NAME, key=key)


tabs = st.tabs(["📤 Upload TB", "📄 TB template & AI prompt", "📂 Resume / Excel generator", "🔎 Find a code",
               "✏️ Edit lines", "🗑️ Delete lines", "📅 Years"])

# ================================================================== upload ==
with tabs[0]:
    section("Upload the trial balance")
    st.caption("Excel (.xlsx / .xls / .xlsm) or CSV. One line per account, all years on the same line — "
               "Debit/Credit columns per year, or one signed balance column per year. Any number of years "
               "(e.g. 5). No file yet? Download the template in the 📄 TB template tab. No CIT codes in your TB? "
               "The app suggests them on page 2 — or map the TB first with any AI using the prompt of the 📄 tab.")
    f = st.file_uploader("Trial balance file", type=["xlsx", "xls", "xlsm", "csv"], key="arg_tb_file")
    raw = None
    if f is not None:
        data, name = f.getvalue(), f.name
        try:
            sheets = tb_io.sheet_names(data, name)
        except Exception as e:  # noqa: BLE001
            sheets = None
            red_alert(f"This file cannot be read: {e}")
        if sheets:
            found = tb_io.tb_sheets(data, name)
            show_all = False
            if len(found) > 1:
                info_banner(f"This file contains <b>{len(found)} trial balances</b>. Choose the one to use:")
                st.dataframe(pd.DataFrame([{"Sheet": f_["sheet"], "Years": ", ".join(map(str, f_["years"])),
                                            "Lines": f_["lines"], "Balanced": "✅" if f_["balanced"] else "❌"}
                                           for f_ in found]), hide_index=True, width="stretch")
                show_all = st.checkbox("Show every sheet of the file", value=False)
            choices = sheets if (show_all or not found) else [f_["sheet"] for f_ in found]
            default_sheet = 0 if found and not show_all else next(
                (i for i, s in enumerate(choices) if re.search(r"trial|balance|tb", s, re.I)), 0)
            c1, c2 = st.columns([2, 1])
            sheet = c1.selectbox("Trial balance to use (sheet)" if len(found) > 1 else "Sheet", choices, index=default_sheet)
            sheet_arg = 0 if sheet == "(csv)" else sheet
            header = c2.number_input("Header row (row holding the column titles)", min_value=1, max_value=50,
                                     value=tb_io.guess_header_row(data, name, sheet_arg), step=1)
            try:
                raw = tb_io.read_table(data, name, sheet_arg, int(header))
            except Exception as e:  # noqa: BLE001
                red_alert(f"Could not read that sheet/header row: {e}")
    if raw is not None:
        with st.expander(f"Preview — {len(raw)} rows", expanded=False):
            st.dataframe(raw.head(30), width="stretch")

        section("Column mapping")
        guess = tb_io.guess_mapping(list(raw.columns))
        opts = ["(none)"] + list(raw.columns)

        def pick(label, g, key, col, help_=None, hidden=False):
            return col.selectbox(label, opts, index=opts.index(g) if g in opts else 0, key=key, help=help_,
                                 label_visibility="collapsed" if hidden else "visible")

        c = st.columns(3)
        m_code = pick("CIT code", guess.get("code"), "arg_map_code", c[0], "Optional — missing codes are suggested on page 2")
        m_acc = pick("Account name *", guess.get("account"), "arg_map_account", c[1])
        m_com = pick("Comment", guess.get("comment"), "arg_map_comment", c[2])
        layout = st.radio("Amount layout", ["Debit / Credit columns per year", "One signed balance column per year (+ debit / − credit)"],
                          index=0 if guess.get("layout", "dc") == "dc" else 1, horizontal=True)
        dc = layout.startswith("Debit")
        gy = guess.get("years") or []
        n = st.number_input("Number of years in the file", min_value=1, max_value=15, value=max(len(gy), 1), step=1,
                            help="Years found in the headers are pre-filled. The most recent year is normally the "
                                 "Current Year (CY) of the report; the others serve as Previous Years (PY).")
        years_map, default_year = [], (gy[0]["year"] if gy else pd.Timestamp.today().year - 1)
        hdr = st.columns([1, 2, 2] if dc else [1, 4])
        hdr[0].markdown("**Year**")
        hdr[1].markdown("**Debit column**" if dc else "**Balance column**")
        if dc:
            hdr[2].markdown("**Credit column**")
        for i in range(int(n)):
            g = gy[i] if i < len(gy) else {}
            cols = st.columns([1, 2, 2] if dc else [1, 4])
            yr = cols[0].number_input("Year", min_value=1990, max_value=2100, value=int(g.get("year") or default_year - i),
                                      step=1, key=f"arg_map_y{i}", label_visibility="collapsed")
            if dc:
                d = pick("Debit", g.get("debit"), f"arg_map_d{i}", cols[1], hidden=True)
                cr = pick("Credit", g.get("credit"), f"arg_map_c{i}", cols[2], hidden=True)
                years_map.append({"year": int(yr), "debit": None if d == "(none)" else d, "credit": None if cr == "(none)" else cr})
            else:
                b = pick("Balance", g.get("balance"), f"arg_map_b{i}", cols[1], hidden=True)
                years_map.append({"year": int(yr), "balance": None if b == "(none)" else b})
        mapping = {"code": None if m_code == "(none)" else m_code, "account": None if m_acc == "(none)" else m_acc,
                   "comment": None if m_com == "(none)" else m_com, "years": years_map,
                   "group": guess.get("group"), "line": guess.get("line")}
        if mapping["line"]:
            st.caption(f"Template columns detected: a blank CIT code will be derived from “{mapping['group']}” + "
                       f"“{mapping['line']}”.")

        problems = []
        if not mapping["account"]:
            problems.append("the account name column")
        if any(not (y.get("debit") or y.get("credit") or y.get("balance")) for y in years_map):
            problems.append("at least one amount column for every year")
        if len({y["year"] for y in years_map}) != len(years_map):
            problems.append("a different year on each row")
        used = [v for v in [mapping["code"], mapping["account"], mapping["comment"]] if v] + \
               [v for y in years_map for k, v in y.items() if k != "year" and v]
        if len(used) != len(set(used)):
            problems.append("different columns for each field (a column is used twice)")
        if problems:
            warn_banner("Select " + "; ".join(problems) + ".")
        else:
            ys = sorted(y["year"] for y in years_map)
            st.caption(f"Years loaded: {', '.join(map(str, ys))} → reports possible for CY "
                       f"{', '.join(map(str, ys[1:] or ys))} (each compared with its PY).")
        company_part = None
        if company_data.has_company_sheets(sheets):
            try:
                company_part = company_data.from_file(data, name)
                info_banner("This file also contains <b>Company & Report Data</b> sheets (company, auditor, per-year "
                            "data…). They will be proposed on <b>3 · Company & Report Data</b> after loading the TB — "
                            "nothing is replaced until you apply them there.")
            except Exception as e:  # noqa: BLE001
                warn_banner(f"Company & Report Data sheets found but not readable: {e}")
        if st.button("▶️ LOAD TRIAL BALANCE", type="primary", disabled=bool(problems)):
            tb, notes = tb_io.to_tb(raw, mapping, state.code_catalogue())
            if tb.empty:
                red_alert("No account lines found with this mapping.")
            else:
                if company_part:
                    st.session_state["arg_pending_company"] = {"part": company_part, "source": name}
                state.set_tb(tb, f"{name} [{sheet}]")
                st.session_state["arg_demo"] = False
                st.session_state["arg_import_notes"] = notes + tb_io.tb_notices(state.tb())
                st.session_state["arg_active_year"] = None
                st.rerun()

    if state.has_tb():
        section("Current trial balance")
        st.caption(f"Source: {st.session_state.get('arg_tb_source')} — {len(state.tb())} lines — "
                   f"years {', '.join(map(str, state.years()))}")
        for msg in st.session_state.get("arg_import_notes", []):
            if msg.startswith("NOT BALANCED"):
                red_alert(msg)
            elif msg.startswith("NEGATIVE"):
                warn_banner(msg)
            else:
                info_banner(msg)
        balance_summary()
        issues = tb_io.line_issues(state.tb(), state.valid_codes())
        nb = int((issues["Level"] == "BLOCKING").sum()) if not issues.empty else 0
        if nb:
            red_alert(f"{nb} blocking issue(s) on TB lines (missing/unknown CIT codes, sign errors…). "
                      "They must be corrected before the report can be generated.")
        st.page_link("pages/2_Checks_and_Corrections.py", label="Next → 2 · Checks & Corrections", icon="🔍")

# ================================================================ template ==
with tabs[1]:
    section("Blank trial-balance template")
    st.markdown("An Excel file ready to fill, one line per ledger account: **Statement › Section › Group › Statement "
                "line** cascading drop-downs that narrow the **CIT-code** list, the account description, a **Debit** and "
                "a **Credit** column per year (most recent first), the list of codes and the instructions. Uploaded "
                "back on this page, it is recognised automatically.")
    info_banner("<b>Several lines with the same CIT code</b> are allowed (e.g. two bank accounts under BS 03.01.03.02) — "
                "but <b>each line needs its own description</b>. Duplicated descriptions are highlighted in red in the "
                "template, and the app asks to merge or rename them (2 · Checks & Corrections → 👯 Duplicates).")
    c1, c2, c3 = st.columns(3)
    ny = c1.number_input("Number of years", min_value=1, max_value=10, value=2, step=1,
                         help="2 = Current Year (CY) + Previous Year (PY). Choose 5 to prepare five years at once.")
    ly = c2.number_input("Most recent year", min_value=1990, max_value=2100,
                         value=int(state.years()[-1]) if state.has_tb() else pd.Timestamp.today().year - 1, step=1)
    comp = c3.text_input("Company name (title of the sheet)", state.project()["meta"].get("company_name") or "")
    yrs = [int(ly) - i for i in range(int(ny))]
    with_cd = st.checkbox("Also include the Company & Report Data sheets (pre-filled with this project's data)",
                          value=False, help="Company, auditor, per-year tax data… in the same workbook as the TB. "
                                            "When the file is uploaded, they are proposed on page 3.")
    st.caption("Columns: Statement · Section · Group · Statement line · CIT code · Account name · " +
               " · ".join(f"Debit {y} · Credit {y}" for y in yrs) + " · Comments · Check")
    download_button("⬇️ Download the TB template (Excel)",
                    package.tb_template(yrs, state.code_catalogue(), comp,
                                        extra_sheets=company_data.frames(state.project(), yrs)[0] if with_cd else None),
                    f"{package.company_slug(comp or 'Company')}_TB_template_{min(yrs)}-{max(yrs)}.xlsx",
                    key="arg_dl_template", primary=True)

    section("🤖 Map a TB without CIT codes with any AI")
    ai_prompt_block("arg_dl_prompt_p1")

# ================================================================== resume ==
with tabs[2]:
    section("Resume a saved project")
    st.caption("The project file (…_project.json) is downloaded on 5 · Generate & Download. It holds the TB of "
               "every year, the CIT codes and all company / report data. Files of version V1-0a (…_input.json) "
               "are accepted too.")
    pj = st.file_uploader("Project file (.json)", type=["json"], key="arg_project_file")
    if pj is not None and st.button("📂 LOAD PROJECT", type="primary"):
        try:
            d = json.loads(pj.getvalue().decode("utf-8"))
            if "trial_balance" not in d or "meta" not in d:
                raise ValueError("not a project file (keys 'meta' and 'trial_balance' expected)")
            state.load_project(d, pj.name)
            st.session_state["arg_dirty"] = False
            st.success(f"Project loaded: {len(state.tb())} TB lines, years {', '.join(map(str, state.years()))}.")
        except Exception as e:  # noqa: BLE001
            red_alert(f"Cannot load this project file: {e}")

    section("Import the Excel generator (V11)")
    st.caption("Reads the TrialBalance, Generaldata, Incometax and Inventorydetails sheets of "
               "Template__Tool_Annualreport_Generator (values only — macros are not run).")
    xf = st.file_uploader("Excel generator workbook (.xlsm)", type=["xlsm", "xlsx"], key="arg_xlsm_file")
    if xf is not None and st.button("📥 IMPORT WORKBOOK", type="primary"):
        try:
            d = xlsm_import.read_generator(io.BytesIO(xf.getvalue()))
            d["meta"]["variables_color"] = "000000"
            state.load_project(d, xf.name)
            st.success(f"Imported {len(state.tb())} TB lines — {d['meta'].get('company_name')}, "
                       f"years {', '.join(map(str, state.years()))}.")
        except Exception as e:  # noqa: BLE001
            red_alert(f"This workbook does not have the V11 layout: {e}")

# ==================================================================== edit ==
def _norm(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


cat = state.code_catalogue()
ys = sorted(state.years(), reverse=True)
ay = state.active_year()

with tabs[3]:
    if state.require_tb():
        # ------------------------------------------------------------ finder --
        st.caption("No need to know the code: type a word (e.g. rent, bank, salary, loan, stock) and/or narrow by "
                   "statement › section › group. Then add a new TB line with the code found, or apply it to an "
                   "existing line.")
        f1, f2, f3, f4 = st.columns([2, 1, 1.4, 1.6])
        kw = f1.text_input("Keyword", placeholder="e.g. rent, bank charges, retained, vehicle…", key="arg_find_kw")
        stt = f2.selectbox("Statement", ["(all)"] + list(dict.fromkeys(cat["statement"])), key="arg_find_st")
        c1 = cat if stt == "(all)" else cat[cat["statement"] == stt]
        sec = f3.selectbox("Section", ["(all)"] + list(dict.fromkeys(c1["section"])), key="arg_find_sec")
        c2 = c1 if sec == "(all)" else c1[c1["section"] == sec]
        grp = f4.selectbox("Group", ["(all)"] + list(dict.fromkeys(c2["group"])), key="arg_find_grp")
        c3 = c2 if grp == "(all)" else c2[c2["group"] == grp]
        if kw.strip():
            words = _norm(kw).split()
            hay = (c3["code"] + " " + c3["section"] + " " + c3["group"] + " " + c3["line"]).map(_norm)
            c3 = c3[hay.apply(lambda h: all(w in h for w in words))]
        st.dataframe(c3.rename(columns={"code": "CIT code", "statement": "Statement", "section": "Section",
                                        "group": "Group", "line": "Statement line", "note": "Note"}),
                     hide_index=True, width="stretch", height=min(38 * (len(c3) + 1), 280))
        if c3.empty:
            warn_banner("No code matches — try another word or widen the filters.")
        else:
            chosen = st.selectbox(f"Code to use ({len(c3)} match{'es' if len(c3) > 1 else ''})",
                                  [f"{r.code} — {r.line}  ·  {r.group}" for r in c3.itertuples()], key="arg_find_pick")
            code_found = chosen.split(" — ")[0]
            a1, a2 = st.columns(2)
            with a1.container(border=True):
                st.markdown(f"**➕ Add a new TB line with {code_found}**")
                acc = st.text_input("Account description (must be unique)", key="arg_add_acc")
                one = pd.DataFrame([{f"{s_} {y}": 0.0 for y in ys for s_ in ("Debit", "Credit")}])
                amt = st.data_editor(one, hide_index=True, width="stretch", key="arg_add_amts",
                                     column_config={c: st.column_config.NumberColumn(
                                         c + (" (CY)" if c.endswith(str(ay)) else (" (PY)" if c.endswith(str((ay or 0) - 1)) else "")),
                                         format="localized", min_value=0) for c in one.columns})
                vals = {f"{c.split()[0].lower()}_{c.split()[1]}": float(amt.iloc[0][c] or 0) for c in one.columns}
                clash = acc.strip() and tb_io.desc_key(acc) in set(state.tb()["account"].map(tb_io.desc_key))
                if clash:
                    st.warning("This description already exists in the TB — choose a different one.")
                if st.button("➕ ADD LINE", type="primary", disabled=not acc.strip() or bool(clash)):
                    new = pd.concat([state.tb(), pd.DataFrame([{"code": code_found, "account": acc.strip(), "comment": "",
                                                                "note": "", **vals}])], ignore_index=True)
                    state.set_tb(new)
                    st.success(f"Line added: {acc.strip()} → {code_found}")
                    st.rerun()
            with a2.container(border=True):
                st.markdown(f"**🎯 Apply {code_found} to an existing line**")
                tbv = state.tb()
                choices = [f"#{i + 1} — {r['account'] or '(no name)'}  [{r['code'] or 'no code'}]" for i, r in tbv.iterrows()]
                missing_first = sorted(range(len(choices)), key=lambda i: tbv.iloc[i]["code"] in state.valid_codes())
                tgt = st.selectbox("TB line (lines without a valid code first)", [choices[i] for i in missing_first],
                                   key="arg_apply_line")
                if st.button("🎯 APPLY CODE", type="primary"):
                    idx = int(tgt.split(" — ")[0][1:]) - 1
                    new = tbv.copy()
                    new.at[idx, "code"] = code_found
                    state.set_tb(new)
                    st.success(f"Line #{idx + 1} now uses {code_found}.")
                    st.rerun()

with tabs[4]:
    if state.require_tb():
        # ------------------------------------------------------------ editor --
        st.caption("Change codes, names or amounts, add or delete lines, then press APPLY (to delete lines with 0 "
                   "everywhere in one click, use the 🗑️ Delete lines tab). In the CIT-code cell you can "
                   "type part of the statement line to search the list. Statement line, group and section are shown "
                   "for information (they follow the code). Columns: most recent year first.")
        lab = {r.code: f"{r.code} — {r.line}" for r in cat.itertuples()}
        info = cat.set_index("code")
        df = state.tb().copy()
        amt_cols = [f"{s}_{y}" for y in ys for s in ("debit", "credit")]
        df["line"] = df["code"].map(lambda c: info.at[c, "line"] if c in info.index else ("⚠️ no code" if not c else "⚠️ unknown code"))
        df["group"] = df["code"].map(lambda c: info.at[c, "group"] if c in info.index else "")
        df["section"] = df["code"].map(lambda c: info.at[c, "section"] if c in info.index else "")
        df = df[["account", "code"] + amt_cols + ["line", "group", "section", "comment", "note"]]
        df["code"] = df["code"].map(lambda c: lab.get(c, c))
        df.index = range(1, len(df) + 1)
        extra = sorted({c for c in df["code"] if c and c not in lab.values()})
        cfg = {"code": st.column_config.SelectboxColumn("CIT code", options=[""] + list(lab.values()) + extra, width="medium",
                                                        help="Type part of the code or of the statement line to search"),
               "line": st.column_config.TextColumn("Statement line", disabled=True),
               "group": st.column_config.TextColumn("Group", disabled=True),
               "section": st.column_config.TextColumn("Section", disabled=True),
               "account": st.column_config.TextColumn("Account", width="large"),
               "comment": st.column_config.TextColumn("Comment"),
               "note": st.column_config.TextColumn("Note override", help="Only to force an account into another note (e.g. 13)")}
        for y in ys:
            role = " (CY)" if y == ay else (" (PY)" if y == (ay or 0) - 1 else "")
            for s_ in ("debit", "credit"):
                cfg[f"{s_}_{y}"] = st.column_config.NumberColumn(f"{s_.title()} {y}{role}", format="localized",
                                                                 help=f"{s_.title()} balance at the end of {y}. "
                                                                      "CY = Current Year, PY = Previous Year.")
        g1, g2 = st.columns([2, 1])
        flt = g1.text_input("Filter the lines shown (account, code, statement line, group or section)", key="arg_edit_filter")
        if flt.strip():
            words = _norm(flt).split()
            hay = (df["account"].astype(str) + " " + df["code"].astype(str) + " " + df["line"] + " " + df["group"] + " " +
                   df["section"]).map(_norm)
            view = df[hay.apply(lambda h: all(w in h for w in words))]
            g2.caption(f"{len(view)} of {len(df)} lines shown — edits apply to the lines shown; adding/deleting lines "
                       "is disabled while filtering.")
        else:
            view = df
        edited = st.data_editor(view, num_rows="fixed" if flt.strip() else "dynamic", width="stretch", height=520,
                                key=f"arg_tb_editor_{_norm(flt)}", column_config=cfg,
                                disabled=["line", "group", "section"])
        if st.button("💾 APPLY CHANGES", type="primary"):
            ed = edited.drop(columns=["line", "group", "section"])
            ed["code"] = ed["code"].map(lambda v: str(v).split(" — ")[0] if v else "")
            if flt.strip():
                base = df.drop(columns=["line", "group", "section"]).copy()
                base["code"] = base["code"].map(lambda v: str(v).split(" — ")[0] if v else "")
                base.loc[ed.index] = ed
                ed = base
            new = tb_io.normalise(ed)
            new = new[(new["account"] != "") | (new[tb_io.amount_cols(new)].abs().sum(axis=1) > 0)]
            state.set_tb(new.reset_index(drop=True))
            st.success("Trial balance updated.")
            st.rerun()
        tot = state.tb()[[f"{s_}_{y}" for y in ys for s_ in ("debit", "credit")]].sum()
        st.caption("Totals (saved TB) — " + " · ".join(f"{y}: debit {fmt(tot[f'debit_{y}'])} / credit {fmt(tot[f'credit_{y}'])} "
                                                       f"(diff {fmt(tot[f'debit_{y}'] - tot[f'credit_{y}'])})" for y in ys))

with tabs[5]:
    if state.require_tb():
        line_tools.undo_box("arg_del_p1")
        section("Lines with 0 in every year")
        line_tools.zero_lines_panel("arg_del_p1")
        section("Delete other lines")
        line_tools.any_lines_panel("arg_del_p1")

with tabs[6]:
    if state.require_tb():
        st.caption("Years of the trial balance. Each year except the earliest can be reported as CY (Current Year); "
                   "the year before is its PY (Previous Year).")
        st.dataframe(tb_io.balance_table(state.tb()), hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="localized")
                                    for c in ("Total debit", "Total credit", "Difference (debit − credit)")})
        c1, c2 = st.columns(2)
        with c1:
            add = st.number_input("Add an empty year", min_value=1990, max_value=2100, value=min(ys) - 1, step=1)
            if st.button("➕ ADD YEAR"):
                new = state.tb().copy()
                if f"debit_{int(add)}" in new.columns:
                    st.warning(f"{int(add)} is already in the TB.")
                else:
                    new[f"debit_{int(add)}"] = 0.0
                    new[f"credit_{int(add)}"] = 0.0
                    state.set_tb(new)
                    st.rerun()
        with c2:
            rem = st.selectbox("Remove a year", ys)
            if st.button("🗑️ REMOVE YEAR", disabled=len(ys) < 2):
                state.set_tb(state.tb().drop(columns=[f"debit_{rem}", f"credit_{rem}"]))
                st.session_state["arg_active_year"] = None
                st.rerun()
