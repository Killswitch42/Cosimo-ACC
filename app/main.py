from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.v1 import (
    account_balances, ai_classify, alerts, auth, bank, compliance,
    dashboard, health, invoices, journal_entries, nl_query, periods,
    reports, vat_register,
)
from app.config import settings

scheduler = AsyncIOScheduler()


async def daily_watchdog_job():
    """Runs at 07:00 CET every day."""
    from app.database import async_session_factory
    from app.services.watchdog_service import scan_vat_period
    from app.services.deadline_service import run_deadline_scan
    from datetime import date
    import uuid

    company_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    today = date.today()
    vat_period = today.strftime("%Y-%m")

    async with async_session_factory() as session:
        async with session.begin():
            await run_deadline_scan(session, company_id)
            await scan_vat_period(session, company_id, vat_period)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Medici Analytica AI Accounting System",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Phase 01-05 API routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(journal_entries.router, prefix="/api/v1")
    app.include_router(account_balances.router, prefix="/api/v1")
    app.include_router(periods.router, prefix="/api/v1")
    app.include_router(invoices.router, prefix="/api/v1")
    app.include_router(vat_register.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(compliance.router, prefix="/api/v1")
    app.include_router(ai_classify.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")

    # Phase 06: auth, dashboard UI, NL query, bank stub
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(nl_query.router)
    app.include_router(bank.router, prefix="/api/v1")

    @app.on_event("startup")
    async def start_scheduler():
        scheduler.add_job(
            daily_watchdog_job,
            CronTrigger(hour=7, minute=0, timezone="Europe/Prague"),
            id="daily_watchdog",
            replace_existing=True,
        )
        scheduler.start()

    @app.on_event("shutdown")
    async def stop_scheduler():
        scheduler.shutdown()

    return app


app = create_app()
