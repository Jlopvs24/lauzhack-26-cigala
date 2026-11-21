"""Render DocContent to a one-page A4 PDF with reportlab (text layer included)."""
from __future__ import annotations

import random

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .content import DocContent, ZIP
from .i18n import MONTHS, label

W, H = A4
FONTS = [("Helvetica", "Helvetica-Bold"), ("Times-Roman", "Times-Bold"), ("Courier", "Courier-Bold")]


def fmt_money(x: float, style: str) -> str:
    s = f"{abs(x):,.2f}"  # 1,234.50
    if style == "apos":
        s = s.replace(",", "'")
    elif style == "space_comma":
        s = s.replace(",", " ").replace(".", ",")
    elif style == "plain":
        s = s.replace(",", "")
    return ("-" if x < 0 else "") + s


def money_style(lang: str, rng: random.Random) -> str:
    return {"de": "apos", "it": "apos", "fr": rng.choice(["apos", "space_comma"]),
            "en": rng.choice(["comma_dot", "apos", "plain"])}[lang]


def fmt_date(y: int, m: int, d: int, lang: str, style: int) -> str:
    if style == 0:
        return f"{d:02d}.{m:02d}.{y}"
    if style == 1:
        return f"{d} {MONTHS[lang][m - 1]} {y}"
    return f"{y}-{m:02d}-{d:02d}"


class Doc:
    def __init__(self, path, c: DocContent, rng: random.Random):
        self.cv = canvas.Canvas(str(path), pagesize=A4)
        self.c, self.rng, self.lang = c, rng, c.lang
        self.font, self.bold = rng.choice(FONTS[:2]) if rng.random() < 0.85 else FONTS[2]
        self.ms = money_style(c.lang, rng)
        self.ds = rng.randint(0, 2)
        self.cur = rng.choice(["CHF ", "Fr. ", ""]) if c.lang != "en" else rng.choice(["CHF ", ""])
        self.x0 = rng.randint(50, 70)
        self.y = H - rng.randint(50, 75)

    def m(self, x):
        return f"{self.cur}{fmt_money(x, self.ms)}"

    def d(self, y, mo, da):
        return fmt_date(y, mo, da, self.lang, self.ds)

    def text(self, s, x=None, size=10, bold=False, dy=14):
        self.cv.setFont(self.bold if bold else self.font, size)
        self.cv.drawString(self.x0 if x is None else x, self.y, s)
        self.y -= dy

    def row(self, left, right, size=10, bold=False, dy=15, xr=None):
        self.cv.setFont(self.bold if bold else self.font, size)
        self.cv.drawString(self.x0, self.y, left)
        self.cv.drawRightString(xr or W - self.x0, self.y, right)
        self.y -= dy

    def rule(self, dy=10):
        self.cv.setLineWidth(0.6)
        self.cv.line(self.x0, self.y + 9, W - self.x0, self.y + 9)
        self.y -= dy - 10 + 4

    def save(self):
        self.cv.showPage()
        self.cv.save()


def render(c: DocContent, path, rng: random.Random):
    {"payslip": _payslip, "bank_statement": _bank, "rental_contract": _lease}[c.doc_type](Doc(path, c, rng))


def _addr_block(doc: Doc, x, lines):
    y0 = doc.y
    for ln in lines:
        doc.text(ln, x=x, size=10)
    return y0


def _payslip(doc: Doc):
    c, rng, lg = doc.c, doc.rng, doc.lang
    p, dt = c.person, c.data
    title_key = {"salary": "payslip_title", "pension": "pension_title", "unemployment": "unemployment_title"}[dt["kind"]]
    doc.text(dt["issuer"], size=13, bold=True, dy=14)
    doc.text(f"{rng.choice(['Postfach', 'Case postale', 'Casella postale'])} {rng.randint(10, 999)}, {rng.choice(list(ZIP.values()))}", size=9, dy=40)
    y_top = doc.y
    doc.y = y_top
    for ln in [p.full_name, p.street, f"{p.zip} {p.city}"]:
        doc.text(ln, x=W - 230, size=10)
    doc.y -= 25
    doc.text(f"{label(title_key, lg, rng)}  {MONTHS[lg][11]} 2024", size=15, bold=True, dy=22)
    who = "beneficiary" if dt["kind"] != "salary" else "employee"
    doc.row(f"{label(who, lg)}: {p.full_name}", f"{label('period', lg)}: {doc.d(2024, 12, 1)} - {doc.d(2024, 12, 31)}", size=9)
    doc.row(f"{label('employee_no', lg)}: {dt['staff_no']}", f"{label('ahv_no', lg)}: {dt['ahv']}", size=9, dy=24)
    gkey = {"salary": "gross", "pension": "pension_gross", "unemployment": "benefit_gross"}[dt["kind"]]
    if dt["kind"] == "salary" and rng.random() < 0.5:
        doc.row(label("base", lg), doc.m(dt["gross"]))
    doc.row(label(gkey, lg), doc.m(dt["gross"]), bold=True)
    doc.rule(16)
    for k, v in dt["lines"]:
        doc.row(f"  {label(k, lg)}", doc.m(-v))
    if dt["lines"]:
        doc.rule(16)
        doc.row(label("deductions", lg), doc.m(-dt["deductions"]))
    doc.y -= 8
    doc.row(label("net", lg, rng), doc.m(dt["net"]), size=12, bold=True, dy=30)
    doc.text(f"{label('paid_to', lg)}: {dt['iban']}", size=9)
    doc.save()


