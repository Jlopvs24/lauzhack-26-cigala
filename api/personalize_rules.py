"""Deterministic fast path for /tree/personalize (no LLM, ~ms). EN / ES / FR / DE.

Covers the common shapes:
- an amount + period + what it is: scholarship / grant / job / salary / help from family / allowance (income),
  rent (new total), extra costs, a one-off gift / inheritance / purchase;
- "<N>% job" with an amount;
- moving to a Swiss city / canton / another country; getting married / having children (tax household);
- gross salaries ("gross", "brut", "bruto", "brutto").
Windows: "during the master's / while studying" = the branch's study window, "after the master's" = from its end,
"for N years|months", "next year". Anything else returns None and the LLM parser takes over.
Returns {"interventions": [...], "label", "mode"} or {"missing": "amount"} (a money condition without an amount).
"""
from __future__ import annotations

import re

_CUR = r"(?:chf|fr\.?|francs?|francos?|franken|sfr\.?|€|eur(?:os?)?)"
_NUM = r"(\d{1,3}(?:[ '’ ,.]\d{3})+|\d+(?:[.,]\d+)?)\s*(k\b)?"
AMOUNT = re.compile(rf"(?:{_CUR}\s*)?{_NUM}\s*{_CUR}?", re.I)
PER_MONTH = re.compile(r"/\s*(?:month|mo|mois|mes|monat)\b|\b(?:a|per|each|every)\s+month\b|\bmonthly\b|"
                       r"\b(?:al|por|cada|el)\s+mes\b|\bmensual(?:es|mente)?\b|\bpar\s+mois\b|\bmensuel(?:le)?s?\b|"
                       r"\bpro\s+monat\b|\bim\s+monat\b|\bmonatlich\b|\bjeden\s+monat\b", re.I)
PER_YEAR = re.compile(r"/\s*(?:year|yr|an|año|jahr)\b|\b(?:a|per|each|every)\s+year\b|\byearly\b|\bannual(?:ly)?\b|"
                      r"\b(?:al|por)\s+año\b|\banual(?:es)?\b|\bpar\s+an\b|\bannuel(?:le)?\b|\bpro\s+jahr\b|"
                      r"\bim\s+jahr\b|\bjährlich\b", re.I)
GROSS = re.compile(r"\b(?:gross|brut|brute|bruto|brutto)\b", re.I)

INCOME = {
    "scholarship": (r"scholarship|grant|bursary|stipend|beca|bourse|stipendium", "Scholarship"),
    "family": (r"parents|family|mum|mom|dad|grandma|grandpa|padres|familia|abuel[ao]s?|famille|grand-?m[eè]re|"
               r"eltern|familie|oma|opa", "Help from family"),
    "job": (r"(?:part-?time\s+)?job|work(?:ing)?|salary|earn|wage|trabajo|trabajar|sueldo|salario|ganar[ií]a|"
            r"emploi|travail(?:ler)?|salaire|gagner(?:ais)?|stelle|arbeit(?:en)?|gehalt|lohn|verdienen|verdiene", "Job"),
    "allowance": (r"allowance|pension|benefit|subsid[yio]|ayuda|aide|allocation|zuschuss|unterstützung", "Allowance"),
}
RENT = re.compile(r"\b(?:rent|flat|apartment|studio|room|alquiler|piso|habitaci[oó]n|loyer|colocation|appartement|"
                  r"chambre|miete|wohnung|zimmer|wg)\b", re.I)
COSTS = re.compile(r"\b(?:costs?|expenses?|spend(?:ing)?|gastos?|gastar[ií]a|d[eé]penses?|ausgaben|kosten)\b", re.I)
GIFT = re.compile(r"\b(?:gift|inherit(?:ance)?|give me|regalo|herencia|darían|daría|cadeau|h[eé]ritage|donner(?:aient)?|"
                  r"geschenk|erbe|erbschaft|schenken)\b", re.I)
