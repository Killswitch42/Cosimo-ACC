"""
Filing orchestration — ties together reconciliation, XML/PDF generation,
and FilingRecord tracking.
"""
import os
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.filing_record import FilingRecord
from app.models.vat_register import VatRegisterEntry
from app.services.reconciliation_service import ReconciliationError, run_full_reconciliation
from app.services.report_data_service import (
    build_dph_priznani_data, build_kh_data, get_company
)
from app.services.dph_xml_service import build_dph_priznani_xml, compute_checksum
from app.services.kh_xml_service import build_kh_xml
from app.services.rozvaha_service import generate_rozvaha
from app.services.vzz_service import generate_vzz
from app.services.pdf_report_service import render_rozvaha_pdf, render_vzz_pdf


class FilingError(Exception):
    pass


def _ensure_output_dir() -> str:
    output_dir = settings.filing_output_dir
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


async def generate_dph_priznani(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
    fiscal_period_id: uuid.UUID,
    generated_by: str = "system",
) -> FilingRecord:
    """
    Generate the DPH přiznání XML. Blocks on reconciliation failure.
    """
    try:
        await run_full_reconciliation(session, company_id, vat_period, fiscal_period_id)
    except ReconciliationError as e:
        record = FilingRecord(
            id=uuid.uuid4(),
            company_id=company_id,
            filing_type="DPH_PRIZNANI",
            period_label=vat_period,
            status="draft",
            reconciliation_passed=False,
            reconciliation_detail=str(e),
        )
        session.add(record)
        await session.flush()
        raise FilingError(
            f"Cannot generate DPH přiznání for {vat_period}: reconciliation failed.\n{e}"
        )

    company       = await get_company(session, company_id)
    priznani_data = await build_dph_priznani_data(session, company_id, vat_period)

    xml_bytes = build_dph_priznani_xml(
        company_dic=company.dic or "",
        company_name=company.name,
        vat_period=vat_period,
        priznani_data=priznani_data,
        tax_office_code="2207",
        is_quarterly=(company.vat_filing_period == "quarterly"),
    )
    checksum = compute_checksum(xml_bytes)

    output_dir = _ensure_output_dir()
    file_path = os.path.join(output_dir, f"DPH_priznani_{vat_period}.xml")
    with open(file_path, "wb") as f:
        f.write(xml_bytes)

    record = FilingRecord(
        id=uuid.uuid4(),
        company_id=company_id,
        filing_type="DPH_PRIZNANI",
        period_label=vat_period,
        status="generated",
        reconciliation_passed=True,
        reconciliation_detail="All checks passed.",
        file_path=file_path,
        file_checksum_sha256=checksum,
        generated_at=datetime.now(timezone.utc),
        generated_by=generated_by,
    )
    session.add(record)
    await session.flush()

    entries_result = await session.execute(
        select(VatRegisterEntry).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
        )
    )
    for entry in entries_result.scalars().all():
        entry.priznani_submitted = True
        entry.priznani_submission_date = datetime.now(timezone.utc).date()

    await session.flush()
    return record


async def generate_kontrolni_hlaseni(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
    fiscal_period_id: uuid.UUID,
    generated_by: str = "system",
) -> FilingRecord:
    """Generate the kontrolní hlášení XML. Blocks on reconciliation failure."""
    try:
        await run_full_reconciliation(session, company_id, vat_period, fiscal_period_id)
    except ReconciliationError as e:
        record = FilingRecord(
            id=uuid.uuid4(),
            company_id=company_id,
            filing_type="KONTROLNI_HLASENI",
            period_label=vat_period,
            status="draft",
            reconciliation_passed=False,
            reconciliation_detail=str(e),
        )
        session.add(record)
        await session.flush()
        raise FilingError(
            f"Cannot generate kontrolní hlášení for {vat_period}: reconciliation failed.\n{e}"
        )

    company  = await get_company(session, company_id)
    kh_data  = await build_kh_data(session, company_id, vat_period)

    xml_bytes = build_kh_xml(
        company_dic=company.dic or "",
        company_name=company.name,
        vat_period=vat_period,
        kh_data=kh_data,
        tax_office_code="2207",
    )
    checksum = compute_checksum(xml_bytes)

    output_dir = _ensure_output_dir()
    file_path = os.path.join(output_dir, f"KH_{vat_period}.xml")
    with open(file_path, "wb") as f:
        f.write(xml_bytes)

    record = FilingRecord(
        id=uuid.uuid4(),
        company_id=company_id,
        filing_type="KONTROLNI_HLASENI",
        period_label=vat_period,
        status="generated",
        reconciliation_passed=True,
        reconciliation_detail="All checks passed.",
        file_path=file_path,
        file_checksum_sha256=checksum,
        generated_at=datetime.now(timezone.utc),
        generated_by=generated_by,
    )
    session.add(record)
    await session.flush()

    entries_result = await session.execute(
        select(VatRegisterEntry).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
        )
    )
    for entry in entries_result.scalars().all():
        entry.kh_submitted = True
        entry.kh_submission_date = datetime.now(timezone.utc).date()

    await session.flush()
    return record


async def generate_rozvaha_report(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
    period_label: str,
    generated_by: str = "system",
) -> tuple[FilingRecord, bytes]:
    """Generate the rozvaha PDF. Returns (FilingRecord, pdf_bytes)."""
    company      = await get_company(session, company_id)
    rozvaha_data = await generate_rozvaha(session, company_id, fiscal_period_id)

    pdf_bytes = render_rozvaha_pdf(
        company_name=company.name,
        company_ico=company.ico or "",
        period_label=period_label,
        rozvaha_data=rozvaha_data,
    )
    checksum = compute_checksum(pdf_bytes)

    output_dir = _ensure_output_dir()
    file_path = os.path.join(output_dir, f"Rozvaha_{period_label}.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    record = FilingRecord(
        id=uuid.uuid4(),
        company_id=company_id,
        filing_type="ROZVAHA",
        period_label=period_label,
        status="generated",
        reconciliation_passed=True,
        reconciliation_detail=None,
        file_path=file_path,
        file_checksum_sha256=checksum,
        generated_at=datetime.now(timezone.utc),
        generated_by=generated_by,
    )
    session.add(record)
    await session.flush()
    return record, pdf_bytes


async def generate_vzz_report(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
    period_label: str,
    generated_by: str = "system",
) -> tuple[FilingRecord, bytes]:
    """Generate the VZZ PDF. Returns (FilingRecord, pdf_bytes)."""
    company  = await get_company(session, company_id)
    vzz_data = await generate_vzz(session, company_id, fiscal_period_id)

    pdf_bytes = render_vzz_pdf(
        company_name=company.name,
        company_ico=company.ico or "",
        period_label=period_label,
        vzz_data=vzz_data,
    )
    checksum = compute_checksum(pdf_bytes)

    output_dir = _ensure_output_dir()
    file_path = os.path.join(output_dir, f"VZZ_{period_label}.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    record = FilingRecord(
        id=uuid.uuid4(),
        company_id=company_id,
        filing_type="VZZ",
        period_label=period_label,
        status="generated",
        reconciliation_passed=True,
        reconciliation_detail=None,
        file_path=file_path,
        file_checksum_sha256=checksum,
        generated_at=datetime.now(timezone.utc),
        generated_by=generated_by,
    )
    session.add(record)
    await session.flush()
    return record, pdf_bytes
