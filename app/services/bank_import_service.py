"""
Bank statement import — parse CSV / MT940 into BankTransaction records.

Phase 07. Two ingestion formats are supported without adding a dependency:

  * CSV — a canonical column mapping that covers common Czech-bank exports
    (FIO-style headers are recognised explicitly). Header names are matched
    case-insensitively against a set of known aliases.
  * MT940 — the SWIFT statement format Czech banks offer for download. A
    focused parser handles the tags we need: :25: (account), :61: (statement
    line, amount + debit/credit mark) and :86: (details, incl. variable symbol).

Parsers return plain dicts; `import_transactions` deduplicates and persists.
The matching engine (bank_matching_service) runs separately after import.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_transaction import BankTransaction


class BankImportError(Exception):
    """Raised when a statement cannot be parsed."""


# ── Column aliases for CSV (lower-cased, stripped) ──────────────────────────
_CSV_ALIASES = {
    "transaction_date": {"date", "datum", "datum provedení", "datum zaúčtování", "value date"},
    "amount": {"amount", "částka", "castka", "objem"},
    "variable_symbol": {"vs", "variabilní symbol", "variabilni symbol", "variable symbol"},
    "counterparty_account": {"protiúčet", "protiucet", "counterparty account", "účet protistrany"},
    "counterparty_name": {"název protiúčtu", "nazev protiuctu", "counterparty", "counterparty name", "protistrana"},
    "description": {"zpráva pro příjemce", "zprava", "poznámka", "poznamka", "message", "description", "popis"},
}


def _clean_amount(raw: str) -> Decimal:
    """Parse a Czech/'.'-or-','-decimal amount, stripping spaces and NBSPs."""
    cleaned = (
        raw.replace("\xa0", "")
        .replace(" ", "")
        .replace("Kč", "")
        .replace("CZK", "")
        .strip()
    )
    # If both separators present, assume '.' thousands + ',' decimal (cs format).
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise BankImportError(f"Unparseable amount: {raw!r}") from exc


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise BankImportError(f"Unrecognised date format: {raw!r}")


def _build_alias_map(header: list[str]) -> dict[str, int]:
    """Map canonical field → column index using the alias table."""
    index_by_field: dict[str, int] = {}
    for col_idx, name in enumerate(header):
        key = name.strip().lower()
        for field, aliases in _CSV_ALIASES.items():
            if key in aliases and field not in index_by_field:
                index_by_field[field] = col_idx
    return index_by_field


def parse_csv(
    content: bytes,
    bank_account_number: str,
    import_source: str = "MANUAL_CSV",
) -> list[dict]:
    """Parse a CSV bank export into normalised transaction dicts.

    A positive amount is treated as CREDIT (money in); negative as DEBIT
    (money out). ``amount_czk`` in the result is always the absolute value.
    """
    text = content.decode("utf-8-sig", errors="replace")
    # Sniff the delimiter (Czech exports use ';' as often as ',').
    sample = text[:2048]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise BankImportError("CSV file is empty.")

    header = rows[0]
    alias_map = _build_alias_map(header)
    if "transaction_date" not in alias_map or "amount" not in alias_map:
        raise BankImportError(
            "CSV header must contain recognisable date and amount columns. "
            f"Detected columns: {header}"
        )

    def cell(row: list[str], field: str) -> str | None:
        idx = alias_map.get(field)
        if idx is None or idx >= len(row):
            return None
        value = row[idx].strip()
        return value or None

    parsed: list[dict] = []
    for row in rows[1:]:
        raw_amount = cell(row, "amount")
        raw_date = cell(row, "transaction_date")
        if not raw_amount or not raw_date:
            continue
        amount = _clean_amount(raw_amount)
        parsed.append(
            {
                "bank_account_number": bank_account_number,
                "transaction_date": _parse_date(raw_date),
                "amount_czk": abs(amount),
                "direction": "CREDIT" if amount >= 0 else "DEBIT",
                "variable_symbol": cell(row, "variable_symbol"),
                "counterparty_account": cell(row, "counterparty_account"),
                "counterparty_name": cell(row, "counterparty_name"),
                "description": cell(row, "description"),
                "import_source": import_source,
            }
        )
    if not parsed:
        raise BankImportError("CSV contained no data rows with a date and amount.")
    return parsed


# ── MT940 ───────────────────────────────────────────────────────────────────
# :61: line layout: <value date YYMMDD>[entry date MMDD]<D|C><amount>N...
_MT940_61 = re.compile(
    r":61:(?P<vdate>\d{6})(?P<edate>\d{4})?(?P<mark>[DC])(?P<amount>[\d,]+)"
)
_MT940_VS = re.compile(r"(?:/VS/|\bVS[:\s]?)(\d{1,10})")


def parse_mt940(content: bytes, import_source: str = "MT940") -> list[dict]:
    """Parse an MT940 statement into normalised transaction dicts."""
    text = content.decode("utf-8", errors="replace")
    # Join continuation lines; MT940 tags start with ':'.
    account_number = ""
    parsed: list[dict] = []
    current: dict | None = None

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.rstrip()
        if line.startswith(":25:"):
            account_number = line[4:].strip().split("/")[-1]
        elif line.startswith(":61:"):
            m = _MT940_61.match(line)
            if not m:
                continue
            if current:
                parsed.append(current)
            vdate = datetime.strptime(m.group("vdate"), "%y%m%d").date()
            amount = _clean_amount(m.group("amount"))
            current = {
                "bank_account_number": account_number,
                "transaction_date": vdate,
                "amount_czk": abs(amount),
                # In MT940 'C' = credit (money in), 'D' = debit (money out).
                "direction": "CREDIT" if m.group("mark") == "C" else "DEBIT",
                "variable_symbol": None,
                "counterparty_account": None,
                "counterparty_name": None,
                "description": None,
                "import_source": import_source,
            }
        elif line.startswith(":86:") and current is not None:
            detail = line[4:].strip()
            current["description"] = detail
            vs = _MT940_VS.search(detail)
            if vs:
                current["variable_symbol"] = vs.group(1)
        elif current is not None and not line.startswith(":") and line:
            # Continuation of the :86: detail line.
            current["description"] = f"{current.get('description') or ''} {line}".strip()

    if current:
        parsed.append(current)
    if not parsed:
        raise BankImportError("MT940 file contained no :61: transaction lines.")
    return parsed


async def import_transactions(
    session: AsyncSession,
    company_id: uuid.UUID,
    rows: list[dict],
    import_source: str,
) -> list[BankTransaction]:
    """Persist parsed rows, skipping duplicates already in the database.

    A duplicate is the same (company, account, date, amount, VS, counterparty
    account). Re-importing the same statement is therefore idempotent.
    """
    created: list[BankTransaction] = []
    for row in rows:
        existing = await session.scalar(
            select(BankTransaction).where(
                BankTransaction.company_id == company_id,
                BankTransaction.bank_account_number == row["bank_account_number"],
                BankTransaction.transaction_date == row["transaction_date"],
                BankTransaction.amount_czk == row["amount_czk"],
                BankTransaction.direction == row["direction"],
                BankTransaction.variable_symbol.is_not_distinct_from(row.get("variable_symbol")),
                BankTransaction.counterparty_account.is_not_distinct_from(
                    row.get("counterparty_account")
                ),
            )
        )
        if existing:
            continue
        tx = BankTransaction(
            id=uuid.uuid4(),
            company_id=company_id,
            bank_account_number=row["bank_account_number"],
            transaction_date=row["transaction_date"],
            amount_czk=row["amount_czk"],
            direction=row["direction"],
            counterparty_name=row.get("counterparty_name"),
            counterparty_account=row.get("counterparty_account"),
            variable_symbol=row.get("variable_symbol"),
            description=row.get("description"),
            import_source=row.get("import_source", import_source),
            is_reconciled=False,
            match_status="UNMATCHED",
        )
        session.add(tx)
        created.append(tx)
    await session.flush()
    return created
