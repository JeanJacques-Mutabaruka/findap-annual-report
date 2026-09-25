"""Session state and the rebuild pipeline — multi-year.

Session keys are prefixed `arg_`. Nothing is stored on the server: the whole project lives in the
browser session and is saved by downloading the project file on 5 · Generate & Download.

Vocabulary used everywhere in the app:
  CY = Current Year  — the financial year being reported;
  PY = Previous Year — the comparative year just before it.
A TB may hold any number of years. The Word report always compares two years (CY vs PY); the app can
show all years side by side, or work "two by two" on the pair selected in the sidebar.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import CHART, DEMO, NOTES, VERSION, build_model, multiyear, tb_io, templates  # noqa: E402

EMPTY_PROJECT = {
    "format": multiyear.FORMAT,
    "meta": {"company_name": "", "period_end": "", "currency": "Rwf", "company_type": "CORPORATE",
             "tables_font_size": 8, "variables_color": "000000", "hide_zero_lines": True,
             "template_id": "", "font_name": ""},
    "general": {"audit_company_name": "", "audit_company_address": "", "directors": "", "registered_office": "",
                "bankers": "", "main_activity": "", "auditor_report_framework": "International Financial Reporting Standards (IFRS)",
                "accounting_framework": "International Financial Reporting Standard", "proposed_dividend": 0,
                "signature_date": "", "company_representative": "", "fs_signing_date": "", "company_director": ""},
    "years_data": {},
    "notes": None,
    "bookmark_overrides": {},
}

REQUIRED_GENERAL = {
    "audit_company_name": "Audit firm name", "audit_company_address": "Audit firm address",
    "directors": "Directors", "registered_office": "Registered office", "bankers": "Principal bankers",
    "main_activity": "Main activity", "auditor_report_framework": "Auditor's report framework",
    "accounting_framework": "Accounting framework",
}
MODE_PAIR, MODE_ALL = "Two years (CY vs PY)", "All years side by side"


# ------------------------------------------------------------ reference data --
@st.cache_data
def chart() -> dict:
    return json.loads(CHART.read_text(encoding="utf-8"))


@st.cache_data
def notes_default() -> dict:
    return json.loads(NOTES.read_text(encoding="utf-8"))


def current_template() -> dict | None:
    """Template chosen for the project (default: the first active template of templates/)."""
    return templates.get(project()["meta"].get("template_id"))


def current_notes() -> dict:
    """Notes list of the chosen template if it has its own notes.json, else the default notes."""
    t = current_template()
    if t and t.get("notes"):
        return json.loads(Path(t["notes"]).read_text(encoding="utf-8"))
    return notes_default()


@st.cache_data
def code_catalogue() -> pd.DataFrame:
    rows = []
    for stmt, key in (("P&L", "pnl"), ("Balance sheet", "bs")):
        for sec in chart()[key]:
            for g in sec.get("groups", []):
                for ln in g["lines"]:
                    rows.append({"code": ln["code"], "statement": stmt, "section": sec.get("title"),
                                 "group": g.get("label") or sec.get("title"), "line": ln["label"],
                                 "note": g.get("note") or sec.get("note") or ""})
    return pd.DataFrame(rows)


def code_options() -> list[str]:
    return [""] + [f"{r.code} — {r.line}" for r in code_catalogue().itertuples()]


def code_label(code: str) -> str:
    cat = code_catalogue()
    hit = cat[cat["code"] == code]
    return f"{code} — {hit.iloc[0]['line']}" if len(hit) else (code or "")


def valid_codes() -> set[str]:
    return set(code_catalogue()["code"])


# ------------------------------------------------------------------- state --
def init_state() -> None:
    ss = st.session_state
    if ss.get("arg_ready"):
        return
    ss["arg_project"] = copy.deepcopy(EMPTY_PROJECT)
    ss["arg_tb"] = tb_io.empty_tb()
    ss["arg_tb_source"] = None
    ss["arg_models"] = {}
    ss["arg_model_error"] = None
    ss["arg_outputs"] = {}
    ss["arg_template"] = None
    ss["arg_dirty"] = False
    ss["arg_demo"] = False
    ss["arg_import_notes"] = []
    ss["arg_view_mode"] = MODE_PAIR
    ss["arg_active_year"] = None
    ss["arg_ready"] = True


def mark_dirty() -> None:
    ss = st.session_state
    ss["arg_dirty"] = True
    ss["arg_models"] = {}
    ss["arg_outputs"] = {}


def project() -> dict:
    return st.session_state["arg_project"]


def tb() -> pd.DataFrame:
    return st.session_state["arg_tb"]


def has_tb() -> bool:
    return not tb().empty and bool(tb_io.years_of(tb()))


def years() -> list[int]:
    return tb_io.years_of(tb())


def report_years() -> list[int]:
    return multiyear.pairs(years()) if has_tb() else []


def active_year() -> int | None:
    ry = report_years()
    if not ry:
        return None
    y = st.session_state.get("arg_active_year")
    return y if y in ry else ry[-1]


def view_all() -> bool:
    return st.session_state.get("arg_view_mode") == MODE_ALL and len(report_years()) > 1


def set_tb(df: pd.DataFrame, source: str | None = None) -> None:
    st.session_state["arg_tb"] = tb_io.normalise(df)
    if source:
        st.session_state["arg_tb_source"] = source
    ys = years()
    if ys and not project()["meta"].get("period_end"):
        project()["meta"]["period_end"] = f"{ys[-1]}-12-31"
    mark_dirty()


def load_project(d: dict, source: str, demo: bool = False) -> None:
    """Project file (multi-year), a 2-year input.json (V1-0a / skill), or a V11 import."""
    if d.get("format") == multiyear.FORMAT:
        proj = {k: v for k, v in d.items() if k != "trial_balance"}
        tbm = tb_io.from_records(d.get("trial_balance", []))
    else:
        proj, tbm = multiyear.from_pair_input(d)
    base = copy.deepcopy(EMPTY_PROJECT)
    for k, v in proj.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    st.session_state["arg_project"] = base
    set_tb(tbm, source)
    st.session_state["arg_demo"] = demo
    st.session_state["arg_active_year"] = None


def load_demo(five_years: bool = False) -> None:
    if five_years:
        path = DEMO.parent / "demo_project_5years.json"
        load_project(json.loads(path.read_text(encoding="utf-8")), "DEMO 5 years — TEST COMPANY LTD", demo=True)
    else:
        load_project(json.loads(DEMO.read_text(encoding="utf-8")), "DEMO — TEST COMPANY LTD", demo=True)


def full_project() -> dict:
    d = copy.deepcopy(project())
    d["trial_balance"] = tb_io.to_records(tb())
    return d


def pair_input(year: int) -> dict:
    return multiyear.pair_input(project(), tb(), year)


# ------------------------------------------------------------------ models --
def missing_general() -> list[str]:
    g, m = project()["general"], project()["meta"]
    miss = [lab for k, lab in REQUIRED_GENERAL.items()
            if not str(g.get(k) or "").strip() or str(g.get(k)).strip() in ("-", "00:00:00")]
    if not str(m.get("company_name") or "").strip():
        miss.insert(0, "Company name")
    if not str(m.get("period_end") or "").strip():
        miss.insert(1, "Financial year end date")
    return miss


def can_build() -> tuple[bool, str]:
    m = project()["meta"]
    if not has_tb():
        return False, "Load a trial balance first (1 · Trial Balance)."
    if not m.get("period_end"):
        return False, "Enter the financial year end date (3 · Company & Report Data → Period & tax)."
    if not m.get("company_name"):
        return False, "Enter the company name (3 · Company & Report Data)."
    return True, ""


def model(year: int | None = None) -> dict | None:
    """Statements + controls for CY = year (default: active year). Cached until data changes."""
    ss = st.session_state
    year = year or active_year()
    if year is None:
        return None
    if year in ss["arg_models"]:
        return ss["arg_models"][year]
    ok, why = can_build()
    if not ok:
        ss["arg_model_error"] = why
        return None
    try:
        m = build_model.build(pair_input(year), chart(), current_notes())
        ss["arg_models"][year] = m
        ss["arg_model_error"] = None
        return m
    except Exception as e:  # noqa: BLE001 — shown to the user
        ss["arg_model_error"] = f"Computation failed for {year}: {type(e).__name__}: {e}"
        return None


def rebuild() -> dict | None:
    return model(active_year())


def all_models() -> dict[int, dict]:
    out = {}
    for y in report_years():
        m = model(y)
        if m is not None:
            out[y] = m
    return out


def steps() -> list[tuple[str, str, str]]:
    """(status, label, detail) with status in ok / warn / todo / fail."""
    if not has_tb():
        return [("todo", "Trial balance loaded", "Upload a TB on 1 · Trial Balance")]
    ys = years()
    out = [("ok", "Trial balance loaded",
            f"{len(tb())} lines · years {', '.join(map(str, ys))} — {st.session_state.get('arg_tb_source') or ''}")]
    bal = tb_io.balance(tb())
    bad_years = [str(y) for y in ys if not bal[y]["ok"]]
    out.append(("ok" if not bad_years else "fail", "Trial balance balances",
                "every year" if not bad_years else "NOT balanced in " + ", ".join(bad_years)))
    bad = tb()[~tb()["code"].isin(valid_codes())]
    out.append(("ok" if bad.empty else "fail", "Every line has a valid CIT code",
                "all mapped" if bad.empty else f"{len(bad)} line(s) to map"))
    miss = missing_general()
    out.append(("ok" if not miss else "warn", "Company & report data complete",
                "complete" if not miss else "missing: " + ", ".join(miss[:5]) + ("…" if len(miss) > 5 else "")))
    targets = report_years() if view_all() else [active_year()]
    nb = nw = 0
    for y in targets:
        m = model(y)
        if m is None:
            out.append(("todo", "Statements computed", st.session_state.get("arg_model_error") or ""))
            break
        nb += sum(c["level"] == "BLOCKING" for c in m["controls"])
        nw += sum(c["level"] == "WARNING" for c in m["controls"])
    else:
        scope = "all year pairs" if view_all() else f"CY {active_year()} vs PY {active_year() - 1}"
        out.append(("fail" if nb else ("warn" if nw else "ok"), "Report controls",
                    f"{nb} blocking, {nw} warning(s) — {scope}"))
    out.append(("ok" if st.session_state.get("arg_outputs") else "todo", "Files generated",
                "ready to download" if st.session_state.get("arg_outputs") else "5 · Generate & Download"))
    return out


# ------------------------------------------------------------------ sidebar --
def sidebar() -> None:
    ss, sb = st.session_state, st.sidebar
    m = project()["meta"]
    if ss.get("arg_demo"):
        sb.warning("🧪 DEMO — TEST COMPANY LTD")
    if m.get("company_name"):
        sb.markdown(f"**{m['company_name']}**")
    if has_tb():
        ys = years()
        sb.caption(f"TB years: {', '.join(map(str, ys))}")
        ry = report_years()
        if len(ry) > 1:
            ss["arg_view_mode"] = sb.radio(
                     "Years shown", [MODE_PAIR, MODE_ALL], index=1 if ss.get("arg_view_mode") == MODE_ALL else 0,
                     help="Two years: the app, the checks and the report work on the pair CY / PY chosen below.\n\n"
                          "All years: statements and checks are shown for every year side by side; the Word "
                          "reports are produced for each pair.")
        ay = active_year()
        if ry:
            idx = ry.index(ay)
            ss["arg_active_year"] = sb.selectbox("Current Year (CY) reported", ry, index=idx,
                         format_func=lambda y: f"CY {y}  ·  PY {y - 1}",
                         help="CY = Current Year: the financial year being reported.\n\n"
                              "PY = Previous Year: the comparative year printed next to it (CY − 1).")
        bal = tb_io.balance(tb())
        (sb.success if bal["ok"] else sb.error)("TB balances (all years)" if bal["ok"] else "TB does NOT balance")
    sb.info("**CY** = Current Year (year reported)  \n**PY** = Previous Year (comparative)", icon="ℹ️")
    cfg = deployment_settings()
    if cfg["tester_mode"]:
        sb.warning(f"🧪 TEST VERSION {VERSION} — use the demo or anonymised data only.")
    if cfg["feedback_url"]:
        sb.link_button("💬 Send feedback / report a problem", cfg["feedback_url"], width="stretch")
    elif cfg["feedback_email"]:
        sb.link_button("💬 Send feedback by e-mail", f"mailto:{cfg['feedback_email']}?subject=Annual%20Report%20Generator%20{VERSION}",
                       width="stretch")
    if ss.get("arg_dirty"):
        sb.info("💾 Work not saved — download the project file on 5 · Generate & Download to resume later.")
    sb.caption(f"Annual Report Generator {VERSION}")


def deployment_settings() -> dict:
    """Optional settings from .streamlit/secrets.toml (locally) or the app's Secrets box (Streamlit Cloud):
        tester_mode = true
        feedback_url = "https://forms.gle/..."      # e.g. a Google Form
        feedback_email = "name@example.com"         # used when no feedback_url
    Missing file or keys -> defaults (nothing shown)."""
    out = {"tester_mode": False, "feedback_url": "", "feedback_email": ""}
    try:
        for k in out:
            if k in st.secrets:
                out[k] = st.secrets[k]
    except Exception:  # noqa: BLE001 — no secrets file locally
        pass
    return out


def page_setup(title: str) -> None:
    from app.style import inject_css
    st.set_page_config(page_title=f"Annual Report Generator — {title.split(' ', 1)[-1]}", page_icon="📊", layout="wide")
    inject_css()
    st.title(title)
    sidebar()


def require_tb() -> bool:
    if has_tb():
        return True
    from app.style import info_banner
    info_banner("No trial balance loaded yet. Go to <b>1 · Trial Balance</b>, or load the demo from the Home page.")
    return False
