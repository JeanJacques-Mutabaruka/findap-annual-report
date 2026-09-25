#!/usr/bin/env python3
"""
render_report.py — fill the Word annual-report template from model.json (output of build_model.py).

Usage:
    python render_report.py template.docx model.json output.docx [--keep-zero-lines] [--allow-blocking]

What it does (python equivalent of VBA Generate_Annualreportdocument, see references/vba-to-skill-map.md):
  1. str_* bookmarks  -> text (highlight removed, colour = meta.variables_color)
  2. tbl_* bookmarks  -> Word tables built from the statements (P&L, BS, equity, cash flow)
  3. var_Pnlrelatednotessection -> explanatory notes (Heading 3 + tables + text), auto-numbered
  4. leftover {placeholders} in the TOC field result -> replaced by their value
  5. settings.xml: updateFields=true so Word refreshes TOC / PAGE / NUMPAGES on opening
  6. removes the trailing blank page (merges the notes section into the last section)
Works only on raw XML (lxml); never re-saves through Word/LibreOffice, so template styles are untouched.
"""
import argparse, copy, json, re, sys, zipfile
from datetime import date
from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{%s}" % W_NS
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}
TEXT_WIDTH = 9072  # twips, A4 with 2.5 cm margins

# --------------------------------------------------------------------------- formatting helpers
def fmt_date(s):
    try:
        d = date.fromisoformat(str(s)[:10])
        return f"{d.day:02d}-{d.strftime('%B')}-{d.year}"
    except Exception:
        return s


def fmt_num(v):
    if v is None:
        return ""
    if abs(v) < 0.5:
        return "-"
    s = f"{abs(v):,.0f}"
    return f"({s})" if v < 0 else s


def el(tag, attrib=None, *children):
    e = etree.Element(W + tag)
    for k, v in (attrib or {}).items():
        e.set(W + k, str(v))
    for c in children:
        if c is not None:
            e.append(c)
    return e


TABLE_FONT = {"name": "Cambria"}   # set by render(): chosen font, else the template's main font


def run(text, bold=False, italic=False, size=None, color=None, font=None, caps=False):
    font = font or TABLE_FONT["name"]
    rpr = el("rPr")
    rpr.append(el("rFonts", {"ascii": font, "hAnsi": font}))
    if bold:
        rpr.append(el("b")); rpr.append(el("bCs"))
    if italic:
        rpr.append(el("i"))
    if caps:
        rpr.append(el("caps"))
    if color:
        rpr.append(el("color", {"val": color}))
    if size:
        rpr.append(el("sz", {"val": size})); rpr.append(el("szCs", {"val": size}))
    r = el("r", None, rpr)
    set_run_text(r, text)
    return r


def set_run_text(r, text):
    for c in list(r):
        if c.tag != W + "rPr":
            r.remove(c)
    lines = str(text).split("\n")
    for i, line in enumerate(lines):
        if i:
            r.append(el("br"))
        t = el("t"); t.text = line
        t.set("{%s}space" % XML_NS, "preserve")
        r.append(t)


# --------------------------------------------------------------------------- bookmarks
def find_bookmark(root, name):
    r = root.xpath(f'.//w:bookmarkStart[@w:name="{name}"]', namespaces=NS)
    return r[0] if r else None


def runs_in_bookmark(root, bs):
    bid = bs.get(W + "id")
    out, started = [], False
    for e in root.iter():
        if e is bs:
            started = True; continue
        if not started:
            continue
        if e.tag == W + "bookmarkEnd" and e.get(W + "id") == bid:
            break
        if e.tag == W + "r" and e.getparent().tag != W + "r":
            out.append(e)
    return out


