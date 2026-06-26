"""
ARES validation service.
"""

from dataclasses import dataclass
from typing import Optional

import httpx

ARES_BASE_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"
_ares_cache: dict[str, dict] = {}


@dataclass
class AresValidationResult:
    is_valid: bool
    ico_found: bool
    dic_matches: bool
    is_vat_payer: bool
    registered_name: Optional[str]
    warnings: list[str]
    errors: list[str]


async def validate_counterparty(
    ico: Optional[str],
    dic: Optional[str],
    counterparty_name: Optional[str] = None,
) -> AresValidationResult:
    warnings = []
    errors = []

    if not ico and not dic:
        warnings.append("No IČO or DIČ provided for counterparty. ARES validation skipped.")
        return AresValidationResult(True, False, False, False, None, warnings, errors)

    if not ico and dic and dic.upper().startswith("CZ"):
        ico = dic[2:]

    if dic and not dic.upper().startswith("CZ"):
        warnings.append(f"Counterparty DIČ {dic} is not a Czech DIČ. ARES skipped.")
        return AresValidationResult(True, False, True, True, None, warnings, errors)

    if ico in _ares_cache:
        ares_data = _ares_cache[ico]
    else:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{ARES_BASE_URL}/ekonomicke-subjekty/{ico}")
                if response.status_code == 404:
                    errors.append(f"IČO {ico} not found in ARES.")
                    return AresValidationResult(False, False, False, False, None, warnings, errors)
                response.raise_for_status()
                ares_data = response.json()
                _ares_cache[ico] = ares_data
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            warnings.append(f"ARES API unavailable: {exc}. Manual verification required.")
            return AresValidationResult(True, False, False, False, None, warnings, errors)

    registered_name = ares_data.get("obchodniJmeno", "")
    ares_dic = ares_data.get("dic", "")
    dic_matches = False
    if dic:
        dic_matches = ares_dic.upper() == dic.upper()
        if not dic_matches:
            errors.append(f"DIČ mismatch: provided {dic}, ARES shows {ares_dic}.")

    is_vat_payer = bool(ares_data.get("datumRegistraceDph"))
    if not is_vat_payer and dic:
        warnings.append(f"Counterparty IČO {ico} ({registered_name}) is not an active VAT payer in ARES.")

    if counterparty_name and registered_name and not _names_roughly_match(
        counterparty_name, registered_name
    ):
        warnings.append(
            f"Counterparty name '{counterparty_name}' differs from ARES '{registered_name}'."
        )

    return AresValidationResult(
        len(errors) == 0,
        True,
        dic_matches,
        is_vat_payer,
        registered_name,
        warnings,
        errors,
    )


def _names_roughly_match(name_a: str, name_b: str) -> bool:
    def normalise(value: str) -> str:
        return (
            value.lower()
            .replace("s. r. o.", "sro")
            .replace("s.r.o.", "sro")
            .replace("a. s.", "as")
            .replace("a.s.", "as")
            .replace(" ", "")
            .replace(",", "")
            .replace(".", "")
        )

    return normalise(name_a)[:15] == normalise(name_b)[:15]


def format_dic(ico: str) -> str:
    return f"CZ{ico}"


def validate_dic_format(dic: str) -> list[str]:
    errors = []
    if not dic:
        return ["DIČ is empty."]

    dic_upper = dic.upper()
    if dic_upper.startswith("CZ"):
        numeric_part = dic_upper[2:]
        if not numeric_part.isdigit():
            errors.append(f"Czech DIČ {dic}: the part after 'CZ' must be digits only.")
        if not (8 <= len(numeric_part) <= 10):
            errors.append(
                f"Czech DIČ {dic}: expected 8-10 digits after 'CZ', got {len(numeric_part)}."
            )
    else:
        eu_countries = {
            "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR",
            "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
            "SE", "SI", "SK", "GB"
        }
        country_code = dic_upper[:2]
        if not (len(dic_upper) >= 4 and country_code.isalpha()):
            errors.append(f"DIČ {dic} must start with a 2-letter country code followed by digits/letters.")
        elif country_code not in eu_countries:
            errors.append(f"DIČ {dic} starts with invalid country code '{country_code}'.")
    return errors
