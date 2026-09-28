"""Suggest a CIT code from an account name (EN / FR keywords) and the balance direction.

Suggestions are never applied silently: the user confirms them on
2 · Checks & Corrections. Order matters — the first matching rule wins,
so specific rules (accumulated depreciation, goods in transit) come first.

`suggest(account)`  -> (code, reason)                      keyword rules only (kept for compatibility)
`propose(account, net, catalogue)` -> dict                 code, confidence, reason, alternative, comment
`normal_side(code)` -> "DR" | "CR"                         usual balance of a CIT code in a TB
`keyword_hints()`   -> {code: "kw1, kw2…"}                 readable keywords (AI mapping prompt)
"""
from __future__ import annotations

import re
import unicodedata

RULES: list[tuple[str, str, str]] = [
    # (regex, code, reason)
    (r"accum|amort.*cumul|cumul.*amort|provision.*deprec|depreciation\s*reserve", "BS 01.10", "accumulated depreciation"),
    (r"^dep[\s\-.]|deprec|amortis|dotation", "PL 05.01", "depreciation charge"),
    (r"goods\s*in\s*transit|en\s*transit|work\s*in\s*progress|wip|en[\s-]cours", "BS 03.01.01.03", "work in progress / goods in transit"),
    (r"raw\s*material|mati[eè]res?\s*premi", "BS 03.01.01.02", "raw materials"),
    (r"inventor|stock|marchandise", "BS 03.01.01.04", "inventories"),
    (r"land|terrain", "BS 01.01", "land"),
    (r"building|b[aâ]timent|construction", "BS 01.02", "buildings"),
    (r"vehic|vehcle|moto|car\b|truck|v[ée]hicule", "BS 01.03", "motor vehicles"),
    (r"machin|plant|equipement industriel", "BS 01.04", "machinery"),
    (r"software|logiciel|intangible|incorporel|licen[cs]e\s*(software)?$", "BS 01.06", "intangible assets"),
    (r"furnit|fitting|mobilier|fixture", "BS 01.08", "furniture and fittings"),
    (r"computer|laptop|ordinateur|informatique|\bit\s*equip|printer|imprimante|server|serveur", "BS 01.07", "IT equipment"),
    (r"office\s*equip|equipment|mat[ée]riel", "BS 01.09", "other assets (equipment)"),
    (r"bank\s*charge|frais\s*bancaire|commission\s*bancaire", "PL 07.02", "bank charges"),
    (r"petty\s*cash|cash\s*in\s*hand|caisse|pettycash", "BS 03.01.03.01", "cash in hand"),
    (r"bank|banque|bk\b|equity\s*bank|momo|mobile\s*money", "BS 03.01.03.02", "bank balances"),
    (r"\bpaye\b", "BS 08.01.06", "PAYE payable"),
    (r"other\s*current\s*assets?|autres?\s*actifs?\s*courants?", "BS 03.01.04", "other current assets"),
    (r"vat\s*rec|tva\s*r[ée]cup|input\s*vat", "BS 03.01.04.01", "VAT receivable"),
    (r"wht|withholding|retenue", "BS 03.01.04.02", "WHT receivable"),
    (r"\bvat\b|\btva\b", "BS 03.01.04.01", "VAT balance"),
    (r"prepa|pr[ée]pay|avance.*fournisseur|charges?\s*constat", "BS 03.01.02.02", "prepayments"),
    (r"salary\s*adv|staff\s*(loan|adv)|avance.*personnel", "BS 03.02.04", "advances to staff"),
    (r"receiv|debtor|client|cr[ée]ance", "BS 03.01.02.01", "trade receivables"),
    (r"share\s*capital|capital\s*social|^capital", "BS 05.01", "share capital"),
    (r"retained|report\s*[àa]\s*nouveau|r[ée]sultat.*ant[ée]rieur|accumulated\s*(profit|loss)", "BS 05.07", "retained earnings"),
    (r"overdraft|d[ée]couvert", "BS 08.01.04", "bank overdraft"),
    (r"dividend.*pay", "BS 08.01.05", "dividends payable"),
    (r"payable.*(salary|paye|rssb|tax|vat)|(salary|paye|rssb|vat|tva).*payab|accrual|accrued|dette.*(fiscal|social)", "BS 08.01.06", "other current liabilities"),
    (r"payable|creditor|fournisseur|supplier", "BS 08.01.01", "trade payables"),
    (r"shareholder|associ[ée]|director.*(loan|account)|compte\s*courant", "BS 06.02.04", "other loans (shareholders)"),
    (r"loan|emprunt|borrow", "BS 06.02.03", "local loans"),
    (r"cost\s*of\s*(sales|goods)|cogs|purchase|achat", "PL 02.02.01", "cost of sales"),
    (r"sales|revenue|turnover|chiffre|vente|income\s*from", "PL 01.01", "revenue"),
    (r"interest\s*income|produit.*financ", "PL 08.01", "interest income"),
    (r"other\s*income|autres?\s*produits", "PL 08.13", "other income"),
    (r"rssb|pension|retirement|social\s*security|cotisation", "PL 06.04", "contribution to retirement fund"),
    (r"insurance|assurance", "PL 06.06", "insurance"),
    (r"salar|wage|staff|payroll|salaire|remun", "PL 06.01", "staff salaries"),
    (r"travel|transport|voyage|d[ée]placement", "PL 04.01", "travel"),
    (r"advert|marketing|publicit", "PL 04.02", "advertisement & marketing"),
    (r"audit", "PL 04.03", "audit expenses"),
    (r"legal|juridique|avocat|notaire", "PL 04.04", "legal expense"),
    (r"consult|honoraire", "PL 04.07", "consultancy"),
    (r"communic|telephon|internet|airtime", "PL 04.08", "communication"),
    (r"entertain|r[ée]ception", "PL 04.09", "entertainment"),
    (r"donation|don\b", "PL 04.10", "donations"),
    (r"\brent\b|loyer", "PL 04.12", "rent"),
    (r"electric", "PL 04.14", "electricity"),
    (r"water|eau\b", "PL 04.15", "water"),
    (r"utilit|gaz|gas", "PL 04.16", "other utilities"),
    (r"fuel|carburant|essence", "PL 04.17", "fuel"),
    (r"station|printing|fourniture\s*de\s*bureau", "PL 04.24", "printing & stationery"),
    (r"clean|nettoyage", "PL 04.25", "cleaning"),
    (r"security|s[ée]curit|gardiennage", "PL 04.26", "security"),
    (r"fine|penal|amende", "PL 05.08.02", "fines and penalties"),
    (r"trading\s*licen|patente|licence", "PL 05.07", "licence fees"),
    (r"interest|int[ée]r[eê]t", "PL 07.01", "interest expense"),
    (r"exchange\s*loss|perte\s*de\s*change", "PL 07.05", "exchange loss"),
    (r"exchange\s*gain|gain\s*de\s*change", "PL 08.04", "exchange gain"),
    (r"repair|maint|entretien", "PL 04.27", "other operating expenses (repairs)"),
    (r"expense|charge|frais|cost", "PL 04.27", "other operating expenses"),
]

