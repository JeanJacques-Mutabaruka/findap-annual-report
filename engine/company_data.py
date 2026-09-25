"""Save / load the data of page 3 · Company & Report Data (everything except the trial balance).

JSON  : {"format": "arg-company-data-1", "meta": {...}, "general": {...}, "years_data": {...}, "notes": ..., "bookmark_overrides": {...}}
Excel : sheets  Company · Report options · Per-year data · Inventory movement · Fixed assets · Notes · Read me
Both formats can be re-imported. Only the sections present in the file are replaced.
"""
from __future__ import annotations

import io
import json
from datetime import datetime

import pandas as pd

from . import multiyear

FORMAT = "arg-company-data-1"
META_FIELDS = {  # key -> label
    "company_name": "Company name", "period_end": "Financial year end (YYYY-MM-DD)", "currency": "Currency",
    "company_type": "Taxpayer type (CORPORATE / INDIVIDUAL)",
}
OPTION_FIELDS = {
    "template_id": "Word template (folder id)", "font_name": "Font (empty = template default)",
    "tables_font_size": "Table font size (pt)", "variables_color": "Colour of inserted data (hex)",
    "hide_zero_lines": "Hide zero lines (TRUE/FALSE)",
    "detail_level": "Level of detail (detailed / summarised / condensed)",
    "comparative": "Comparative year (auto / with / without)",
}
GENERAL_FIELDS = {
    "main_activity": "Main activity", "registered_office": "Registered office", "directors": "Directors",
    "bankers": "Principal bankers", "audit_company_name": "Audit firm name", "audit_company_address": "Audit firm address",
    "auditor_report_framework": "Auditor's report framework", "accounting_framework": "Accounting framework",
    "proposed_dividend": "Proposed dividend", "company_representative": "Company representative",
    "signature_date": "Approval / signature date (YYYY-MM-DD)", "company_director": "Director signing the balance sheet",
    "fs_signing_date": "Financial statements signing date (YYYY-MM-DD)",
}
FA_COLS = ["name", "rate", "cost_opening", "additions", "disposals", "dep_opening", "charge", "dep_on_disposals"]


def extract(project: dict) -> dict:
    return {"format": FORMAT, "saved_at": datetime.now().isoformat(timespec="minutes"),
            "meta": {k: project.get("meta", {}).get(k) for k in list(META_FIELDS) + list(OPTION_FIELDS)},
            "general": dict(project.get("general", {})),
            "years_data": project.get("years_data") or {},
            "notes": project.get("notes"),
            "bookmark_overrides": project.get("bookmark_overrides") or {}}


def to_json(project: dict) -> bytes:
    return json.dumps(extract(project), indent=1, ensure_ascii=False, default=str).encode("utf-8")


def to_excel(project: dict, years: list[int]) -> bytes:
    from .package import workbook
    sheets, money = frames(project, years)
    return workbook(sheets, money)


SHEETS = ("Company", "Report options", "Per-year data", "Inventory movement", "Fixed assets", "Notes")


def has_company_sheets(sheet_names: list[str]) -> bool:
    """A workbook (e.g. a TB file) that also carries Company & Report Data sheets saved by the app."""
    return "Company" in sheet_names and any(s in sheet_names for s in SHEETS[1:])


def frames(project: dict, years: list[int]) -> tuple[dict, dict]:
    d = extract(project)
    ys = sorted({int(y) for y in list(d["years_data"]) + list(years)}, reverse=True)
    comp = pd.DataFrame([{"Field": lab, "Key": k, "Value": d["meta"].get(k) if k in META_FIELDS else d["general"].get(k)}
                         for k, lab in list(META_FIELDS.items()) + list(GENERAL_FIELDS.items())])
    opts = pd.DataFrame([{"Field": lab, "Key": k, "Value": d["meta"].get(k)} for k, lab in OPTION_FIELDS.items()])
    per = pd.DataFrame([{"Year": y, **{lab: multiyear.yd(project, y)[k] for k, (lab, _) in multiyear.YEAR_FIELDS.items()}}
                        for y in ys], columns=["Year"] + [lab for lab, _ in multiyear.YEAR_FIELDS.values()])
    inv = pd.DataFrame([{"Item": lab, "Key": k, **{str(y): ((multiyear.yd(project, y).get("inventory_movement") or {}).get(k))
                                                    for y in ys}} for k, lab in multiyear.INV_KEYS],
                       columns=["Item", "Key"] + [str(y) for y in ys])
    fa_rows = []
    for y in ys:
        for c in multiyear.yd(project, y).get("fixed_assets") or []:
            fa_rows.append({"Year": y, **{k: c.get(k) for k in FA_COLS}})
    fa = pd.DataFrame(fa_rows, columns=["Year"] + FA_COLS)
    notes = pd.DataFrame([{"id": n.get("id"), "title": n.get("title"), "way": n.get("way"),
                           "tables": ", ".join(n.get("tables", [])), "text": n.get("text")} for n in (d["notes"] or [])],
                         columns=["id", "title", "way", "tables", "text"])
    readme = pd.DataFrame({"Read me": [
        "Company & Report Data of the Annual Report Generator — re-import this file on page 3 (💾 Save / load tab),",
        "or keep these sheets in the same workbook as the trial balance: they are proposed when the TB is uploaded.",
        "Change values in the 'Value' / year columns only; keep the 'Key' columns and the sheet names.",
        "Per-year data: CIT rate as a percentage (28 = 28%). Empty cells = 0.",
        "Notes sheet empty = the notes of the chosen template are used.",
        f"Saved on {d['saved_at']}."]})
    sheets = {"Company": comp, "Report options": opts, "Per-year data": per, "Inventory movement": inv,
              "Fixed assets": fa, "Notes": notes, "Read me": readme}
    pct = multiyear.YEAR_FIELDS["cit_rate"][0]
    sheets["Per-year data"][pct] = sheets["Per-year data"][pct].astype(float) * 100
    money = {"Per-year data": [lab for k, (lab, _) in multiyear.YEAR_FIELDS.items() if k != "cit_rate"],
             "Inventory movement": [str(y) for y in ys],
             "Fixed assets": FA_COLS[2:]}
    return sheets, money


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d")
    return v


