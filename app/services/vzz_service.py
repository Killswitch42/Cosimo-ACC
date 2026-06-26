"""
VZZ (výkaz zisku a ztráty — profit and loss statement) line mapping.

Per vyhláška 500/2002 Sb., příloha č. 2 — zkrácený rozsah, druhové členění.
"""
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ledger_service import get_trial_balance
import uuid


# Revenue lines (class 6, CREDIT-normal) and expense lines (class 5, DEBIT-normal)
VZZ_LINE_MAP: dict[str, list[str]] = {
    "I":   ["601", "602", "604"],           # Tržby z prodeje výrobků, služeb, zboží
    "A":   ["504"],                          # Náklady vynaložené na prodané zboží
    "II":  ["611", "612", "613", "614"],     # Změna stavu zásob vlastní činnosti
    "III": ["621", "622", "623", "624"],     # Aktivace
    "B":   ["501", "502", "503"],            # Spotřeba materiálu a energie
    "C":   ["511", "512", "513", "518"],     # Služby
    "D":   ["521", "522", "523", "524", "525", "527", "528"],  # Osobní náklady
    "E":   ["551", "552", "554", "555", "557", "558", "559"],  # Odpisy a úpravy hodnot
    "IV":  ["641", "642"],                   # Tržby z prodaného DHM a materiálu
    "F":   ["541", "542"],                   # ZC prodaného DHM a materiálu
    "V":   ["644", "646", "648"],            # Ostatní provozní výnosy
    "G":   ["531", "532", "538",
            "543", "544", "545", "546", "548", "549"],  # Ostatní provozní náklady
    "VI":  ["662", "663", "664", "665", "666", "667", "668"],  # Finanční výnosy
    "J":   ["562", "563", "564", "566", "567", "568", "569"],  # Finanční náklady
    "VII": ["661"],                          # Ostatní finanční výnosy (doplňkové)
    "L":   ["591", "592"],                   # Daň z příjmů splatná
    "M":   ["593"],                          # Daň z příjmů odložená
}

REVENUE_LINES = {"I", "II", "III", "IV", "V", "VI", "VII"}


async def generate_vzz(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> dict:
    """
    Generate the VZZ for a fiscal period using period movements.
    Revenue accounts (class 6): use period_credit_czk.
    Expense accounts (class 5): use period_debit_czk.
    """
    balances = await get_trial_balance(session, company_id, fiscal_period_id)
    debit_by_account  = {b.account_number: b.period_debit_czk  for b in balances}
    credit_by_account = {b.account_number: b.period_credit_czk for b in balances}

    def sum_prefixes(prefixes: list[str], use_credit: bool) -> Decimal:
        source = credit_by_account if use_credit else debit_by_account
        total = Decimal("0.00")
        for acct, amount in source.items():
            if any(acct.startswith(p) for p in prefixes):
                total += amount
        return total

    lines: dict[str, Decimal] = {}
    for line, prefixes in VZZ_LINE_MAP.items():
        lines[line] = sum_prefixes(prefixes, use_credit=(line in REVENUE_LINES))

    total_revenue = sum(lines[l] for l in REVENUE_LINES if l in lines)
    income_tax = lines.get("L", Decimal(0)) + lines.get("M", Decimal(0))
    total_expense_excl_tax = sum(
        v for k, v in lines.items()
        if k not in REVENUE_LINES and k not in ("L", "M")
    )
    profit_before_tax = total_revenue - total_expense_excl_tax
    net_profit_loss   = profit_before_tax - income_tax

    return {
        "lines": lines,
        "total_revenue": total_revenue,
        "total_expense_excl_tax": total_expense_excl_tax,
        "profit_before_tax": profit_before_tax,
        "income_tax_current": lines.get("L", Decimal(0)),
        "income_tax_deferred": lines.get("M", Decimal(0)),
        "net_profit_loss": net_profit_loss,
    }