def replace_bookmark_text(root, name, text, color):
    bs = find_bookmark(root, name)
    if bs is None:
        return False
    runs = runs_in_bookmark(root, bs)
    if not runs:
        bs.addnext(run(text, color=color))
        return True
    first = runs[0]
    rpr = first.find(W + "rPr")
    if rpr is None:
        rpr = el("rPr"); first.insert(0, rpr)
    for tag in ("highlight", "color"):
        for x in rpr.findall(W + tag):
            rpr.remove(x)
    if color:
        # schema order: color comes before sz/highlight/lang...; insert after rFonts/b/i/caps if present
        c = el("color", {"val": color})
        anchor = None
        for tag in ("rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "noProof", "vanish"):
            f = rpr.find(W + tag)
            if f is not None:
                anchor = f
        if anchor is not None:
            anchor.addnext(c)
        else:
            rpr.insert(0, c)
    set_run_text(first, text)
    if "\n" in str(text):  # justified paragraphs stretch lines ending with a manual break
        p = first.getparent()
        while p is not None and p.tag != W + "p":
            p = p.getparent()
        jc = p.find(f"{W}pPr/{W}jc") if p is not None else None
        if jc is not None and jc.get(W + "val") == "both":
            jc.set(W + "val", "left")
    for r in runs[1:]:
        r.getparent().remove(r)
    return True


def placeholder_paragraph(root, bs):
    """Paragraph holding the placeholder text of a block bookmark (the bookmarkStart may sit at the end of
    the previous, empty paragraph). The bookmark markers are moved out so that removing the paragraph is safe."""
    runs = [r for r in runs_in_bookmark(root, bs) if "".join(t.text or "" for t in r.iter(W + "t")).strip()]
    p = runs[0] if runs else bs
    while p.tag != W + "p":
        p = p.getparent()
    bid = bs.get(W + "id")
    for e in root.xpath(f'.//w:bookmarkEnd[@w:id="{bid}"]', namespaces=NS):
        e.getparent().remove(e)
    bs.getparent().remove(bs)
    return p


# --------------------------------------------------------------------------- tables
BORDER = lambda kind: el(kind, {"val": "single", "sz": "4", "space": "0", "color": "000000"})


def cell(text, width, bold=False, italic=False, align="left", indent=0, size=16, top=None, bottom=None, shade=None):
    tcpr = el("tcPr", None, el("tcW", {"w": width, "type": "dxa"}))
    if top or bottom:
        b = el("tcBorders")
        if top:
            b.append(el("top", {"val": top, "sz": "4", "space": "0", "color": "000000"}))
        if bottom:
            b.append(el("bottom", {"val": bottom, "sz": "6" if bottom == "double" else "4", "space": "0", "color": "000000"}))
        tcpr.append(b)
    if shade:
        tcpr.append(el("shd", {"val": "clear", "color": "auto", "fill": shade}))
    tcpr.append(el("vAlign", {"val": "bottom"}))
    ppr = el("pPr", None, el("spacing", {"before": "0", "after": "0", "line": "240", "lineRule": "auto"}))
    if indent:
        ppr.append(el("ind", {"left": indent}))
    ppr.append(el("jc", {"val": {"left": "left", "right": "right", "center": "center"}[align]}))
    p = el("p", None, ppr)
    if text not in (None, ""):
        p.append(run(text, bold=bold, italic=italic, size=size))
    return el("tc", None, tcpr, p)


def table(widths, header_rows, body_rows, size, bookmark=None):
    tblpr = el("tblPr", None,
               el("tblW", {"w": sum(widths), "type": "dxa"}),
               el("jc", {"val": "center"}),
               el("tblLayout", {"type": "fixed"}),
               el("tblCellMar", None, el("left", {"w": "70", "type": "dxa"}), el("right", {"w": "70", "type": "dxa"})),
               el("tblLook", {"val": "04A0", "firstRow": "1", "lastRow": "0", "firstColumn": "1", "lastColumn": "0", "noHBand": "0", "noVBand": "1"}))
    grid = el("tblGrid", None, *[el("gridCol", {"w": w}) for w in widths])
    t = el("tbl", None, tblpr, grid)
    for i, cells in enumerate(header_rows):
        tr = el("tr", None, el("trPr", None, el("cantSplit"), el("tblHeader")))
        for j, txt in enumerate(cells):
            tr.append(cell(txt, widths[j], bold=True, align="left" if j == 0 else "right" if j >= 1 else "left", size=size,
                           bottom="single" if i == len(header_rows) - 1 else None))
        t.append(tr)
    for cells in body_rows:
        tr = el("tr", None, el("trPr", None, el("cantSplit")))
        for j, c in enumerate(cells):
            tr.append(cell(c.get("text"), widths[j], size=size, **{k: v for k, v in c.items() if k != "text"}))
        t.append(tr)
    rows_ = t.findall(W + "tr")
    if len(rows_) <= 30:  # keep short tables on one page: keepNext on every row but the last
        for tr in rows_[:-1]:
            for pp in tr.iter(W + "pPr"):
                pp.insert(0, el("keepNext"))
    if bookmark:
        p = t.find(f".//{W}p")
        bid = str(9000 + abs(hash(bookmark)) % 50000)
        p.insert(1 if p.find(W + "pPr") is not None else 0, el("bookmarkStart", {"id": bid, "name": bookmark}))
        p.append(el("bookmarkEnd", {"id": bid}))
    return t


STYLE = {  # row type -> (bold, italic, indent, top border, bottom border)
    "heading": (True, False, 0, None, None),
    "title": (True, False, 0, None, None),
    "group": (True, True, 0, None, None),
    "line": (False, False, 227, None, None),
    "line_bold": (True, False, 0, None, None),
    "total": (True, False, 0, "single", None),
    "sectiontotal": (True, False, 0, "single", None),
    "subtotal": (True, False, 0, "single", "single"),
    "grandtotal": (True, False, 0, "single", "double"),
}


def filter_zero(rows, valkeys):
    def isz(r):
        vals = [r.get(k) for k in valkeys] if "values" not in r else (r["values"] or [])
        return all(v is None or abs(v) < 0.5 for v in vals)
    kept = [r for r in rows if not (r["type"] == "line" and isz(r))]
    out = []
    for i, r in enumerate(kept):
        nxt = kept[i + 1]["type"] if i + 1 < len(kept) else None
        if r["type"] == "group" and nxt != "line" and isz(r):
            continue
        if r["type"] == "total" and isz(r) and (not out or out[-1]["type"] != "line"):
            continue
        out.append(r)
    return out


# ------------------------------------------------------------------ detail levels
DETAIL_LEVELS = {  # key -> (Excel-style level, label shown to users)
    "detailed": (2, "Detailed — every statement line"),
    "summarised": (1, "Summarised — headings and sub-totals"),
    "condensed": (0, "Condensed — main headings only"),
}


def _vals(r):
    return r["values"] if "values" in r else [r.get("cy"), r.get("py")]


def _has_values(r):
    return any(v is not None for v in _vals(r))


def _note_range(notes):
    nums = sorted({int(n) for n in notes if str(n).isdigit()})
    if not nums:
        return None
    parts, start = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None]):
        if b != a + 1:
            parts.append(str(start) if start == a else (f"{start}, {a}" if a == start + 1 else f"{start}–{a}"))
            start = b
    return ", ".join(parts)


