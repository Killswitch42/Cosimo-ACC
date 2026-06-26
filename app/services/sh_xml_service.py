"""
Souhrnné hlášení (EC sales list) XML generator — for EU B2B zero-rated supplies (§ 64 ZDPH).

⚠️ SCHEMA VALIDATION REQUIRED BEFORE ANY REAL FILING.
"""
from decimal import Decimal

from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.vat_register import VatRegisterEntry


async def get_eu_supplies_for_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
) -> list[VatRegisterEntry]:
    result = await session.execute(
        select(VatRegisterEntry).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
            VatRegisterEntry.is_eu_supply == True,
        ).order_by(VatRegisterEntry.counterparty_country, VatRegisterEntry.counterparty_dic)
    )
    return list(result.scalars().all())


def build_sh_xml(
    company_dic: str,
    vat_period: str,
    eu_entries: list[VatRegisterEntry],
    tax_office_code: str = "2207",
) -> bytes:
    """
    Build the souhrnné hlášení XML document.
    Aggregates by (country, buyer VAT ID, supply type code).
    """
    year, month = vat_period.split("-")
    dic_bare = company_dic.replace("CZ", "") if company_dic else ""

    root = etree.Element("Pisemnost")
    sh = etree.SubElement(root, "DPHSHV")
    sh.set("k_uladis", tax_office_code)
    sh.set("rok", year)
    sh.set("mesic", month)

    veta_d = etree.SubElement(sh, "VetaD")
    veta_d.set("dic", dic_bare)

    # Aggregate by (country, buyer DIČ, supply_type)
    aggregates: dict[tuple, Decimal] = {}
    for entry in eu_entries:
        key = (
            entry.counterparty_country,
            entry.counterparty_dic or "",
            entry.eu_supply_type or 1,
        )
        aggregates[key] = aggregates.get(key, Decimal("0.00")) + entry.tax_base_czk

    for (country, dic, supply_type), total in aggregates.items():
        buyer_dic = dic.replace(country, "")
        el = etree.SubElement(sh, "VetaP")
        el.set("kod_st", country)
        el.set("dic_obch_p", buyer_dic)
        el.set("hodnota_pl", str(total.quantize(Decimal("0.01"))))
        el.set("kod_pl", str(supply_type))  # 1=zboží, 2=triangulace, 3=služby — verify against XSD

    return etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )
