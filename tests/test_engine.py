"""Regression tests for the engine. Run with:  pytest -q

Expected figures are those of the V11 Excel generator on its own test data (TEST COMPANY LTD, FY 2025).
"""
from __future__ import annotations

import copy
import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import CHART, DEMO, NOTES, TEMPLATE, build_model, code_suggest, multiyear, package, render_report, tb_io  # noqa: E402

CHART_D = json.loads(CHART.read_text(encoding="utf-8"))
NOTES_D = json.loads(NOTES.read_text(encoding="utf-8"))


@pytest.fixture
def demo():
    return json.loads(DEMO.read_text(encoding="utf-8"))


def build(d):
    return build_model.build(d, CHART_D, NOTES_D)


def ids(model, level):
    return {c["id"] for c in model["controls"] if c["level"] == level}


def test_figures_match_excel_v11(demo):
    k = build(demo)["key_figures"]
    assert round(k["revenue"]["cy"]) == 535_837_403
    assert round(k["pbt"]["cy"]) == 127_715_819
    assert round(k["net_profit"]["cy"]) == 89_851_899
    assert round(k["total_assets"]["cy"]) == 296_521_579
    assert round(k["total_equity"]["cy"]) == 233_349_876


def test_demo_controls(demo):
    m = build(demo)
    assert "ACCDEP_DEBIT" in ids(m, "BLOCKING")
    assert {"TB_PLUG_COMMENT", "CIT_RATE"} <= ids(m, "WARNING")
    assert {"TB_BALANCED", "BS_BALANCED", "CF_CASH"} <= ids(m, "INFO")


def test_unbalanced_tb_is_blocking(demo):
    d = copy.deepcopy(demo)
    d["trial_balance"][0]["debit_cy"] += 1000
    m = build(d)
    assert "TB_NOT_BALANCED" in ids(m, "BLOCKING")


def test_unmapped_code_is_blocking(demo):
    d = copy.deepcopy(demo)
    d["trial_balance"][0]["code"] = "XX 9.9"
    assert "TB_UNMAPPED" in ids(build(d), "BLOCKING")


VALID = {c["code"] for s in CHART_D["pnl"] + CHART_D["bs"] for g in s.get("groups", []) for c in g["lines"]}


def test_tb_balance_and_line_issues(demo):
    tb = tb_io.from_pair_rows(demo["trial_balance"], 2025)
    assert tb_io.years_of(tb) == [2024, 2025]
    assert tb_io.balance(tb)["ok"]
    iss = tb_io.line_issues(tb, VALID)
    assert (iss["Issue"].str.contains("Accumulated depreciation")).sum() == 8   # 4 lines x 2 years
    assert not iss["Issue"].str.contains("Identical line").any()


def test_upload_mapping_roundtrip():
    data = (ROOT / "data" / "demo" / "demo_trial_balance.xlsx").read_bytes()
    name = "demo_trial_balance.xlsx"
    hdr = tb_io.guess_header_row(data, name)
    assert hdr == 3
    raw = tb_io.read_table(data, name, 0, hdr)
    mp = tb_io.guess_mapping(list(raw.columns))
    assert mp["account"] == "Account name" and [y["year"] for y in mp["years"]] == [2025, 2024]
    assert mp["years"][1]["credit"] == "Credit 2024"
    tb, notes = tb_io.to_tb(raw, mp)
    assert len(tb) == 42 and tb_io.balance(tb)["ok"]
    assert (tb["code"] == "").sum() == 4


def test_five_year_upload_drops_unlabelled_total():
    data = (ROOT / "data" / "demo" / "demo_trial_balance_5years.xlsx").read_bytes()
    name = "x.xlsx"
    raw = tb_io.read_table(data, name, 0, tb_io.guess_header_row(data, name))
    mp = tb_io.guess_mapping(list(raw.columns))
    assert sorted(y["year"] for y in mp["years"]) == [2021, 2022, 2023, 2024, 2025]
    tb, notes = tb_io.to_tb(raw, mp)
    assert len(tb) == 42 and tb_io.balance(tb)["ok"]
    assert any("total" in n for n in notes)


