"""Smoke tests of the Streamlit pages (headless, streamlit.testing). Run with:  pytest -q"""
from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
HOME = str(ROOT / "app" / "Home.py")
PAGES = ("1_Trial_Balance", "2_Checks_and_Corrections", "3_Company_and_Report_Data", "4_Statements_Preview",
         "5_Generate_and_Download", "6_Templates", "7_Tax_and_CIT", "8_Long_term_Assets_Check",
         "9_Stock_Control", "10_Global_Assessment")


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]


def test_pages_empty_state():
    at = AppTest.from_file(HOME, default_timeout=60).run()
    _ok(at)
    for p in PAGES:
        at.switch_page(f"pages/{p}.py").run()
        _ok(at)


def test_demo_two_years_generation():
    at = AppTest.from_file(HOME, default_timeout=180).run()
    next(b for b in at.button if "2 YEARS" in b.label).click().run()
    _ok(at)
    for p in PAGES[:4]:
        at.switch_page(f"pages/{p}.py").run()
        _ok(at)
    at.switch_page("pages/2_Checks_and_Corrections.py").run()
    assert any("ACCDEP_DEBIT" in m.value for m in at.markdown)
    at.switch_page("pages/5_Generate_and_Download.py").run()
    _ok(at)
    next(c for c in at.checkbox if c.label.startswith("Generate DRAFT")).check().run()
    for c in at.checkbox:
        if c.label.startswith("Also produce the PDF"):
            c.uncheck()
    at.run()
    next(b for b in at.button if "GENERATE" in b.label).click().run()
    _ok(at)
    files = at.session_state["arg_outputs"]["files"]
    assert any(n.endswith("_FY2025") is False and n.endswith("_DRAFT.docx") for n in files)
    assert any(n.endswith("_project.json") for n in files)


def test_demo_five_years_all_views():
    at = AppTest.from_file(HOME, default_timeout=240).run()
    next(b for b in at.button if "5 YEARS" in b.label).click().run()
    _ok(at)
    assert at.session_state["arg_tb"].shape[1] == 4 + 10
    at.sidebar.radio[0].set_value("All years side by side").run()
    _ok(at)
    for p in PAGES:
        at.switch_page(f"pages/{p}.py").run()
        _ok(at)
    at.switch_page("pages/4_Statements_Preview.py").run()
    assert len(at.dataframe) >= 4
    at.switch_page("pages/5_Generate_and_Download.py").run()
    next(c for c in at.checkbox if c.label.startswith("Generate DRAFT")).check().run()
    for c in at.checkbox:
        if c.label.startswith("Also produce the PDF"):
            c.uncheck()
    at.run()
    next(b for b in at.button if "GENERATE" in b.label).click().run()
    _ok(at)
    files = at.session_state["arg_outputs"]["files"]
    assert sum(n.endswith(".docx") for n in files) == 4          # 2022..2025
    assert any("multi-year" in n for n in files)


def test_mapping_suggestions_and_zero_line_deletion():
    import pandas as pd
    at = AppTest.from_file(HOME, default_timeout=180).run()
    next(b for b in at.button if "2 YEARS" in b.label).click().run()
    tb = at.session_state["arg_tb"].copy()
    n0 = len(tb)
    tb.loc[0, "code"] = ""                                                 # a line to map
    zero = {c: 0.0 for c in tb.columns if c.startswith(("debit_", "credit_"))}
    tb = pd.concat([tb, pd.DataFrame([{"code": "PL 04.12", "account": "OLD RENT ACCOUNT", "comment": "", "note": "", **zero}])],
                   ignore_index=True)
    at.session_state["arg_tb"] = tb
    at.switch_page("pages/2_Checks_and_Corrections.py").run()
    _ok(at)
    assert any(m.label.startswith("🟢") for m in at.metric)
    next(t for t in at.toggle if t.label.startswith("Pre-tick")).set_value(True).run()
    next(b for b in at.button if b.label.startswith("✅ APPLY CONFIRMED")).click().run()
    _ok(at)
    assert at.session_state["arg_tb"].loc[0, "code"] != ""
    next(b for b in at.button if "ZERO LINE" in b.label).click().run()
    _ok(at)
    left = at.session_state["arg_tb"]
    assert "OLD RENT ACCOUNT" not in set(left["account"]) and len(left) < n0 + 1
    next(b for b in at.button if b.label.startswith("↩️ UNDO")).click().run()
    assert "OLD RENT ACCOUNT" in set(at.session_state["arg_tb"]["account"])
    at.switch_page("pages/1_Trial_Balance.py").run()
    _ok(at)
    assert any("AI mapping prompt" in d.proto.label for d in at.get("download_button"))


def test_tax_and_cit_page():
    at = AppTest.from_file(HOME, default_timeout=180).run()
    next(b for b in at.button if "2 YEARS" in b.label).click().run()
    at.switch_page("pages/7_Tax_and_CIT.py").run()
    _ok(at)
    labels = [d.proto.label for d in at.get("download_button")]
    assert any("Taxable income" in l for l in labels) and any("RRA annex" in l for l in labels)
