"""
Kontrolní hlášení XML generator.

⚠️ SCHEMA VALIDATION REQUIRED BEFORE ANY REAL FILING.
Download current KH XSD from:
https://adisspr.mfcr.cz/dpr/adis/idpr_pub/epo2_info/popis_struktury_seznam.faces
"""
from decimal import Decimal

from lxml import etree


def _d(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _dic_bare(dic: str | None, country: str = "CZ") -> str:
    if not dic:
        return ""
    return dic.replace(country, "").replace("CZ", "")


def build_kh_xml(
    company_dic: str,
    company_name: str,
    vat_period: str,
    kh_data: dict,
    tax_office_code: str = "2207",
) -> bytes:
    """Build the kontrolní hlášení XML document."""
    year, month = vat_period.split("-")

    root = etree.Element("Pisemnost")
    root.set("verzeSW", "MediciAnalytica-1.0")

    kh = etree.SubElement(root, "DPHKH1")
    kh.set("k_uladis", tax_office_code)
    kh.set("rok", year)
    kh.set("mesic", month)

    veta_d = etree.SubElement(kh, "VetaD")
    veta_d.set("dic", _dic_bare(company_dic))
    veta_d.set("typ_ds", "P")  # P = právnická osoba (s.r.o.)

    # Section A1 — issued invoices with full detail (VAT >= 10 000 Kč)
    for entry in kh_data["section_a1_detail"]:
        el = etree.SubElement(kh, "VetaA1")
        el.set("c_evid_dd", entry["invoice_number"])
        el.set("dppd", entry["duzp"].strftime("%d%m%Y"))
        el.set("dic_odb", _dic_bare(entry["counterparty_dic"]))
        rate_key = "zakl_dane1" if entry["vat_rate"] == Decimal("21") else "zakl_dane2"
        tax_key  = "dan1"       if entry["vat_rate"] == Decimal("21") else "dan2"
        el.set(rate_key, _d(entry["tax_base_czk"]))
        el.set(tax_key,  _d(entry["tax_amount_czk"]))

    # Section B1 — reverse charge received (§ 92a ZDPH)
    for entry in kh_data["section_b1_detail"]:
        el = etree.SubElement(kh, "VetaB1")
        el.set("c_evid_dd", entry["invoice_number"])
        el.set("dppd", entry["duzp"].strftime("%d%m%Y"))
        el.set("dic_dod", _dic_bare(entry["counterparty_dic"]))
        rate_key = "zakl_dane1" if entry["vat_rate"] == Decimal("21") else "zakl_dane2"
        tax_key  = "dan1"       if entry["vat_rate"] == Decimal("21") else "dan2"
        el.set(rate_key, _d(entry["tax_base_czk"]))
        el.set(tax_key,  _d(entry["tax_amount_czk"]))

    # Section B2 — received invoices with full detail (VAT >= 10 000 Kč)
    for entry in kh_data["section_b2_detail"]:
        el = etree.SubElement(kh, "VetaB2")
        el.set("c_evid_dd", entry["invoice_number"])
        el.set("dppd", entry["duzp"].strftime("%d%m%Y"))
        el.set("dic_dod", _dic_bare(entry["counterparty_dic"]))
        rate_key = "zakl_dane1" if entry["vat_rate"] == Decimal("21") else "zakl_dane2"
        tax_key  = "dan1"       if entry["vat_rate"] == Decimal("21") else "dan2"
        el.set(rate_key, _d(entry["tax_base_czk"]))
        el.set(tax_key,  _d(entry["tax_amount_czk"]))

    # Section A4 — aggregate for A2/A3/A4/A5
    veta_a4 = etree.SubElement(kh, "VetaA4")
    veta_a4.set("zakl_dane1", _d(kh_data["section_a2_aggregate"]["base"]))
    veta_a4.set("dan1",       _d(kh_data["section_a2_aggregate"]["tax"]))

    # Section B3 — aggregated received invoices (< 10 000 Kč VAT)
    veta_b3 = etree.SubElement(kh, "VetaB3")
    veta_b3.set("zakl_dane1", _d(kh_data["section_b3_aggregate"]["base"]))
    veta_b3.set("dan1",       _d(kh_data["section_b3_aggregate"]["tax"]))

    return etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )
