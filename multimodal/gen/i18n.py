"""Labels for synthetic Swiss documents in FR / DE / IT / EN.

Our own wording (not copied from any kit or real document). Each document type
has several title variants so templates are not trivially identical.
"""

LANG_BY_CANTON = {
    "VD": "fr", "GE": "fr", "NE": "fr", "FR": "fr", "VS": "fr", "JU": "fr",
    "ZH": "de", "BE": "de", "BS": "de", "LU": "de", "SG": "de", "AG": "de",
    "TI": "it",
}

MONTHS = {
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
           "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}

L = {
    # ---------------- payslip ----------------
    "payslip_title": {
        "fr": ["Fiche de salaire", "Décompte de salaire", "Bulletin de salaire"],
        "de": ["Lohnabrechnung", "Gehaltsabrechnung", "Lohnausweis Monat"],
        "it": ["Conteggio salariale", "Busta paga", "Distinta salario"],
        "en": ["Payslip", "Salary statement", "Pay statement"],
    },
    "pension_title": {
        "fr": ["Attestation de rente mensuelle", "Décompte de rente"],
        "de": ["Rentenabrechnung", "Monatliche Rentenbescheinigung"],
        "it": ["Conteggio della rendita", "Attestazione rendita mensile"],
        "en": ["Pension statement", "Monthly pension advice"],
    },
    "unemployment_title": {
        "fr": ["Décompte d'indemnités de chômage"],
        "de": ["Abrechnung Arbeitslosenentschädigung"],
        "it": ["Conteggio indennità di disoccupazione"],
        "en": ["Unemployment benefit statement"],
    },
    "period": {"fr": "Période", "de": "Periode", "it": "Periodo", "en": "Period"},
    "employee": {"fr": "Collaborateur/trice", "de": "Mitarbeiter/in", "it": "Collaboratore/trice", "en": "Employee"},
    "beneficiary": {"fr": "Bénéficiaire", "de": "Begünstigte/r", "it": "Beneficiario/a", "en": "Beneficiary"},
    "employee_no": {"fr": "N° personnel", "de": "Personal-Nr.", "it": "N. personale", "en": "Staff no."},
    "ahv_no": {"fr": "N° AVS", "de": "AHV-Nr.", "it": "N. AVS", "en": "AHV no."},
    "gross": {"fr": "Salaire brut", "de": "Bruttolohn", "it": "Salario lordo", "en": "Gross salary"},
    "base": {"fr": "Salaire de base", "de": "Grundlohn", "it": "Salario di base", "en": "Base salary"},
    "pension_gross": {"fr": "Rente brute", "de": "Bruttorente", "it": "Rendita lorda", "en": "Gross pension"},
    "benefit_gross": {"fr": "Indemnité brute", "de": "Bruttoentschädigung", "it": "Indennità lorda", "en": "Gross benefit"},
    "ahv": {"fr": "AVS/AI/APG", "de": "AHV/IV/EO", "it": "AVS/AI/IPG", "en": "AHV/IV/EO"},
    "alv": {"fr": "AC", "de": "ALV", "it": "AD", "en": "ALV (unemployment ins.)"},
    "nbu": {"fr": "AANP", "de": "NBU", "it": "AINP", "en": "NBU (accident ins.)"},
    "bvg": {"fr": "LPP", "de": "BVG / Pensionskasse", "it": "LPP", "en": "BVG pension fund"},
    "tax": {"fr": "Impôt à la source", "de": "Quellensteuer", "it": "Imposta alla fonte", "en": "Withholding tax"},
    "deductions": {"fr": "Total déductions", "de": "Total Abzüge", "it": "Totale deduzioni", "en": "Total deductions"},
    "net": {
        "fr": ["Salaire net", "Net à payer", "Montant versé"],
        "de": ["Nettolohn", "Auszahlung", "Auszahlungsbetrag"],
        "it": ["Salario netto", "Importo versato", "Netto da pagare"],
        "en": ["Net pay", "Net salary", "Amount paid"],
    },
    "paid_to": {"fr": "Versé sur le compte", "de": "Überwiesen auf Konto", "it": "Versato sul conto", "en": "Paid to account"},
    # ---------------- bank statement ----------------
    "bank_title": {
        "fr": ["Relevé de compte", "Extrait de compte privé"],
        "de": ["Kontoauszug", "Auszug Privatkonto"],
        "it": ["Estratto conto", "Estratto conto privato"],
        "en": ["Account statement", "Bank statement"],
    },
    "holder": {"fr": "Titulaire", "de": "Kontoinhaber/in", "it": "Titolare", "en": "Account holder"},
    "iban": {"fr": "IBAN", "de": "IBAN", "it": "IBAN", "en": "IBAN"},
    "opening": {"fr": "Solde initial", "de": "Anfangssaldo", "it": "Saldo iniziale", "en": "Opening balance"},
    "closing": {"fr": "Solde final", "de": "Schlusssaldo", "it": "Saldo finale", "en": "Closing balance"},
    "date": {"fr": "Date", "de": "Datum", "it": "Data", "en": "Date"},
    "text": {"fr": "Libellé", "de": "Buchungstext", "it": "Descrizione", "en": "Description"},
    "debit": {"fr": "Débit", "de": "Belastung", "it": "Addebito", "en": "Debit"},
    "credit": {"fr": "Crédit", "de": "Gutschrift", "it": "Accredito", "en": "Credit"},
    "balance": {"fr": "Solde", "de": "Saldo", "it": "Saldo", "en": "Balance"},
    "tx_salary": {"fr": "Salaire {m}", "de": "Lohn {m}", "it": "Stipendio {m}", "en": "Salary {m}"},
    "tx_pension": {"fr": "Rente AVS {m}", "de": "AHV-Rente {m}", "it": "Rendita AVS {m}", "en": "AHV pension {m}"},
    "tx_benefit": {"fr": "Caisse de chômage", "de": "Arbeitslosenkasse", "it": "Cassa disoccupazione", "en": "Unemployment fund"},
    "tx_rent": {"fr": "Loyer {m} - {ll}", "de": "Miete {m} - {ll}", "it": "Affitto {m} - {ll}", "en": "Rent {m} - {ll}"},
    "tx_insurance": {"fr": "Prime assurance maladie", "de": "Krankenkassenprämie", "it": "Premio cassa malati", "en": "Health insurance premium"},
    "tx_card": {"fr": "Achat carte", "de": "Kartenzahlung", "it": "Pagamento carta", "en": "Card payment"},
    "tx_atm": {"fr": "Retrait Bancomat", "de": "Bancomat Bezug", "it": "Prelievo Bancomat", "en": "ATM withdrawal"},
    "tx_phone": {"fr": "Abonnement mobile", "de": "Handy-Abo", "it": "Abbonamento mobile", "en": "Mobile plan"},
    "tx_transport": {"fr": "Abonnement transports", "de": "ÖV-Abo", "it": "Abbonamento trasporti", "en": "Transit pass"},
    "tx_twint": {"fr": "TWINT envoi", "de": "TWINT Zahlung", "it": "TWINT pagamento", "en": "TWINT payment"},
    # ---------------- rental contract ----------------
    "lease_title": {
        "fr": ["Bail à loyer pour locaux d'habitation", "Contrat de bail à loyer"],
        "de": ["Mietvertrag für Wohnräume", "Mietvertrag"],
        "it": ["Contratto di locazione per locali d'abitazione", "Contratto di locazione"],
        "en": ["Residential tenancy agreement", "Lease agreement"],
    },
    "landlord": {"fr": "Bailleur", "de": "Vermieter/in", "it": "Locatore", "en": "Landlord"},
    "tenant": {"fr": "Locataire", "de": "Mieter/in", "it": "Conduttore", "en": "Tenant"},
    "object": {"fr": "Objet loué", "de": "Mietobjekt", "it": "Oggetto locato", "en": "Rented property"},
    "rooms": {"fr": "{n} pièces, {f}e étage", "de": "{n}-Zimmerwohnung, {f}. Stock", "it": "{n} locali, {f}° piano", "en": "{n}-room flat, floor {f}"},
    "start": {"fr": "Début du bail", "de": "Mietbeginn", "it": "Inizio locazione", "en": "Lease start"},
    "notice": {"fr": "Délai de résiliation: 3 mois", "de": "Kündigungsfrist: 3 Monate", "it": "Termine di disdetta: 3 mesi", "en": "Notice period: 3 months"},
    "rent_net": {"fr": "Loyer net mensuel", "de": "Nettomietzins monatlich", "it": "Pigione netta mensile", "en": "Net monthly rent"},
    "charges": {"fr": "Acompte de charges", "de": "Akonto Nebenkosten", "it": "Acconto spese accessorie", "en": "Service charges (advance)"},
    "parking": {"fr": "Place de parc", "de": "Parkplatz", "it": "Posteggio", "en": "Parking space"},
    "rent_total": {"fr": "Loyer mensuel total", "de": "Bruttomietzins total", "it": "Pigione mensile totale", "en": "Total monthly rent"},
    "deposit": {"fr": "Garantie de loyer", "de": "Mietzinskaution", "it": "Deposito di garanzia", "en": "Security deposit"},
    "payable": {"fr": "Payable d'avance le 1er de chaque mois.", "de": "Zahlbar monatlich im Voraus auf den Ersten.",
                "it": "Pagabile anticipatamente il 1° di ogni mese.", "en": "Payable monthly in advance on the 1st."},
    "signatures": {"fr": "Lieu, date et signatures", "de": "Ort, Datum und Unterschriften", "it": "Luogo, data e firme", "en": "Place, date and signatures"},
}


def label(key: str, lang: str, rng=None) -> str:
    v = L[key][lang]
    if isinstance(v, list):
        return v[0] if rng is None else rng.choice(v)
    return v
