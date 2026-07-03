"""
DPPO — daň z příjmů právnických osob (corporate income tax).

A *simplified* calculation: it takes the accounting profit before tax from the
VZZ, adds back the non-deductible expenses this system can identify from the
chart of accounts (§ 25 ZDP), rounds the base down to whole thousands, and
applies the statutory rate (21 % from 2024, 19 % before).

This is a decision-support figure, not a filed return. The official DPPO
(DPDPPO) XML — with all §23 adjustments, tax loss carry-forwards, reliefs and
advance payments — is deferred. Every simplification is surfaced in the output
so an accountant can see exactly what was and wasn't accounted for.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ledger_service import get_trial_balance
from app.services.vzz_service import generate_vzz

# Non-deductible expense accounts we can recognise (flagged in the seeded chart
# of accounts). Deliberately a small, auditable subset — not the full §25 list.
DPPO_NONDEDUCTIBLE_ACCOUNTS: dict[str, str] = {
    "513": "Náklady na reprezentaci (§ 25 odst. 1 písm. t) ZDP)",
    "543": "Dary (§ 25 odst. 1 písm. t) ZDP)",
}


def dppo_rate(year: int) -> Decimal:
    """Statutory DPPO rate for a given tax year."""
    return Decimal("21") if year >= 2024 else Decimal("19")


async def compute_dppo(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
    year: int,
) -> dict:
    """Compute a simplified DPPO estimate for a fiscal period."""
    vzz = await generate_vzz(session, company_id, fiscal_period_id)
    profit_before_tax: Decimal = vzz["profit_before_tax"]

    balances = await get_trial_balance(session, company_id, fiscal_period_id)
    debit_by_account = {b.account_number: b.period_debit_czk for b in balances}

    adjustments: list[dict] = []
    total_adjustments = Decimal("0.00")
    for prefix, label in DPPO_NONDEDUCTIBLE_ACCOUNTS.items():
        amount = sum(
            (amt for acct, amt in debit_by_account.items() if acct.startswith(prefix)),
            Decimal("0.00"),
        )
        if amount:
            adjustments.append({"account": prefix, "label": label, "amount": amount})
            total_adjustments += amount

    tax_base = profit_before_tax + total_adjustments

    rate = dppo_rate(year)
    if tax_base > 0:
        # Základ daně se zaokrouhluje na celé tisíce Kč dolů (§ 20 odst. 11 ZDP).
        rounded_tax_base = (tax_base / 1000).to_integral_value(ROUND_FLOOR) * 1000
        # Daň se zaokrouhluje na celé koruny nahoru (§ 146 daňového řádu).
        tax = (rounded_tax_base * rate / 100).quantize(Decimal("1"), ROUND_CEILING)
    else:
        rounded_tax_base = Decimal("0")
        tax = Decimal("0")

    return {
        "year": year,
        "profit_before_tax": profit_before_tax,
        "adjustments": adjustments,
        "total_adjustments": total_adjustments,
        "tax_base": tax_base,
        "rounded_tax_base": rounded_tax_base,
        "rate": rate,
        "tax": tax,
        "net_profit_after_tax": profit_before_tax - tax,
        "is_simplified": True,
    }