PURCHASE = re.compile(r"\b(?:buy|purchase|car|laptop|trip|comprar[ií]a|compra|coche|viaje|acheter|ach[eè]terais|"
                      r"voiture|voyage|kaufen|kaufe|auto|reise)\b", re.I)
PERCENT_JOB = re.compile(r"(\d{1,3})\s*%\s*(?:job|work|position|trabajo|jornada|emploi|travail|poste|stelle|pensum|job)",
                         re.I)
MARRIED = re.compile(r"\b(?:get married|marry|married|wedding|casarme|me caso|casad[oa]|boda|me marier|mari[ée]e?|"
                     r"mariage|heiraten|heirate|verheiratet|hochzeit)\b", re.I)
KIDS = re.compile(r"\b(?:kids?|child(?:ren)?|baby|hijos?|beb[eé]|enfants?|b[eé]b[eé]|kinder|kind|baby)\b", re.I)
MOVE = re.compile(r"\b(?:move|moving|relocate|live|mudar(?:me|ía)?|irme|ir[ií]a|vivir|d[eé]m[eé]nager|"
                  r"d[eé]m[eé]nagerais|habiter|vivre|ziehen|umziehen|wohnen|leben)\b", re.I)
# Only an explicit alternative makes a new branch; "instead of the studio" replaces something on this branch.
INSTEAD = re.compile(r"\b(?:another option|other option|as an option|alternative|compare|otra opci[oó]n|"
                     r"como opci[oó]n|alternativa|autre option|comme option|andere option|als option)\b", re.I)
DURING = re.compile(r"\b(?:during|while)\b.{0,20}\b(?:master|study|studies|studying)|durante (?:el )?m[aá]ster|"
                    r"mientras estudi|pendant (?:le |mon )?master|pendant mes [eé]tudes|w[äa]hrend (?:des |dem |meines )?"
                    r"(?:master|studium)", re.I)
AFTER = re.compile(r"\bafter (?:the |my )?(?:master|studies|graduat)|despu[eé]s del m[aá]ster|al terminar|"
                   r"apr[eè]s (?:le |mon )?master|apr[eè]s mes [eé]tudes|nach dem (?:master|studium)", re.I)
FOR_N = re.compile(r"\b(?:for|durante|pendant|f[üu]r)\s+(\d+|one|two|three|four|five|un|una|uno|dos|tres|cuatro|"
                   r"cinco|deux|trois|quatre|cinq|ein|eins|zwei|drei|vier|f[üu]nf)\s+(years?|months?|años?|meses|"
                   r"ans?|ann[ée]es?|mois|jahre?n?|monate?n?)", re.I)
NEXT_YEAR = re.compile(r"next year|in a year|año que viene|pr[oó]ximo año|l'ann[ée]e prochaine|l'an prochain|"
                       r"dans un an|n[äa]chste[smnr]? jahr|in einem jahr", re.I)
_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3,
            "cuatro": 4, "cinco": 5, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "ein": 1, "eins": 1, "zwei": 2,
            "drei": 3, "vier": 4, "fünf": 5, "funf": 5}

