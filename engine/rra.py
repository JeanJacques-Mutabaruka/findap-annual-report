"""RRA CIT annexure (e-tax "CITRealAnnexure") — balance sheet and P&L lines, totals, update check.

data/rra_annexure.json holds the lines of the RRA file the chart was mapped to (sheet, row, serial as text,
description, level, formula). The link from every app code to its RRA line is stored in
data/chart_of_accounts.json ("rra": {"sheet", "row", "serial"}; sub-codes carry "rollup": true).

Traps of the RRA file handled here:
- PROFIT_AND_LOSS stores the Serial No as a NUMBER (4.10 reads 4.1, 4.20 reads 4.2, 8.10 reads 8.1):
  the text serial is rebuilt from the row order (n-th numeric child of its parent);
- BALANCE_SHEET gives 3.1.3.1 to both "Cash in hand" and "Bank balances": lines are identified by
  (sheet, row), never by the serial alone.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

from engine import DATA
from engine.codes import from_serial

RRA_FILE = DATA / "rra_annexure.json"
SHEETS = {"BALANCE_SHEET": "BS", "PROFIT_AND_LOSS": "PL"}
# Headings whose total is not "sum of the lines below" and whose RRA description gives no formula.
FORMULA_OVERRIDES = {("PL", "2"): ("2.1+2.2+2.3+2.4-2.5", "app assumption — cost of sales = opening stock + purchases + "
                                   "other direct costs + factory overheads − closing stock (RRA gives no formula)")}
# P&L lines below profit before tax that come from the tax computation, not from the TB.
TAX_LINES = {"11": "add_backs", "14": "loss_brought_forward", "16": "income_tax"}


def _txt(v) -> str:
    return " ".join(str(v).replace("\xa0", " ").split()) if v is not None else ""


def parse_workbook(data: bytes) -> dict:
    """Read the BALANCE_SHEET and PROFIT_AND_LOSS sheets of an RRA annexure (.xlsm / .xlsx).
    Returns {"lines": [...], "source": ...}. Raises ValueError if the sheets are missing."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    missing = [s for s in SHEETS if s not in wb.sheetnames]
    if missing:
        raise ValueError(f"sheet(s) {', '.join(missing)} not found — is this the RRA CIT annexure file?")
    lines = []
    for sheet, pre in SHEETS.items():
        count: dict[str, int] = {}
        for i, row in enumerate(wb[sheet].iter_rows(min_row=2, max_col=2, values_only=True), start=2):
            v, d = row[0], row[1]
            if v is None or _txt(v) == "":
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if float(v).is_integer():
                    serial = str(int(v))
                else:                                       # numeric child: rebuild from the order (4.1 -> 4.10)
                    par = str(int(v))
                    count[par] = count.get(par, 0) + 1
                    serial = f"{par}.{count[par]}"
                    if float(serial) != float(v):           # order does not fit: keep the value as written
                        serial = repr(float(v))
            else:
                serial = _txt(v).rstrip(".")
                if serial.count(".") == 1:                  # a text child counts in its parent's numbering too
                    par = serial.split(".")[0]
                    count[par] = count.get(par, 0) + 1
            lines.append({"sheet": pre, "row": i, "serial": serial, "raw": v if not isinstance(v, str) else _txt(v),
                          "desc": _txt(d), "level": serial.count(".") + 1})
    for ln in lines:
        ln.update(_formula(ln, lines))
    return {"lines": lines}