# Reasons of catch-all rules: a match only says "some expense / some equipment" -> medium confidence at best.
GENERIC = {"other operating expenses", "other assets (equipment)", "inventories", "revenue",
           "other operating expenses (repairs)", "local loans", "trade receivables", "trade payables"}

# Balance-direction corrections: (code matched by the name, side found in the TB) -> (code, reason, confidence)
FLIP: dict[tuple[str, str], tuple[str, str, str]] = {
    ("PL 05.01", "CR"): ("BS 01.10", "depreciation with a credit balance = accumulated depreciation", "Medium"),
    ("BS 03.01.03.02", "CR"): ("BS 08.01.04", "bank account with a credit balance = bank overdraft", "Medium"),
    ("PL 07.01", "CR"): ("PL 08.01", "interest with a credit balance = interest income", "Medium"),
    ("PL 07.05", "CR"): ("PL 08.04", "exchange difference with a credit balance = exchange gain", "Medium"),
    ("PL 08.04", "DR"): ("PL 07.05", "exchange difference with a debit balance = exchange loss", "Medium"),
    ("BS 03.01.04.01", "CR"): ("BS 08.01.06", "VAT with a credit balance = VAT payable", "Medium"),
    ("BS 03.01.04.02", "CR"): ("BS 08.01.06", "WHT with a credit balance = WHT payable", "Medium"),
    ("BS 06.02.03", "DR"): ("BS 03.02.03", "loan with a debit balance = loan granted (asset)", "Medium"),
    ("BS 06.02.04", "DR"): ("BS 03.02.06", "shareholder / director account with a debit balance = advance to others", "Medium"),
    ("BS 08.01.01", "DR"): ("BS 03.01.02.02", "supplier account with a debit balance = advance to suppliers (prepayment)", "Low"),
    ("BS 03.01.02.01", "CR"): ("BS 08.01.06", "customer account with a credit balance = advance from customers", "Low"),
    ("PL 01.01", "DR"): ("PL 02.02.01", "sales-type name with a debit balance — cost of sales or sales returns?", "Low"),
}
ALTERNATIVES: dict[str, str] = {        # classic hesitations, shown as "alternative"
    "BS 08.01.06": "BS 07.02", "PL 04.27": "PL 05.08", "BS 01.09": "BS 01.08", "BS 01.07": "BS 01.09", "PL 01.01": "PL 01.02",
    "BS 06.02.03": "BS 06.01.03", "PL 02.02.01": "PL 02.02.01.01", "PL 04.12": "PL 02.04.01", "PL 04.17": "PL 02.04.03",
    "PL 06.01": "PL 02.03.01", "PL 06.06": "PL 07.03", "BS 03.01.01.04": "BS 03.01.01.01", "PL 05.01": "PL 02.04.06",
}
SAME_FAMILY = {("BS 01.10", "PL 05.01"), ("BS 03.01.01.03", "BS 03.01.01.04"), ("BS 03.01.01.02", "BS 03.01.01.04")}  # rule order is intended
RANK = {"High": 3, "Medium": 2, "Low": 1}


