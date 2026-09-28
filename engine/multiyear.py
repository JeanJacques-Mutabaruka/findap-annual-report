"""Multi-year project handling.

Project (app) format — saved as <stem>_project.json:
{
  "format": "arg-project-2",
  "meta":    {company_name, period_end (latest year end, ISO), currency, company_type, tables_font_size,
              variables_color, hide_zero_lines},
  "general": {... printed data: auditor, directors, bankers, frameworks, signatures ...},
  "years_data": {"2025": {cit_rate, prepayments, wht, grants, loss_brought_forward, income_tax_paid,
                          disposal_proceeds, additional_loans_from_directors, short_term_borrowings,
                          drawings, adjustments, inventory_movement, fixed_assets}, ...},
  "notes": null | [...], "bookmark_overrides": {},
  "trial_balance": [{"code","account","comment","note","amounts": {"2025": [debit, credit], ...}}]
}

The calculation engine and the Word template work on TWO years: Current Year (CY) and Previous Year (PY).
`pair_input(project, tb, Y)` builds that 2-year input for CY = Y, PY = Y-1 — the same format as the
annual-report-generator skill's input.json.
"""
from __future__ import annotations

import copy
from datetime import date

import pandas as pd

from . import tb_io

FORMAT = "arg-project-2"
YEAR_FIELDS = {  # key -> (label, help)
    "cit_rate": ("CIT rate (%)", "Corporate income tax rate of the year. Rwanda: 30% up to 2023, 28% from 2024."),
    "prepayments": ("Quarterly prepayments", "CIT quarterly prepayments paid for the year"),
    "wht": ("WHT credits", "Withholding tax (3% / 15%) credited against the CIT of the year"),
    "grants": ("Grants received", "Not used for the moment — treatment of grants to be designed"),
    "loss_brought_forward": ("Tax loss brought forward (old)", "Replaced by the table of tax losses per year of origin"),
    "income_tax_paid": ("Income tax paid", "Tax actually paid during the year (cash flow)"),
    "disposal_proceeds": ("Disposal proceeds", "Cash received from the sale of fixed assets (cash flow)"),
    "additional_loans_from_directors": ("Loans from directors", "New loans from directors in the year (cash flow)"),
    "short_term_borrowings": ("Short-term borrowings (net)", "Net short-term borrowings of the year (cash flow)"),
    "drawings": ("Drawings / dividends paid", "Dividends paid or drawings (equity statement)"),
    "adjustments": ("Prior-year adjustments", "Adjustments booked directly in retained earnings (equity statement)"),
}
INV_KEYS = [("opening", "At 1st January"), ("purchases", "Purchases"), ("purchase_returns", "Purchase returns (negative)"),
            ("cost_of_sales", "Cost of sales (negative)"), ("gain_loss", "Inventory gain / (loss)")]


def statutory_cit(year: int) -> float:
    """Standard CIT rate of a year — from chart_of_accounts.json income_tax.cit_standard_rates (one place)."""
    import json
    from engine import CHART
    tab = sorted(json.loads(CHART.read_text(encoding="utf-8"))["income_tax"].get("cit_standard_rates") or [[0, 0.30]],
                 reverse=True)
    return next((r for fy, r in tab if year >= fy), tab[-1][1])


def year_end(meta: dict, year: int) -> date | None:
    try:
        d = date.fromisoformat(str(meta.get("period_end"))[:10])
    except ValueError:
        return None
    try:
        return d.replace(year=year)
    except ValueError:  # 29 February
        return d.replace(year=year, day=28)


def yd(project: dict, year: int) -> dict:
    """Year data with defaults (statutory CIT rate)."""
    d = dict((project.get("years_data") or {}).get(str(year), {}))
    d.setdefault("cit_rate", statutory_cit(year))
    for k in YEAR_FIELDS:
        d.setdefault(k, 0.0)
    return d