def test_nan_account_does_not_crash():
    df = pd.DataFrame({"Account": ["Bank", None], "Debit 2025": [100, 5], "Credit 2025": [0, 5]})
    tb, _ = tb_io.to_tb(df, tb_io.guess_mapping(list(df.columns)))
    iss = tb_io.line_issues(tb, VALID)
    assert "Account name missing" in set(iss["Issue"])
    assert code_suggest.suggest(float("nan"))[0] is None and code_suggest.suggest(None)[0] is None


def test_signed_balance_column():
    df = pd.DataFrame({"Account": ["Bank", "Capital"], "Balance 2025": [100, -100], "Balance 2024": ["(50)", "50"]})
    tb, _ = tb_io.to_tb(df, tb_io.guess_mapping(list(df.columns)))
    assert tb.loc[0, "debit_2025"] == 100 and tb.loc[1, "credit_2025"] == 100 and tb.loc[0, "credit_2024"] == 50


def test_multiyear_pairs_match_two_year_engine(demo):
    proj, tb = multiyear.from_pair_input(demo)
    m = build(multiyear.pair_input(proj, tb, 2025))
    assert round(m["key_figures"]["net_profit"]["cy"]) == 89_851_899
    assert m["meta"]["cit_rate"] if "cit_rate" in m["meta"] else True
    five = json.loads((ROOT / "data" / "demo" / "demo_project_5years.json").read_text(encoding="utf-8"))
    tb5 = tb_io.from_records(five["trial_balance"])
    assert multiyear.pairs(tb_io.years_of(tb5)) == [2022, 2023, 2024, 2025]
    models = {y: build(multiyear.pair_input(five, tb5, y)) for y in multiyear.pairs(tb_io.years_of(tb5))}
    rows, years = multiyear.multi_statement(models, "pnl")
    assert years == [2021, 2022, 2023, 2024, 2025]
    npr = next(r for r in rows if r["label"].startswith("Net profit"))
    assert round(npr["values"][-1]) == 89_851_899
    notes, ny = multiyear.multi_notes(models)
    assert ny == years and notes[0]["rows"]


def test_tb_template_reuploads():
    cat = pd.DataFrame([{"code": "BS 1.01", "statement": "Balance sheet", "section": "x", "group": "g", "line": "Land", "note": "11"}])
    x = package.tb_template([2025, 2024, 2023], cat, "ACME")
    hdr = tb_io.guess_header_row(x, "t.xlsx", "Trial Balance")
    assert hdr == 3
    raw = tb_io.read_table(x, "t.xlsx", "Trial Balance", hdr)
    mp = tb_io.guess_mapping(list(raw.columns))
    assert [y["year"] for y in mp["years"]] == [2025, 2024, 2023] and mp["code"] == "CIT code"


def test_code_suggestions():
    assert code_suggest.suggest("ACCUMULATED DEPRECIATION")[0] == "BS 1.09"
    assert code_suggest.suggest("Bank charges")[0] == "PL 7.02"
    assert code_suggest.suggest("BPR BANK PLC RWF")[0] == "BS 3.1.3.2"
    assert code_suggest.suggest("Dep-Moto Vehicle")[0] == "PL 5.01"


