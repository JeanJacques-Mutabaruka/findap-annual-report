"""Trial balance input/output and TB-level checks — multi-year.

Inside the app a trial balance is a DataFrame with the base columns BASE plus, for every
financial year Y, two amount columns  debit_Y  and  credit_Y  (e.g. debit_2025, credit_2025).
Any number of years is allowed (1 … n). The 2-year engine (build_model) receives one pair of
years at a time through `pair_rows` (Y = Current Year, Y-1 = Previous Year).

Everything here is pure pandas (no Streamlit) so it can be unit-tested.
"""
from __future__ import annotations

import io
import re

import pandas as pd

BASE = ["code", "account", "comment", "note"]
TOL = 1.0
YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")


# ------------------------------------------------------------ year columns --
def years_of(tb: pd.DataFrame) -> list[int]:
    return sorted({int(c.split("_")[1]) for c in tb.columns if re.fullmatch(r"(debit|credit)_\d{4}", str(c))})


def amount_cols(tb: pd.DataFrame) -> list[str]:
    return [f"{s}_{y}" for y in years_of(tb) for s in ("debit", "credit")]


def empty_tb(years: list[int] | None = None) -> pd.DataFrame:
    return pd.DataFrame(columns=BASE + [f"{s}_{y}" for y in sorted(years or []) for s in ("debit", "credit")])


# ------------------------------------------------------------------ reading --
def sheet_names(data: bytes, filename: str) -> list[str]:
    if filename.lower().endswith(".csv"):
        return ["(csv)"]
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


def read_table(data: bytes, filename: str, sheet: str | int = 0, header_row: int = 1) -> pd.DataFrame:
    """Raw table with the given (1-based) header row. Column names are made unique and stripped."""
    if filename.lower().endswith(".csv"):
        raw = data.decode("utf-8-sig", errors="replace")
        sep = ";" if raw.count(";") > raw.count(",") else ","
        df = pd.read_csv(io.StringIO(raw), header=header_row - 1, sep=sep)
    else:
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=header_row - 1)
    cols, seen = [], {}
    for c in df.columns:
        c = str(c).strip()
        if c.lower().startswith("unnamed"):
            c = f"(col {len(cols) + 1})"
        if c in seen:
            seen[c] += 1
            c = f"{c} #{seen[c]}"
        else:
            seen[c] = 1
        cols.append(c)
    df.columns = cols
    return df.dropna(how="all")


def find_header_row(data: bytes, filename: str, sheet=0, max_rows: int = 15) -> int | None:
    """First row (1-based) holding an 'account'-like and a 'debit'/'balance'-like label, or None."""
    r = guess_header_row(data, filename, sheet, max_rows, default=None)
    return r


def tb_sheets(data: bytes, filename: str) -> list[dict]:
    """Sheets of a file that look like a trial balance: [{"sheet", "header_row", "years", "lines", "balanced"}].
    Hidden sheets are skipped (e.g. the template's 'Lists')."""
    if filename.lower().endswith(".csv"):
        return [{"sheet": "(csv)", "header_row": guess_header_row(data, filename), "years": [], "lines": None, "balanced": None}]
    hidden = set()
    if filename.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
            hidden = {ws.title for ws in wb.worksheets if ws.sheet_state != "visible"}
        except Exception:  # noqa: BLE001
            pass
    out = []
    for sh in sheet_names(data, filename):
        if sh in hidden:
            continue
        h = find_header_row(data, filename, sh)
        if not h:
            continue
        info = {"sheet": sh, "header_row": h, "years": [], "lines": None, "balanced": None}
        try:
            raw = read_table(data, filename, sh, h)
            mp = guess_mapping(list(raw.columns))
            if mp.get("account") and mp["years"]:
                tb, _ = to_tb(raw, mp)
                info.update(years=years_of(tb), lines=len(tb), balanced=balance(tb)["ok"])
            else:
                continue
        except Exception:  # noqa: BLE001
            continue
        out.append(info)
    return out


