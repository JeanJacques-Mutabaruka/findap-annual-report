"""Delete TB lines — lines with 0 in every year first, any line on request — with a one-step undo.

Used on 1 · Trial Balance (🗑️ Delete lines) and 2 · Checks & Corrections (🛠️ Quick fixes).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import state
from app.formatting import fmt
from app.style import info_banner, ok_banner, warn_banner
from engine import tb_io

UNDO = "arg_undo_tb"


def _delete(rows: list[int], what: str) -> None:
    st.session_state[UNDO] = {"tb": state.tb().copy(), "what": what}
    state.set_tb(tb_io.delete_lines(state.tb(), rows))
    st.session_state["arg_delete_msg"] = what
    st.rerun()


def undo_box(key: str) -> None:
    """Message after a deletion + UNDO button (restores the TB as it was just before)."""
    u = st.session_state.get(UNDO)
    msg = st.session_state.pop("arg_delete_msg", None)
    if msg:
        ok_banner(msg)
    if u and st.button(f"↩️ UNDO THE LAST DELETION ({u['what']})", key=f"{key}_undo"):
        state.set_tb(u["tb"])
        st.session_state.pop(UNDO, None)
        st.rerun()


def zero_lines_panel(key: str) -> None:
    """Lines with 0 or nothing in every year: review (untick to keep) and delete in one click."""
    tb = state.tb()
    zeros = tb_io.zero_lines(tb)
    if not zeros:
        ok_banner("No line with 0 in every year.")
        return
    info_banner(f"<b>{len(zeros)} line(s)</b> have 0 (or nothing) in every year — they add nothing to the statements. "
                "Untick the ones you want to keep, then delete. The balance does not change.")
    view = pd.DataFrame({"delete": True, "line": [i + 1 for i in zeros],
                         "account": [tb.at[i, "account"] or "(no name)" for i in zeros],
                         "code": [tb.at[i, "code"] or "(no code)" for i in zeros],
                         "comment": [tb.at[i, "comment"] for i in zeros]})
    ed = st.data_editor(view, hide_index=True, width="stretch", key=f"{key}_zero_ed_{len(tb)}",
                        height=min(38 * (len(view) + 1), 300), disabled=["line", "account", "code", "comment"],
                        column_config={"delete": st.column_config.CheckboxColumn("DELETE"),
                                       "line": st.column_config.NumberColumn("Line", format="%d")})
    rows = [int(r["line"]) - 1 for _, r in ed.iterrows() if r["delete"]]
    if st.button(f"🗑️ DELETE {len(rows)} ZERO LINE(S)", key=f"{key}_zero_go", type="primary", disabled=not rows):
        _delete(rows, f"{len(rows)} zero line(s) deleted")


def any_lines_panel(key: str) -> None:
    """Delete chosen lines, whatever their amounts (the balance changes if they are not zero)."""
    tb = state.tb()
    ys = sorted(state.years(), reverse=True)
    labels = {f"#{i + 1} — {r['account'] or '(no name)'}  [{r['code'] or 'no code'}]": i for i, r in tb.iterrows()}
    pick = st.multiselect("Lines to delete (type part of the name or of the code)", list(labels), key=f"{key}_any_pick")
    rows = [labels[p] for p in pick]
    if rows:
        sel = tb.loc[rows]
        effect = " · ".join(f"{y}: debit −{fmt(sel[f'debit_{y}'].sum())} / credit −{fmt(sel[f'credit_{y}'].sum())}" for y in ys)
        nonzero = [i for i in rows if i not in set(tb_io.zero_lines(tb))]
        if nonzero:
            warn_banner(f"{len(nonzero)} of these line(s) have amounts — deleting them changes the totals ({effect}). "
                        "The trial balance may then no longer balance.")
        ok = st.checkbox("I confirm the deletion of these lines", key=f"{key}_any_ok_{len(rows)}")
        if st.button(f"🗑️ DELETE {len(rows)} LINE(S)", key=f"{key}_any_go", type="primary", disabled=not ok):
            _delete(rows, f"{len(rows)} line(s) deleted")