def apply_level(rows, level="detailed"):
    """Balance sheet / P&L rows at a detail level ('detailed' | 'summarised' | 'condensed', or 2 | 1 | 0).
    Rows need the 'lvl' attribute set by build_model.assign_levels. Works on 2-year rows and multi-year rows."""
    lv = DETAIL_LEVELS.get(level, (level,))[0] if isinstance(level, str) else level
    if lv >= 2 or not rows or "lvl" not in rows[0]:
        return rows
    out = []
    if lv == 1:
        pending = None
        for r in rows:
            if r["lvl"] == 2:
                continue
            if r["type"] == "group" and not _has_values(r):
                pending = r
                continue
            if r["type"] == "total" and pending is not None:
                out.append({**r, "type": "line", "label": pending["label"], "note": r.get("note") or pending.get("note")})
                pending = None
                continue
            pending = None
            out.append({**r, "type": "line"} if r["type"] == "group" else r)
        return out
    title, notes = None, []
    for r in rows:
        if r["type"] == "title":
            title, notes = r, [r.get("note")] if r.get("note") else []
            continue
        if r.get("note") and any(v is not None and abs(v) >= 0.5 for v in _vals(r)):
            notes += [x.strip() for x in str(r["note"]).replace("&", ",").split(",")]
        if r["lvl"] != 0:
            continue
        if r["type"] == "sectiontotal":
            lab = title["label"] if title else r["label"].replace("Total ", "")
            out.append({**r, "type": "line", "label": lab, "note": r.get("note") or _note_range(notes)})
            title, notes = None, []
        elif r["type"] == "line_bold":
            out.append({**r, "type": "line"})
        else:
            out.append(r)
    return out


def statement_rows(rows, cols, size):
    """cols: list of ('note'|'cy'|'py'|int index into values)"""
    body = []
    for r in rows:
        b, it, ind, top, bot = STYLE.get(r["type"], STYLE["line"])
        label = r["label"].upper() if r["type"] == "heading" else r["label"]
        cells = [{"text": label, "bold": b, "italic": it, "indent": ind}]
        for c in cols:
            if c == "note":
                cells.append({"text": r.get("note") or "", "bold": b, "align": "center"})
            else:
                v = r["values"][c] if isinstance(c, int) else r.get(c)
                show = v is not None and r["type"] not in ("title", "heading") and not (r["type"] == "group" and v is None)
                cells.append({"text": fmt_num(v) if show else "", "bold": b, "align": "right", "top": top if show else None, "bottom": bot if show else None})
        body.append(cells)
    return body


