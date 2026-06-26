"""
VAT register service — KH section assignment and period aggregation.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.vat_register import VatRegisterEntry

KH_THRESHOLD_CZK = Decimal("10000.00")


def assign_kh_section(
    direction: str,
    total_vat_czk: Decimal,
    counterparty_is_vat_payer: bool,
    is_reverse_charge: bool,
    invoice_type: str,
) -> tuple[str, bool]:
    above_threshold = total_vat_czk >= KH_THRESHOLD_CZK

    if direction == "ISSUED":
        if invoice_type == "ADVANCE":
            return ("A4", False)
        if not counterparty_is_vat_payer:
            return ("A3", False)
        if above_threshold:
            return ("A1", True)
        return ("A2", False)

    if direction == "RECEIVED":
        if is_reverse_charge:
            return ("B1", True)
        if above_threshold:
            return ("B2", True)
        return ("B3", False)

    raise ValueError(f"Unknown invoice direction: {direction}")


async def create_vat_register_entries(
    session: AsyncSession,
    invoice: Invoice,
    vat_period: str,
) -> list[VatRegisterEntry]:
    import uuid as uuid_module

    rate_totals: dict[Decimal, dict] = {}
    for line in invoice.lines:
        rate = line.vat_rate
        if rate not in rate_totals:
            rate_totals[rate] = {"base": Decimal("0.00"), "tax": Decimal("0.00")}
        rate_totals[rate]["base"] += line.line_net_czk
        rate_totals[rate]["tax"] += line.line_vat_czk

    kh_section, kh_detail_required = assign_kh_section(
        direction=invoice.direction,
        total_vat_czk=invoice.total_vat_czk,
        counterparty_is_vat_payer=invoice.counterparty_is_vat_payer,
        is_reverse_charge=invoice.is_reverse_charge,
        invoice_type=invoice.invoice_type,
    )
    zdph_paragraph = None
    if invoice.is_reverse_charge:
        zdph_paragraph = "§92a"
    elif invoice.is_eu_supply:
        zdph_paragraph = "§64"

    entries = []
    for vat_rate, totals in rate_totals.items():
        entry = VatRegisterEntry(
            id=uuid_module.uuid4(),
            company_id=invoice.company_id,
            invoice_id=invoice.id,
            vat_period=vat_period,
            direction=invoice.direction,
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date,
            duzp=invoice.duzp,
            counterparty_name=invoice.counterparty_name,
            counterparty_dic=invoice.counterparty_dic,
            counterparty_country=invoice.counterparty_country,
            vat_rate=vat_rate,
            tax_base_czk=totals["base"],
            tax_amount_czk=totals["tax"],
            kh_section=kh_section,
            kh_detail_required=kh_detail_required,
            is_reverse_charge=invoice.is_reverse_charge,
            is_eu_supply=invoice.is_eu_supply,
            eu_supply_type=1 if invoice.is_eu_supply else None,
            zdph_paragraph=zdph_paragraph,
        )
        session.add(entry)
        entries.append(entry)
    return entries


async def get_vat_period_totals(
    session: AsyncSession,
    company_id,
    vat_period: str,
) -> dict:
    result = await session.execute(
        select(
            VatRegisterEntry.direction,
            VatRegisterEntry.vat_rate,
            func.sum(VatRegisterEntry.tax_base_czk).label("total_base"),
            func.sum(VatRegisterEntry.tax_amount_czk).label("total_tax"),
            func.count(VatRegisterEntry.id).label("count"),
        )
        .where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
        )
        .group_by(VatRegisterEntry.direction, VatRegisterEntry.vat_rate)
    )

    totals = {}
    for row in result.all():
        key = f"{row.direction.lower()}_{int(row.vat_rate)}"
        totals[key] = {
            "base": row.total_base or Decimal("0.00"),
            "tax": row.total_tax or Decimal("0.00"),
            "count": row.count,
        }
    return totals


async def get_kh_detail_entries(
    session: AsyncSession,
    company_id,
    vat_period: str,
    kh_section: str,
) -> list[VatRegisterEntry]:
    result = await session.execute(
        select(VatRegisterEntry)
        .where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
            VatRegisterEntry.kh_section == kh_section,
            VatRegisterEntry.kh_detail_required == True,
        )
        .order_by(VatRegisterEntry.duzp, VatRegisterEntry.invoice_number)
    )
    return list(result.scalars().all())
