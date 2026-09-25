#!/usr/bin/env python3
"""
xlsm_to_input.py — convert an Excel generator workbook (Template__Tool_Annualreport_Generator V11 layout)
into the input.json expected by build_model.py.

Usage: python xlsm_to_input.py generator.xlsm input.json

Reads (values only, macros untouched): Generaldata (bookmark table B7:E..), TrialBalance, Incometax
(prepayments / WHT), Inventorydetails, Assetdepreciation (additions), Equitystatement (drawings).
Anything it cannot find is left out so that build_model.py flags it.
"""
import json, sys, datetime as dt
import openpyxl


def iso(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return v.date().isoformat() if isinstance(v, dt.datetime) else v.isoformat()
    return v


def clean(v):
    if v is None:
        return None
    if isinstance(v, (dt.datetime, dt.date)):
        return iso(v)
    s = str(v).strip()
    return s


def read_generator(src):
    """src: path or file-like of a V11 generator workbook. Returns an input dict (same schema as input.json)."""
    wb = openpyxl.load_workbook(src, data_only=True, keep_vba=False)
    gd = wb["Generaldata"]
    bm = {}
    for r in range(8, gd.max_row + 1):
        name = gd.cell(r, 2).value
        if name:
            bm[str(name).strip()] = gd.cell(r, 4).value
    ctype = str(gd["B2"].value or "CORPORATE").strip().upper()
    pend = bm.get("str_Coverpage_FSenddate")
    pend = iso(pend) if pend else None

    def g(k):
        return clean(bm.get(k))

    aud_full = g("str_Regulatory_Auditcompanyfulladress") or g("str_Coverpage_Auditcompanyname") or ""
    aud_lines = [x.strip() for x in aud_full.splitlines() if x.strip()]
    general = {
        "audit_company_name": aud_lines[0] if aud_lines else g("str_Footer_Auditcompanyname"),
        "audit_company_address": "\n".join(aud_lines[1:]) if len(aud_lines) > 1 else None,
        "directors": g("str_Corpoinfo_Listofdirectors"),
        "registered_office": g("str_Corpoinfo_Companylocation"),
        "bankers": g("str_Corpoinfo_Listofbanks"),
        "main_activity": g("str_Notes01_Companymainactivity"),
        "auditor_report_framework": g("str_Auditorreport_Framework"),
        "accounting_framework": g("str_Notes_Auditframework"),
        "proposed_dividend": g("str_proposeddividend"),
        "signature_date": g("str_Directorstatement_Signaturedate"),
        "company_representative": g("str_Directorstatement_Representative"),
        "fs_signing_date": g("str_financialstatementsigningdate"),
        "company_director": g("str_Balancesheet_Companydirectorname"),
    }
    meta = {
        "company_name": g("str_Coverpage_Companyname"),
        "period_start": None,
        "period_end": pend,
        "currency": "Rwf",
        "company_type": ctype,
        "cit_rate": {"cy": gd["B4"].value, "py": gd["B5"].value},
        "tables_font_size": gd["F2"].value or 8,
        "variables_color": "0070C0",
        "hide_zero_lines": True,
        "source": getattr(src, "name", str(src)),
    }
    tbws = wb["TrialBalance"]
    tb = []
    for r in range(3, tbws.max_row + 1):
        code, acc = tbws.cell(r, 2).value, tbws.cell(r, 3).value
        code = str(code).strip() if code is not None else ""
        acc = str(acc).strip() if acc is not None else ""
        vals = [tbws.cell(r, c).value for c in (4, 5, 7, 8)]
        vals = [v if isinstance(v, (int, float)) else 0 for v in vals]
        if not acc:
            continue  # blank line or the un-labelled TOTAL line of the TrialBalance sheet
        if acc.upper() in ("TOTAL", "TOTALS", "GRAND TOTAL"):
            continue
        tb.append({"code": code, "account": acc, "debit_cy": vals[0] or 0, "credit_cy": vals[1] or 0,
                   "debit_py": vals[2] or 0, "credit_py": vals[3] or 0,
                   "comment": tbws.cell(r, 10).value})
    it = wb["Incometax"]
    tax = {"prepayments": {"cy": it["E23"].value or 0, "py": it["G23"].value or 0},
           "wht": {"cy": it["E24"].value or 0, "py": it["G24"].value or 0}}
    inv = wb["Inventorydetails"]
    inventory = None
    if any((inv.cell(r, 2).value or 0) != 0 for r in range(3, 8)):
        keys = {3: "opening", 4: "purchases", 5: "purchase_returns", 6: "cost_of_sales", 7: "gain_loss"}
        inventory = {y: {k: inv.cell(r, col).value or 0 for r, k in keys.items()} for y, col in (("cy", 2), ("py", 4))}
    model = {"meta": meta, "general": general, "trial_balance": tb, "tax": tax}
    if inventory:
        model["inventory_movement"] = inventory
    return json.loads(json.dumps(model, default=str))


def main(src, dst):
    model = read_generator(src)
    json.dump(model, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(f"{dst}: {len(model['trial_balance'])} TB lines, period end {model['meta']['period_end']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
