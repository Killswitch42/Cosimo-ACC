"""
Invoice service — authorised path for creating and posting invoices.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import uuid as uuid_module

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceLine
from app.schemas.invoice import InvoiceCreate
from app.schemas.journal_entry import JournalEntryCreate, JournalEntryLineCreate
from app.services.ares_service import validate_counterparty, validate_dic_format
from app.services.cnb_fx_service import get_cnb_rate
from app.services.duzp_service import resolve_vat_period, validate_duzp, validate_vat_rate
from app.services.ledger_service import LedgerError, post_journal_entry, reverse_journal_entry
from app.services.vat_service import create_vat_register_entries


class InvoiceError(Exception):
    pass


ISSUED_RECEIVABLE_ACCOUNT = "311"
ISSUED_REVENUE_ACCOUNT = "602"
RECEIVED_PAYABLE_ACCOUNT = "321"
RECEIVED_EXPENSE_ACCOUNT = "518"
VAT_ACCOUNT = "343"


def _compute_line_amounts(
    quantity: Decimal,
    unit_price_net: Decimal,
    vat_rate: Decimal,
    exchange_rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    net_foreign = (quantity * unit_price_net).quantize(Decimal("0.01"), ROUND_HALF_UP)
    vat_foreign = (net_foreign * vat_rate / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    gross_foreign = net_foreign + vat_foreign
    net_czk = (net_foreign * exchange_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    vat_czk = (vat_foreign * exchange_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    gross_czk = (gross_foreign * exchange_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return net_czk, vat_czk, gross_czk


def _build_issued_journal_lines(invoice: Invoice) -> list[JournalEntryLineCreate]:
    lines = []
    for inv_line in invoice.lines:
        lines.append(
            JournalEntryLineCreate(
                account_number=inv_line.account_number or ISSUED_REVENUE_ACCOUNT,
                side="CREDIT",
                amount_foreign=inv_line.line_net_czk,
                description=inv_line.description,
                cost_centre=inv_line.cost_centre,
                vat_rate=inv_line.vat_rate,
            )
        )
    if invoice.total_vat_czk != Decimal("0.00"):
        lines.append(
            JournalEntryLineCreate(
                account_number=VAT_ACCOUNT,
                side="CREDIT",
                amount_foreign=invoice.total_vat_czk,
                description=f"DPH z vydané faktury {invoice.invoice_number}",
            )
        )
    lines.append(
        JournalEntryLineCreate(
            account_number=ISSUED_RECEIVABLE_ACCOUNT,
            side="DEBIT",
            amount_foreign=invoice.total_gross_czk,
            description=f"Pohledávka: {invoice.counterparty_name} — {invoice.invoice_number}",
        )
    )
    return lines


def _build_received_journal_lines(invoice: Invoice) -> list[JournalEntryLineCreate]:
    lines = []
    for inv_line in invoice.lines:
        lines.append(
            JournalEntryLineCreate(
                account_number=inv_line.account_number or RECEIVED_EXPENSE_ACCOUNT,
                side="DEBIT",
                amount_foreign=inv_line.line_net_czk,
                description=inv_line.description,
                cost_centre=inv_line.cost_centre,
                vat_rate=inv_line.vat_rate,
            )
        )
    if invoice.is_reverse_charge:
        if invoice.total_vat_czk != Decimal("0.00"):
            lines.append(
                JournalEntryLineCreate(
                    account_number=VAT_ACCOUNT,
                    side="DEBIT",
                    amount_foreign=invoice.total_vat_czk,
                    description=f"DPH vstup PDP § 92a: {invoice.invoice_number}",
                )
            )
            lines.append(
                JournalEntryLineCreate(
                    account_number=VAT_ACCOUNT,
                    side="CREDIT",
                    amount_foreign=invoice.total_vat_czk,
                    description=f"DPH výstup PDP § 92a: {invoice.invoice_number}",
                )
            )
        lines.append(
            JournalEntryLineCreate(
                account_number=RECEIVED_PAYABLE_ACCOUNT,
                side="CREDIT",
                amount_foreign=invoice.total_net_czk,
                description=f"Závazek PDP: {invoice.counterparty_name} — {invoice.invoice_number}",
            )
        )
    else:
        if invoice.total_vat_czk != Decimal("0.00"):
            lines.append(
                JournalEntryLineCreate(
                    account_number=VAT_ACCOUNT,
                    side="DEBIT",
                    amount_foreign=invoice.total_vat_czk,
                    description=f"DPH vstup: {invoice.invoice_number}",
                )
            )
        lines.append(
            JournalEntryLineCreate(
                account_number=RECEIVED_PAYABLE_ACCOUNT,
                side="CREDIT",
                amount_foreign=invoice.total_gross_czk,
                description=f"Závazek: {invoice.counterparty_name} — {invoice.invoice_number}",
            )
        )
    return lines


async def post_invoice(
    session: AsyncSession,
    company_id: uuid_module.UUID,
    data: InvoiceCreate,
    posted_by: str = "system",
) -> Invoice:
    validation_warnings = []
    validation_errors = []

    duzp_result = validate_duzp(data.duzp, data.invoice_date, data.direction)
    validation_warnings.extend(duzp_result.warnings)
    validation_errors.extend(duzp_result.errors)

    if data.counterparty_dic:
        validation_warnings.extend(validate_dic_format(data.counterparty_dic))

    for line in data.lines:
        validation_errors.extend(validate_vat_rate(line.vat_rate))

    if validation_errors:
        raise InvoiceError(f"Invoice validation failed: {'; '.join(validation_errors)}")

    ares_result = await validate_counterparty(
        ico=data.counterparty_ico,
        dic=data.counterparty_dic,
        counterparty_name=data.counterparty_name,
    )
    validation_warnings.extend(ares_result.warnings)
    if not ares_result.is_valid:
        validation_warnings.extend(ares_result.errors)

    exchange_rate = Decimal("1.000000")
    if data.currency != "CZK":
        exchange_rate = await get_cnb_rate(session, data.currency, data.duzp)

    total_net_czk = Decimal("0.00")
    total_vat_czk = Decimal("0.00")
    total_gross_czk = Decimal("0.00")
    invoice_id = uuid_module.uuid4()
    invoice_lines = []

    for index, line_data in enumerate(data.lines):
        net_czk, vat_czk, gross_czk = _compute_line_amounts(
            line_data.quantity,
            line_data.unit_price_net,
            line_data.vat_rate,
            exchange_rate,
        )
        invoice_lines.append(
            InvoiceLine(
                id=uuid_module.uuid4(),
                invoice_id=invoice_id,
                line_number=index + 1,
                description=line_data.description,
                quantity=line_data.quantity,
                unit=line_data.unit,
                unit_price_net=line_data.unit_price_net,
                vat_rate=line_data.vat_rate,
                line_net_czk=net_czk,
                line_vat_czk=vat_czk,
                line_gross_czk=gross_czk,
                account_number=line_data.account_number,
                cost_centre=line_data.cost_centre,
            )
        )
        total_net_czk += net_czk
        total_vat_czk += vat_czk
        total_gross_czk += gross_czk

    vat_period = resolve_vat_period(data.duzp)
    # Variable symbol: use the supplied value, else derive from the invoice
    # number's digits (max 10, the Czech VS length) so bank matching has a key.
    variable_symbol = data.variable_symbol
    if not variable_symbol:
        digits = "".join(ch for ch in data.invoice_number if ch.isdigit())
        variable_symbol = digits[-10:] if digits else None
    invoice = Invoice(
        id=invoice_id,
        company_id=company_id,
        direction=data.direction,
        invoice_type=data.invoice_type,
        invoice_number=data.invoice_number,
        internal_reference=data.internal_reference,
        invoice_date=data.invoice_date,
        duzp=data.duzp,
        due_date=data.due_date,
        variable_symbol=variable_symbol,
        counterparty_name=data.counterparty_name,
        counterparty_ico=data.counterparty_ico,
        counterparty_dic=data.counterparty_dic,
        counterparty_address=data.counterparty_address,
        counterparty_country=data.counterparty_country,
        currency=data.currency,
        exchange_rate=exchange_rate,
        total_net_czk=total_net_czk,
        total_vat_czk=total_vat_czk,
        total_gross_czk=total_gross_czk,
        total_net_foreign=(total_net_czk / exchange_rate).quantize(Decimal("0.01")),
        total_vat_foreign=(total_vat_czk / exchange_rate).quantize(Decimal("0.01")),
        total_gross_foreign=(total_gross_czk / exchange_rate).quantize(Decimal("0.01")),
        counterparty_is_vat_payer=data.counterparty_is_vat_payer,
        is_reverse_charge=data.is_reverse_charge,
        is_eu_supply=data.is_eu_supply,
        ares_validated=ares_result.is_valid,
        ares_validation_note="; ".join(validation_warnings) if validation_warnings else None,
        notes=data.notes,
        status="validated",
    )
    invoice.lines = invoice_lines
    session.add(invoice)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise InvoiceError("Duplicate received invoice for this supplier DIČ and number.") from exc

    je_lines = _build_issued_journal_lines(invoice) if data.direction == "ISSUED" else _build_received_journal_lines(invoice)
    je_data = JournalEntryCreate(
        entry_date=data.duzp,
        description=(
            f"{'Vydaná' if data.direction == 'ISSUED' else 'Přijatá'} faktura "
            f"{data.invoice_number} — {data.counterparty_name}"
        ),
        currency="CZK",
        entry_type="STANDARD",
        source_type=f"INVOICE_{data.direction}",
        source_id=invoice.id,
        lines=je_lines,
    )

    try:
        journal_entry = await post_journal_entry(session, company_id, je_data, posted_by)
    except LedgerError as exc:
        raise InvoiceError(f"Ledger posting failed: {exc}") from exc

    invoice.journal_entry_id = journal_entry.id
    invoice.status = "posted"
    await session.flush()

    if data.invoice_type not in ("PROFORMA",):
        await create_vat_register_entries(session, invoice, vat_period)

    try:
        from app.services.watchdog_service import scan_invoice

        await scan_invoice(session, invoice, company_id)
    except Exception:
        # Compliance scanning should not block invoice posting.
        pass

    await session.flush()
    return invoice


async def void_invoice(
    session: AsyncSession,
    invoice_id: uuid_module.UUID,
    company_id: uuid_module.UUID,
    void_reason: str,
    posted_by: str = "system",
) -> Invoice:
    from app.schemas.journal_entry import ReversalRequest

    result = await session.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise InvoiceError(f"Invoice {invoice_id} not found.")
    if invoice.status != "posted":
        raise InvoiceError(
            f"Only posted invoices can be voided. Invoice {invoice.invoice_number} has status '{invoice.status}'."
        )
    if not invoice.journal_entry_id:
        raise InvoiceError(f"Invoice {invoice.invoice_number} has no linked journal entry.")

    reversal_request = ReversalRequest(
        reversal_date=date.today(),
        reason=f"Storno faktury {invoice.invoice_number}: {void_reason}",
    )
    await reverse_journal_entry(
        session, invoice.journal_entry_id, company_id, reversal_request, posted_by
    )

    invoice.status = "voided"
    invoice.void_reason = void_reason
    for vat_entry in invoice.vat_entries:
        vat_entry.kh_submitted = False

    await session.flush()
    return invoice