CITIES = {  # name variants -> (canonical city, canton)
    "lausanne": ("Lausanne", "VD"), "zurich": ("Zurich", "ZH"), "zürich": ("Zurich", "ZH"), "zurique": ("Zurich", "ZH"),
    "geneva": ("Geneva", "GE"), "genève": ("Geneva", "GE"), "geneve": ("Geneva", "GE"), "genf": ("Geneva", "GE"),
    "ginebra": ("Geneva", "GE"), "bern": ("Bern", "BE"), "berne": ("Bern", "BE"), "berna": ("Bern", "BE"),
    "biel": ("Biel", "BE"), "bienne": ("Biel", "BE"), "basel": ("Basel", "BS"), "bâle": ("Basel", "BS"),
    "bale": ("Basel", "BS"), "basilea": ("Basel", "BS"), "fribourg": ("Fribourg", "FR"), "freiburg": ("Fribourg", "FR"),
    "neuchatel": ("Neuchatel", "NE"), "neuchâtel": ("Neuchatel", "NE"), "st gallen": ("St Gallen", "SG"),
    "st. gallen": ("St Gallen", "SG"), "saint-gall": ("St Gallen", "SG"), "lugano": ("Lugano", "TI"),
    "lucerne": ("Lucerne", "LU"), "luzern": ("Lucerne", "LU"), "lucerna": ("Lucerne", "LU"),
    "winterthur": ("Winterthur", "ZH"),
}
COUNTRIES = {
    "germany": "DE", "alemania": "DE", "allemagne": "DE", "deutschland": "DE", "france": "FR", "francia": "FR",
    "frankreich": "FR", "italy": "IT", "italia": "IT", "italie": "IT", "italien": "IT", "spain": "ES",
    "españa": "ES", "espana": "ES", "espagne": "ES", "spanien": "ES", "austria": "AT", "autriche": "AT",
    "österreich": "AT", "portugal": "PT", "netherlands": "NL", "holland": "NL", "países bajos": "NL",
    "pays-bas": "NL", "niederlande": "NL", "uk": "GB", "england": "GB", "london": "GB", "londres": "GB",
    "london": "GB", "belgium": "BE", "bélgica": "BE", "belgique": "BE", "belgien": "BE",
}


def _num(tok: str, k: str | None) -> float:
    t = tok.strip()
    if re.fullmatch(r"\d{1,3}(?:[ '’ ,.]\d{3})+", t):
        v = float(re.sub(r"[ '’ ,.]", "", t))
    else:
        v = float(t.replace(",", "."))
    return v * 1000 if k else v


def _amounts(text: str) -> list[float]:
    out = []
    for m in AMOUNT.finditer(text):
        whole = m.group(0)
        # skip percentages and small counts that are durations ("2 years", "60%")
        tail = text[m.end():m.end() + 8].lower()
        if tail.lstrip().startswith("%"):
            continue
        v = _num(m.group(1), m.group(2))
        has_cur = re.search(_CUR, whole, re.I) is not None
        if re.match(r"\s*(?:years?|months?|años?|meses|ans?|ann[ée]es?|mois|jahre?n?|monate?n?)\b", tail) and not has_cur:
            continue
        if v < 10 and not has_cur:
            continue
        out.append(v)
    return out


def _study_window(ctx: dict) -> tuple[int, int] | None:
    """The branch's own income window that ends before the horizon (e.g. the master's months 0-24)."""
    H = ctx["horizon_months"]
    ivs = ctx["node"]["interventions"] + [iv for c in ctx.get("path_above", []) for iv in c["interventions"]]
    for iv in ivs:
        if iv.get("param") in ("monthly_net_income", "monthly_rent", "monthly_other_expenses") \
                and isinstance(iv.get("to_month"), int) and 0 < iv["to_month"] < H:
            return int(iv.get("from_month") or 0), int(iv["to_month"])
    return None


def _window(text: str, ctx: dict, kind: str) -> tuple[int, int]:
    H = ctx["horizon_months"]
    study = _study_window(ctx)
    m = FOR_N.search(text)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _WORDNUM.get(m.group(1).lower(), 1)
        unit = m.group(2).lower()
        months = n if unit.startswith(("month", "mes", "mois", "monat")) else n * 12
        start = 12 if NEXT_YEAR.search(text) else 0
        return start, min(H, start + months)
    if AFTER.search(text) and study:
        return study[1], H
    if DURING.search(text) and study:
        return study
    if NEXT_YEAR.search(text):
        return 12, H
    if kind == "scholarship" and study:  # a scholarship lasts the studies by default
        return study
    return 0, H


