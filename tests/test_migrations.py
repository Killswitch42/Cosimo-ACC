import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_companies_table_exists(client):
    from app.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'companies'"
            )
        )
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_fiscal_periods_table_exists(client):
    from app.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'fiscal_periods'"
            )
        )
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_ledger_accounts_table_exists(client):
    from app.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'ledger_accounts'"
            )
        )
        assert result.scalar() == 1
