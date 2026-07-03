"""
Bank reconciliation engine — match BankTransaction records to invoices,
post the settlement journal entry, and flag the rest for human review.

Matching tiers (most reliable first):
  1. AUTO      — variable symbol matches AND amount equals the invoice gross,
                 on exactly one unpaid posted invoice of the right direction.
  2. SUGGESTED — VS matches but the amount differs, OR (no VS) amount + a
                 counterparty/date match. A human confirms these.
  3. UNMATCHED — nothing plausible; raise an INFO alert.

Direction: a bank CREDIT (money in) settles an ISSUED invoice (a customer paid
us); a bank DEBIT (money out) settles a RECEIVED invoice (we paid a supplier).

Reconciliation posts a payment entry through the one authorised ledger path
(ledger_service.post_journal_entry): ISSUED → DEBIT 221 / CREDIT 311;
RECEIVED → DEBIT 321 / CREDIT 221. Unmatching reverses that entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRecord
from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice
from app.schemas.journal_entry import (
    JournalEntryCreate,
    JournalEntryLineCreate,
    ReversalRequest,
)
from app.services.ledger_service import (
    LedgerError,
    post_journal_entry,
    reverse_journal_entry,
)
from app.services.watchdog_service import _upsert_alert

BANK_ACCOUNT = "221"       # Bankovní účty CZK
RECEIVABLE_ACCOUNT = "311"  # Pohledávky z obchodních vztahů
PAYABLE_ACCOUNT = "321"     # Závazky z obchodních vztahů

# How far a transaction date may sit from an invoice's due/DUZP date and still
# be considered a plausible (VS-less) match.
DATE_WINDOW_DAYS = 30


@dataclass
class MatchResult:
    status: str  # "AUTO" | "SUGGESTED" | "NONE"
    invoice: Invoice | None = None
    candidates: list[Invoice] = field(default_factory=list)
    reason: str = ""


def _target_direction(tx: BankTransaction) -> str:
    return "ISSUED" if tx.direction == "CREDIT" else "RECEIVED"


def _normalise(name: str | None) -> str:
    return (name or "").strip().lower()


async def _unpaid_invoices(
    session: AsyncSession, company_id: uuid.UUID, direction: str
) -> list[Invoice]:
    result = await session.execute(
        select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.direction == direction,
            Invoice.status == "posted",
            Invoice.payment_date.is_(None),
        )
    )
    return list(result.scalars().all())


def _counterparty_matches(tx: BankTransaction, inv: Invoice) -> bool:
    tx_name = _normalise(tx.counterparty_name)
    inv_name = _normalise(inv.counterparty_name)
    if tx_name and inv_name and (tx_name in inv_name or inv_name in tx_name):
        return True
    if tx.counterparty_account and inv.counterparty_ico:
        # A payer's account often embeds the IČO; loose containment is enough
        # to raise a suggestion (never an auto-match).
        if inv.counterparty_ico in tx.counterparty_account:
            return True
    return False


def _within_date_window(tx: BankTransaction, inv: Invoice) -> bool:
    reference = inv.due_date or inv.duzp
    return abs((tx.transaction_date - reference).days) <= DATE_WINDOW_DAYS


async def score_candidates(
    session: AsyncSession, company_id: uuid.UUID, tx: BankTransaction
) -> MatchResult:
    """Classify a single transaction against the unpaid invoices."""
    invoices = await _unpaid_invoices(session, company_id, _target_direction(tx))

    # Tier 1/2 — variable symbol.
    if tx.variable_symbol:
        vs_matches = [i for i in invoices if i.variable_symbol == tx.variable_symbol]
        exact = [i for i in vs_matches if i.total_gross_czk == tx.amount_czk]
        if len(exact) == 1:
            return MatchResult("AUTO", invoice=exact[0], candidates=exact,
                               reason="VS + částka souhlasí")
        if vs_matches:
            return MatchResult(
                "SUGGESTED", candidates=vs_matches,
                reason="VS souhlasí, ale částka se liší"
                if not exact else "Více faktur se stejným VS",
            )

    # Tier 3 — no VS hit: amount + counterparty + date window.
    amount_matches = [
        i for i in invoices
        if i.total_gross_czk == tx.amount_czk
        and _counterparty_matches(tx, i)
        and _within_date_window(tx, i)
    ]
    if len(amount_matches) == 1:
        return MatchResult(
            "SUGGESTED", candidates=amount_matches,
            reason="Částka a protistrana souhlasí (bez VS)",
        )
    if amount_matches:
        return MatchResult(
            "SUGGESTED", candidates=amount_matches,
            reason="Více faktur odpovídá částce a protistraně",
        )

    return MatchResult("NONE", reason="Žádná odpovídající faktura")


def _payment_lines(tx: BankTransaction, invoice: Invoice) -> list[JournalEntryLineCreate]:
    amount = tx.amount_czk
    if invoice.direction == "ISSUED":
        # Customer paid us: money into the bank, receivable cleared.
        return [
            JournalEntryLineCreate(
                account_number=BANK_ACCOUNT, side="DEBIT", amount_foreign=amount,
                description=f"Úhrada přijata — {invoice.invoice_number}",
            ),
            JournalEntryLineCreate(
                account_number=RECEIVABLE_ACCOUNT, side="CREDIT", amount_foreign=amount,
                description=f"Zápočet pohledávky — {invoice.counterparty_name}",
            ),
        ]
    # We paid a supplier: money out of the bank, payable cleared.
    return [
        JournalEntryLineCreate(
            account_number=PAYABLE_ACCOUNT, side="DEBIT", amount_foreign=amount,
            description=f"Zápočet závazku — {invoice.counterparty_name}",
        ),
        JournalEntryLineCreate(
            account_number=BANK_ACCOUNT, side="CREDIT", amount_foreign=amount,
            description=f"Úhrada odeslána — {invoice.invoice_number}",
        ),
    ]


async def _resolve_tx_alerts(
    session: AsyncSession, company_id: uuid.UUID, tx_id: uuid.UUID
) -> None:
    await session.execute(
        update(AlertRecord)
        .where(
            AlertRecord.company_id == company_id,
            AlertRecord.source_id == tx_id,
            AlertRecord.category == "RECONCILIATION",
            AlertRecord.status == "open",
        )
        .values(status="resolved", resolution_note="Transakce spárována")
    )


async def reconcile(
    session: AsyncSession,
    tx: BankTransaction,
    invoice: Invoice,
    posted_by: str = "system",
) -> BankTransaction:
    """Post the settlement entry and mark the transaction reconciled."""
    if tx.is_reconciled:
        raise LedgerError("Transakce je již spárována.")
    if _target_direction(tx) != invoice.direction:
        raise LedgerError(
            "Směr transakce neodpovídá směru faktury "
            f"({tx.direction} → {invoice.direction})."
        )

    je_data = JournalEntryCreate(
        entry_date=tx.transaction_date,
        description=f"Úhrada faktury {invoice.invoice_number} — {invoice.counterparty_name}",
        currency="CZK",
        entry_type="STANDARD",
        source_type="BANK_PAYMENT",
        source_id=tx.id,
        lines=_payment_lines(tx, invoice),
    )
    entry = await post_journal_entry(session, tx.company_id, je_data, posted_by)

    tx.matched_invoice_id = invoice.id
    tx.matched_journal_entry_id = entry.id
    tx.is_reconciled = True
    tx.match_status = "MATCHED"
    invoice.payment_date = tx.transaction_date

    await _resolve_tx_alerts(session, tx.company_id, tx.id)
    await session.flush()
    return tx


async def unmatch(
    session: AsyncSession,
    tx: BankTransaction,
    posted_by: str = "system",
    reason: str = "Ruční zrušení párování",
) -> BankTransaction:
    """Reverse the settlement entry and return the transaction to UNMATCHED."""
    if not tx.is_reconciled:
        raise LedgerError("Transakce není spárována.")

    if tx.matched_journal_entry_id:
        await reverse_journal_entry(
            session,
            tx.matched_journal_entry_id,
            tx.company_id,
            ReversalRequest(reversal_date=date.today(), reason=reason),
            posted_by,
        )

    if tx.matched_invoice_id:
        invoice = await session.get(Invoice, tx.matched_invoice_id)
        if invoice:
            invoice.payment_date = None

    tx.matched_invoice_id = None
    tx.matched_journal_entry_id = None
    tx.is_reconciled = False
    tx.match_status = "UNMATCHED"
    await session.flush()
    return tx


async def run_auto_match(
    session: AsyncSession,
    company_id: uuid.UUID,
    posted_by: str = "system",
) -> dict:
    """Match every unreconciled transaction; auto-post the certain ones,
    raise alerts for the ambiguous and the orphaned."""
    result = await session.execute(
        select(BankTransaction).where(
            BankTransaction.company_id == company_id,
            BankTransaction.is_reconciled.is_(False),
        )
    )
    transactions = list(result.scalars().all())

    summary = {"auto_matched": 0, "suggested": 0, "unmatched": 0}

    for tx in transactions:
        match = await score_candidates(session, company_id, tx)

        if match.status == "AUTO" and match.invoice is not None:
            try:
                await reconcile(session, tx, match.invoice, posted_by)
                summary["auto_matched"] += 1
                continue
            except LedgerError as exc:
                # e.g. no open fiscal period for the transaction date — downgrade
                # to a suggestion so the import never fails wholesale.
                match = MatchResult(
                    "SUGGESTED", candidates=[match.invoice],
                    reason=f"Automatické zaúčtování selhalo: {exc}",
                )

        if match.status == "SUGGESTED":
            tx.match_status = "SUGGESTED"
            names = ", ".join(i.invoice_number for i in match.candidates[:5])
            await _upsert_alert(
                session, company_id,
                rule_code="BANK_TX_SUGGESTED",
                severity="WARNING",
                category="RECONCILIATION",
                title=f"Návrh spárování — {tx.amount_czk} Kč {tx.transaction_date}",
                detail=(
                    f"Bankovní transakce ({tx.direction}, {tx.amount_czk} Kč, "
                    f"VS {tx.variable_symbol or '—'}) pravděpodobně patří k fakturám: "
                    f"{names}. Důvod: {match.reason}."
                ),
                suggested_action="Potvrďte navrhované spárování na stránce Banka.",
                source_type="BANK_TRANSACTION",
                source_id=tx.id,
            )
            summary["suggested"] += 1
        else:
            tx.match_status = "UNMATCHED"
            await _upsert_alert(
                session, company_id,
                rule_code="BANK_TX_UNMATCHED",
                severity="INFO",
                category="RECONCILIATION",
                title=f"Nespárovaná transakce — {tx.amount_czk} Kč {tx.transaction_date}",
                detail=(
                    f"Bankovní transakce ({tx.direction}, {tx.amount_czk} Kč, "
                    f"VS {tx.variable_symbol or '—'}, {tx.counterparty_name or '—'}) "
                    f"nemá odpovídající otevřenou fakturu."
                ),
                suggested_action="Spárujte ručně nebo vytvořte chybějící fakturu.",
                source_type="BANK_TRANSACTION",
                source_id=tx.id,
            )
            summary["unmatched"] += 1

    await session.flush()
    return summary
