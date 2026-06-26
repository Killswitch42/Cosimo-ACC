"""
Czech statutory compliance rules — seeded into compliance_rules table.
"""

from sqlalchemy import select

from app.models.compliance_rule import ComplianceRule

COMPLIANCE_RULES = [
    {
        "code": "MISSING_DIC_10000",
        "name_cz": "Přijatá faktura nad 10 000 Kč bez DIČ",
        "name_en": "Received invoice over 10 000 CZK without VAT ID",
        "description": "Received invoice over 10 000 Kč must include supplier DIČ.",
        "category": "COMPLIANCE",
        "default_severity": "BLOCKER",
        "is_active": True,
    },
    {
        "code": "INVALID_DIC_FORMAT",
        "name_cz": "Neplatný formát DIČ",
        "name_en": "Invalid VAT ID format",
        "description": "Supplier VAT ID does not follow Czech or EU VAT formatting rules.",
        "category": "COMPLIANCE",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "DPH_MONTHLY_REMINDER",
        "name_cz": "Připomenutí DPH přiznání",
        "name_en": "VAT return reminder",
        "description": "Reminder for upcoming monthly VAT return deadline.",
        "category": "DEADLINE",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "DPPO_ANNUAL_REMINDER",
        "name_cz": "Připomenutí DPPO podání",
        "name_en": "Corporate tax return reminder",
        "description": "Reminder for annual corporate income tax return.",
        "category": "DEADLINE",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "UCETNI_ZAVERKA_REMINDER",
        "name_cz": "Připomenutí účetní závěrky",
        "name_en": "Annual financial statements reminder",
        "description": "Reminder for preparing annual financial statements.",
        "category": "DEADLINE",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "AI_CLASSIFICATION_SUGGESTION",
        "name_cz": "AI účetní klasifikace",
        "name_en": "AI accounting classification",
        "description": "AI-assisted suggestion for transaction account classification.",
        "category": "CLASSIFICATION",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "KH_PRIZNANI_MISMATCH",
        "name_cz": "Neshoda mezi KH a přiznáním",
        "name_en": "KH register and VAT return mismatch",
        "description": "Cross-report consistency check failed between KH register and VAT return totals.",
        "category": "CONSISTENCY",
        "default_severity": "BLOCKER",
        "is_active": True,
    },
    {
        "code": "BALANCE_SHEET_INCONSISTENCY",
        "name_cz": "Neshoda v rozvaze",
        "name_en": "Balance sheet inconsistency",
        "description": "Balance sheet check failed for the fiscal period.",
        "category": "CONSISTENCY",
        "default_severity": "BLOCKER",
        "is_active": True,
    },
    {
        "code": "VAT_SUPPORT_MISSING",
        "name_cz": "Chybí podklady k DPH",
        "name_en": "Missing VAT support documents",
        "description": "Required supporting documents for VAT filing are missing.",
        "category": "VAT",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "LEDGER_ENTRY_WARNING",
        "name_cz": "Varování k účetnímu zápisu",
        "name_en": "Ledger entry warning",
        "description": "Potential issue detected in a ledger entry.",
        "category": "LEDGER",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "DEADLINE_OVERDUE",
        "name_cz": "Překročený termín",
        "name_en": "Overdue deadline",
        "description": "A statutory filing deadline has passed.",
        "category": "DEADLINE",
        "default_severity": "BLOCKER",
        "is_active": True,
    },
    {
        "code": "DEADLINE_WARNING",
        "name_cz": "Upozornění na termín",
        "name_en": "Upcoming deadline warning",
        "description": "A statutory filing deadline is approaching.",
        "category": "DEADLINE",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "NOTIFICATION_CALENDAR",
        "name_cz": "Kalendář termínů",
        "name_en": "Deadline calendar notification",
        "description": "General deadline calendar reminder.",
        "category": "DEADLINE",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "AI_ASSISTED_COMPLIANCE_REVIEW",
        "name_cz": "AI asistovaná kontrola shody",
        "name_en": "AI-assisted compliance review",
        "description": "AI-assisted review of an invoice or transaction for compliance.",
        "category": "COMPLIANCE",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "DPH_PERIOD_REVIEW",
        "name_cz": "Kontrola období DPH",
        "name_en": "VAT period review",
        "description": "Review of a VAT filing period for completeness.",
        "category": "VAT",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "KH_SECTION_FLAG",
        "name_cz": "KH sekce vyžadující detail",
        "name_en": "KH section detail required",
        "description": "A KH entry requires a detailed report line.",
        "category": "VAT",
        "default_severity": "INFO",
        "is_active": True,
    },
    {
        "code": "ACCOUNT_PAIRING_REVIEW",
        "name_cz": "Kontrola spárování účtů",
        "name_en": "Account pairing review",
        "description": "Review of unusual debit/credit account pairings.",
        "category": "CLASSIFICATION",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "EXPENSE_NONDEDUCTIBLE",
        "name_cz": "Nedaňový výdaj",
        "name_en": "Non-deductible expense",
        "description": "An expense may be non-deductible under Czech tax law.",
        "category": "COMPLIANCE",
        "default_severity": "WARNING",
        "is_active": True,
    },
    {
        "code": "DOCUMENT_RETENTION_ALERT",
        "name_cz": "Upozornění na archivaci",
        "name_en": "Document retention alert",
        "description": "Alert for statutory document retention requirements.",
        "category": "COMPLIANCE",
        "default_severity": "INFO",
        "is_active": True,
    },
]


async def seed_compliance_rules(session):
    existing_codes = set(
        await session.scalars(
            select(ComplianceRule.code).where(ComplianceRule.code.in_([rule["code"] for rule in COMPLIANCE_RULES]))
        )
    )
    inserted = 0
    for rule in COMPLIANCE_RULES:
        if rule["code"] in existing_codes:
            continue
        session.add(ComplianceRule(**rule))
        inserted += 1
    await session.flush()
    print(f"✓ Compliance rules seeded: {len(COMPLIANCE_RULES)} rules ({inserted} new)")
