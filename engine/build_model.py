#!/usr/bin/env python3
"""
build_model.py — Trial balance + additional data  ->  financial statements model + controls.

Usage:
    python build_model.py input.json model.json [--chart ../assets/chart_of_accounts.json]
                          [--notes ../assets/notes_default.json] [--controls controls.md]

Deterministic replacement of the Excel generator sheets PnL, BalanceSheet, Cashflow,
Equitystatement, Incometax, Assetdepreciation, Inventorydetails and Note## (VBA
Give_Trialbalancenote + Generate_FSnoteTables + Add_Specialnotes).
Every rule, and every deviation from the V11 workbook, is documented in
references/computation-rules.md.
"""
import argparse, json, re, sys
from collections import OrderedDict, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOL = 1.0  # Rwf tolerance for equality checks


# --------------------------------------------------------------------------- helpers
def num(x):
    if x in (None, "", "-"):
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).replace(",", "").replace(" ", "").replace("\u202f", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def norm_code(c):
    if c is None:
        return ""
    c = re.sub(r"\s+", " ", str(c).strip().upper())
    # "BS3.1.2" -> "BS 3.1.2"
    c = re.sub(r"^(BS|PL)\s*", lambda m: m.group(1) + " ", c)
    return c


def zero(v):
    return abs(v) < 0.5


class Controls:
    def __init__(self):
        self.items = []

    def add(self, level, cid, msg, **data):
        # level: BLOCKING | WARNING | INFO
        self.items.append({"level": level, "id": cid, "message": msg, **data})

    def blocking(self):
        return [i for i in self.items if i["level"] == "BLOCKING"]


# --------------------------------------------------------------------------- TB
class TB:
    def __init__(self, rows, ctl):
        self.rows = []
        for i, r in enumerate(rows):
            code = norm_code(r.get("code"))
            row = {
                "idx": i + 1,
                "code": code,
                "account": ("" if r.get("account") is None or r.get("account") != r.get("account") else str(r.get("account"))).strip(),
                "dr_cy": num(r.get("debit_cy")), "cr_cy": num(r.get("credit_cy")),
                "dr_py": num(r.get("debit_py")), "cr_py": num(r.get("credit_py")),
                "note": r.get("note"),  # optional manual note override
                "comment": r.get("comment"),
            }
            if all(zero(row[k]) for k in ("dr_cy", "cr_cy", "dr_py", "cr_py")) and not row["account"]:
                continue
            self.rows.append(row)
        self.ctl = ctl

    def net(self, code, year, sign):
        """sign 'DR' -> debit-credit ; 'CR' -> credit-debit"""
        d = sum(r["dr_" + year] for r in self.rows if r["code"] == code)
        c = sum(r["cr_" + year] for r in self.rows if r["code"] == code)
        return d - c if sign == "DR" else c - d

    def totals(self, year):
        return (sum(r["dr_" + year] for r in self.rows), sum(r["cr_" + year] for r in self.rows))


# --------------------------------------------------------------------------- model
def build(inp, chart, notes_cfg):
    ctl = Controls()
    meta = inp.get("meta", {})
    pend = date.fromisoformat(meta["period_end"])
    y_cy, y_py = pend.year, pend.year - 1
    tb = TB(inp["trial_balance"], ctl)

    # ---------------- TB integrity
    for y, lab in (("cy", y_cy), ("py", y_py)):
        d, c = tb.totals(y)
        if abs(d - c) > TOL:
            ctl.add("BLOCKING", "TB_NOT_BALANCED", f"Trial balance {lab} does not balance: debit {d:,.0f} vs credit {c:,.0f} (diff {d-c:,.0f}).")
        else:
            ctl.add("INFO", "TB_BALANCED", f"Trial balance {lab} balances ({d:,.0f}).")

    known = {}
    for sec in chart["pnl"] + chart["bs"]:
        for g in sec.get("groups", []):
            for l in g["lines"]:
                known[l["code"]] = (sec, g, l)
    computed = set(chart.get("computed_lines", {}).keys())
    unmapped = [r for r in tb.rows if r["code"] not in known]
    for r in unmapped:
        amt = r["dr_cy"] - r["cr_cy"]
        ctl.add("BLOCKING", "TB_UNMAPPED", f"TB line {r['idx']} '{r['account']}' has code '{r['code'] or '(blank)'}' which is not in the chart — amount {amt:,.0f} would be lost.", line=r["idx"])
    for r in tb.rows:
        if r["code"] in computed:
            ctl.add("WARNING", "TB_COMPUTED_CODE", f"TB line {r['idx']} '{r['account']}' uses {r['code']}, a line computed by the generator (not read from TB). Its balance is ignored in the statements.", line=r["idx"])
        if re.search(r"balanc|plug|make.*tb", str(r.get("comment") or ""), re.I):
            ctl.add("WARNING", "TB_PLUG_COMMENT", f"TB line {r['idx']} '{r['account']}' is commented as a balancing figure: '{str(r.get('comment')).strip()[:80]}'. Its {r['dr_cy']-r['cr_cy']:,.0f} (CY) must be analysed before issuing the report.", line=r["idx"])
        if re.search(r"suspense|balancing|plug|to be allocated", r["account"], re.I):
            ctl.add("WARNING", "TB_SUSPENSE", f"TB line {r['idx']} '{r['account']}' looks like a suspense/plug account.", line=r["idx"])
    # a CIT code may be used on several lines, but each line needs its own description (notes list accounts by name)
    seen = defaultdict(list)
    for r in tb.rows:
        k = re.sub(r"[^a-z0-9]+", " ", r["account"].lower()).strip()
        if k:
            seen[k].append(r)
    for k, rs in seen.items():
        if len(rs) > 1:
            ctl.add("BLOCKING", "DUPLICATE_ACCOUNT", f"Account description '{rs[0]['account']}' is used on {len(rs)} TB lines "
                    f"({', '.join(str(x['idx']) for x in rs)}) — merge them into one line or give each line a different description.")
    if all(zero((r["dr_cy"] - r["cr_cy"]) - (r["dr_py"] - r["cr_py"])) for r in tb.rows if r["code"].startswith("BS")):
        ctl.add("WARNING", "PY_EQUALS_CY", "All balance-sheet balances are identical in both years — previous-year column may be a copy of the current year.")

    # ---------------- line amounts
    def amt(code, sign, y):
        return tb.net(code, y, sign)

    # ---------------- P&L
    val = {}  # section/group id -> {"cy":..,"py":..}
    pnl_rows = []

    def add_row(rows, typ, label, note=None, cy=None, py=None, code=None):
        rows.append({"type": typ, "label": label, "note": note,
                     "cy": None if cy is None else round(cy, 2), "py": None if py is None else round(py, 2), "code": code})

    def group_block(rows, g, sec_note):
        lines = []
        for l in g["lines"]:
            cy, py = amt(l["code"], g["sign"], "cy"), amt(l["code"], g["sign"], "py")
            lines.append((l, cy, py))
        gcy, gpy = sum(x[1] for x in lines), sum(x[2] for x in lines)
        val[g["id"]] = {"cy": gcy, "py": gpy}
        return lines, gcy, gpy

    tax = None
    for sec in chart["pnl"]:
        if "subtotal" in sec:
            cy = sum(val[s]["cy"] for s in sec["of"]); py = sum(val[s]["py"] for s in sec["of"])
            val[sec["id"]] = {"cy": cy, "py": py}
            add_row(pnl_rows, "grandtotal" if sec["id"] == "np" else "subtotal", sec["subtotal"], None, cy, py)
            continue
        if sec.get("special") == "income_tax":
            tax = income_tax(inp, chart, tb, val["pbt"], ctl, meta)
            cy, py = -tax["charge"]["cy"], -tax["charge"]["py"]
            val[sec["id"]] = {"cy": cy, "py": py}
            add_row(pnl_rows, "line_bold", sec["label"], str(int(sec["note"])), cy, py, sec["code"])
            continue
        add_row(pnl_rows, "title", sec["title"], str(int(sec["note"])) if sec.get("note") else None)
        tcy = tpy = 0.0
        for g in sec["groups"]:
            lines, gcy, gpy = group_block(pnl_rows, g, sec.get("note"))
            if g["label"]:
                add_row(pnl_rows, "group", g["label"], None)
            for l, cy, py in lines:
                add_row(pnl_rows, "line", l["label"], None, cy, py, l["code"])
            if g["label"]:
                add_row(pnl_rows, "total", "Total " + g["label"], str(int(g["note"])) if g.get("note") and sec["id"] == "opex" else None, gcy, gpy)
            if g.get("in_total", True):
                tcy += gcy; tpy += gpy
        if "stock_variation" in sec:
            sv = sec["stock_variation"]
            add_row(pnl_rows, "group", sv["label"], None)
            scy = spy = 0.0
            for o, c, lab in sv["pairs"]:
                gs = "CR"
                cy = amt(o, gs, "cy") + amt(c, gs, "cy"); py = amt(o, gs, "py") + amt(c, gs, "py")
                scy += cy; spy += py
                add_row(pnl_rows, "line", lab, None, cy, py)
            add_row(pnl_rows, "total", "Total " + sv["label"], None, scy, spy)
            tcy += scy; tpy += spy
        val[sec["id"]] = {"cy": tcy, "py": tpy}
        add_row(pnl_rows, "sectiontotal", sec["total_label"], sec.get("total_note") or (str(int(sec["note"])) if sec.get("note") else None), tcy, tpy)

    # ---------------- Balance sheet
    bs_rows = []
    net_profit = val["np"]
    side_tot = defaultdict(lambda: {"cy": 0.0, "py": 0.0})
    bsval = {}
    current_side = None
    for sec in chart["bs"]:
        if sec["side"] != current_side:
            if current_side == "assets":
                add_row(bs_rows, "grandtotal", "TOTAL ASSETS", None, side_tot["assets"]["cy"], side_tot["assets"]["py"])
            current_side = sec["side"]
            add_row(bs_rows, "heading", "ASSETS" if current_side == "assets" else "EQUITY & LIABILITIES")
        add_row(bs_rows, "title", sec["title"], None)
        tcy = tpy = 0.0
        for g in sec["groups"]:
            lines = []
            for l in g["lines"]:
                if l["code"] == "BS 5.08":
                    cy, py = net_profit["cy"], net_profit["py"]
                elif l["code"] == "BS 8.2.1":
                    cy, py = tax["charge"]["cy"], tax["charge"]["py"]
                else:
                    cy, py = amt(l["code"], g["sign"], "cy"), amt(l["code"], g["sign"], "py")
                lines.append((l, cy, py))
            gcy, gpy = sum(x[1] for x in lines), sum(x[2] for x in lines)
            bsval[g["id"]] = {"cy": gcy, "py": gpy}
            if g["label"]:
                add_row(bs_rows, "group", g["label"], str(int(g["note"])) if g.get("note") else None, gcy, gpy)
            for l, cy, py in lines:
                add_row(bs_rows, "line", l["label"], None, cy, py, l["code"])
            tcy += gcy; tpy += gpy
        bsval[sec["id"]] = {"cy": tcy, "py": tpy}
        add_row(bs_rows, "sectiontotal", sec["total_label"], None, tcy, tpy)
        side_tot[sec["side"]]["cy"] += tcy; side_tot[sec["side"]]["py"] += tpy
    add_row(bs_rows, "grandtotal", "TOTAL EQUITY & LIABILITIES", None, side_tot["equity_liabilities"]["cy"], side_tot["equity_liabilities"]["py"])
    for y, lab in (("cy", y_cy), ("py", y_py)):
        d = side_tot["assets"][y] - side_tot["equity_liabilities"][y]
        if abs(d) > TOL:
            ctl.add("BLOCKING", "BS_NOT_BALANCED", f"Balance sheet {lab} does not balance: assets {side_tot['assets'][y]:,.0f} vs equity & liabilities {side_tot['equity_liabilities'][y]:,.0f} (diff {d:,.0f}).")
        else:
            ctl.add("INFO", "BS_BALANCED", f"Balance sheet {lab} balances ({side_tot['assets'][y]:,.0f}).")

    # accumulated depreciation sign
    for y in ("cy", "py"):
        ad = amt("BS 1.09", "DR", y)
        if ad > TOL:
            ctl.add("BLOCKING", "ACCDEP_DEBIT", f"Accumulated depreciation (BS 1.09) has a DEBIT balance {ad:,.0f} ({y_cy if y=='cy' else y_py}) — it is ADDED to fixed assets. It must be a credit balance.")
    dep_pl = -amt("PL 5.01", "CR", "cy")
    dacc = -(amt("BS 1.09", "DR", "cy") - amt("BS 1.09", "DR", "py"))
    if abs(dep_pl - dacc) > TOL:
        ctl.add("WARNING", "DEP_MISMATCH", f"Depreciation charge in P&L (PL 5.01) {dep_pl:,.0f} differs from the movement of accumulated depreciation (BS 1.09) {dacc:,.0f} (disposals?).")

    # retained earnings roll-forward
    re_cy, re_py = amt("BS 5.07", "CR", "cy"), amt("BS 5.07", "CR", "py")
    drawings = inp.get("equity_movements", {}).get("cy", {})
    exp_re = re_py + net_profit["py"] + num(drawings.get("dividends_paid")) * -1 + num(drawings.get("adjustments"))
    if abs(re_cy - exp_re) > TOL:
        ctl.add("WARNING", "RE_ROLLFORWARD", f"Retained earnings {y_cy} opening ({re_cy:,.0f}) ≠ retained earnings {y_py} ({re_py:,.0f}) + profit {y_py} ({net_profit['py']:,.0f}) ± movements = {exp_re:,.0f}.")

    # ---------------- Cash flow (current year, V11 logic)
    cf = cash_flow(inp, val, bsval, amt, ctl, y_cy)

    # ---------------- Equity statement
    eq = equity_statement(inp, amt, net_profit, bsval, ctl, pend)

    # ---------------- PPE schedule & inventory
    ppe = ppe_schedule(inp, amt, dep_pl, ctl, pend)
    inv = inventory_movement(inp, bsval, ctl, y_cy, y_py)

    # ---------------- Notes
    notes = build_notes(inp, notes_cfg, chart, tb, known, tax, ppe, inv, bsval, val, ctl, pend)

    # ---------------- general data completeness
    g = inp.get("general", {})
    required = ["company_name", "audit_company_name", "audit_company_address", "directors", "registered_office",
                "bankers", "main_activity", "auditor_report_framework", "accounting_framework"]
    for k in required:
        v = g.get(k) if k != "company_name" else meta.get("company_name", g.get("company_name"))
        if v in (None, "", "-") or (isinstance(v, str) and re.fullmatch(r"[-\s0:]*", v)):
            ctl.add("WARNING", "MISSING_DATA", f"General data '{k}' is missing or a placeholder ('{v}').", field=k)
    rate = meta.get("cit_rate", {})
    if meta.get("company_type", "CORPORATE") == "CORPORATE":
        for y, yr in (("cy", pend.year), ("py", pend.year - 1)):
            r_ = num(rate.get(y, 0))
            std = 0.28 if yr >= 2024 else 0.30
            if abs(r_ - std) > 1e-4:
                ctl.add("WARNING", "CIT_RATE", f"CIT rate used for {yr} is {r_:.2%}; Rwanda standard rate is {std:.0%} for {yr} (Law 051/2023: 28% from 2024; 2023 prorated). Confirm any reduced/incentive rate.")

    return {
        "meta": {**meta, "year_cy": y_cy, "year_py": y_py},
        "general": g,
        "pnl": pnl_rows, "bs": bs_rows, "cashflow": cf, "equity": eq,
        "income_tax": tax, "ppe": ppe, "inventory": inv, "notes": notes,
        "key_figures": {"revenue": val["rev"], "gross_profit": val["gp"], "pbt": val["pbt"], "net_profit": net_profit,
                         "total_assets": side_tot["assets"], "total_equity": bsval["eq"]},
        "controls": ctl.items,
    }


def income_tax(inp, chart, tb, pbt, ctl, meta):
    it = chart["income_tax"]
    t = inp.get("tax", {})
    ctype = meta.get("company_type", "CORPORATE").upper()
    rates = meta.get("cit_rate", {"cy": 0.28, "py": 0.30})
    res = {"rows": [], "charge": {}, "base": {}, "payable": {}}
    lines = {"cy": [], "py": []}
    out = {}
    for y in ("cy", "py"):
        grant = num(t.get("grants", {}).get(y))
        pn = pbt[y] + grant
        adds = []
        for code, lab, coef in it["add_backs"]:
            adds.append((lab, coef * tb.net(code, y, "DR")))
        tot_add = sum(a for _, a in adds)
        adj = pn + tot_add
        lb = t.get("loss_brought_forward", {}).get(y)
        if lb is None:
            lb = 0.0
            if y == "py":
                lb = min(0.0, tb.net("BS 5.07", "py", "DR") * -1) if tb.net("BS 5.07", "py", "DR") > 0 else 0.0
        lb = -abs(num(lb))
        base = adj + lb
        if ctype == "CORPORATE" and base > 0:
            charge = num(rates.get(y)) * base
        else:
            charge = 0.0
            if base > 360000:
                charge = 0.2 * (min(base, 1200000) - 360000) + (0.3 * (base - 1200000) if base > 1200000 else 0)
        prepay = num(t.get("prepayments", {}).get(y)); wht = num(t.get("wht", {}).get(y))
        out[y] = dict(pbt=pbt[y], grant=grant, pn=pn, adds=adds, tot_add=tot_add, adj=adj, lb=lb, base=base,
                      charge=charge, prepay=prepay, wht=wht, payable=charge - prepay - wht)
        res["charge"][y] = charge; res["base"][y] = base; res["payable"][y] = charge - prepay - wht
    c, p = out["cy"], out["py"]
    R = res["rows"]
    def r(typ, lab, k=None, cy=None, py=None):
        R.append({"type": typ, "label": lab, "cy": round(cy if cy is not None else c[k], 2), "py": round(py if py is not None else p[k], 2)})
    r("line", "Profit before tax", "pbt"); r("line", "Grant received", "grant"); r("total", "Profit net of grant received", "pn")
    R.append({"type": "group", "label": "Non-admissible expenses", "cy": None, "py": None})
    for i, (lab, _) in enumerate(c["adds"]):
        r("line", lab, cy=c["adds"][i][1], py=p["adds"][i][1])
    r("total", "Total expenses to add back", "tot_add"); r("line_bold", "Adjusted profit", "adj")
    r("line", "Loss from previous periods", "lb"); r("total", "Tax base", "base")
    r("sectiontotal", f"Tax charge for the period", "charge")
    r("line", "Quarterly prepayments", "prepay"); r("line", "Withholding tax (3% & 15%)", "wht")
    r("grandtotal", "Income tax payable", "payable")
    res["detail"] = out
    if c["base"] > 0 and ctype == "CORPORATE":
        ctl.add("INFO", "CIT", f"CIT {meta.get('period_end')}: base {c['base']:,.0f} × {num(rates.get('cy')):.2%} = {c['charge']:,.0f}.")
    return res


def cash_flow(inp, val, bsval, amt, ctl, y_cy):
    pbt = val["pbt"]["cy"]
    dep = -amt("PL 5.01", "CR", "cy")
    intr = -amt("PL 7.01", "CR", "cy")
    d = lambda k: bsval[k]["cy"] - bsval[k]["py"]
    inv = -d("stock")
    rec = -(d("ar") + d("loans") + d("taxrec"))
    pay = d("cur") + d("prov") + d("sttax")
    opbwc = pbt + dep + intr
    gen = opbwc + inv + rec + pay
    cfin = inp.get("cashflow", {})
    taxpaid = -abs(num(cfin.get("income_tax_paid")))
    intpaid = -intr
    op = gen + taxpaid + intpaid
    capex = -(d("ppe") + dep) - num(cfin.get("intangibles_acquired"))
    disp = num(cfin.get("disposal_proceeds"))
    inv_cf = capex + disp - num(cfin.get("intangibles_acquired")) * 0
    eqv = d("eq") - pbt
    lt = d("secured") + d("unsecured")
    st = num(cfin.get("short_term_borrowings"))
    dirl = num(cfin.get("additional_loans_from_directors"))
    fin = eqv + dirl + lt + st
    net = op + inv_cf + fin
    opening = bsval["cash"]["py"]; closing = opening + net
    rows = [
        ("title", "Cash flows from operating activities", None),
        ("line", "Profit for the year before taxation", pbt),
        ("group", "Adjustment for:", None),
        ("line", "Depreciation of property and equipment", dep),
        ("line", "Interest expense", intr),
        ("total", "Operating profit before working capital changes", opbwc),
        ("group", "Changes in operating assets and liabilities:", None),
        ("line", "(Increase)/decrease in inventories", inv),
        ("line", "(Increase)/decrease in trade and other receivables", rec),
        ("line", "Increase/(decrease) in trade and other payables", pay),
        ("total", "Cash generated from operations", gen),
        ("line", "Income tax paid", taxpaid),
        ("line", "Interest paid", intpaid),
        ("sectiontotal", "Net cash generated from operating activities", op),
        ("title", "Cash flows from investing activities", None),
        ("line", "Purchase of property and equipment", capex),
        ("line", "Proceeds from disposal of property and equipment", disp),
        ("sectiontotal", "Net cash used in investing activities", inv_cf),
        ("title", "Cash flows from financing activities", None),
        ("line", "Variation of equity", eqv),
        ("line", "Additional loans from directors", dirl),
        ("line", "Long term borrowings", lt),
        ("line", "Short term borrowings", st),
        ("sectiontotal", "Net cash generated from financing activities", fin),
        ("subtotal", "Net increase/(decrease) in cash and cash equivalents", net),
        ("line", "Cash and cash equivalents at the beginning of the year", opening),
        ("grandtotal", "Cash and cash equivalents at the end of the year", closing),
    ]
    if abs(closing - bsval["cash"]["cy"]) > TOL:
        ctl.add("BLOCKING", "CF_CASH", f"Cash flow closing cash {closing:,.0f} ≠ balance-sheet cash {bsval['cash']['cy']:,.0f} (diff {closing-bsval['cash']['cy']:,.0f}).")
    else:
        ctl.add("INFO", "CF_CASH", "Cash flow statement reconciles to balance-sheet cash.")
    if taxpaid == 0:
        ctl.add("INFO", "CF_TAXPAID", "Income tax paid is 0 in the cash flow (V11 behaviour: tax provision movement stays in payables). Provide cashflow.income_tax_paid if tax was paid.")
    return [{"type": t, "label": l, "cy": (round(v, 2) if v is not None else None), "py": None} for t, l, v in rows]


def equity_statement(inp, amt, np_, bsval, ctl, pend):
    cols = [("Share Capital", ["BS 5.01", "BS 5.02"]), ("Retained earnings", ["BS 5.07"]),
            ("Revaluation reserves", ["BS 5.03"]), ("General reserves", ["BS 5.04", "BS 5.05", "BS 5.06"]),
            ("Grants", ["BS 5.09"])]
    mv = inp.get("equity_movements", {})
    blocks = []
    for y, lab in (("cy", pend.year), ("py", pend.year - 1)):
        opening = [sum(amt(c, "CR", y) for c in codes) for _, codes in cols]
        dr = [-num(mv.get(y, {}).get("drawings", {}).get(n, 0)) if isinstance(mv.get(y, {}).get("drawings"), dict) else 0 for n, _ in cols]
        if not isinstance(mv.get(y, {}).get("drawings"), dict):
            dr[1] = -num(mv.get(y, {}).get("drawings", 0))
        adj = [0.0] * 5; adj[1] = num(mv.get(y, {}).get("adjustments", 0))
        prof = [0.0] * 5; prof[1] = np_[y]
        close = [opening[i] + dr[i] + adj[i] + prof[i] for i in range(5)]
        rows = []
        for t, l, v in (("line", "At 1st January", opening), ("line", "Drawings / dividends", dr),
                        ("line", "Adjustment from previous years", adj), ("line", "Profit (Loss) of the year", prof),
                        ("grandtotal", "At 31st December", close)):
            rows.append({"type": t, "label": l, "values": [round(x, 2) for x in v] + [round(sum(v), 2)]})
        blocks.append({"title": f"Year ended {pend.day:02d}-{pend.strftime('%B')}-{lab}", "rows": rows})
        tot = sum(close)
        if abs(tot - bsval["eq"][y]) > TOL:
            ctl.add("WARNING", "EQ_STATEMENT", f"Equity statement closing {lab} {tot:,.0f} ≠ balance-sheet equity {bsval['eq'][y]:,.0f}.")
    return {"columns": [c for c, _ in cols] + ["Total"], "blocks": blocks}


DEFAULT_PPE = [("Land", ["BS 1.01", "BS 1.10"], 0.0), ("Buildings", ["BS 1.02"], 0.05), ("Motor vehicles", ["BS 1.03"], 0.25),
               ("Machinery", ["BS 1.04", "BS 1.05"], 0.25), ("Intangible", ["BS 1.06"], 0.10),
               ("Furniture", ["BS 1.07"], 0.25), ("Computers & other", ["BS 1.08"], 0.50)]


def ppe_schedule(inp, amt, dep_pl, ctl, pend):
    fa = inp.get("fixed_assets")
    if fa and fa.get("categories"):
        cats = fa["categories"]
        cols = [c["name"] for c in cats]
        get = lambda k: [num(c.get(k)) for c in cats]
        cost_o, add, disp = get("cost_opening"), get("additions"), get("disposals")
        dep_o, chg, depdisp = get("dep_opening"), get("charge"), get("dep_on_disposals")
        source = "fixed asset register (input)"
    else:
        cats = [c for c in DEFAULT_PPE if any(abs(amt(k, "DR", y)) > TOL for k in c[1] for y in ("cy", "py"))]
        cols = [c[0] for c in cats]
        cost_o = [sum(amt(k, "DR", "py") for k in c[1]) for c in cats]
        cost_c = [sum(amt(k, "DR", "cy") for k in c[1]) for c in cats]
        add = [max(0.0, cost_c[i] - cost_o[i]) for i in range(len(cats))]
        disp = [min(0.0, cost_c[i] - cost_o[i]) for i in range(len(cats))]
        # accumulated depreciation is only known in total (BS 1.09) -> allocate pro rata to cost
        acc_o = -amt("BS 1.09", "DR", "py")  # credit balance positive
        tc = sum(cost_o) or 1.0
        dep_o = [acc_o * c / tc for c in cost_o]
        tcc = sum(cost_c) or 1.0
        chg = [dep_pl * c / tcc for c in cost_c]
        depdisp = [0.0] * len(cats)
        source = "trial balance (accumulated depreciation and charge allocated pro rata to cost)"
        ctl.add("WARNING", "PPE_ALLOCATED", "No fixed asset register provided: depreciation by category in note 11 is allocated pro rata to cost. Provide fixed_assets.categories for an exact schedule.")
    n = len(cols)
    cost_c = [cost_o[i] + add[i] + disp[i] for i in range(n)]
    dep_c = [dep_o[i] + chg[i] + depdisp[i] for i in range(n)]
    nbv = [cost_c[i] - dep_c[i] for i in range(n)]
    S = lambda v: [round(x, 2) for x in v] + [round(sum(v), 2)]
    rows = [("group", "Cost", None), ("line", "At 1st January", S(cost_o)), ("line", "Additions", S(add)),
            ("line", "Disposals", S(disp)), ("total", "At 31st December", S(cost_c)),
            ("group", "Depreciation", None), ("line", "At 1st January", S(dep_o)), ("line", "Charge for the year", S(chg)),
            ("line", "On disposals", S(depdisp)), ("total", "At 31st December", S(dep_c)),
            ("grandtotal", "Net book value at 31st December", S(nbv))]
    if abs(sum(chg) - dep_pl) > TOL:
        ctl.add("WARNING", "PPE_CHARGE", f"Depreciation charge in note 11 ({sum(chg):,.0f}) ≠ P&L depreciation ({dep_pl:,.0f}).")
    return {"columns": cols + ["Total"], "rows": [{"type": t, "label": l, "values": v} for t, l, v in rows],
            "source": source, "nbv_total": round(sum(nbv), 2)}


def inventory_movement(inp, bsval, ctl, y_cy, y_py):
    im = inp.get("inventory_movement")
    if not im:
        if abs(bsval["stock"]["cy"]) > TOL:
            ctl.add("WARNING", "INV_MISSING", "Inventories exist but no inventory movement (opening, purchases, cost of sales, gains/losses) was provided — note 12 movement table omitted.")
        return None
    rows = []
    keys = [("opening", "At 1st January"), ("purchases", "Purchases"), ("purchase_returns", "Purchase returns"),
            ("cost_of_sales", "Cost of sales"), ("gain_loss", "Inventory gain/(loss)")]
    vals = {y: [num(im.get(y, {}).get(k)) for k, _ in keys] for y in ("cy", "py")}
    for i, (k, lab) in enumerate(keys):
        rows.append({"type": "line", "label": lab, "cy": vals["cy"][i], "py": vals["py"][i]})
    cc, cp = sum(vals["cy"]), sum(vals["py"])
    rows.append({"type": "grandtotal", "label": "At 31st December", "cy": cc, "py": cp})
    if abs(cc - bsval["stock"]["cy"]) > TOL:
        ctl.add("WARNING", "INV_CLOSING", f"Inventory movement closing {cc:,.0f} ≠ balance-sheet inventories {bsval['stock']['cy']:,.0f}.")
    return {"rows": rows}


def build_notes(inp, notes_cfg, chart, tb, known, tax, ppe, inv, bsval, val, ctl, pend):
    code_note = {}
    for sec in chart["pnl"] + chart["bs"]:
        for g in sec.get("groups", []):
            n = g.get("note", sec.get("note"))
            for l in g["lines"]:
                code_note[l["code"]] = n
    cfg = inp.get("notes") or notes_cfg["notes"]
    fmt_date = f"{pend.day:02d}-{pend.strftime('%B')}-{pend.year}"
    by_note = defaultdict(list)
    for r in tb.rows:
        n = r["note"] or code_note.get(r["code"])
        if r["code"] in ("BS 5.08", "BS 8.2.1"):
            continue
        if n:
            by_note[str(n).zfill(2)].append(r)
    out = []
    used = set()
    for nc in cfg:
        nid = str(nc["id"]).zfill(2)
        note = {"id": nid, "title": nc["title"], "blocks": []}
        way = {"D": 1, "C": -1}.get(nc.get("way"), 1)
        for src in nc.get("tables", []):
            if src == "tb":
                rows = [r for r in by_note.get(nid, []) if not (zero(r["dr_cy"] - r["cr_cy"]) and zero(r["dr_py"] - r["cr_py"]))]
                used.add(nid)
                extra = []
                if nid == str(code_note.get("BS 8.2.1") or "").zfill(2):
                    extra = [{"type": "line", "label": "Provision for income tax (note 10)", "cy": round(tax["charge"]["cy"], 2), "py": round(tax["charge"]["py"], 2)}]
                if rows or extra:
                    tr = extra + [{"type": "line", "label": r["account"], "cy": round((r["dr_cy"] - r["cr_cy"]) * way, 2),
                           "py": round((r["dr_py"] - r["cr_py"]) * way, 2)} for r in rows]
                    tr.append({"type": "grandtotal", "label": "TOTAL", "cy": round(sum(x["cy"] for x in tr), 2), "py": round(sum(x["py"] for x in tr), 2)})
                    note["blocks"].append({"kind": "table2", "subtitle": nc.get("tb_subtitle"), "rows": tr})
            elif src == "income_tax":
                note["blocks"].append({"kind": "table2", "subtitle": None, "rows": tax["rows"]})
            elif src == "ppe" and ppe:
                note["blocks"].append({"kind": "tableN", "subtitle": nc.get("ppe_subtitle"), "columns": ppe["columns"], "rows": ppe["rows"]})
            elif src == "inventory" and inv:
                note["blocks"].append({"kind": "table2", "subtitle": nc.get("inventory_subtitle"), "rows": inv["rows"]})
        if nc.get("text"):
            note["blocks"].append({"kind": "text", "text": nc["text"].replace("{period_end}", fmt_date)})
        if not note["blocks"]:
            note["blocks"].append({"kind": "text", "text": nc.get("empty_text", "Nil for the years presented.")})
            ctl.add("INFO", "NOTE_EMPTY", f"Note {nid} '{nc['title']}' has no balance — rendered with the text 'Nil'.")
        out.append(note)
    for nid, rows in by_note.items():
        if nid not in used:
            ctl.add("WARNING", "NOTE_ORPHAN", f"{len(rows)} TB account(s) map to note {nid}, which is not in the notes list — they appear in the statements but in no note.")
    # numbering continuity (Word auto-numbers Heading 3)
    ids = [n["id"] for n in out]
    nums = [int(re.match(r"\d+", i).group()) for i in ids]
    for a, b in zip(nums, nums[1:]):
        if b != a + 1:
            ctl.add("BLOCKING", "NOTE_SEQUENCE", f"Note ids must be consecutive (Word numbers Heading 3 automatically): {a} is followed by {b}.")
    return out


def controls_md(model):
    L = ["# Controls report", "", f"Company: {model['meta'].get('company_name')} — period ended {model['meta']['period_end']}", ""]
    for lvl in ("BLOCKING", "WARNING", "INFO"):
        it = [i for i in model["controls"] if i["level"] == lvl]
        L.append(f"## {lvl} ({len(it)})")
        L += [f"- `{i['id']}` {i['message']}" for i in it] or ["- none"]
        L.append("")
    k = model["key_figures"]
    L += ["## Key figures", "", "| | CY | PY |", "|---|---:|---:|"]
    for n, v in k.items():
        L.append(f"| {n} | {v['cy']:,.0f} | {v['py']:,.0f} |")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("output")
    ap.add_argument("--chart", default=str(HERE.parent / "assets" / "chart_of_accounts.json"))
    ap.add_argument("--notes", default=str(HERE.parent / "assets" / "notes_default.json"))
    ap.add_argument("--controls", default=None)
    a = ap.parse_args()
    inp = json.load(open(a.input, encoding="utf-8"))
    model = build(inp, json.load(open(a.chart)), json.load(open(a.notes, encoding="utf-8")))
    json.dump(model, open(a.output, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    md = controls_md(model)
    if a.controls:
        open(a.controls, "w", encoding="utf-8").write(md)
    b = [i for i in model["controls"] if i["level"] == "BLOCKING"]
    w = [i for i in model["controls"] if i["level"] == "WARNING"]
    print(f"model written: {a.output} | BLOCKING {len(b)} | WARNING {len(w)}")
    for i in b:
        print("  BLOCKING", i["id"], i["message"])
    sys.exit(0)
