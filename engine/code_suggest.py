"""Suggest a CIT code from an account name (EN / FR keywords).

Suggestions are never applied silently: the user confirms them on
2 · Checks & Corrections. Order matters — the first matching rule wins,
so specific rules (accumulated depreciation, goods in transit) come first.
"""
from __future__ import annotations

import re

RULES: list[tuple[str, str, str]] = [
    # (regex, code, reason)
    (r"accum|amort.*cumul|cumul.*amort|provision.*deprec|depreciation\s*reserve", "BS 1.09", "accumulated depreciation"),
    (r"^dep[\s\-.]|deprec|amortis|dotation", "PL 5.01", "depreciation charge"),
    (r"goods\s*in\s*transit|en\s*transit|work\s*in\s*progress|wip|en[\s-]cours", "BS 3.1.1.3", "work in progress / goods in transit"),
    (r"raw\s*material|mati[eè]res?\s*premi", "BS 3.1.1.2", "raw materials"),
    (r"inventor|stock|marchandise", "BS 3.1.1.4", "inventories"),
    (r"land|terrain", "BS 1.01", "land"),
    (r"building|b[aâ]timent|construction", "BS 1.02", "buildings"),
    (r"vehic|vehcle|moto|car\b|truck|v[ée]hicule", "BS 1.03", "motor vehicles"),
    (r"machin|plant|equipement industriel", "BS 1.04", "machinery"),
    (r"software|logiciel|intangible|incorporel|licen[cs]e\s*(software)?$", "BS 1.06", "intangible assets"),
    (r"furnit|fitting|mobilier|fixture", "BS 1.07", "furniture and fittings"),
    (r"computer|office\s*equip|equipment|informatique|mat[ée]riel", "BS 1.08", "other assets (equipment)"),
    (r"bank\s*charge|frais\s*bancaire|commission\s*bancaire", "PL 7.02", "bank charges"),
    (r"petty\s*cash|cash\s*in\s*hand|caisse|pettycash", "BS 3.1.3.1", "cash in hand"),
    (r"bank|banque|bk\b|equity\s*bank|momo|mobile\s*money", "BS 3.1.3.2", "bank balances"),
    (r"\bpaye\b", "BS 8.1.6", "PAYE payable"),
    (r"other\s*current\s*assets?|autres?\s*actifs?\s*courants?", "BS 3.1.4", "other current assets"),
    (r"vat\s*rec|tva\s*r[ée]cup|input\s*vat", "BS 3.3.1", "VAT receivable"),
    (r"wht|withholding|retenue", "BS 3.3.2", "WHT receivable"),
    (r"prepa|pr[ée]pay|avance.*fournisseur|charges?\s*constat", "BS 3.1.2.2", "prepayments"),
    (r"salary\s*adv|staff\s*(loan|adv)|avance.*personnel", "BS 3.2.4", "advances to staff"),
    (r"receiv|debtor|client|cr[ée]ance", "BS 3.1.2.1", "trade receivables"),
    (r"share\s*capital|capital\s*social|^capital", "BS 5.01", "share capital"),
    (r"retained|report\s*[àa]\s*nouveau|r[ée]sultat.*ant[ée]rieur|accumulated\s*(profit|loss)", "BS 5.07", "retained earnings"),
    (r"overdraft|d[ée]couvert", "BS 8.1.4", "bank overdraft"),
    (r"dividend.*pay", "BS 8.1.5", "dividends payable"),
    (r"payable.*(salary|paye|rssb|tax|vat)|(salary|paye|rssb|vat|tva).*payab|accrual|accrued|dette.*(fiscal|social)", "BS 8.1.6", "other current liabilities"),
    (r"payable|creditor|fournisseur|supplier", "BS 8.1.1", "trade payables"),
    (r"shareholder|associ[ée]|director.*(loan|account)|compte\s*courant", "BS 6.2.4", "other loans (shareholders)"),
    (r"loan|emprunt|borrow", "BS 6.2.3", "local loans"),
    (r"cost\s*of\s*(sales|goods)|cogs|purchase|achat", "PL 2.2.1", "cost of sales"),
    (r"sales|revenue|turnover|chiffre|vente|income\s*from", "PL 1.1", "revenue"),
    (r"interest\s*income|produit.*financ", "PL 8.01", "interest income"),
    (r"other\s*income|autres?\s*produits", "PL 8.14", "other income"),
    (r"rssb|pension|retirement|social\s*security|cotisation", "PL 6.06", "contribution to retirement fund"),
    (r"insurance|assurance", "PL 6.08", "insurance"),
    (r"salar|wage|staff|payroll|salaire|remun", "PL 6.01", "staff salaries"),
    (r"travel|transport|voyage|d[ée]placement", "PL 4.01", "travel"),
    (r"advert|marketing|publicit", "PL 4.02", "advertisement & marketing"),
    (r"audit", "PL 4.03", "audit expenses"),
    (r"legal|juridique|avocat|notaire", "PL 4.04", "legal expense"),
    (r"consult|honoraire", "PL 4.07", "consultancy"),
    (r"communic|telephon|internet|airtime", "PL 4.08", "communication"),
    (r"entertain|r[ée]ception", "PL 4.09", "entertainment"),
    (r"donation|don\b", "PL 4.10", "donations"),
    (r"\brent\b|loyer", "PL 4.12", "rent"),
    (r"electric", "PL 4.14", "electricity"),
    (r"water|eau\b", "PL 4.15", "water"),
    (r"utilit|gaz|gas", "PL 4.16", "other utilities"),
    (r"fuel|carburant|essence", "PL 4.17", "fuel"),
    (r"station|printing|fourniture\s*de\s*bureau", "PL 4.24", "printing & stationery"),
    (r"clean|nettoyage", "PL 4.25", "cleaning"),
    (r"security|s[ée]curit|gardiennage", "PL 4.26", "security"),
    (r"fine|penal|amende", "PL 5.10", "fines and penalties"),
    (r"trading\s*licen|patente|licence", "PL 5.07", "licence fees"),
    (r"interest|int[ée]r[eê]t", "PL 7.01", "interest expense"),
    (r"exchange\s*loss|perte\s*de\s*change", "PL 7.05", "exchange loss"),
    (r"exchange\s*gain|gain\s*de\s*change", "PL 8.04", "exchange gain"),
    (r"repair|maint|entretien", "PL 4.27", "other operating expenses (repairs)"),
    (r"expense|charge|frais|cost", "PL 4.27", "other operating expenses"),
]


def suggest(account: str) -> tuple[str | None, str]:
    if account is None or (isinstance(account, float) and account != account):  # None / NaN
        return None, "no account name"
    a = str(account).strip().lower()
    for pat, code, why in RULES:
        if re.search(pat, a):
            return code, why
    return None, "no keyword matched — choose manually"