def normal_side(code: str | None) -> str:
    """Usual balance of a CIT code in a trial balance: revenues, closing stock, BS 01.10, equity and liabilities
    are credits; expenses, opening stock and assets are debits (BS 05.07 is a debit when losses are carried forward)."""
    c = (code or "").strip()
    if c.startswith("PL"):
        return "CR" if re.match(r"PL (01|08|02\.05)(\.|$)", c) else "DR"
    if c == "BS 01.10" or re.match(r"BS 0[5678](\.|$)", c):
        return "CR"
    return "DR"


def _norm(t) -> str:
    s = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _matches(a: str) -> list[tuple[str, str]]:
    """Codes matched by the rules, in rule order. A later rule is ignored when its keyword overlaps the text
    already explained by the first code (e.g. 'bank' inside 'bank charges', 'interest' inside 'interest income')."""
    found = []
    for pat, code, why in RULES:
        m = re.search(pat, a)
        if m:
            found.append((code, why, m.span()))
    if not found:
        return []
    first = found[0][0]
    covered = [sp for c, _, sp in found if c == first]
    out = [(first, found[0][1])]
    for code, why, (b, e) in found[1:]:
        if code in [c for c, _ in out] or why in GENERIC or (first, code) in SAME_FAMILY:
            continue
        if any(b < ce and cb < e for cb, ce in covered):
            continue
        out.append((code, why))
    return out


def _cap(conf: str, limit: str) -> str:
    return conf if RANK[conf] <= RANK[limit] else limit


