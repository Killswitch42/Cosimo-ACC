"""
Invoice/receipt UI — server-rendered page + HTMX partials for data entry.

Reuses the invoice-posting service (full double-entry + VAT register + AI
classification) and the document service. Creation runs in its own transaction
so a validation failure never poisons the follow-up listing query.
"""
import logging
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select

logger = logging.getLogger("medici.invoices")

from app.database import async_session_factory
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
from app.services.auth_service import get_current_user, get_current_user_web
from app.services.document_service import DocumentError, save_invoice_document
from app.services.invoice_extraction_service import ExtractionError, extract_invoice
from app.services.invoice_service import InvoiceError, post_invoice, void_invoice
from app.services.ledger_service import LedgerError

router = APIRouter(tags=["invoices-ui"])
templates = Jinja2Templates(directory="app/templates")


def _clean(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


async def _list_invoices(session, company_id):
    result = await session.execute(
        select(Invoice)
        .where(Invoice.company_id == company_id)
        .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
    )
    return list(result.scalars().all())


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(e.get("msg", "chyba") for e in exc.errors())
    return str(exc)


@router.get("/invoices", response_class=HTMLResponse)
async def invoices_page(
    request: Request,
    user: User = Depends(get_current_user_web),
):
    async with async_session_factory() as session:
        invoices = await _list_invoices(session, user.company_id)
    return templates.TemplateResponse(
        "invoices.html",
        {"request": request, "user": user, "invoices": invoices},
    )


@router.post("/invoices/extract", response_class=HTMLResponse)
async def invoices_extract(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Read an uploaded PDF invoice and return the entry form pre-filled."""
    content = await file.read()
    try:
        fields, source = await extract_invoice(content, file.content_type, file.filename)
        return templates.TemplateResponse(
            "partials/invoice_form.html",
            {"request": request, "f": fields, "extract_note": source},
        )
    except ExtractionError as exc:
        return templates.TemplateResponse(
            "partials/invoice_form.html",
            {"request": request, "f": {}, "extract_error": str(exc)},
        )
    except Exception:
        logger.exception("Invoice extraction failed")
        return templates.TemplateResponse(
            "partials/invoice_form.html",
            {"request": request, "f": {},
             "extract_error": "Zpracování PDF selhalo. Vyplňte údaje ručně."},
        )


@router.post("/invoices/create", response_class=HTMLResponse)
async def invoices_create(
    request: Request,
    direction: str = Form(...),
    invoice_number: str = Form(...),
    invoice_date: str = Form(...),
    duzp: str = Form(""),
    due_date: str = Form(""),
    variable_symbol: str = Form(""),
    counterparty_name: str = Form(...),
    counterparty_ico: str = Form(""),
    counterparty_dic: str = Form(""),
    currency: str = Form("CZK"),
    line_description: str = Form(...),
    unit_price_net: str = Form(...),
    vat_rate: str = Form("21.00"),
    account_number: str = Form(""),
    user: User = Depends(get_current_user),
):
    error = None
    success = None

    # Pre-validate the fields users most often mis-enter, with clear messages,
    # before anything touches the database.
    ico = _clean(counterparty_ico)
    account = _clean(account_number)
    if ico and (not ico.isdigit() or len(ico) != 8):
        error = f"IČO musí mít přesně 8 číslic (zadáno „{ico}“) — nezaměňujte s číslem účtu."

    async with async_session_factory() as session:
        if error is None:
            try:
                async with session.begin():
                    inv_date = date.fromisoformat(invoice_date)
                    data = InvoiceCreate(
                        direction=direction,
                        invoice_number=invoice_number,
                        invoice_date=inv_date,
                        duzp=date.fromisoformat(duzp) if duzp.strip() else inv_date,
                        due_date=date.fromisoformat(due_date) if due_date.strip() else None,
                        variable_symbol=_clean(variable_symbol),
                        counterparty_name=counterparty_name,
                        counterparty_ico=ico,
                        counterparty_dic=_clean(counterparty_dic),
                        currency=currency or "CZK",
                        lines=[
                            InvoiceLineCreate(
                                description=line_description,
                                unit_price_net=Decimal(unit_price_net),
                                vat_rate=Decimal(vat_rate),
                                account_number=account,
                            )
                        ],
                    )
                    invoice = await post_invoice(
                        session, user.company_id, data, posted_by=user.email
                    )
                success = f"Faktura {invoice.invoice_number} byla zaúčtována."
            except (InvoiceError, LedgerError, ValidationError, ValueError, InvalidOperation) as exc:
                error = _friendly_error(exc)
            except Exception as exc:  # never return a 500 to the form — always show a reason
                logger.exception("Invoice create failed")
                error = f"Uložení selhalo: {type(exc).__name__}. Zkontrolujte zadané údaje."

        # Fresh transaction — safe even if the create above rolled back.
        async with session.begin():
            invoices = await _list_invoices(session, user.company_id)

    return templates.TemplateResponse(
        "partials/invoice_list.html",
        {"request": request, "invoices": invoices, "error": error, "success": success},
    )


@router.post("/invoices/{invoice_id}/void-ui", response_class=HTMLResponse)
async def invoices_void(
    invoice_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Void a posted invoice (posts a reversal entry — nothing is deleted)."""
    reason = (request.headers.get("HX-Prompt") or "Storno dokladu").strip() or "Storno dokladu"
    error = None
    success = None
    async with async_session_factory() as session:
        try:
            async with session.begin():
                invoice = await void_invoice(
                    session, invoice_id, user.company_id, reason, posted_by=user.email
                )
            success = f"Faktura {invoice.invoice_number} byla stornována."
        except (InvoiceError, LedgerError) as exc:
            error = str(exc)
        async with session.begin():
            invoices = await _list_invoices(session, user.company_id)

    return templates.TemplateResponse(
        "partials/invoice_list.html",
        {"request": request, "invoices": invoices, "error": error, "success": success},
    )


@router.post("/invoices/{invoice_id}/document-ui", response_class=HTMLResponse)
async def invoices_upload_document(
    invoice_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    error = None
    success = None
    content = await file.read()
    async with async_session_factory() as session:
        async with session.begin():
            invoice = await session.get(Invoice, invoice_id)
            if not invoice or invoice.company_id != user.company_id:
                error = "Faktura nenalezena."
            else:
                try:
                    path = save_invoice_document(
                        user.company_id, invoice_id,
                        file.filename or "document", content, file.content_type,
                    )
                    invoice.document_path = path
                    success = f"Doklad připojen k faktuře {invoice.invoice_number}."
                except DocumentError as exc:
                    error = str(exc)
        async with session.begin():
            invoices = await _list_invoices(session, user.company_id)

    return templates.TemplateResponse(
        "partials/invoice_list.html",
        {"request": request, "invoices": invoices, "error": error, "success": success},
    )
