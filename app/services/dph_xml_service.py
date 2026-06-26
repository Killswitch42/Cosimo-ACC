"""
DPH přiznání XML generator — format DPHDP3.

⚠️ SCHEMA VALIDATION REQUIRED BEFORE ANY REAL FILING.
The element names used here follow the publicly documented DPHDP3 structure
(stable since 2011 per Finanční správa). Before first production use:
  1. Download current XSD from https://adisspr.mfcr.cz (Dokumentace →
     Struktury XML souborů EPO → DPH přiznání)
  2. Validate generated XML with lxml.etree.XMLSchema against that XSD
  3. Fix any tag name / namespace mismatches found
"""
import hashlib
from decimal import Decimal

from lxml import etree


def _d(value: Decimal) -> str:
    """Format Decimal as Czech tax XML string (no thousands separator)."""
    return str(value.quantize(Decimal("0.01")))


def build_dph_priznani_xml(
    company_dic: str,
    company_name: str,
    vat_period: str,
    priznani_data: dict,
    tax_office_code: str = "2207",
    is_quarterly: bool = False,
) -> bytes:
    """
    Build the DPH přiznání XML document.
    Returns UTF-8 encoded XML bytes.

    ⚠️ Verify element names against live XSD before filing.
    """
    year, month = vat_period.split("-")
    dic_bare = company_dic.replace("CZ", "") if company_dic else ""

    root = etree.Element("Pisemnost")
    root.set("verzeSW", "MediciAnalytica-1.0")

    dphdp3 = etree.SubElement(root, "DPHDP3")
    dphdp3.set("verzePis", "01")
    dphdp3.set("k_uladis", tax_office_code)
    dphdp3.set("rok", year)
    if is_quarterly:
        quarter = str((int(month) - 1) // 3 + 1)
        dphdp3.set("ctvrtleti", quarter)
    else:
        dphdp3.set("mesic", month)

    veta_d = etree.SubElement(dphdp3, "VetaD")
    veta_d.set("dic", dic_bare)

    veta_p = etree.SubElement(dphdp3, "VetaP")
    veta_p.set("naz_obch", company_name)

    veta_pdph = etree.SubElement(dphdp3, "VetaPDPH")
    veta_pdph.set("R1_zd",   _d(priznani_data["row_01_base"]))
    veta_pdph.set("R1_dan",  _d(priznani_data["row_01_tax"]))
    veta_pdph.set("R2_zd",   _d(priznani_data["row_02_base"]))
    veta_pdph.set("R2_dan",  _d(priznani_data["row_02_tax"]))
    veta_pdph.set("R40_zd",  _d(priznani_data["row_40_base"]))
    veta_pdph.set("R40_odp", _d(priznani_data["row_40_tax"]))
    veta_pdph.set("R41_zd",  _d(priznani_data["row_41_base"]))
    veta_pdph.set("R41_odp", _d(priznani_data["row_41_tax"]))
    veta_pdph.set("R63",     _d(priznani_data["row_63_total_output_tax"]))
    veta_pdph.set("R64",     _d(priznani_data["row_64_total_input_tax"]))

    net_vat = priznani_data["row_65_net_vat"]
    if priznani_data["is_excess_deduction"]:
        veta_pdph.set("R65_2", _d(abs(net_vat)))  # Nadměrný odpočet
    else:
        veta_pdph.set("R65_1", _d(net_vat))       # Vlastní daňová povinnost

    return etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )


def validate_against_xsd(xml_bytes: bytes, xsd_path: str) -> tuple[bool, list[str]]:
    """
    Validate generated XML against a downloaded XSD file.
    Returns (is_valid, list_of_errors).
    """
    try:
        xml_doc = etree.fromstring(xml_bytes)
        xsd_doc = etree.parse(xsd_path)
        schema  = etree.XMLSchema(xsd_doc)
        is_valid = schema.validate(xml_doc)
        errors   = [str(e) for e in schema.error_log] if not is_valid else []
        return is_valid, errors
    except (etree.XMLSyntaxError, OSError) as e:
        return False, [f"Could not validate: {e}"]


def compute_checksum(xml_bytes: bytes) -> str:
    """SHA-256 checksum of generated XML — stored in FilingRecord."""
    return hashlib.sha256(xml_bytes).hexdigest()