def build_two_year(rows, meta, with_note=True, keep_zero=False, bookmark=None):
    size = int(meta.get("tables_font_size", 8)) * 2
    single = bool(meta.get("single_year"))
    if not keep_zero:
        rows = filter_zero(rows, ["cy"] if single else ["cy", "py"])
    cur = meta.get("currency", "Rwf")
    if single:   # first financial year: Current Year only
        if with_note:
            widths, hdr, cols = [6822, 700, 1550], [["", "Note", str(meta["year_cy"])], ["", "", cur]], ["note", "cy"]
        else:
            widths, hdr, cols = [7522, 1550], [["", str(meta["year_cy"])], ["", cur]], ["cy"]
        return table(widths, hdr, statement_rows(rows, cols, size), size, bookmark)
    if with_note:
        widths = [5272, 700, 1550, 1550]
        hdr = [["", "Note", str(meta["year_cy"]), str(meta["year_py"])], ["", "", cur, cur]]
        cols = ["note", "cy", "py"]
    else:
        widths = [5972, 1550, 1550]
        hdr = [["", str(meta["year_cy"]), str(meta["year_py"])], ["", cur, cur]]
        cols = ["cy", "py"]
    return table(widths, hdr, statement_rows(rows, cols, size), size, bookmark)


def build_cashflow(rows, meta, keep_zero=False, bookmark=None):
    size = int(meta.get("tables_font_size", 8)) * 2
    if not keep_zero:
        rows = filter_zero(rows, ["cy"])
    widths = [7072, 2000]
    hdr = [["", str(meta["year_cy"])], ["", meta.get("currency", "Rwf")]]
    return table(widths, hdr, statement_rows(rows, ["cy"], size), size, bookmark)


def build_matrix(columns, rows, meta, label_width=2400, bookmark=None, subtitle_row=None):
    size = int(meta.get("tables_font_size", 8)) * 2
    n = len(columns)
    w = (TEXT_WIDTH - label_width) // n
    widths = [label_width] + [w] * n
    widths[0] += TEXT_WIDTH - sum(widths)
    hdr = [[""] + columns, [""] + [meta.get("currency", "Rwf")] * n]
    body = []
    for r in rows:
        if r["type"] == "blocktitle":
            body.append([{"text": r["label"], "bold": True}] + [{"text": ""}] * n)
            continue
        vals = r.get("values")
        rr = dict(r)
        if vals is None:
            rr["values"] = [None] * n
        body += statement_rows([rr], list(range(n)), size)
    return table(widths, hdr, body, size, bookmark)


# --------------------------------------------------------------------------- notes
def para(style=None, runs=(), ppr_extra=()):
    ppr = el("pPr")
    if style:
        ppr.append(el("pStyle", {"val": style}))
    for x in ppr_extra:
        ppr.append(x)
    p = el("p", None, ppr)
    for r in runs:
        p.append(r)
    return p


def note_text(text):
    return para("ListParagraph", [run(text)], [
        el("spacing", {"before": "240", "after": "120", "line": "276", "lineRule": "auto"}),
        el("ind", {"left": "357"}), el("contextualSpacing", {"val": "0"}), el("jc", {"val": "both"})])


def build_notes(model, keep_zero):
    meta = model["meta"]
    out = []
    for n in model["notes"]:
        out.append(para("Heading3", [run(n["title"])], [el("keepNext")]))
        for b in n["blocks"]:
            if b.get("subtitle"):
                out.append(para("Heading4", [run(b["subtitle"])], [el("keepNext")]))
            if b["kind"] == "text":
                out.append(note_text(b["text"]))
            elif b["kind"] == "table2":
                out.append(build_two_year(b["rows"], meta, with_note=False, keep_zero=keep_zero))
                out.append(para(None, [], [el("spacing", {"after": "120"})]))
            elif b["kind"] == "tableN":
                out.append(build_matrix(b["columns"], b["rows"], meta, label_width=2200))
                out.append(para(None, [], [el("spacing", {"after": "120"})]))
    return out


def restore_note4(body, report):
    """V09 template: note 4 'Significant judgements and key sources of estimation uncertainty' is typed as a
    Heading 4 under note 3, and an EMPTY numbered Heading 3 closes the section to push the first injected note
    to number 5. Renderers disagree on counting empty numbered paragraphs, so: promote that Heading 4 to
    Heading 3 (as the template TOC intends) and switch numbering off on the empty Heading 3."""
    promoted = False
    for q in body.iterchildren(W + "p"):
        sty = q.find(f"{W}pPr/{W}pStyle")
        if sty is None:
            continue
        txt = "".join(t.text or "" for t in q.iter(W + "t")).strip()
        if sty.get(W + "val") == "Heading4" and txt.lower().startswith("significant judgements and key sources"):
            sty.set(W + "val", "Heading3"); promoted = True
        elif sty.get(W + "val") == "Heading3" and not txt and promoted:
            ppr = q.find(W + "pPr")
            if ppr.find(W + "numPr") is None:
                sty.addnext(el("numPr", None, el("ilvl", {"val": "0"}), el("numId", {"val": "0"})))
    if promoted:
        report["warnings"].append("INFO: template note 'Significant judgements and key sources of estimation uncertainty' promoted from Heading 4 to Heading 3 (note 4); empty numbered Heading 3 un-numbered.")


