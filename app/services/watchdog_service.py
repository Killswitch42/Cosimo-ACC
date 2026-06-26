"""
Compliance watchdog — scans the system for Czech legal violations
and creates AlertRecord entries.

Designed to run:
  1. Synchronously after every invoice POST (invoice-level checks)
  2. On a daily schedule (period-level and cross-report checks)
  3. On demand via GET /compliance/scan

Rules are split into:
  DETERMINISTIC — pure logic, runs without Claude
  AI_ASSISTED   — calls Claude for context-sensitive analysis

The watchdog NEVER blocks invoice posting — it runs after the fact
and raises alerts. Only the pre-filing consistency checker (Phase 05)
can block a filing.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.alert import AlertRecord
from app.models.invoice import Invoice
from app.models.vat_register import VatRegisterEntry
from app.services.ai_client import call_claude, AIClientError
from app.services.ares_service import validate_dic_format
from app.services.duzp_service import validate_duzp

DEFAULT_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _upsert_alert(
    session: AsyncSession,
    company_id: uuid.UUID,
    rule_code: str,
    severity: str,
    category: str,
    title: str,
    detail: str,
    suggested_action: str | None = None,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
    deadline_date: date | None = None,
    ai_generated: bool = False,
    ai_confidence: float | None = None,
) -> AlertRecord:
    """
    Create an alert if one with this rule_code + source_id doesn't already exist.
    Prevents duplicate alerts for the same issue.
    """
    # Check for existing open alert with same rule_code and source_id
    existing_result = await session.execute(
        select(AlertRecord).where(
            AlertRecord.company_id == company_id,
            AlertRecord.rule_code == rule_code,
            AlertRecord.source_id == source_id,
            AlertRecord.status == "open",
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return existing  # Don't duplicate

    alert = AlertRecord(
        id=uuid.uuid4(),
        company_id=company_id,
        severity=severity,
        category=category,
        rule_code=rule_code,
        title=title,
        detail=detail,
        suggested_action=suggested_action,
        source_type=source_type,
        source_id=source_id,
        deadline_date=deadline_date,
        status="open",
        ai_generated=ai_generated,
        ai_confidence=ai_confidence,
    )
    session.add(alert)
    await session.flush()
    return alert


async def scan_invoice(
    session: AsyncSession,
    invoice: Invoice,
    company_id: uuid.UUID,
) -> list[AlertRecord]:
    """
    Run all invoice-level compliance checks immediately after posting.
    Returns list of alerts created.
    """
    alerts = []

    # ── RULE: VAT_MISSING_DIC (Threshold is 10000 CZK total gross including VAT) ──
    if (
        invoice.total_gross_czk >= Decimal("10000.00")
        and not invoice.counterparty_dic
        and invoice.direction == "RECEIVED"
    ):
        a = await _upsert_alert(
            session, company_id,
            rule_code="MISSING_DIC_10000",
            severity="BLOCKER",
            category="COMPLIANCE",
            title=f"Chybí DIČ dodavatele — {invoice.invoice_number}",
            detail=(
                f"Přijatá faktura {invoice.invoice_number} od {invoice.counterparty_name} "
                f"má celkovou částku {invoice.total_gross_czk} Kč (nad prahem 10 000 Kč pro KH) "
                f"ale nemá uvedené DIČ. Faktura nemůže být správně zařazena do "
                f"kontrolního hlášení bez DIČ dodavatele."
            ),
            suggested_action=(
                f"Doplňte DIČ dodavatele {invoice.counterparty_name} "
                f"a aktualizujte fakturu. Ověřte DIČ na https://ares.gov.cz"
            ),
            source_type="INVOICE",
            source_id=invoice.id,
        )
        alerts.append(a)

    # ── RULE: VAT_INVALID_DIC_FORMAT ─────────────────────────────
    if invoice.counterparty_dic:
        dic_errors = validate_dic_format(invoice.counterparty_dic)
        if dic_errors:
            a = await _upsert_alert(
                session, company_id,
                rule_code="INVALID_DIC_FORMAT",
                severity="WARNING",
                category="COMPLIANCE",
                title=f"Neplatný formát DIČ — {invoice.invoice_number}",
                detail=(
                    f"DIČ '{invoice.counterparty_dic}' na faktuře "
                    f"{invoice.invoice_number} má neplatný formát: "
                    f"{'; '.join(dic_errors)}"
                ),
                suggested_action="Ověřte DIČ na https://ares.gov.cz and opravte fakturu.",
                source_type="INVOICE",
                source_id=invoice.id,
            )
            alerts.append(a)

    # ── RULE: VAT_DUZP_WRONG_PERIOD ──────────────────────────────
    duzp_result = validate_duzp(invoice.duzp, invoice.invoice_date, invoice.direction)
    if duzp_result.warnings:
        for warning in duzp_result.warnings:
            a = await _upsert_alert(
                session, company_id,
                rule_code=f"VAT_DUZP_{invoice.invoice_number}",
                severity="WARNING",
                category="VAT",
                title=f"Upozornění k DUZP — {invoice.invoice_number}",
                detail=warning,
                suggested_action=(
                    "Zkontrolujte správnost data DUZP. "
                    "DPH musí být vykázáno v období DUZP, nikoli v období vystavení faktury."
                ),
                source_type="INVOICE",
                source_id=invoice.id,
            )
            alerts.append(a)

    # ── RULE: AI — UNUSUAL ACCOUNT / NON-DEDUCTIBLE DETECTION ────
    try:
        from app.services.classifier_service import classify_transaction
        from app.config import settings
        if settings.anthropic_api_key:
            clf_log = await classify_transaction(
                session=session,
                company_id=company_id,
                description=f"{invoice.direction} invoice: {invoice.counterparty_name}",
                counterparty=invoice.counterparty_name,
                direction=invoice.direction,
                source_id=invoice.id,
                classification_type="INVOICE",
            )
            # Low confidence alert
            if clf_log.confidence_score and clf_log.confidence_score < Decimal("0.60"):
                a = await _upsert_alert(
                    session, company_id,
                    rule_code=f"CLASS_LOW_CONFIDENCE_{invoice.invoice_number}",
                    severity="WARNING",
                    category="CLASSIFICATION",
                    title=f"Nízká jistota klasifikace — {invoice.invoice_number}",
                    detail=(
                        f"AI klasifikace faktury {invoice.invoice_number} "
                        f"dosáhla jistoty pouze {float(clf_log.confidence_score):.0%}. "
                        f"Doporučení: {clf_log.reasoning or 'bez komentáře'}"
                    ),
                    suggested_action="Ručně ověřte přiřazení účtů pro tuto fakturu.",
                    source_type="INVOICE",
                    source_id=invoice.id,
                    ai_generated=True,
                    ai_confidence=float(clf_log.confidence_score),
                )
                alerts.append(a)

            # Non-deductible expense detection
            if (
                clf_log.raw_response
                and clf_log.raw_response.get("is_nondeductible")
                and invoice.direction == "RECEIVED"
            ):
                reason = clf_log.raw_response.get("nondeductible_reason", "")
                a = await _upsert_alert(
                    session, company_id,
                    rule_code=f"CLASS_NONDEDUCTIBLE_{invoice.invoice_number}",
                    severity="WARNING",
                    category="CLASSIFICATION",
                    title=f"Potenciálně daňově neuznatelný náklad — {invoice.invoice_number}",
                    detail=(
                        f"AI identifikoval, že faktura {invoice.invoice_number} "
                        f"od {invoice.counterparty_name} může obsahovat daňově "
                        f"neuznatelný náklad dle § 25 ZDP. Důvod: {reason}"
                    ),
                    suggested_action=(
                        "Ověřte, zda výdaj splňuje podmínky § 24 ZDP "
                        "(výdaj vynaložený na dosažení, zajištění a udržení příjmů). "
                        "Reprezentace a dary jsou daňově neuznatelné."
                    ),
                    source_type="INVOICE",
                    source_id=invoice.id,
                    ai_generated=True,
                    ai_confidence=float(clf_log.confidence_score or 0),
                )
                alerts.append(a)

    except AIClientError:
        pass  # AI unavailable — skip AI-assisted checks, continue

    return alerts


async def scan_vat_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
) -> list[AlertRecord]:
    """
    Run period-level consistency checks for a VAT period.
    Called daily by the scheduler and before any filing.
    """
    alerts = []

    # ── RULE: CONS_KH_PRIZNANI_MISMATCH ──────────────────────────
    # Sum KH entries and compare to přiznání-level aggregates
    from app.services.vat_service import get_vat_period_totals

    totals = await get_vat_period_totals(session, company_id, vat_period)

    # For now we verify internal consistency: KH detail entries sum to totals.
    kh_detail_result = await session.execute(
        select(
            func.sum(VatRegisterEntry.tax_base_czk).label("base"),
            func.sum(VatRegisterEntry.tax_amount_czk).label("tax"),
        ).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
            VatRegisterEntry.kh_detail_required == True,
        )
    )
    kh_row = kh_detail_result.one()

    agg_result = await session.execute(
        select(
            func.sum(VatRegisterEntry.tax_base_czk).label("base"),
            func.sum(VatRegisterEntry.tax_amount_czk).label("tax"),
        ).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
        )
    )
    agg_row = agg_result.one()

    if agg_row.tax and kh_row.tax:
        if abs((agg_row.tax or Decimal(0)) - (kh_row.tax or Decimal(0))) > Decimal("0.50"):
            a = await _upsert_alert(
                session, company_id,
                rule_code=f"CONS_KH_PRIZNANI_MISMATCH_{vat_period}",
                severity="BLOCKER",
                category="CONSISTENCY",
                title=f"Nesoulad KH a přiznání — období {vat_period}",
                detail=(
                    f"Součet daně v KH detail entries ({kh_row.tax} Kč) se liší "
                    f"od celkového součtu v registru DPH ({agg_row.tax} Kč) "
                    f"za období {vat_period}. Rozdíl: "
                    f"{abs(agg_row.tax - kh_row.tax):.2f} Kč."
                ),
                suggested_action=(
                    "Zkontrolujte faktury s KH sekcí A1/B1/B2 za toto období. "
                    "Ověřte, že žádná faktura nebyla ručně upravena mimo systém."
                ),
            )
            alerts.append(a)

    return alerts
