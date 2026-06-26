"""
Report generation endpoints for Czech statutory filings.

All XML and PDF generators produce draft documents — validate against
the official XSD from Finanční správa before any real filing.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.ledger_service import get_default_company_id
from app.services.report_data_service import (
    ReportDataError, build_dph_priznani_data, build_kh_data, get_period_by_label
)
from app.services.rozvaha_service import generate_rozvaha
from app.services.vzz_service import generate_vzz
from app.services.pdf_report_service import render_rozvaha_pdf, render_vzz_pdf
from app.services.filing_service import (
    FilingError,
    generate_dph_priznani,
    generate_kontrolni_hlaseni,
    generate_rozvaha_report,
    generate_vzz_report,
)
from app.services.report_data_service import get_company

router = APIRouter(prefix="/reports", tags=["reports"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


# ── DPH přiznání ──────────────────────────────────────────────────────────────

@router.get("/dph-priznani/data")
async def dph_priznani_data(
    vat_period: str = Query(..., description="Format: YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    """Return raw DPH přiznání row values without generating a filing record."""
    company_id = await get_default_company_id(session)
    return await build_dph_priznani_data(session, company_id, vat_period)


@router.post("/dph-priznani/generate")
async def generate_dph_priznani_endpoint(
    vat_period: str = Query(..., description="Format: YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    """
    Generate the DPH přiznání XML for a VAT period.
    Blocks and records failure if reconciliation does not pass.
    """
    company_id = await get_default_company_id(session)
    try:
        period = await get_period_by_label(session, company_id, vat_period[:4])
    except ReportDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        record = await generate_dph_priznani(
            session, company_id, vat_period, period.id, generated_by="api_user"
        )
    except FilingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "filing_id": str(record.id),
        "status": record.status,
        "file_path": record.file_path,
        "file_checksum_sha256": record.file_checksum_sha256,
        "generated_at": record.generated_at.isoformat() if record.generated_at else None,
    }


# ── Kontrolní hlášení ─────────────────────────────────────────────────────────

@router.get("/kontrolni-hlaseni/data")
async def kh_data_endpoint(
    vat_period: str = Query(..., description="Format: YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    """Return KH data without generating a filing record."""
    company_id = await get_default_company_id(session)
    return await build_kh_data(session, company_id, vat_period)


@router.post("/kontrolni-hlaseni/generate")
async def generate_kh_endpoint(
    vat_period: str = Query(..., description="Format: YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    """Generate the kontrolní hlášení XML for a VAT period."""
    company_id = await get_default_company_id(session)
    try:
        period = await get_period_by_label(session, company_id, vat_period[:4])
    except ReportDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        record = await generate_kontrolni_hlaseni(
            session, company_id, vat_period, period.id, generated_by="api_user"
        )
    except FilingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "filing_id": str(record.id),
        "status": record.status,
        "file_path": record.file_path,
        "file_checksum_sha256": record.file_checksum_sha256,
        "generated_at": record.generated_at.isoformat() if record.generated_at else None,
    }


# ── Rozvaha ───────────────────────────────────────────────────────────────────

@router.get("/rozvaha/data")
async def rozvaha_data_endpoint(
    period_label: str = Query(..., description="Format: YYYY"),
    session: AsyncSession = Depends(get_session),
):
    """Return rozvaha data as JSON."""
    company_id = await get_default_company_id(session)
    try:
        period = await get_period_by_label(session, company_id, period_label)
    except ReportDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = await generate_rozvaha(session, company_id, period.id)
    # Convert Decimal to str for JSON serialisation
    return {
        "aktiva": {k: str(v) for k, v in data["aktiva"].items()},
        "aktiva_celkem": str(data["aktiva_celkem"]),
        "pasiva": {k: str(v) for k, v in data["pasiva"].items()},
        "pasiva_celkem": str(data["pasiva_celkem"]),
        "is_balanced": data["is_balanced"],
        "difference": str(data["difference"]),
    }


@router.get("/rozvaha/pdf")
async def rozvaha_pdf_endpoint(
    period_label: str = Query(..., description="Format: YYYY"),
    session: AsyncSession = Depends(get_session),
):
    """Generate and return the rozvaha PDF."""
    company_id = await get_default_company_id(session)
    try:
        period = await get_period_by_label(session, company_id, period_label)
    except ReportDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    _record, pdf_bytes = await generate_rozvaha_report(
        session, company_id, period.id, period_label, generated_by="api_user"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Rozvaha_{period_label}.pdf"'},
    )


# ── VZZ ───────────────────────────────────────────────────────────────────────

@router.get("/vzz/data")
async def vzz_data_endpoint(
    period_label: str = Query(..., description="Format: YYYY"),
    session: AsyncSession = Depends(get_session),
):
    """Return VZZ data as JSON."""
    company_id = await get_default_company_id(session)
    try:
        period = await get_period_by_label(session, company_id, period_label)
    except ReportDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = await generate_vzz(session, company_id, period.id)
    return {
        "lines": {k: str(v) for k, v in data["lines"].items()},
        "profit_before_tax": str(data["profit_before_tax"]),
        "income_tax_current": str(data["income_tax_current"]),
        "income_tax_deferred": str(data["income_tax_deferred"]),
        "net_profit_loss": str(data["net_profit_loss"]),
    }


@router.get("/vzz/pdf")
async def vzz_pdf_endpoint(
    period_label: str = Query(..., description="Format: YYYY"),
    session: AsyncSession = Depends(get_session),
):
    """Generate and return the VZZ PDF."""
    company_id = await get_default_company_id(session)
    try:
        period = await get_period_by_label(session, company_id, period_label)
    except ReportDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    _record, pdf_bytes = await generate_vzz_report(
        session, company_id, period.id, period_label, generated_by="api_user"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="VZZ_{period_label}.pdf"'},
    )