def pair_input(project: dict, tb: pd.DataFrame, year: int, chart: dict | None = None) -> dict:
    """2-year engine input (skill input.json format) for CY = year, PY = year-1."""
    c, p = yd(project, year), yd(project, year - 1)
    if chart is None:
        import json
        from engine import CHART
        chart = json.loads(CHART.read_text(encoding="utf-8"))
    ls = loss_schedule(project, tb, chart)
    src = (f"tax losses of the previous {ls['years']} years" + (" (extension)" if ls["extension"] else "") +
           " — 1 · Company & Report Data → Period & tax")
    src = src.replace("1 · Company", "3 · Company")
    from engine import fixed_assets as fa_mod
    fa_cats, fa_why = fa_mod.note11_from_project(project, tb, chart, year)
    fa_input = ({"categories": fa_cats, "source_note": fa_why} if fa_cats else
                ({"categories": c["fixed_assets"]} if c.get("fixed_assets") else None))
    loss_av, loss_src = {}, {}
    for tag, yy, v in (("cy", year, c), ("py", year - 1, p)):
        loss_av[tag] = (ls["by_year"].get(yy) or {}).get("available", 0.0)
        loss_src[tag] = src
        if not ls["origins"] and float(v.get("loss_brought_forward") or 0):     # older project: total entered per year
            loss_av[tag] = abs(float(v["loss_brought_forward"]))
            loss_src[tag] = "total entered per year (older project) — enter the losses per year of origin instead"
    meta = copy.deepcopy(project["meta"])
    ye = year_end(meta, year)
    meta["period_end"] = ye.isoformat() if ye else ""
    meta["period_start"] = ""
    meta["cit_rate"] = {"cy": float(c["cit_rate"]), "py": float(p["cit_rate"])}
    meta["single_year"] = single_year(project, tb, year)
    for k in ("years", "active_year", "view_mode"):
        meta.pop(k, None)
    inv = None
    from engine import stock as stock_mod
    z = {k: 0.0 for k, _ in INV_KEYS}
    im = {}
    for tag, yy, v in (("cy", year, c), ("py", year - 1, p)):
        form_im, _why = stock_mod.note12_from_project(project, tb, chart, yy) if chart.get("stock") else (None, "")
        im[tag] = form_im or v.get("inventory_movement")
    if im["cy"] or im["py"]:
        inv = {"cy": im["cy"] or z, "py": im["py"] or z}
    return {
        "meta": meta,
        "general": copy.deepcopy(project.get("general", {})),
        "trial_balance": tb_io.pair_rows(tb, year),
        "tax": {"prepayments": {"cy": c["prepayments"], "py": p["prepayments"]},
                "wht": {"cy": c["wht"], "py": p["wht"]},
                "grants": {"cy": 0.0, "py": 0.0},
                "loss_available": loss_av, "loss_source": loss_src},
        "cashflow": {k: c[k] for k in ("income_tax_paid", "disposal_proceeds", "additional_loans_from_directors",
                                       "short_term_borrowings")},
        "equity_movements": {"cy": {"drawings": c["drawings"], "adjustments": c["adjustments"]},
                             "py": {"drawings": p["drawings"], "adjustments": p["adjustments"]}},
        "inventory_movement": inv,
        "fixed_assets": fa_input,
        "notes": project.get("notes"),
        "bookmark_overrides": project.get("bookmark_overrides") or {},
    }


COMPARATIVE = {"auto": "Automatic — Current Year only when the TB has no Previous Year figures",
               "with": "Always show the Previous Year (PY) column",
               "without": "Current Year only — first financial year, no comparative"}


def has_year_data(tb: pd.DataFrame, year: int) -> bool:
    cols = [f"debit_{year}", f"credit_{year}"]
    return all(c in tb.columns for c in cols) and float(tb[cols].abs().sum().sum()) > 0.5


def single_year(project: dict, tb: pd.DataFrame, year: int) -> bool:
    """True when the report of CY = year must show the Current Year only (no PY column)."""
    mode = project.get("meta", {}).get("comparative") or "auto"
    if mode == "without":
        return True
    if mode == "with":
        return False
    return not has_year_data(tb, year - 1)


