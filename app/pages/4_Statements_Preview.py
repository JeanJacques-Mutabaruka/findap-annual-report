"""4 · Statements Preview — two years (CY vs PY) or all years side by side."""
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
from app.style import cy_py_note, info_banner, red_alert, section  # noqa: E402
from engine import multiyear, package, render_report, tb_io  # noqa: E402

state.init_state()
state.page_setup("📑 Statements Preview")
if not state.require_tb():
    st.stop()

BOLD = {"heading", "title", "group", "line_bold", "total", "sectiontotal", "subtotal", "grandtotal", "blocktitle"}
meta = state.project()["meta"]
hide = st.toggle("Hide lines that are zero in every year shown", value=bool(meta.get("hide_zero_lines", True)))


def show(rows, cols, labels, note=True):
    """rows: engine rows; cols: 'cy'/'py' keys or integer indexes into r['values']; labels: column titles."""
    if hide:
        rows = render_report.filter_zero(rows, [c for c in cols if isinstance(c, str)])
    recs, types = [], []
    for r in rows:
        rec = {"": ("\u2003" if r["type"] == "line" else "") + (r["label"].upper() if r["type"] == "heading" else r["label"])}
        if note:
            rec["Note"] = r.get("note") or ""
        for c, lab in zip(cols, labels):
            v = (r.get("values") or [None] * (c + 1))[c] if isinstance(c, int) else r.get(c)
            rec[lab] = "" if r["type"] in ("title", "heading", "blocktitle") or v is None else fmt_acc(v)
        recs.append(rec)
        types.append(r["type"])
    if not recs:
        st.caption("Nothing to show.")
        return
    df = pd.DataFrame(recs)
    sty = df.style.apply(lambda row: ["font-weight: bold" if types[row.name] in BOLD else "" for _ in row], axis=1)
    sty = sty.set_properties(subset=[c for c in df.columns if c not in ("", "Note")], **{"text-align": "right"})
    st.dataframe(sty, hide_index=True, width="stretch", height=min(38 * (len(df) + 1), 900))


def ylab(y, cy):
    return f"{y} (CY)" if y == cy else (f"{y} (PY)" if y == cy - 1 else str(y))


# =================================================================== ALL ====
if state.view_all():
    cy_py_note(all_years=True)
    models = state.all_models()
    if len(models) != len(state.report_years()):
        info_banner(st.session_state.get("arg_model_error") or "Statements not computed yet.")
        st.stop()
    nb = sum(c["level"] == "BLOCKING" for m in models.values() for c in m["controls"])
    if nb:
        red_alert(f"{nb} blocking issue(s) across the years — figures below are provisional. See 2 · Checks & Corrections.")
    sheets = {}
    tabs = st.tabs(["P&L", "Balance sheet", "Cash flow", "Income tax", "Notes"])
    for tab, (key, title) in zip(tabs[:4], [("pnl", "Statement of comprehensive income"),
                                             ("bs", "Statement of financial position"),
                                             ("cashflow", "Statement of cash flows"),
                                             ("income_tax", "Income tax computation")]):
        rows, yrs = multiyear.multi_statement(models, key)
        sheets[title[:31]] = (rows, yrs)
        with tab:
            section(f"{title} — {yrs[0]} to {yrs[-1]}")
            if key == "cashflow":
                st.caption(f"The cash flow of a year needs the balance sheet of the year before, so it starts in {yrs[0]}.")
            show(rows, list(range(len(yrs))), [str(y) for y in yrs], note=key in ("pnl", "bs"))
    with tabs[4]:
        notes, yrs = multiyear.multi_notes(models)
        note_rows = []
        for n in notes:
            section(f"{int(n['id'])}. {n['title']}")
            for t in n["texts"]:
                st.write(t)
            if n["rows"]:
                show(n["rows"], list(range(len(yrs))), [str(y) for y in yrs], note=False)
            note_rows.append({"type": "title", "label": f"{int(n['id'])}. {n['title']}", "values": [None] * len(yrs)})
            note_rows += n["rows"]
        sheets["Notes"] = (note_rows, yrs)
    st.divider()
    download_button("⬇️ Multi-year statements workbook (Excel)",
                    package.multi_year_workbook(sheets, tb_io.balance_table(state.tb())),
                    package.stem(meta.get("company_name"), kind="Statements_multi-year") + ".xlsx",
                    key="arg_dl_multi_preview", primary=True)
    st.stop()

# ================================================================== PAIR ====
cy = state.active_year()
model = state.rebuild()
if model is None:
    info_banner(st.session_state.get("arg_model_error") or "Statements not computed yet.")
    st.stop()
cy_py_note(cy)
y, p = model["meta"]["year_cy"], model["meta"]["year_py"]
L = [ylab(y, cy), ylab(p, cy)]
blocking = [c for c in model["controls"] if c["level"] == "BLOCKING"]
if blocking:
    red_alert(f"{len(blocking)} blocking issue(s) — figures below are provisional. See 2 · Checks & Corrections.")

tabs = st.tabs(["P&L", "Balance sheet", "Cash flow", "Equity", "Income tax", "Fixed assets", "Notes"])
with tabs[0]:
    section(f"Statement of comprehensive income — year ended {model['meta']['period_end']}")
    show(model["pnl"], ["cy", "py"], L)
with tabs[1]:
    section(f"Statement of financial position — as at {model['meta']['period_end']}")
    show(model["bs"], ["cy", "py"], L)
with tabs[2]:
    section(f"Statement of cash flows — CY {y}")
    show(model["cashflow"], ["cy"], [L[0]], note=False)
with tabs[3]:
    section("Statement of changes in equity")
    for blk in model["equity"]["blocks"]:
        st.markdown(f"**{blk['title']}**")
        show(blk["rows"], list(range(len(model["equity"]["columns"]))), model["equity"]["columns"], note=False)
with tabs[4]:
    section("Income tax computation (note 10)")
    show(model["income_tax"]["rows"], ["cy", "py"], L, note=False)
with tabs[5]:
    section("Property and equipment (note 11)")
    st.caption(f"Source: {model['ppe']['source']}")
    show(model["ppe"]["rows"], list(range(len(model["ppe"]["columns"]))), model["ppe"]["columns"], note=False)
with tabs[6]:
    for note in model["notes"]:
        section(f"{int(note['id'])}. {note['title']}")
        for b in note["blocks"]:
            if b.get("subtitle"):
                st.markdown(f"**{b['subtitle']}**")
            if b["kind"] == "text":
                st.write(b["text"])
            elif b["kind"] == "table2":
                show(b["rows"], ["cy", "py"], L, note=False)
            elif b["kind"] == "tableN":
                show(b["rows"], list(range(len(b["columns"]))), b["columns"], note=False)

st.divider()
download_button("⬇️ Statements workbook (Excel)", package.statements_workbook(model, state.tb()),
                package.stem(meta.get("company_name"), year=y) + "_statements.xlsx", key="arg_dl_stmt_preview")