def guess_header_row(data: bytes, filename: str, sheet=0, max_rows: int = 15, default: int | None = 1) -> int | None:
    """First row (1-based) that contains an 'account'-like and a 'debit'/'balance'-like label (else `default`)."""
    try:
        raw = (pd.read_csv(io.BytesIO(data), header=None, nrows=max_rows) if filename.lower().endswith(".csv")
               else pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=None, nrows=max_rows))
    except Exception:  # noqa: BLE001
        return default
    for i, row in raw.iterrows():
        cells = [str(x).lower() for x in row.tolist() if str(x).strip() not in ("", "nan", "None")]
        if len(cells) < 3:  # a title or instruction line, not a header row
            continue
        txt = " | ".join(cells)
        if re.search(r"account|compte|libell|name|intitul", txt) and re.search(r"debit|débit|credit|crédit|balance|solde", txt):
            return int(i) + 1
    return default


def guess_mapping(columns: list[str], default_latest_year: int | None = None) -> dict:
    """Best-effort mapping.

    Returns {"code": col|None, "account": col|None, "comment": col|None, "layout": "dc"|"balance",
             "years": [{"year": int, "debit": col, "credit": col} | {"year": int, "balance": col}, ...]}
    Years are read from the headers ("Debit 2025"); otherwise columns are paired in order and numbered
    backwards from `default_latest_year` (most recent first, the usual TB layout).
    """
    low = {c: c.lower() for c in columns}

    def first(pattern, exclude=()):
        for c, l in low.items():
            if c not in exclude and re.search(pattern, l):
                return c
        return None

    m: dict = {"code": first(r"cit\s*code|^code|rra|\bcit\b")}
    m["account"] = first(r"account\s*name|intitul|libell|account|compte|description|name", exclude=[m["code"]])
    m["comment"] = first(r"comment|remark|observ")
    m["group"] = first(r"^group$")                 # TB template: used to derive a missing CIT code
    m["line"] = first(r"^statement\s*line$")
    debits = [c for c, l in low.items() if re.search(r"d[ée]bit", l)]
    credits = [c for c, l in low.items() if re.search(r"cr[ée]dit", l)]
    latest = default_latest_year or (pd.Timestamp.today().year - 1)
    years = []
    if debits or credits:
        m["layout"] = "dc"
        for i in range(max(len(debits), len(credits))):
            d = debits[i] if i < len(debits) else None
            c = credits[i] if i < len(credits) else None
            yr = None
            for col in (d, c):
                mm = YEAR_RE.search(col) if col else None
                if mm:
                    yr = int(mm.group(0)); break
            years.append({"year": yr, "debit": d, "credit": c})
    else:
        m["layout"] = "balance"
        for col in [c for c, l in low.items() if re.search(r"balance|solde|amount|montant", l)]:
            mm = YEAR_RE.search(col)
            years.append({"year": int(mm.group(0)) if mm else None, "balance": col})
    known = [y["year"] for y in years if y["year"]]
    used, nxt = set(known), (max(known) if known else latest)
    for y in years:
        if y["year"] is None:
            while nxt in used:
                nxt -= 1
            y["year"] = nxt
            used.add(nxt)
    m["years"] = years
    return m