def isolate_prenote_heading4(doc, parts):
    if "word/numbering.xml" not in parts:
        return
    numx = etree.fromstring(parts["word/numbering.xml"])
    st = etree.fromstring(parts["word/styles.xml"])
    h4 = st.xpath('.//w:style[@w:styleId="Heading4"]//w:numId/@w:val', namespaces=NS)
    if not h4:
        return
    num = numx.xpath(f'.//w:num[@w:numId="{h4[0]}"]', namespaces=NS)[0]
    absid = num.find(W + "abstractNumId").get(W + "val")
    absn = numx.xpath(f'.//w:abstractNum[@w:abstractNumId="{absid}"]', namespaces=NS)[0]
    new_abs = copy.deepcopy(absn)
    new_absid = str(max(int(x) for x in numx.xpath(".//w:abstractNum/@w:abstractNumId", namespaces=NS)) + 1)
    new_abs.set(W + "abstractNumId", new_absid)
    for x in new_abs.iter(W + "pStyle"):
        x.getparent().remove(x)
    nsid = new_abs.find(W + "nsid")
    if nsid is not None:
        nsid.set(W + "val", "5A11C0DE")
    last_abs = numx.findall(W + "abstractNum")[-1]
    last_abs.addnext(new_abs)
    new_numid = str(max(int(x) for x in numx.xpath(".//w:num/@w:numId", namespaces=NS)) + 1)
    numx.append(el("num", {"numId": new_numid}, el("abstractNumId", {"val": new_absid})))
    body = doc.find(W + "body")
    for q in body.iterchildren(W + "p"):
        sty = q.find(f"{W}pPr/{W}pStyle")
        v = sty.get(W + "val") if sty is not None else None
        if v == "Heading3":
            break
        if v == "Heading4" and q.find(f"{W}pPr/{W}numPr") is None:
            sty.addnext(el("numPr", None, el("ilvl", {"val": "1"}), el("numId", {"val": new_numid})))
    parts["word/numbering.xml"] = etree.tostring(numx, xml_declaration=True, encoding="UTF-8", standalone=True)


# --------------------------------------------------------------------------- main
# Canonical fields a template can print. In a template, a text placeholder is a bookmark named
#   str_<field>   or   str_<field>__<n>   (n = 1, 2, … when the same field appears several times)
# e.g. str_companyname__1, str_periodend__3. Tables: tbl_pnl, tbl_balancesheet, tbl_equity, tbl_cashflow.
# Notes block: var_notes. Legacy V09 bookmark names (LEGACY below) keep working.
FIELDS = {
    "companyname": "Company name",
    "periodend": "Financial year end date (e.g. 31-December-2025)",
    "yearcy": "Current Year (CY), e.g. 2025",
    "yearpy": "Previous Year (PY), e.g. 2024",
    "currency": "Currency (e.g. Rwf)",
    "auditcompanyname": "Audit firm name",
    "auditcompanyfulladdress": "Audit firm name + address (several lines)",
    "directors": "List of directors (several lines)",
    "registeredoffice": "Registered office (several lines)",
    "bankers": "Principal bankers (several lines)",
    "mainactivity": "Main activity of the company",
    "auditorframework": "Framework cited in the auditor's opinion",
    "accountingframework": "Accounting framework (note 2)",
    "proposeddividend": "Proposed dividend (formatted amount)",
    "signaturedate": "Directors' statement signature date (dotted line if empty)",
    "companyrepresentative": "Company representative (dotted line if empty)",
    "fssigningdate": "Financial statements signing date (dotted line if empty)",
    "companydirector": "Director signing the balance sheet (dotted line if empty)",
}
TABLES = {"pnl": "Statement of comprehensive income", "balancesheet": "Statement of financial position",
          "equity": "Statement of changes in equity", "cashflow": "Statement of cash flows"}