def test_render_docx_no_placeholder_left(demo):
    m = build(demo)
    with pytest.raises(render_report.BlockingControls):
        render_report.render(str(TEMPLATE), m, io.BytesIO())
    out = io.BytesIO()
    rep = render_report.render(str(TEMPLATE), m, out, allow_blocking=True)
    assert not rep["missing"] and rep["draft"]
    xml = zipfile.ZipFile(io.BytesIO(out.getvalue())).read("word/document.xml").decode("utf-8")
    assert "{" not in "".join(__import__("re").findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def test_statements_workbook(demo):
    x = package.statements_workbook(build(demo))
    sheets = pd.ExcelFile(io.BytesIO(x)).sheet_names
    assert {"P&L", "Balance sheet", "Cash flow", "Notes", "Controls"} <= set(sheets)


def test_template_cascade_lists_and_code_derivation():
    import openpyxl
    rows = []
    for stt, key in (("P&L", "pnl"), ("Balance sheet", "bs")):
        for sec in CHART_D[key]:
            for g in sec.get("groups", []):
                for ln in g["lines"]:
                    rows.append({"code": ln["code"], "statement": stt, "section": sec.get("title"),
                                 "group": g.get("label") or sec.get("title"), "line": ln["label"], "note": ""})
    cat = pd.DataFrame(rows)
    x = package.tb_template([2025, 2024], cat, "ACME")
    wb = openpyxl.load_workbook(io.BytesIO(x))
    assert wb.sheetnames == ["Instructions", "Trial Balance", "CIT codes", "Lists"]
    assert wb["Lists"].sheet_state == "hidden"
    assert len(wb["Trial Balance"].data_validations.dataValidation) == 5
    ws = wb["Trial Balance"]
    ws["C30"], ws["D30"], ws["F30"], ws["G30"] = "Cash and Cash equivalents", "Bank balances", "BK USD", 100
    buf = io.BytesIO(); wb.save(buf); data = buf.getvalue()
    raw = tb_io.read_table(data, "t.xlsx", "Trial Balance", tb_io.guess_header_row(data, "t.xlsx", "Trial Balance"))
    mp = tb_io.guess_mapping(list(raw.columns))
    tb, notes = tb_io.to_tb(raw, mp, cat)
    assert tb.loc[tb["account"] == "BK USD", "code"].iloc[0] == "BS 3.1.3.2"


def test_duplicate_descriptions_blocking_and_merge(demo):
    tb = tb_io.from_pair_rows(demo["trial_balance"], 2025)
    groups = tb_io.duplicate_groups(tb)
    acc = [g for g in groups if g["key"] == "accumulated depreciation"]
    assert acc and len(acc[0]["rows"]) == 4 and acc[0]["same_code"]
    assert "DUPLICATE_ACCOUNT" in ids(build(demo), "BLOCKING")
    merged = tb_io.merge_lines(tb, acc[0]["rows"])
    assert len(merged) == len(tb) - 3
    assert abs(merged[tb_io.amount_cols(merged)].sum() - tb[tb_io.amount_cols(tb)].sum()).max() < 0.01
    assert tb_io.balance(merged)["ok"]
    assert tb_io.desc_key("Bank  of Kigali - RWF ") == tb_io.desc_key("BANK OF KIGALI RWF")


def test_template_registry_and_generic_bookmarks(demo):
    import re as _re
    from engine import templates
    ts = templates.list_templates()
    assert ts and ts[0]["id"] == "standard-v09" and not ts[0]["error"]
    assert templates.check(ts[0]["docx"])["ok"]
    # a template using the generic names: rename two V09 bookmarks
    z = zipfile.ZipFile(str(TEMPLATE))
    parts = {n: z.read(n) for n in z.namelist()}
    x = parts["word/document.xml"].decode("utf-8")
    x = x.replace('w:name="str_Coverpage_Companyname"', 'w:name="str_companyname__9"')
    x = x.replace('w:name="tbl_PnL_Pnltable"', 'w:name="tbl_pnl"').replace('w:name="var_Pnlrelatednotessection"', 'w:name="var_notes"')
    parts["word/document.xml"] = x.encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zo:
        for n, d in parts.items():
            zo.writestr(n, d)
    chk = templates.check(buf.getvalue())
    assert chk["ok"] and "companyname" in chk["fields"]
    out = io.BytesIO()
    rep = render_report.render(io.BytesIO(buf.getvalue()), build(demo), out, allow_blocking=True, font_name="Georgia")
    assert "str_companyname__9" in rep["replaced"] and "tbl_pnl" in rep["replaced"] and "var_notes" in rep["replaced"]
    doc = zipfile.ZipFile(io.BytesIO(out.getvalue())).read("word/document.xml").decode("utf-8")
    assert set(_re.findall(r'w:ascii="([^"]+)"', doc)) <= {"Georgia", "Symbol"}


def test_company_data_roundtrip_and_multi_tb(demo):
    from engine import company_data
    proj, tb = multiyear.from_pair_input(demo)
    proj["general"]["audit_company_name"] = "AUDIT X"
    proj.setdefault("years_data", {}).setdefault("2025", {})["prepayments"] = 1234.0
    for fmt, data in (("json", company_data.to_json(proj)), ("xlsx", company_data.to_excel(proj, [2024, 2025]))):
        part = company_data.from_file(data, f"x.{fmt}")
        assert part["general"]["audit_company_name"] == "AUDIT X"
        assert abs(part["years_data"]["2025"]["prepayments"] - 1234) < 0.01
        assert abs(part["years_data"]["2025"]["cit_rate"] - proj["years_data"]["2025"]["cit_rate"]) < 1e-6
        target = {"meta": {}, "general": {}, "years_data": {}}
        assert "printed data" in company_data.apply(target, part)
    cat = pd.DataFrame([{"code": "BS 3.1.3.2", "statement": "Balance sheet", "section": "s", "group": "g", "line": "Bank", "note": ""},
                        {"code": "BS 5.01", "statement": "Balance sheet", "section": "s", "group": "g2", "line": "Capital", "note": ""}])
    rows = [{"code": "BS 3.1.3.2", "account": "BANK", "amounts": {2025: (100, 0), 2024: (50, 0)}},
            {"code": "BS 5.01", "account": "CAPITAL", "amounts": {2025: (0, 100), 2024: (0, 50)}}]
    x = package.tb_template([2025, 2024], cat, "ACME", sheets={"TB A": rows, "TB B": rows[:1]})
    found = tb_io.tb_sheets(x, "t.xlsx")
    assert [f["sheet"] for f in found] == ["TB A", "TB B"]
    assert found[0]["balanced"] and not found[1]["balanced"] and found[0]["lines"] == 2


def test_single_year_and_detail_levels(demo):
    proj, tb = multiyear.from_pair_input(demo)
    tb1 = tb.drop(columns=["debit_2024", "credit_2024"])            # company in its first year
    assert multiyear.single_year(proj, tb1, 2025)
    m = build(multiyear.pair_input(proj, tb1, 2025))
    assert m["meta"]["single_year"] and len(m["equity"]["blocks"]) == 1
    assert "RE_ROLLFORWARD" not in ids(m, "WARNING")
    out = io.BytesIO()
    render_report.render(str(TEMPLATE), m, out, allow_blocking=True)
    xml = zipfile.ZipFile(io.BytesIO(out.getvalue())).read("word/document.xml").decode("utf-8")
    assert ">2025<" in xml and ">2024<" not in xml
    # forced comparative
    proj["meta"]["comparative"] = "with"
    assert not multiyear.single_year(proj, tb1, 2025)
    # levels
    m2 = build(demo)
    det = render_report.apply_level(m2["pnl"], "detailed")
    summ = render_report.apply_level(m2["pnl"], "summarised")
    cond = render_report.apply_level(m2["bs"], "condensed")
    assert len(det) > len(summ) > 0
    assert [r["label"] for r in cond if r["type"] == "line"] == ["Non Current Assets", "Current Assets", "Equity",
                                                                   "Non Current Liabilities", "Current Liabilities"]
    np_row = next(r for r in render_report.apply_level(m2["pnl"], "condensed") if r["type"] == "grandtotal")
    assert round(np_row["cy"]) == 89_851_899
    rep = render_report.render(str(TEMPLATE), {**m2, "meta": {**m2["meta"], "detail_level": "condensed"}}, io.BytesIO(),
                               allow_blocking=True)
    assert not rep["missing"]


def test_company_sheets_inside_tb_file(demo):
    from engine import company_data
    proj, tb = multiyear.from_pair_input(demo)
    proj["general"]["audit_company_name"] = "AUDIT Y"
    cat = pd.DataFrame([{"code": "BS 5.01", "statement": "Balance sheet", "section": "s", "group": "g", "line": "Capital", "note": ""}])
    x = package.tb_template([2025, 2024], cat, "ACME", extra_sheets=company_data.frames(proj, [2024, 2025])[0])
    names = tb_io.sheet_names(x, "t.xlsx")
    assert company_data.has_company_sheets(names)
    assert [f["sheet"] for f in tb_io.tb_sheets(x, "t.xlsx")] == ["Trial Balance"]
    assert company_data.from_file(x, "t.xlsx")["general"]["audit_company_name"] == "AUDIT Y"
