"""Word template registry.

Templates live in the repository folder  templates/<template-id>/  — managed by the administrator only
(added or replaced by committing files; users can only choose and download them). Each folder holds:

    template.json   manifest (alias shown to users, description, version, language, file names, defaults)
    template.docx   the Word template (bookmarks str_… / tbl_… / var_notes, see render_report.FIELDS)
    notes.json      optional — explanatory notes specific to this template (same format as data/notes_default.json)

Folders whose manifest has "active": false are ignored. See templates/README.md.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from lxml import etree

from . import ROOT, render_report

TEMPLATES_DIR = ROOT / "templates"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FONTS = ["Aptos", "Arial", "Book Antiqua", "Calibri", "Cambria", "Century Gothic", "Garamond", "Georgia",
         "Helvetica", "Amasis MT Pro", "Palatino Linotype", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"]


def list_templates(include_inactive: bool = False) -> list[dict]:
    out = []
    if not TEMPLATES_DIR.exists():
        return out
    for d in sorted(p for p in TEMPLATES_DIR.iterdir() if p.is_dir()):
        mf = d / "template.json"
        if not mf.exists():
            continue
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            out.append({"id": d.name, "alias": d.name, "error": f"template.json is not valid JSON: {e}", "active": False})
            continue
        if not m.get("active", True) and not include_inactive:
            continue
        docx = d / m.get("file", "template.docx")
        notes = d / m["notes_file"] if m.get("notes_file") else None
        out.append({"id": d.name, "alias": m.get("alias") or d.name, "description": m.get("description", ""),
                    "version": m.get("version", ""), "language": m.get("language", "en"),
                    "default_font": m.get("default_font"), "order": m.get("order", 99), "active": m.get("active", True),
                    "docx": docx, "notes": notes if notes and notes.exists() else None,
                    "preview": (d / m.get("preview", "preview.png")) if (d / m.get("preview", "preview.png")).exists() else None,
                    "error": None if docx.exists() else f"file {docx.name} not found in templates/{d.name}/"})
    return sorted(out, key=lambda t: (t["order"], t["alias"]))


def get(template_id: str | None) -> dict | None:
    ts = [t for t in list_templates() if not t["error"]]
    return next((t for t in ts if t["id"] == template_id), ts[0] if ts else None)


def check(docx) -> dict:
    """Compatibility report of a Word template (path or bytes)."""
    data = Path(docx).read_bytes() if not isinstance(docx, (bytes, bytearray)) else bytes(docx)
    z = zipfile.ZipFile(io.BytesIO(data))
    trees = {n: etree.fromstring(z.read(n)) for n in z.namelist() if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n)}
    names = render_report.all_bookmarks(trees)
    targets = {n: render_report.resolve(n) for n in names}
    fields = sorted({t for t in targets.values() if t and not t.startswith("tbl:") and t != "notes"})
    tables = sorted({t[4:] for t in targets.values() if t and t.startswith("tbl:")})
    unknown = [n for n, t in targets.items() if t is None and n.lower().startswith(("str_", "tbl_", "var_"))]
    text = "".join(t.text or "" for tr in trees.values() for t in tr.iter(W + "t"))
    inside = ""
    for tr in trees.values():
        for b in tr.iter(W + "bookmarkStart"):
            inside += "".join(t.text or "" for r in render_report.runs_in_bookmark(tr, b) for t in r.iter(W + "t"))
    auto = {"financialstatementsenddate", "financialstatementenddate", "financialstatements_enddate", "periodenddate",
            "companyname", "my company name ltd", "auditcompanyname"}   # replaced by name anywhere (e.g. TOC copies)
    styles = etree.fromstring(z.read("word/styles.xml"))
    style_ids = {s.get(W + "styleId") for s in styles.iter(W + "style")}
    need_styles = [s for s in ("Heading2", "Heading3", "Heading4", "ListParagraph") if s not in style_ids]
    problems = []
    missing_tables = [k for k in render_report.TABLES if k not in tables]
    if missing_tables:
        problems.append(f"statement table placeholder(s) missing: {', '.join(missing_tables)}")
    if "notes" not in targets.values():
        problems.append("notes placeholder (var_notes) missing")
    if need_styles:
        problems.append(f"style(s) missing: {', '.join(need_styles)}")
    return {"fields": fields, "tables": tables, "notes": "notes" in targets.values(), "unknown": unknown,
            "loose_placeholders": sorted({p for p in re.findall(r"\{[A-Za-z_ ]{3,40}\}", text)
                                          if p not in inside and p[1:-1].lower() not in auto}),
            "missing_styles": need_styles, "problems": problems, "ok": not problems,
            "main_font": render_report.main_font({n: z.read(n) for n in z.namelist() if n.startswith("word/")})}
