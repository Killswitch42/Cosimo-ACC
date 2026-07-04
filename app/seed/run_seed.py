"""
Run this once after migrations to populate the chart of accounts
and create the Medici Analytica company record.

Usage:
    python -m app.seed.run_seed
"""

import asyncio
from datetime import date
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.company import Company
from app.models.fiscal_period import FiscalPeriod
from app.models.ledger_account import LedgerAccount
from app.models.user import User
from app.seed.chart_of_accounts import get_full_chart
from app.seed.compliance_rules import seed_compliance_rules
from app.services.auth_service import hash_password


async def seed_company(session: AsyncSession) -> Company:
    existing = await session.scalar(
        select(Company)
        .where(Company.name == settings.company_name)
        .where(Company.is_active.is_(True))
        .limit(1)
    )
    if existing:
        print(f"✓ Company exists: {existing.name} ({existing.id})")
        return existing

    company = Company(
        id=uuid.uuid4(),
        name=settings.company_name,
        ico=settings.company_ico or None,
        dic=settings.company_dic or None,
        registered_office=settings.company_registered_office or None,
        legal_form="s.r.o.",
        fiscal_year_start_month=settings.fiscal_year_start_month,
        is_vat_payer=True,
        vat_filing_period="monthly",
        is_active=True,
    )
    session.add(company)
    await session.flush()
    print(f"✓ Company created: {company.name} ({company.id})")
    return company


async def seed_fiscal_period(
    session: AsyncSession, company: Company
) -> FiscalPeriod:
    current_year = date.today().year
    existing = await session.scalar(
        select(FiscalPeriod)
        .where(FiscalPeriod.company_id == company.id)
        .where(FiscalPeriod.label == str(current_year))
        .where(FiscalPeriod.period_type == "annual")
        .limit(1)
    )
    if existing:
        print(f"✓ Fiscal period exists: {existing.label} ({existing.status})")
        return existing

    period = FiscalPeriod(
        id=uuid.uuid4(),
        company_id=company.id,
        label=str(current_year),
        period_type="annual",
        date_start=date(current_year, 1, 1),
        date_end=date(current_year, 12, 31),
        status="open",
        is_current=True,
    )
    session.add(period)
    await session.flush()
    print(f"✓ Fiscal period created: {period.label} ({period.status})")
    return period


async def seed_chart_of_accounts(session: AsyncSession) -> None:
    accounts = get_full_chart()
    account_numbers = [account["account_number"] for account in accounts]
    existing_numbers = set(
        await session.scalars(
            select(LedgerAccount.account_number).where(
                LedgerAccount.account_number.in_(account_numbers)
            )
        )
    )
    missing_accounts = [
        account for account in accounts if account["account_number"] not in existing_numbers
    ]
    if not missing_accounts:
        print(f"✓ Chart of accounts exists: {len(existing_numbers)} accounts")
        return

    for data in missing_accounts:
        account = LedgerAccount(**data)
        session.add(account)
    await session.flush()
    print(f"✓ Chart of accounts seeded: {len(missing_accounts)} new accounts")


async def seed_admin_user(session: AsyncSession, company: Company) -> None:
    existing = await session.scalar(
        select(User).where(User.email == settings.admin_email).limit(1)
    )
    if existing:
        print(f"✓ Admin user exists: {existing.email}")
        return

    admin = User(
        company_id=company.id,
        email=settings.admin_email,
        full_name="Administrator",
        hashed_password=hash_password(settings.admin_password),
        role="admin",
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    print(f"✓ Admin user created: {admin.email}")
    if settings.admin_password_is_default:
        print("  ⚠ Using the default password — CHANGE IT after first login "
              "(or set ADMIN_PASSWORD in .env before seeding).")


async def run() -> None:
    async with async_session_factory() as session:
        async with session.begin():
            company = await seed_company(session)
            await seed_fiscal_period(session, company)
            await seed_chart_of_accounts(session)
            await seed_compliance_rules(session)
            await seed_admin_user(session, company)
    print("\n✓ Seed complete. Medici Analytica is ready.")


if __name__ == "__main__":
    asyncio.run(run())