def _formula(ln: dict, lines: list[dict]) -> dict:
    same = [x for x in lines if x["sheet"] == ln["sheet"]]
    children = [x for x in same if x["serial"].startswith(ln["serial"] + ".") and x["level"] == ln["level"] + 1]
    ov = FORMULA_OVERRIDES.get((ln["sheet"], ln["serial"]))
    if ov:
        return {"kind": "total", "formula": ov[0], "formula_source": ov[1]}
    m = re.search(r"\(([\d\s.+\-TOSUM()]+)\)\s*$", ln["desc"].replace("SUM (", "SUM(").upper())
    if m and re.search(r"\d", m.group(1)) and ("TO" in m.group(1) or "+" in m.group(1) or "-" in m.group(1)):
        f = re.sub(r"SUM\s*\(|\)", "", m.group(1)).replace(" ", "").replace("TO", " TO ")
        return {"kind": "total", "formula": f, "formula_source": "RRA description"}
    if ln["sheet"] == "PL" and ln["level"] == 1 and int(ln["serial"]) >= 10:
        return {"kind": "tax", "formula": "", "formula_source": ""}
    if children:
        return {"kind": "total", "formula": "+".join(c["serial"] for c in children),
                "formula_source": "sum of the lines below"}
    return {"kind": "line", "formula": "", "formula_source": ""}


def load() -> dict:
    return json.loads(Path(RRA_FILE).read_text(encoding="utf-8"))


def key(ln: dict) -> str:
    return f"{ln['sheet']}:{ln['row']}"


def _terms(formula: str) -> list[tuple[int, str]]:
    out, sign = [], 1
    for tok in re.findall(r"[+\-]|[^+\-]+", formula.replace(" TO ", "~")):
        if tok == "+":
            sign = 1
        elif tok == "-":
            sign = -1
        else:
            out.append((sign, tok.strip()))
    return out


def evaluate(rra: dict, leaf_values: dict[str, float], extra: dict[str, float] | None = None) -> dict[str, float | None]:
    """Values of every RRA line. leaf_values: {"BS:12": amount, ...} for lines fed by app codes;
    extra: {"PL:16": ...} for tax lines. Totals follow their formula; a range "a TO b" sums the lines of the
    same level between the rows of a and b (so both "3.1.3.1" lines are included)."""
    lines = rra["lines"]
    val: dict[str, float | None] = {}
    by_serial: dict[tuple[str, str], list[dict]] = {}
    for ln in lines:
        by_serial.setdefault((ln["sheet"], ln["serial"]), []).append(ln)
    extra = extra or {}

    def get(sheet: str, serial: str, depth=0) -> float:
        tot = 0.0
        for ln in by_serial.get((sheet, serial), []):
            v = value(ln, depth + 1)
            tot += v or 0.0
        return tot

    def value(ln: dict, depth=0) -> float | None:
        k = key(ln)
        if k in val:
            return val[k]
        if depth > 50:
            return None
        if k in extra:
            v = extra[k]
        elif ln["kind"] == "total" and ln["formula"]:
            v = 0.0
            for sign, term in _terms(ln["formula"]):
                if "~" in term:
                    a, b = term.split("~")
                    ra = min(x["row"] for x in by_serial.get((ln["sheet"], a), [{"row": 10 ** 9}]))
                    rb = max(x["row"] for x in by_serial.get((ln["sheet"], b), [{"row": -1}]))
                    lvl = a.count(".") + 1
                    for x in lines:
                        if x["sheet"] == ln["sheet"] and ra <= x["row"] <= rb and x["level"] == lvl:
                            v += sign * (value(x, depth + 1) or 0.0)
                else:
                    v += sign * get(ln["sheet"], term, depth)
        elif ln["kind"] == "tax":
            v = None
        else:
            v = leaf_values.get(k, 0.0)
        val[k] = v
        return v

    for ln in lines:
        value(ln)
    return val