LEGACY = {
    "str_Coverpage_Companyname": "companyname", "str_Header_Companyname": "companyname",
    "str_Auditorreport_Companyname01": "companyname", "str_Auditorreport_Companyname02": "companyname",
    "str_Auditorreport_Companyname03": "companyname", "str_Regulatory_Companyname01": "companyname",
    "str_Regulatory_Companyname02": "companyname", "str_Notes01_Companyname": "companyname",
    "str_Coverpage_FSenddate": "periodend", "str_Header_Periodenddate": "periodend", "str_fsenddate_page04": "periodend",
    "str_Directorstatement_Periodenddate01": "periodend", "str_Directorstatement_Periodenddate02": "periodend",
    "str_Auditorreport_periodenddate01": "periodend", "str_Auditorreport_periodenddate02": "periodend",
    "str_PnL_Pnlenddate": "periodend", "str_Balancesheet_Balancesheetdate": "periodend",
    "str_Equitystate_Finstatedate": "periodend", "str_Cashflow_Finstatedate": "periodend",
    "str_Coverpage_Auditcompanyname": "auditcompanyname", "str_Footer_Auditcompanyname": "auditcompanyname",
    "str_Directorstatement_Auditcompanyname": "auditcompanyname", "str_Regulatory_Auditcompanyname": "auditcompanyname",
    "str_Regulatory_Auditcompanyfulladress": "auditcompanyfulladdress",
    "str_Corpoinfo_Nameindependentauditor": "auditcompanyfulladdress",
    "str_Corpoinfo_Listofdirectors": "directors", "str_Corpoinfo_Companylocation": "registeredoffice",
    "str_Corpoinfo_Listofbanks": "bankers", "str_Notes01_Companymainactivity": "mainactivity",
    "str_Auditorreport_Framework": "auditorframework", "str_Notes_Auditframework": "accountingframework",
    "str_proposeddividend": "proposeddividend", "str_Directorstatement_Signaturedate": "signaturedate",
    "str_Directorstatement_Representative": "companyrepresentative",
    "str_financialstatementsigningdate": "fssigningdate", "str_Balancesheet_Companydirectorname": "companydirector",
    "tbl_PnL_Pnltable": "tbl:pnl", "tbl_Balancesheet_Balancesheettable": "tbl:balancesheet",
    "tbl_Equitystate_Equitystatetable": "tbl:equity", "tbl_Cashflow_Cashflowstatetable": "tbl:cashflow",
    "var_Pnlrelatednotessection": "notes",
}


def canonical_values(model) -> dict:
    m, g = model["meta"], model["general"]
    d = fmt_date(m["period_end"])
    aud = g.get("audit_company_name") or ""
    dash = "-" * 40
    div = g.get("proposed_dividend")
    try:
        div = fmt_num(float(div)) if div not in (None, "") else "-"
        div = "0" if div == "-" else div
    except ValueError:
        pass

    def date_or_dash(v):
        return fmt_date(v) if v and not str(v).startswith("-") else dash

    v = {
        "companyname": m.get("company_name") or g.get("company_name"), "periodend": d,
        "yearcy": m.get("year_cy"), "yearpy": m.get("year_py"), "currency": m.get("currency") or "Rwf",
        "auditcompanyname": aud,
        "auditcompanyfulladdress": aud + ("\n" + g["audit_company_address"] if g.get("audit_company_address") else ""),
        "directors": g.get("directors"), "registeredoffice": g.get("registered_office"),
        "bankers": (g.get("bankers") or "").strip(), "mainactivity": g.get("main_activity"),
        "auditorframework": g.get("auditor_report_framework"), "accountingframework": g.get("accounting_framework"),
        "proposeddividend": div, "signaturedate": date_or_dash(g.get("signature_date")),
        "companyrepresentative": g.get("company_representative") or dash,
        "fssigningdate": date_or_dash(g.get("fs_signing_date")), "companydirector": g.get("company_director") or dash,
    }
    return {k: ("" if x is None else str(x)) for k, x in v.items()}


def resolve(name: str) -> str | None:
    """Bookmark name -> canonical target ('companyname', 'tbl:pnl', 'notes') or None if not a data bookmark."""
    if name in LEGACY:
        return LEGACY[name]
    low = name.lower()
    if low.startswith("str_"):
        key = low[4:].split("__")[0]
        return key if key in FIELDS else None
    if low.startswith("tbl_"):
        key = low[4:].split("__")[0]
        return f"tbl:{key}" if key in TABLES else None
    if low.startswith("var_") and low[4:].split("__")[0] == "notes":
        return "notes"
    return None


def bookmark_values(model):
    """Legacy helper kept for compatibility: V09 bookmark name -> text."""
    cv = canonical_values(model)
    v = {k: cv[t] for k, t in LEGACY.items() if not t.startswith("tbl:") and t != "notes"}
    v.update(model.get("bookmark_overrides", {}) or {})
    return v


def all_bookmarks(trees) -> list[str]:
    out = []
    for t in trees.values():
        out += [b.get(W + "name") for b in t.iter(W + "bookmarkStart")]
    return [b for b in out if b and not b.startswith("_")]


# --------------------------------------------------------------------------- fonts
SYMBOL_FONTS = {"Symbol", "Wingdings", "Wingdings 2", "Wingdings 3", "Webdings", "Courier New"}