def from_file(data: bytes, filename: str) -> dict:
    """Parse a saved JSON / Excel file -> partial project {meta, general, years_data, notes?}."""
    if filename.lower().endswith(".json"):
        d = json.loads(data.decode("utf-8"))
        if d.get("format") not in (FORMAT, multiyear.FORMAT):
            raise ValueError("not a Company & Report Data file (or project file)")
        out = {k: d[k] for k in ("meta", "general", "years_data", "notes", "bookmark_overrides") if k in d}
        if "meta" in out:
            out["meta"] = {k: v for k, v in out["meta"].items() if k in META_FIELDS or k in OPTION_FIELDS}
        return out
    x = pd.ExcelFile(io.BytesIO(data))
    out: dict = {"meta": {}, "general": {}}
    if "Company" not in x.sheet_names:
        raise ValueError("sheet 'Company' not found — use a file saved from page 3")
    for _, r in pd.read_excel(x, "Company").iterrows():
        k, v = str(r["Key"]), _clean(r["Value"])
        (out["meta"] if k in META_FIELDS else out["general"])[k] = v
    if "Report options" in x.sheet_names:
        for _, r in pd.read_excel(x, "Report options").iterrows():
            k, v = str(r["Key"]), _clean(r["Value"])
            if k == "hide_zero_lines":
                v = str(v).strip().upper() in ("TRUE", "1", "YES", "OUI")
            elif k == "tables_font_size":
                v = int(float(v or 8))
            out["meta"][k] = v
    yd: dict = {}
    if "Per-year data" in x.sheet_names:
        lab2key = {lab: k for k, (lab, _) in multiyear.YEAR_FIELDS.items()}
        for _, r in pd.read_excel(x, "Per-year data").iterrows():
            y = str(int(r["Year"]))
            yd[y] = {lab2key[c]: float(_clean(r[c]) or 0) / (100 if lab2key[c] == "cit_rate" else 1)
                     for c in r.index if c in lab2key}
    if "Inventory movement" in x.sheet_names:
        inv = pd.read_excel(x, "Inventory movement")
        for c in [c for c in inv.columns if str(c).isdigit() or isinstance(c, int)]:
            vals = {r["Key"]: _clean(r[c]) for _, r in inv.iterrows()}
            if any(v not in ("", None) for v in vals.values()):
                yd.setdefault(str(int(c)), {})["inventory_movement"] = {k: float(v or 0) for k, v in vals.items()}
    if "Fixed assets" in x.sheet_names:
        fa = pd.read_excel(x, "Fixed assets")
        for y, g in fa.groupby("Year"):
            yd.setdefault(str(int(y)), {})["fixed_assets"] = [
                {k: (_clean(r[k]) if k == "name" else float(_clean(r[k]) or 0)) for k in FA_COLS} for _, r in g.iterrows()]
    if yd:
        out["years_data"] = yd
    if "Notes" in x.sheet_names:
        nt = pd.read_excel(x, "Notes")
        if len(nt):
            out["notes"] = [{"id": str(_clean(r["id"])).split(".")[0].zfill(2), "title": _clean(r["title"]),
                             "way": _clean(r["way"]) or None,
                             "tables": [t.strip() for t in str(_clean(r["tables"])).split(",") if t.strip()],
                             **({"text": _clean(r["text"])} if _clean(r["text"]) else {})} for _, r in nt.iterrows()]
    return out


def apply(project: dict, part: dict) -> list[str]:
    """Merge a parsed file into the project. Returns the list of sections replaced."""
    done = []
    if part.get("meta"):
        project["meta"].update({k: v for k, v in part["meta"].items()}); done.append("company & options")
    if part.get("general"):
        project["general"].update(part["general"]); done.append("printed data")
    if part.get("years_data"):
        for y, v in part["years_data"].items():
            project.setdefault("years_data", {}).setdefault(str(y), {}).update(v)
        done.append(f"per-year data ({', '.join(sorted(part['years_data']))})")
    if "notes" in part:
        project["notes"] = part["notes"] or None; done.append("notes")
    if part.get("bookmark_overrides"):
        project["bookmark_overrides"] = part["bookmark_overrides"]
    return done