# ------------------------------------------------------------------ update check --
def compare(stored: dict, new: dict, chart_links: dict[str, list[str]]) -> dict:
    """Differences between the stored RRA structure and a newly uploaded file.
    chart_links: {"BS:12": ["BS 01.10"], ...} app codes linked to each stored line.
    Returns {"added", "removed", "changed", "moved", "same"} lists and "proposals" for the chart."""
    def ident(ln):
        return (ln["sheet"], ln["serial"], ln["desc"].lower())
    s_lines, n_lines = stored["lines"], new["lines"]
    by_sd = {(x["sheet"], x["serial"], x["desc"].lower()): x for x in n_lines}
    by_s: dict[tuple[str, str], list[dict]] = {}
    for x in n_lines:
        by_s.setdefault((x["sheet"], x["serial"]), []).append(x)
    matched_new = set()
    res = {"added": [], "removed": [], "changed": [], "moved": [], "same": 0, "proposals": []}
    for ln in s_lines:
        hit = by_sd.get(ident(ln))
        if hit:
            matched_new.add(key(hit))
            if hit["row"] != ln["row"]:
                res["moved"].append({"old": ln, "new": hit})
            else:
                res["same"] += 1
            continue
        cand = [x for x in by_s.get((ln["sheet"], ln["serial"]), []) if key(x) not in matched_new]
        if cand:
            matched_new.add(key(cand[0]))
            res["changed"].append({"old": ln, "new": cand[0], "codes": chart_links.get(key(ln), [])})
        else:
            res["removed"].append({"old": ln, "codes": chart_links.get(key(ln), [])})
    for x in n_lines:
        if key(x) not in matched_new:
            res["added"].append({"new": x})
    for a in res["added"]:
        x = a["new"]
        if x["kind"] == "line":
            res["proposals"].append({"action": "ADD CODE", "code": from_serial(x["sheet"], x["serial"]),
                                     "label": x["desc"].capitalize(), "rra": f"{x['sheet']} {x['serial']} (row {x['row']})",
                                     "why": "new RRA line — add it to the chart, in the group of its neighbours"})
        else:
            res["proposals"].append({"action": "CHECK TOTAL", "code": "", "label": x["desc"],
                                     "rra": f"{x['sheet']} {x['serial']} (row {x['row']})",
                                     "why": f"new RRA heading / total — formula: {x.get('formula') or 'none'}"})
    for r in res["removed"]:
        for c in r["codes"]:
            res["proposals"].append({"action": "RELINK CODE", "code": c, "label": "",
                                     "rra": f"{r['old']['sheet']} {r['old']['serial']} (removed)",
                                     "why": "its RRA line no longer exists — choose the RRA line it should roll up into"})
    for c in res["changed"]:
        for code in c["codes"]:
            res["proposals"].append({"action": "CHECK LABEL", "code": code, "label": c["new"]["desc"],
                                     "rra": f"{c['new']['sheet']} {c['new']['serial']} (row {c['new']['row']})",
                                     "why": f"RRA wording changed: '{c['old']['desc']}' → '{c['new']['desc']}'"})
    for m in res["moved"]:
        res["proposals"].append({"action": "UPDATE ROW", "code": ", ".join(chart_links.get(key(m["old"]), [])),
                                 "label": m["new"]["desc"], "rra": f"{m['new']['sheet']} {m['new']['serial']}",
                                 "why": f"same line, row {m['old']['row']} → {m['new']['row']} (updated automatically)"})
    return res


def relinked_chart(chart: dict, stored: dict, new: dict) -> dict:
    """Chart with the RRA rows updated for lines that only moved (same serial and wording). Other differences
    need a decision and are left unchanged."""
    import copy
    ch = copy.deepcopy(chart)
    s_by_key = {key(x): x for x in stored["lines"]}
    n_by_sd = {(x["sheet"], x["serial"], x["desc"].lower()): x for x in new["lines"]}
    for part in ("pnl", "bs"):
        for sec in ch[part]:
            for g in sec.get("groups", []):
                for ln in g["lines"]:
                    r = ln.get("rra")
                    if not r:
                        continue
                    old = s_by_key.get(f"{r['sheet']}:{r['row']}")
                    hit = old and n_by_sd.get((old["sheet"], old["serial"], old["desc"].lower()))
                    if hit and hit["row"] != r["row"]:
                        r["row"] = hit["row"]
    return ch