def _num(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Coerce to float; returns (values, mask_of_unparseable_non_blank_cells)."""
    txt = series.astype(str).str.strip()
    blank = series.isna() | txt.isin(["", "-", "nan", "None"])
    cleaned = (txt.str.replace("[\\s\u202f\u00a0,]", "", regex=True)
                  .str.replace(r"^\((.*)\)$", r"-\1", regex=True))
    vals = pd.to_numeric(cleaned.where(~blank, "0"), errors="coerce")
    bad = vals.isna() & ~blank
    return vals.fillna(0.0), bad


def clean_text(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none") else s


def to_tb(df: pd.DataFrame, mapping: dict, catalogue: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Apply a mapping (see guess_mapping). Returns (tb, notes) — notes explain what was dropped/converted.
    With a catalogue (code/group/line), a blank CIT code is derived from the Group + Statement line columns."""
    notes: list[str] = []
    ylist = [int(y["year"]) for y in mapping["years"]]
    if len(set(ylist)) != len(ylist):
        raise ValueError("Each year can be used only once in the mapping.")
    years = sorted(ylist)
    out = pd.DataFrame(index=df.index)
    for k in ("code", "account", "comment"):
        out[k] = df[mapping[k]] if mapping.get(k) else ""
    out["note"] = ""
    bad_cells = pd.Series(False, index=df.index)
    for y in mapping["years"]:
        yr = int(y["year"])
        if y.get("balance"):
            v, bad = _num(df[y["balance"]])
            out[f"debit_{yr}"], out[f"credit_{yr}"] = v.clip(lower=0), (-v).clip(lower=0)
            bad_cells |= bad
        else:
            for side in ("debit", "credit"):
                col = y.get(side)
                if col:
                    v, bad = _num(df[col]); out[f"{side}_{yr}"] = v; bad_cells |= bad
                else:
                    out[f"{side}_{yr}"] = 0.0
    if bad_cells.any():
        rows = ", ".join(str(i + 1) for i in bad_cells[bad_cells].index[:10])
        notes.append(f"{int(bad_cells.sum())} amount cell(s) were not numbers and were read as 0 (rows {rows}…). Check them.")
    out["code"] = out["code"].apply(norm_code)
    if catalogue is not None and mapping.get("line"):
        key = {(clean_text(r.group), clean_text(r.line)): r.code for r in catalogue.itertuples()}
        by_line = catalogue.groupby("line")["code"].apply(list).to_dict()
        grp = df[mapping["group"]].apply(clean_text) if mapping.get("group") else pd.Series("", index=df.index)
        lin = df[mapping["line"]].apply(clean_text)
        n = 0
        for i in out.index:
            if not out.at[i, "code"] and lin[i]:
                c = key.get((grp[i], lin[i])) or (by_line.get(lin[i], [None])[0] if len(by_line.get(lin[i], [])) == 1 else None)
                if c:
                    out.at[i, "code"] = c
                    n += 1
        if n:
            notes.append(f"{n} CIT code(s) derived from the Group / Statement line columns.")
    for k in ("account", "comment"):
        out[k] = out[k].apply(clean_text)
    out = out[BASE + [f"{s}_{y}" for y in years for s in ("debit", "credit")]].reset_index(drop=True)
    out, n = drop_blank_and_totals(out)
    if n:
        notes.append(f"{n} blank or total line(s) ignored.")
    return out, notes


def drop_blank_and_totals(tb: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove blank lines, lines labelled TOTAL, and un-labelled lines whose amounts equal the sum of all
    the other lines (the total line of most TB exports and of the V11 TrialBalance sheet)."""
    amts = amount_cols(tb)
    if tb.empty:
        return tb, 0
    acc = tb["account"].apply(clean_text)
    has_amt = (tb[amts].abs() > 0).any(axis=1) if amts else pd.Series(False, index=tb.index)
    total_like = acc.str.upper().str.match(r"^(GRAND\s+)?TOTALS?\b|^TOTAL\s+G[ÉE]N[ÉE]RAL")
    drop = ((acc == "") & ~has_amt) | total_like
    for i in tb.index[(acc == "") & has_amt]:
        others = tb.drop(index=i)[amts].sum()
        if all(abs(tb.at[i, c] - others[c]) <= TOL for c in amts):
            drop.at[i] = True
    return tb[~drop].reset_index(drop=True), int(drop.sum())


def norm_code(c) -> str:
    c = clean_text(c)
    if not c:
        return ""
    c = re.sub(r"\s+", " ", c.upper())
    return re.sub(r"^(BS|PL)\s*", lambda m: m.group(1) + " ", c)


def normalise(tb: pd.DataFrame) -> pd.DataFrame:
    """Types and cleaning after any edit."""
    tb = tb.copy()
    for c in BASE:
        if c not in tb.columns:
            tb[c] = ""
    tb["code"] = tb["code"].apply(norm_code)
    for c in ("account", "comment", "note"):
        tb[c] = tb[c].apply(clean_text)
    for c in amount_cols(tb):
        tb[c] = pd.to_numeric(tb[c], errors="coerce").fillna(0.0)
    return tb[BASE + amount_cols(tb)].reset_index(drop=True)


# -------------------------------------------------- 2-year engine interface --
def pair_rows(tb: pd.DataFrame, year: int) -> list[dict]:
    """Engine rows: Current Year (cy) = year, Previous Year (py) = year-1 (zeros if absent)."""
    rows = []
    for r in tb.to_dict("records"):
        rec = {"code": r["code"], "account": r["account"], "comment": r["comment"] or None, "note": r["note"] or None}
        for tag, yr in (("cy", year), ("py", year - 1)):
            rec[f"debit_{tag}"] = float(r.get(f"debit_{yr}", 0.0) or 0.0)
            rec[f"credit_{tag}"] = float(r.get(f"credit_{yr}", 0.0) or 0.0)
        rows.append(rec)
    return rows


def from_pair_rows(rows: list[dict], year_cy: int) -> pd.DataFrame:
    """2-year rows (debit_cy …) -> multi-year TB with the years year_cy-1 and year_cy."""
    cols = BASE + [f"{s}_{y}" for y in (year_cy - 1, year_cy) for s in ("debit", "credit")]
    recs = []
    for r in rows:
        rec = {k: r.get(k) for k in BASE}
        for tag, yr in (("py", year_cy - 1), ("cy", year_cy)):
            rec[f"debit_{yr}"], rec[f"credit_{yr}"] = r.get(f"debit_{tag}", 0), r.get(f"credit_{tag}", 0)
        recs.append(rec)
    tb = normalise(pd.DataFrame(recs, columns=cols))
    return drop_blank_and_totals(tb)[0]


def to_records(tb: pd.DataFrame) -> list[dict]:
    """Project-file format: {"code","account","comment","note","amounts": {"2025": [debit, credit], ...}}."""
    return [{"code": r["code"], "account": r["account"], "comment": r["comment"] or None, "note": r["note"] or None,
             "amounts": {str(y): [float(r[f"debit_{y}"]), float(r[f"credit_{y}"])] for y in years_of(tb)}}
            for r in tb.to_dict("records")]


def from_records(recs: list[dict]) -> pd.DataFrame:
    years = sorted({int(y) for r in recs for y in (r.get("amounts") or {})})
    rows = []
    for r in recs:
        rec = {k: r.get(k) for k in BASE}
        for y in years:
            d, c = (r.get("amounts") or {}).get(str(y), [0, 0])
            rec[f"debit_{y}"], rec[f"credit_{y}"] = d, c
        rows.append(rec)
    return normalise(pd.DataFrame(rows, columns=BASE + [f"{s}_{y}" for y in years for s in ("debit", "credit")]))


# ------------------------------------------------------------------- checks --
def balance(tb: pd.DataFrame) -> dict:
    """{year: {debit, credit, diff, ok}, ..., 'ok': every year balanced}"""
    res: dict = {}
    for y in years_of(tb):
        d, c = float(tb[f"debit_{y}"].sum()), float(tb[f"credit_{y}"].sum())
        res[y] = {"debit": d, "credit": c, "diff": d - c, "ok": abs(d - c) <= TOL}
    res["ok"] = all(v["ok"] for k, v in res.items())
    return res


def balance_table(tb: pd.DataFrame) -> pd.DataFrame:
    b = balance(tb)
    return pd.DataFrame([{"Year": str(y), "Total debit": v["debit"], "Total credit": v["credit"],
                          "Difference (debit − credit)": v["diff"], "Status": "✅ balanced" if v["ok"] else "❌ NOT balanced"}
                         for y, v in b.items() if y != "ok"])


def line_issues(tb: pd.DataFrame, valid_codes: set[str]) -> pd.DataFrame:
    """One row per problem found on a TB line (all years)."""
    out = []
    years, amts = years_of(tb), amount_cols(tb)
    for i, r in tb.iterrows():
        n, acc = i + 1, r["account"] or "(no name)"
        if not r["account"]:
            out.append((n, acc, r["code"], "", "BLOCKING", "Account name missing"))
        if not r["code"]:
            out.append((n, acc, r["code"], "", "BLOCKING", "CIT code missing"))
        elif r["code"] not in valid_codes:
            out.append((n, acc, r["code"], "", "BLOCKING", f"CIT code '{r['code']}' is not in the chart of accounts"))
        for y in years:
            if r[f"debit_{y}"] < 0 or r[f"credit_{y}"] < 0:
                out.append((n, acc, r["code"], str(y), "WARNING", "Negative amount — put credits in the credit column"))
            if abs(r[f"debit_{y}"]) > TOL and abs(r[f"credit_{y}"]) > TOL:
                out.append((n, acc, r["code"], str(y), "WARNING", "Both debit and credit filled (the net is used)"))
            if r["code"] == "BS 1.09" and (r[f"debit_{y}"] - r[f"credit_{y}"]) > TOL:
                out.append((n, acc, r["code"], str(y), "BLOCKING", "Accumulated depreciation with a DEBIT balance (must be credit)"))
        if amts and all(abs(r[a]) <= TOL for a in amts):
            out.append((n, acc, r["code"], "", "INFO", "Zero in every year"))
        if re.search(r"balanc|plug|make.*tb", str(r.get("comment") or ""), re.I):
            out.append((n, acc, r["code"], "", "WARNING", f"Commented as balancing figure: '{r['comment']}'"))
    for grp in duplicate_groups(tb):
        lines = ", ".join(f"#{i + 1}" for i in grp["rows"])
        for i in grp["rows"]:
            out.append((i + 1, tb.at[i, "account"], tb.at[i, "code"], "", "BLOCKING",
                        f"Same account description on lines {lines} — merge them or give each a different description"))
    return pd.DataFrame(out, columns=["Line", "Account", "Code", "Year", "Level", "Issue"])


def desc_key(name) -> str:
    """Comparison key of an account description: case, accents, spaces and punctuation ignored."""
    import unicodedata
    s = unicodedata.normalize("NFKD", clean_text(name)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def duplicate_groups(tb: pd.DataFrame) -> list[dict]:
    """Groups of lines sharing the same account description (a CIT code MAY repeat; a description may not).
    Each group: {"key", "rows": [indexes], "same_code": bool, "codes": [...]}."""
    if tb.empty:
        return []
    keys = tb["account"].map(desc_key)
    groups = []
    for k, idx in keys[keys != ""].groupby(keys[keys != ""]).groups.items():
        rows = sorted(int(i) for i in idx)
        if len(rows) > 1:
            codes = list(dict.fromkeys(tb.loc[rows, "code"]))
            groups.append({"key": k, "rows": rows, "same_code": len(codes) == 1, "codes": codes})
    return sorted(groups, key=lambda g: g["rows"][0])


def merge_lines(tb: pd.DataFrame, rows: list[int]) -> pd.DataFrame:
    """Merge lines into the first one: amounts summed per year, comments joined, other lines removed."""
    tb = tb.copy()
    keep, drop = rows[0], rows[1:]
    for c in amount_cols(tb):
        tb.at[keep, c] = float(tb.loc[rows, c].sum())
    comments = [clean_text(x) for x in tb.loc[rows, "comment"] if clean_text(x)]
    tb.at[keep, "comment"] = " | ".join(dict.fromkeys(comments))
    return tb.drop(index=drop).reset_index(drop=True)