def from_pair_input(d: dict) -> tuple[dict, pd.DataFrame]:
    """2-year input.json (skill format, V1-0a project file, V11 import) -> (project, multi-year TB)."""
    meta = dict(d.get("meta", {}))
    try:
        ycy = date.fromisoformat(str(meta.get("period_end"))[:10]).year
    except ValueError:
        ycy = pd.Timestamp.today().year - 1
    rate = meta.pop("cit_rate", None) or {}
    t, cf, em = d.get("tax", {}) or {}, d.get("cashflow", {}) or {}, d.get("equity_movements", {}) or {}
    inv = d.get("inventory_movement") or {}
    years_data = {}
    for tag, yr in (("cy", ycy), ("py", ycy - 1)):
        v = {"cit_rate": rate.get(tag, statutory_cit(yr)),
             "prepayments": (t.get("prepayments") or {}).get(tag, 0), "wht": (t.get("wht") or {}).get(tag, 0),
             "grants": (t.get("grants") or {}).get(tag, 0),
             "loss_brought_forward": (t.get("loss_brought_forward") or {}).get(tag, 0),
             "drawings": (em.get(tag) or {}).get("drawings", 0), "adjustments": (em.get(tag) or {}).get("adjustments", 0),
             "inventory_movement": inv.get(tag) if inv else None}
        if tag == "cy":
            v.update({k: cf.get(k, 0) for k in ("income_tax_paid", "disposal_proceeds",
                                                 "additional_loans_from_directors", "short_term_borrowings")})
            v["fixed_assets"] = (d.get("fixed_assets") or {}).get("categories")
        years_data[str(yr)] = v
    project = {"format": FORMAT, "meta": meta, "general": d.get("general", {}), "years_data": years_data,
               "notes": d.get("notes"), "bookmark_overrides": d.get("bookmark_overrides") or {}}
    return project, tb_io.from_pair_rows(d.get("trial_balance", []), ycy)


def pairs(years: list[int]) -> list[int]:
    """Current years that have a report: every year except the earliest (which only serves as PY);
    a single-year TB gives one report with an empty previous year."""
    ys = sorted(years)
    return ys[1:] if len(ys) > 1 else ys


# --------------------------------------------------------- multi-year views --
def multi_statement(models: dict[int, dict], key: str) -> tuple[list[dict], list[int]]:
    """Align the rows of a statement across year pairs. Returns (rows with 'values' by year, years).
    models: {current_year: model}. The earliest year's figures come from the first pair's PY column."""
    ys = sorted(models)
    first = models[ys[0]]
    all_years = ([ys[0] - 1] if key != "cashflow" else []) + ys
    base = models[ys[-1]][key] if key != "income_tax" else models[ys[-1]]["income_tax"]["rows"]
    out = []
    for i, r in enumerate(base):
        vals = []
        if key != "cashflow":
            fr = first[key][i] if key != "income_tax" else first["income_tax"]["rows"][i]
            vals.append(fr.get("py"))
        for y in ys:
            rr = models[y][key][i] if key != "income_tax" else models[y]["income_tax"]["rows"][i]
            vals.append(rr.get("cy"))
        out.append({"type": r["type"], "label": r["label"], "note": r.get("note"), "values": vals, "lvl": r.get("lvl", 2)})
    return out, all_years


def multi_notes(models: dict[int, dict]) -> tuple[list[dict], list[int]]:
    """Notes aligned by (note id, line label) across years. Returns ([{id,title,rows|texts}], years)."""
    ys = sorted(models)
    all_years = [ys[0] - 1] + ys
    notes = []
    for n in models[ys[-1]]["notes"]:
        labels, vals, texts = [], {}, []
        for y in ys:
            mn = next((x for x in models[y]["notes"] if x["id"] == n["id"]), None)
            if not mn:
                continue
            for b in mn["blocks"]:
                if b["kind"] == "text":
                    if y == ys[-1]:
                        texts.append(b["text"])
                    continue
                if b["kind"] != "table2":
                    continue
                sub = b.get("subtitle") or ""
                for r in b["rows"]:
                    k = (sub, r["label"], r["type"])
                    if k not in vals:
                        labels.append(k)
                        vals[k] = {}
                    vals[k][y] = r.get("cy")
                    if y == ys[0]:
                        vals[k][ys[0] - 1] = r.get("py")
        rows = [{"type": t, "label": (f"{s} — " if s and t != "grandtotal" else "") + lab,
                 "values": [vals[(s, lab, t)].get(y) for y in all_years]} for (s, lab, t) in labels]
        notes.append({"id": n["id"], "title": n["title"], "rows": rows, "texts": texts})
    return notes, all_years


