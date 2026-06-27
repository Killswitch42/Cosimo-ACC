import os
from datetime import date

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://medici:medici_dev_pass@localhost:5432/medici_accounting",
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.database import async_session_factory, engine
from app.main import app
from app.models.company import Company
from app.models.fiscal_period import FiscalPeriod


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def phase02_open_period():
    await engine.dispose()
    async with async_session_factory() as session:
        async with session.begin():
            company_result = await session.execute(
                select(Company).order_by(Company.created_at).limit(1)
            )
            company = company_result.scalar_one_or_none()
            if not company:
                return

            await session.execute(
                FiscalPeriod.__table__.update()
                .where(FiscalPeriod.company_id == company.id)
                .values(is_current=False)
            )

            period_result = await session.execute(
                select(FiscalPeriod).where(
                    FiscalPeriod.company_id == company.id,
                    FiscalPeriod.label == "2024",
                )
            )
            period = period_result.scalar_one_or_none()
            if not period:
                period = FiscalPeriod(
                    company_id=company.id,
                    label="2024",
                    period_type="annual",
                    date_start=date(2024, 1, 1),
                    date_end=date(2024, 12, 31),
                    status="open",
                    is_current=True,
                )
                session.add(period)
            await session.execute(
                FiscalPeriod.__table__.update()
                .where(
                    FiscalPeriod.company_id == company.id,
                    FiscalPeriod.label == "2024",
                )
                .values(status="open", is_current=True)
            )
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def phase03_clean_invoice_tables():
    await engine.dispose()
    async with async_session_factory() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM vat_register"))
            await session.execute(text("DELETE FROM invoice_lines"))
            await session.execute(text("DELETE FROM invoices"))
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def phase05_clean_filing_tables():
    await engine.dispose()
    async with async_session_factory() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM filing_records"))
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def phase06_seed_admin_user():
    """Ensure admin user exists for Phase 06 auth tests (idempotent)."""
    from app.models.user import User
    from app.services.auth_service import hash_password

    await engine.dispose()
    async with async_session_factory() as session:
        async with session.begin():
            company_result = await session.execute(
                select(Company).order_by(Company.created_at).limit(1)
            )
            company = company_result.scalar_one_or_none()
            if not company:
                return
            existing = await session.scalar(
                select(User).where(User.email == "admin@medicianalytica.cz")
            )
            if not existing:
                admin = User(
                    company_id=company.id,
                    email="admin@medicianalytica.cz",
                    full_name="Administrator",
                    hashed_password=hash_password("changeme123"),
                    role="admin",
                    is_active=True,
                )
                session.add(admin)
    await engine.dispose()
