"""
DUZP service for VAT period resolution and invoice-date warnings.
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class DuzpValidationResult:
    is_valid: bool
    vat_period: str
    warnings: list[str]
    errors: list[str]


ALLOWED_VAT_RATES = {0, 12, 21}


def resolve_vat_period(duzp: date) -> str:
    return duzp.strftime("%Y-%m")


def validate_duzp(
    duzp: date,
    invoice_date: date,
    direction: str,
) -> DuzpValidationResult:
    warnings = []
    errors = []
    today = date.today()

    if duzp > today:
        warnings.append(f"DUZP {duzp} is in the future. Verify the date is correct.")

    if direction == "ISSUED":
        max_invoice_date = duzp + timedelta(days=15)
        if invoice_date > max_invoice_date:
            warnings.append(
                f"Invoice date {invoice_date} is more than 15 days after DUZP {duzp}. "
                f"Maximum invoice date for this DUZP: {max_invoice_date}."
            )

    if direction == "RECEIVED":
        cutoff = date(today.year - 3, today.month, today.day)
        if duzp < cutoff:
            errors.append(
                f"DUZP {duzp} is more than 3 years ago. "
                f"The right to deduct input VAT has likely expired."
            )

    return DuzpValidationResult(
        is_valid=len(errors) == 0,
        vat_period=resolve_vat_period(duzp),
        warnings=warnings,
        errors=errors,
    )


def validate_vat_rate(vat_rate: int | float, supply_description: str = "") -> list[str]:
    errors = []
    rate_int = int(vat_rate)
    if rate_int not in ALLOWED_VAT_RATES:
        errors.append(
            f"VAT rate {vat_rate}% is not a valid Czech DPH rate. "
            f"Valid rates from 2024: 0%, 12%, 21%."
        )
    return errors