def main_font(parts) -> str:
    """Most used explicit font of the document body (fallback: theme minor font, then Cambria)."""
    from collections import Counter
    doc = etree.fromstring(parts["word/document.xml"])
    c = Counter(r.get(W + "ascii") for r in doc.iter(W + "rFonts") if r.get(W + "ascii") and r.get(W + "ascii") not in SYMBOL_FONTS)
    if c:
        return c.most_common(1)[0][0]
    th = parts.get("word/theme/theme1.xml")
    if th:
        m = re.search(rb'<a:minorFont>\s*<a:latin typeface="([^"]+)"', th)
        if m:
            return m.group(1).decode()
    return "Cambria"


def apply_font(parts, trees, font: str) -> None:
    """Replace every text font of the template (body, headers, footers, styles, theme) by `font`.
    Symbol fonts used by bullets are kept."""
    def fix(root):
        for r in root.iter(W + "rFonts"):
            if r.get(W + "ascii") in SYMBOL_FONTS:
                continue
            for a in ("asciiTheme", "hAnsiTheme", "cstheme"):
                if r.get(W + a) is not None:
                    del r.attrib[W + a]
            for a in ("ascii", "hAnsi", "cs"):
                r.set(W + a, font)
    for t in trees.values():
        fix(t)
    st_ = etree.fromstring(parts["word/styles.xml"])
    fix(st_)
    parts["word/styles.xml"] = etree.tostring(st_, xml_declaration=True, encoding="UTF-8", standalone=True)
    for name in [n for n in parts if n.startswith("word/theme/") and n.endswith(".xml")]:
        parts[name] = re.sub(rb'(<a:(?:major|minor)Font>\s*<a:latin typeface=")[^"]*(")',
                             lambda m: m.group(1) + font.encode() + m.group(2), parts[name])


class BlockingControls(Exception):
    pass


