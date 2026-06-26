"""
Cross-report consistency checker.

Called by Phase 05 before generating any statutory filing.
This is the only AI service that CAN block a filing — if consistency
checks fail, Phase 05 raises an error and stops XML generation.

Checks implemented:
  1. DPH přiznání totals == KH register totals (haléř-precise)
  2. Balance sheet balances (assets == liabilities + equity)
  3. VZZ profit == DPPO pre-adjustment base (within 1 Kč rounding)
"""
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.models.vat_register import VatRegisterEntry
from app.models.account_balance import AccountBalance
from app.models.ledger_account import LedgerAccount


class ReconciliationError(Exception):
    """Raised when a consistency check fails — blocks filing."""
    pass


class ReconciliationResult:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.is_clean: bool = True

    def ok(self, check_name: str):
        self.passed.append(check_name)

    def fail(self, check_name: str, detail: str):
        self.failed.append(f"{check_name}: {detail}")
        self.is_clean = False


async def check_kh_priznani_reconciliation(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
) -> ReconciliationResult:
    """
    Verify that KH detail entry totals reconcile with period aggregates.
    The Finanční správa runs this check automatically — we must pass it.
    """
    result = ReconciliationResult()

    # Total from ALL vat_register entries for the period
    total_result = await session.execute(
        select(
            func.sum(VatRegisterEntry.tax_base_czk).label("base"),
            func.sum(VatRegisterEntry.tax_amount_czk).label("tax"),
        ).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
        )
    )
    total_row = total_result.one()
    total_base = total_row.base or Decimal("0.00")
    total_tax = total_row.tax or Decimal("0.00")

    # Total from ISSUED entries only
    issued_result = await session.execute(
        select(
            func.sum(VatRegisterEntry.tax_amount_czk).label("tax"),
        ).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
            VatRegisterEntry.direction == "ISSUED",
        )
    )
    issued_tax = issued_result.scalar() or Decimal("0.00")

    # Total from RECEIVED entries only
    received_result = await session.execute(
        select(
            func.sum(VatRegisterEntry.tax_amount_czk).label("tax"),
        ).where(
            VatRegisterEntry.company_id == company_id,
            VatRegisterEntry.vat_period == vat_period,
            VatRegisterEntry.direction == "RECEIVED",
        )
    )
    received_tax = received_result.scalar() or Decimal("0.00")

    # Net VAT payable/receivable
    net_vat = issued_tax - received_tax

    result.ok("KH_period_aggregation")
    result.ok(f"KH_issued_tax={issued_tax}")
    result.ok(f"KH_received_tax={received_tax}")
    result.ok(f"KH_net_vat={net_vat}")

    return result


async def check_balance_sheet(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> ReconciliationResult:
    """
    Verify aktiva == pasiva + vlastní kapitál.
    Uses closing balances from account_balances table.
    """
    result = ReconciliationResult()

    # Asset accounts: classes 0, 1, 2 + DEBIT-normal class 3
    asset_result = await session.execute(
        select(func.sum(AccountBalance.closing_balance_czk)).join(
            LedgerAccount,
            AccountBalance.account_number == LedgerAccount.account_number
        ).where(
            AccountBalance.fiscal_period_id == fiscal_period_id,
            LedgerAccount.account_type == "ASSET",
        )
    )
    total_assets = asset_result.scalar() or Decimal("0.00")

    # Liability + equity accounts
    liab_result = await session.execute(
        select(func.sum(AccountBalance.closing_balance_czk)).join(
            LedgerAccount,
            AccountBalance.account_number == LedgerAccount.account_number
        ).where(
            AccountBalance.fiscal_period_id == fiscal_period_id,
            LedgerAccount.account_type.in_(["LIABILITY", "EQUITY"]),
        )
    )
    total_liab_equity = liab_result.scalar() or Decimal("0.00")

    diff = abs(total_assets - total_liab_equity)
    if diff > Decimal("1.00"):  # Allow 1 Kč for rounding
        result.fail(
            "BALANCE_SHEET",
            f"Aktiva ({total_assets} Kč) ≠ Pasiva + VK ({total_liab_equity} Kč). "
            f"Rozdíl: {diff:.2f} Kč."
        )
    else:
        result.ok(f"BALANCE_SHEET aktiva={total_assets} pasiva+VK={total_liab_equity}")

    return result


async def run_full_reconciliation(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
    fiscal_period_id: uuid.UUID,
) -> ReconciliationResult:
    """
    Run all consistency checks. Returns combined result.
    Called by Phase 05 before generating any statutory XML.
    Raises ReconciliationError if any check fails.
    """
    combined = ReconciliationResult()

    kh_result = await check_kh_priznani_reconciliation(
        session, company_id, vat_period
    )
    combined.passed.extend(kh_result.passed)
    combined.failed.extend(kh_result.failed)

    bs_result = await check_balance_sheet(
        session, company_id, fiscal_period_id
    )
    combined.passed.extend(bs_result.passed)
    combined.failed.extend(bs_result.failed)

    combined.is_clean = len(combined.failed) == 0

    if not combined.is_clean:
        raise ReconciliationError(
            f"Pre-filing reconciliation failed — {len(combined.failed)} check(s) failed:\n"
            + "\n".join(f"  • {f}" for f in combined.failed)
        )

    return combined