def _place(text: str) -> dict | None:
    low = text.lower()
    for name in sorted(CITIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", low):
            city, canton = CITIES[name]
            return {"city": city, "canton": canton}
    for name in sorted(COUNTRIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", low):
            return {"country": COUNTRIES[name]}
    return None


def parse(text: str, ctx: dict) -> dict | None:
    """Return {"interventions", "label", "mode"} for a recognised shape, {"missing": "amount", "kind"} for a
    money condition without an amount, or None (not recognised: use the LLM)."""
    t = " " + (text or "").strip() + " "
    H = ctx["horizon_months"]
    mode = "new_branch" if INSTEAD.search(t) else "patch"
    amounts = _amounts(t)
    first_month = 12 if NEXT_YEAR.search(t) else 0

    # 1. tax residence: moving / getting married / children (no amount needed)
    place = _place(t) if MOVE.search(t) else None
    household = "family" if (MARRIED.search(t) and KIDS.search(t)) else ("couple" if MARRIED.search(t) else None)
    if (place or household) and not amounts:
        start = _window(t, ctx, "move")[0] if (AFTER.search(t) or NEXT_YEAR.search(t)) else first_month
        iv = {"param": "tax_residence", "from_month": start, **(place or {})}
        if household:
            iv["household"] = household
        where = place.get("city") or place.get("country") if place else None
        label = (f"Move to {where}" if where else "") + (" and " if where and household else "") + \
                ({"couple": "Married", "family": "Married with children"}.get(household, "") if household else "")
        iv["label"] = label
        return {"interventions": [iv], "label": label, "mode": mode}

    # 2. what kind of money
    kind = next((k for k, (pat, _) in INCOME.items() if re.search(rf"\b(?:{pat})\b", t, re.I)), None)
    is_rent, is_costs = bool(RENT.search(t)), bool(COSTS.search(t))
    is_gift, is_purchase = bool(GIFT.search(t)), bool(PURCHASE.search(t))
    monthly, yearly = bool(PER_MONTH.search(t)), bool(PER_YEAR.search(t))
    money_kind = kind or is_rent or is_costs or is_gift or is_purchase
    if not money_kind:
        return None
    if not amounts:
        return {"missing": "amount", "kind": kind or ("rent" if is_rent else "money")}
    if len(amounts) > 1 and not PERCENT_JOB.search(t):
        return None  # several amounts: let the LLM sort them out
    v = amounts[0]

    # 3. one-off gift / purchase (no period)
    if not monthly and not yearly and (is_gift or is_purchase) and kind in (None, "family"):
        param = "one_off_cost" if is_purchase and not is_gift else "one_off_income"
        label = "Purchase" if param == "one_off_cost" else "Gift"
        return {"interventions": [{"param": param, "month": first_month, "value": v, "label": label}],
                "label": label, "mode": mode}
    if not monthly and not yearly:
        return None  # an amount without a period for a recurring item: ambiguous, LLM
    per_month = round(v / 12, 2) if yearly and not monthly else v

    # 4. rent (new total) / extra costs
    if is_rent and kind is None:
        fm, tm = _window(t, ctx, "rent")
        return {"interventions": [{"param": "monthly_rent", "op": "set", "value": per_month, "from_month": fm,
                                   "to_month": tm, "label": "Rent"}], "label": "New rent", "mode": mode}
    if is_costs and kind is None:
        fm, tm = _window(t, ctx, "costs")
        return {"interventions": [{"param": "monthly_other_expenses", "op": "add", "value": per_month,
                                   "from_month": fm, "to_month": tm, "label": "Extra costs"}],
                "label": "Extra costs", "mode": mode}

    # 5. income: scholarship / family / job / allowance, gross or net
    fm, tm = _window(t, ctx, kind or "job")
    label = INCOME.get(kind or "job")[1]
    pj = PERCENT_JOB.search(t)
    if pj:
        label = f"{pj.group(1)}% job"
    if GROSS.search(t) and kind == "job":
        return {"interventions": [{"param": "monthly_gross_income", "op": "set", "value": per_month,
                                   "from_month": fm, "to_month": tm, "label": f"{label} (gross)"}],
                "label": f"{label} (gross)", "mode": mode}
    return {"interventions": [{"param": "monthly_net_income", "op": "add", "value": per_month, "from_month": fm,
                               "to_month": tm, "label": label}], "label": label, "mode": mode}