def _bank(doc: Doc):
    c, rng, lg = doc.c, doc.rng, doc.lang
    p, dt = c.person, c.data
    doc.text(dt["bank"], size=14, bold=True, dy=40)
    for ln in [p.full_name, p.street, f"{p.zip} {p.city}"]:
        doc.text(ln, x=W - 230, size=10)
    doc.y -= 20
    doc.text(f"{label('bank_title', lg, rng)}  {doc.d(2024, 12, 1)} - {doc.d(2024, 12, 31)}", size=14, bold=True, dy=20)
    doc.text(f"{label('holder', lg)}: {p.full_name}", size=9, dy=12)
    doc.text(f"{label('iban', lg)}: {dt['iban']}   CHF", size=9, dy=22)
    cols = [doc.x0, doc.x0 + 70, W - doc.x0 - 190, W - doc.x0 - 110, W - doc.x0]
    cv = doc.cv
    cv.setFont(doc.bold, 9)
    cv.drawString(cols[0], doc.y, label("date", lg))
    cv.drawString(cols[1], doc.y, label("text", lg))
    for i, k in enumerate(["debit", "credit", "balance"]):
        cv.drawRightString(cols[2 + i], doc.y, label(k, lg))
    doc.y -= 6
    doc.rule(14)
    plain = lambda x: fmt_money(x, doc.ms)
    cv.setFont(doc.font, 9)
    cv.drawString(cols[1], doc.y, label("opening", lg))
    cv.drawRightString(cols[4], doc.y, plain(dt["opening"]))
    doc.y -= 14
    mname = MONTHS[lg][11]
    for r in dt["rows"]:
        k = r["key"]
        txt = label(k, lg).format(m=mname, ll=r["landlord"])
        if r["detail"]:
            txt += f" {r['detail']}"
        cv.setFont(doc.font, 9)
        cv.drawString(cols[0], doc.y, fmt_date(2024, 12, r["day"], lg, 0 if doc.ds == 1 else doc.ds))
        cv.drawString(cols[1], doc.y, txt[:48])
        cv.drawRightString(cols[2] if r["dir"] == "debit" else cols[3], doc.y, plain(r["amount"]))
        cv.drawRightString(cols[4], doc.y, plain(r["balance"]))
        doc.y -= 14
    doc.rule(16)
    cv.setFont(doc.bold, 10)
    cv.drawString(cols[1], doc.y, f"{label('closing', lg)} {doc.d(2024, 12, 31)}")
    cv.drawRightString(cols[4], doc.y, plain(dt["closing"]))
    doc.save()


def _lease(doc: Doc):
    c, rng, lg = doc.c, doc.rng, doc.lang
    p, dt = c.person, c.data
    doc.text(label("lease_title", lg, rng), size=15, bold=True, dy=30)
    doc.text(f"{label('landlord', lg)}:", bold=True, dy=13)
    doc.text(dt["landlord"], dy=22)
    doc.text(f"{label('tenant', lg)}:", bold=True, dy=13)
    doc.text(f"{p.full_name}, {p.street}, {p.zip} {p.city}", dy=22)
    doc.text(f"{label('object', lg)}:", bold=True, dy=13)
    doc.text(f"{label('rooms', lg).format(n=dt['rooms'], f=dt['floor'])}, {p.street}, {p.zip} {p.city}", dy=22)
    y, m, d = map(int, dt["start"].split("-"))
    doc.text(f"{label('start', lg)}: {doc.d(y, m, d)}", dy=13)
    doc.text(label("notice", lg), dy=26)
    doc.row(label("rent_net", lg), doc.m(dt["net_rent"]), xr=W - 150)
    doc.row(label("charges", lg), doc.m(dt["charges"]), xr=W - 150)
    if dt["parking"]:
        doc.row(label("parking", lg), doc.m(dt["parking"]), xr=W - 150)
    doc.rule(16)
    doc.row(label("rent_total", lg), doc.m(dt["total"]), bold=True, xr=W - 150, dy=22)
    doc.text(label("payable", lg), size=9, dy=22)
    doc.row(label("deposit", lg), doc.m(dt["deposit"]), xr=W - 150, dy=60)
    doc.text(label("signatures", lg), size=9, dy=40)
    doc.cv.line(doc.x0, doc.y + 20, doc.x0 + 180, doc.y + 20)
    doc.cv.line(W - doc.x0 - 180, doc.y + 20, W - doc.x0, doc.y + 20)
    doc.save()