def render(template, model, output, keep_zero_lines=False, allow_blocking=False, font_name=None):
    """template: path or file-like (.docx); model: dict from build_model.build; output: path or file-like.
    font_name: replace every text font of the template (None = keep the template's fonts).
    Returns a report dict (replaced / missing bookmarks, unknown bookmarks, warnings, draft flag)."""
    meta = model["meta"]
    blocking = [c for c in model["controls"] if c["level"] == "BLOCKING"]
    if blocking and not allow_blocking:
        raise BlockingControls([c["message"] for c in blocking])
    keep_zero = keep_zero_lines or not meta.get("hide_zero_lines", True)
    color = meta.get("variables_color") or None
    if color and color.upper() in ("000000", "AUTO", "BLACK"):
        color = None

    zin = zipfile.ZipFile(template)
    parts = {n: zin.read(n) for n in zin.namelist()}
    trees = {n: etree.fromstring(parts[n]) for n in parts if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n)}
    doc = trees["word/document.xml"]
    report = {"replaced": [], "missing": [], "unknown": [], "warnings": []}
    if font_name:
        apply_font(parts, trees, font_name)
    TABLE_FONT["name"] = font_name or main_font(parts)
    names = all_bookmarks(trees)
    targets = {n: resolve(n) for n in names}
    report["unknown"] = [n for n, t in targets.items() if t is None and n.lower().startswith(("str_", "tbl_", "var_"))]

    # 1. text bookmarks (legacy names and str_<field>[__n])
    cv = canonical_values(model)
    overrides = model.get("bookmark_overrides", {}) or {}
    for name, tgt in targets.items():
        if tgt is None or tgt.startswith("tbl:") or tgt == "notes":
            continue
        val = str(overrides.get(name, cv.get(tgt, "")))
        if any(replace_bookmark_text(t, name, val, color) for t in trees.values()):
            report["replaced"].append(name)

    # 2. tables
    builders = {
        "pnl": lambda bm: build_two_year(apply_level(model["pnl"], meta.get("detail_level", "detailed")), meta, True, keep_zero, bm),
        "balancesheet": lambda bm: build_two_year(apply_level(model["bs"], meta.get("detail_level", "detailed")), meta, True, keep_zero, bm),
        "cashflow": lambda bm: build_cashflow(model["cashflow"], meta, keep_zero, bm),
        "equity": lambda bm: build_matrix(
            model["equity"]["columns"],
            [r for blk in model["equity"]["blocks"] for r in ([{"type": "blocktitle", "label": blk["title"]}] + blk["rows"])],
            meta, label_width=2600, bookmark=bm),
    }
    found_tables = set()
    for name, tgt in targets.items():
        if not (tgt or "").startswith("tbl:"):
            continue
        bs = find_bookmark(doc, name)
        if bs is None:
            continue
        p = placeholder_paragraph(doc, bs)
        p.addnext(builders[tgt[4:]](name))
        p.getparent().remove(p)
        report["replaced"].append(name)
        found_tables.add(tgt[4:])
    report["missing"] += [f"table {k}" for k in TABLES if k not in found_tables]

    # 3. notes
    notes_bm = next((n for n, t in targets.items() if t == "notes"), None)
    bs = find_bookmark(doc, notes_bm) if notes_bm else None
    if bs is None:
        report["missing"].append("notes block (var_notes)")
    else:
        p = placeholder_paragraph(doc, bs)
        body = p.getparent()
        restore_note4(body, report)
        # numbering check: numbered, non-empty Heading 3 paragraphs before the placeholder
        n_h3 = 0
        for q in body.iterchildren(W + "p"):
            if q is p:
                break
            st = q.find(f"{W}pPr/{W}pStyle")
            off = q.find(f"{W}pPr/{W}numPr/{W}numId")
            if st is not None and st.get(W + "val") == "Heading3" and not (off is not None and off.get(W + "val") == "0") \
                    and "".join(t.text or "" for t in q.iter(W + "t")).strip():
                n_h3 += 1
        first = int(re.match(r"\d+", model["notes"][0]["id"]).group()) if model["notes"] else n_h3 + 1
        if first != n_h3 + 1:
            report["warnings"].append(f"NOTE NUMBERING: Word will number the first injected note {n_h3+1} but its id is {first}. Statement note references will be wrong.")
        for e in build_notes(model, keep_zero):
            p.addprevious(e)
        body.remove(p)  # drops its sectPr too -> notes section merges with last section (no blank page)
        report["replaced"].append(notes_bm)

    # 3b. isolate the auditor's-report Heading 4 list (a)..e)) from the notes list so the notes
    #     numbering (1., 2., 3., [4], 5 ...) is identical in Word and LibreOffice
    isolate_prenote_heading4(doc, parts)

    # 4. leftover placeholders in TOC / elsewhere
    d = fmt_date(meta["period_end"])
    generic = {"financialstatementsenddate": d, "financialstatementenddate": d, "financialstatements_enddate": d,
               "periodenddate": d, "companyname": meta.get("company_name"), "my company name ltd": meta.get("company_name"),
               "auditcompanyname": model["general"].get("audit_company_name")}
    for t in trees.values():
        for tt in t.iter(W + "t"):
            if tt.text and "{" in tt.text:
                def sub(m):
                    return generic.get(m.group(1).strip().lower(), m.group(0))
                new = re.sub(r"\{([^{}]+)\}", sub, tt.text)
                if new != tt.text:
                    tt.text = new
                    r = tt.getparent()
                    rpr = r.find(W + "rPr")
                    if rpr is not None:
                        for x in rpr.findall(W + "highlight"):
                            rpr.remove(x)
    left = []
    for n_, t in trees.items():
        txt = "".join(x.text or "" for x in t.iter(W + "t"))
        left += [(n_, m) for m in re.findall(r"\{[^}]{0,60}\}?", txt)]
    if left:
        report["warnings"].append(f"Placeholders left in the document: {left}")

    # 5. updateFields
    st = etree.fromstring(parts["word/settings.xml"])
    if st.find(W + "updateFields") is None:
        uf = el("updateFields", {"val": "true"})
        after = ("hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
                 "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
                 "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown", "smartTagType",
                 "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol", "listSeparator")
        nxt = next((c for c in st if etree.QName(c).localname in after), None)
        (nxt.addprevious(uf) if nxt is not None else st.append(uf))
    parts["word/settings.xml"] = etree.tostring(st, xml_declaration=True, encoding="UTF-8", standalone=True)

    for n_, t in trees.items():
        parts[n_] = etree.tostring(t, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            z.writestr(info, parts[info.filename])
    report["draft"] = bool(blocking)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template"); ap.add_argument("model"); ap.add_argument("output")
    ap.add_argument("--keep-zero-lines", action="store_true")
    ap.add_argument("--allow-blocking", action="store_true", help="render even if the model has BLOCKING controls (draft)")
    a = ap.parse_args()
    model = json.load(open(a.model, encoding="utf-8"))
    try:
        rep = render(a.template, model, a.output, a.keep_zero_lines, a.allow_blocking)
    except BlockingControls as e:
        print("REFUSED: model has BLOCKING controls (use --allow-blocking for a DRAFT):")
        for m in e.args[0]:
            print("  -", m)
        sys.exit(2)
    print(json.dumps({"output": a.output, "replaced": len(rep["replaced"]), "missing": rep["missing"],
                      "warnings": rep["warnings"], "draft": rep["draft"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