def propose(account, net: float | None = None, catalogue=None) -> dict:
    """Best CIT code for an account with a confidence level.

    net = debit - credit of the line (latest year with a non-zero balance), used to check the direction.
    catalogue (DataFrame code/line) enables exact matches on the statement-line wording.
    Returns {"code", "confidence": High|Medium|Low, "reason", "alternative", "comment"}.
    """
    res = {"code": None, "confidence": "Low", "reason": "", "alternative": "", "comment": ""}
    if account is None or (isinstance(account, float) and account != account) or not str(account).strip():
        res["reason"] = "no account name"
        res["comment"] = "No account name — choose the code manually."
        return res
    a = str(account).strip().lower()
    side = None if net is None or abs(net) < 1 else ("DR" if net > 0 else "CR")
    hits = _matches(a)
    # 1. exact wording of a statement line (e.g. "Rent", "Bank charges", "Share premium")
    if catalogue is not None and len(catalogue):
        key = _norm(account)
        exact = [r.code for r in catalogue.itertuples() if _norm(r.line) == key]
        if len(exact) == 1:
            res.update(code=exact[0], confidence="High", reason="same wording as the statement line")
            hits = [(exact[0], res["reason"])] + [h for h in hits if h[0] != exact[0]]
    # 2. keyword rules
    if not res["code"]:
        if not hits:
            res["reason"] = "no keyword matched — choose manually"
            res["comment"] = "No keyword recognised — choose the code manually (1 · Trial Balance → Find a code)."
            return res
        code, why = hits[0]
        conf = "Medium" if why in GENERIC else "High"
        other = next((c for c, _ in hits[1:] if c != code), "")
        if other and why in GENERIC:
            conf = "Low"
        elif other:
            conf = _cap(conf, "Medium")
        res.update(code=code, confidence=conf, reason=f"keyword: {why}", alternative=other)
    # 3. balance direction
    if side and res["code"]:
        flip = FLIP.get((res["code"], side))
        other = next((c for c, _ in hits[1:] if c != res["code"] and normal_side(c) == side), None)
        word = "debit" if side == "DR" else "credit"
        if flip:
            old = res["code"]
            res.update(code=flip[0], confidence=_cap(res["confidence"], flip[2]), reason=flip[1],
                       alternative=ALTERNATIVES.get(flip[0], old))
        elif normal_side(res["code"]) != side and res["code"] != "BS 05.07" and other:
            old = res["code"]
            res.update(code=other, confidence="Medium", alternative=old,
                       reason=f"{dict(hits)[other]} — chosen because the balance is a {word} ({old} would be a "
                              f"{'credit' if side == 'DR' else 'debit'})")
        elif normal_side(res["code"]) != side and res["code"] != "BS 05.07":
            res["confidence"] = "Low"
            res["reason"] += f" — but the balance is a {word}, unusual for this code"
    if not res["alternative"]:
        res["alternative"] = ALTERNATIVES.get(res["code"], "")
    if res["confidence"] != "High":
        alt = f"; alternative {res['alternative']}" if res["alternative"] else ""
        res["comment"] = f"Proposed {res['code']} ({res['confidence'].lower()} confidence): {res['reason']}{alt} — please check."
    return res


def keyword_hints() -> dict[str, str]:
    """Readable keywords per code, derived from RULES (for the AI mapping prompt)."""
    def clean(pat: str) -> list[str]:
        parts, depth, cur = [], 0, ""
        for ch in pat:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "|" and depth == 0:
                parts.append(cur); cur = ""
            else:
                cur += ch
        parts.append(cur)
        out = []
        for p in parts:
            p = re.sub(r"\\[bs]\*?|\^|\$|\?", " ", p)
            p = re.sub(r"\[\\s\\-\.\]", " ", p)
            p = re.sub(r"\[(.)[^\]]*\]", r"\1", p)
            p = p.replace(".*", " … ").replace("(", "").replace(")", "").replace("|", "/")
            p = re.sub(r"\s+", " ", p).strip(" …")
            if p:
                out.append(p)
        return out
    hints: dict[str, list[str]] = {}
    for pat, code, _ in RULES:
        hints.setdefault(code, [])
        for k in clean(pat):
            if k not in hints[code]:
                hints[code].append(k)
    return {c: ", ".join(k) for c, k in hints.items()}


def suggest(account: str) -> tuple[str | None, str]:
    if account is None or (isinstance(account, float) and account != account):  # None / NaN
        return None, "no account name"
    a = str(account).strip().lower()
    for pat, code, why in RULES:
        if re.search(pat, a):
            return code, why
    return None, "no keyword matched — choose manually"