# ------------------------------------------------------------------ tax losses --
def loss_settings(project: dict, chart: dict | None = None) -> dict:
    """{"carry_forward_years": N, "extension": bool, "losses": [{"year", "loss", "used_before"}]}"""
    default_n = int(((chart or {}).get("income_tax") or {}).get("loss_carry_forward_years") or 5)
    s = dict(project.get("tax_losses") or {})
    s.setdefault("extension", False)
    s["carry_forward_years"] = int(s.get("carry_forward_years") or default_n) if s["extension"] else default_n
    s.setdefault("losses", [])
    return s


def loss_schedule(project: dict, tb: pd.DataFrame, chart: dict) -> dict:
    """Tax losses carried forward, year by year (FIFO, oldest first).

    Losses by year of ORIGIN come from project["tax_losses"]["losses"] (entered by the user, positive amounts, with
    the part already used in tax returns before the years of the TB). For a year of the TB whose taxable income before
    losses is negative, that loss is taken automatically unless the user entered the year. A loss can be deducted in
    the N years following its year of origin (N = 5 by default, or the extension entered for the client).
    Returns {"years": N, "by_year": {Y: {"available", "used", "before_losses", "expired"}}, "origins": [...]}.
    """
    from engine import build_model
    st_ = loss_settings(project, chart)
    n = st_["carry_forward_years"]
    tb_years = tb_io.years_of(tb)
    before = {}
    for y in tb_years:
        tbo = build_model.TB(tb_io.pair_rows(tb, y), build_model.Controls())
        before[y] = build_model.pre_loss_taxable(tbo, "cy", chart)["before_losses"]
    origins: dict[int, dict] = {}
    for r in st_["losses"]:
        try:
            yr = int(r.get("year"))
        except (TypeError, ValueError):
            continue
        amt = abs(float(r.get("loss") or 0))
        if amt > 0:
            origins[yr] = {"year": yr, "loss": amt, "used_before": min(amt, abs(float(r.get("used_before") or 0))),
                           "source": "entered"}
    for y in tb_years:
        if before[y] < 0 and y not in origins:
            origins[y] = {"year": y, "loss": -before[y], "used_before": 0.0, "source": "computed from the TB"}
    for o in origins.values():
        o["remaining"] = o["loss"] - o["used_before"]
        o["used_by_year"] = {}
        o["expires_after"] = o["year"] + n
    by_year = {}
    first = min([*origins.keys(), *tb_years]) if (origins or tb_years) else None
    last = max(tb_years) if tb_years else None
    if first is None or last is None:
        return {"years": n, "by_year": {}, "origins": [], "extension": st_["extension"]}
    for Y in range(first + 1, last + 1):
        live = sorted((o for o in origins.values() if Y - n <= o["year"] <= Y - 1 and o["remaining"] > 0.5),
                      key=lambda o: o["year"])
        expired = sum(o["remaining"] for o in origins.values() if o["year"] == Y - n - 1 and o["remaining"] > 0.5)
        avail = sum(o["remaining"] for o in live)
        used = 0.0
        if Y in before and before[Y] > 0:
            need = min(avail, before[Y])
            used = need
            for o in live:
                take = min(o["remaining"], need)
                if take > 0:
                    o["remaining"] -= take
                    o["used_by_year"][Y] = take
                    need -= take
        by_year[Y] = {"available": avail, "used": used, "before_losses": before.get(Y), "expired": expired}
    for y in tb_years:
        by_year.setdefault(y, {"available": 0.0, "used": 0.0, "before_losses": before[y], "expired": 0.0})
    return {"years": n, "extension": st_["extension"], "by_year": by_year,
            "origins": sorted(origins.values(), key=lambda o: o["year"])}
