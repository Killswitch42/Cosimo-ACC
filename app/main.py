import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

security_logger = logging.getLogger("medici.security")

from app.api.v1 import (
    account_balances, ai_classify, alerts, auth, backup, bank, bank_ui,
    compliance, dashboard, health, invoices, invoices_ui, journal_entries,
    ledger_ui, nl_query, periods, reports, vat_register,
)
from app.config import settings
from app.services.auth_service import NotAuthenticatedError

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


async def nightly_backup_job():
    """Runs at 02:00 CET when Google Drive backup is enabled."""
    from app.services.backup_service import run_backup

    try:
        result = await run_backup()
        security_logger.info("Backup job: %s", result)
    except Exception as exc:  # never let a backup failure crash the scheduler
        security_logger.error("Backup job failed: %s", exc)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Medici Analytica AI Accounting System",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.exception_handler(NotAuthenticatedError)
    async def not_authenticated_handler(request: Request, exc: NotAuthenticatedError):
        """Redirect unauthenticated browser visitors to the login page."""
        return RedirectResponse(url="/auth/login", status_code=303)

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
    app.include_router(invoices_ui.router)
    app.include_router(ledger_ui.router)
    app.include_router(bank_ui.router)
    app.include_router(bank.router, prefix="/api/v1")
    app.include_router(backup.router, prefix="/api/v1")

    @app.on_event("startup")
    async def security_audit():
        """Warn (or refuse to start) on unsafe production configuration."""
        issues = []
        if settings.secret_key_is_weak:
            issues.append("APP_SECRET_KEY is missing/placeholder/too short — "
                          "anyone could forge login cookies. Set a strong random value.")
        if settings.admin_password_is_default:
            issues.append("Admin password is the default 'changeme123' — change it now.")
        if not settings.debug and not settings.cookie_secure:
            issues.append("Serving in production without COOKIE_SECURE — enable it behind HTTPS.")

        # In production, a forgeable secret is fatal; refuse to start.
        if not settings.debug and settings.secret_key_is_weak:
            raise RuntimeError(
                "Refusing to start with a weak APP_SECRET_KEY while DEBUG is off. "
                "Set a strong APP_SECRET_KEY in the environment."
            )
        for issue in issues:
            security_logger.warning("SECURITY: %s", issue)

    @app.on_event("startup")
    async def start_scheduler():
        scheduler.add_job(
            daily_watchdog_job,
            CronTrigger(hour=7, minute=0, timezone="Europe/Prague"),
            id="daily_watchdog",
            replace_existing=True,
        )
        if settings.gdrive_backup_enabled:
            scheduler.add_job(
                nightly_backup_job,
                CronTrigger(hour=2, minute=0, timezone="Europe/Prague"),
                id="nightly_backup",
                replace_existing=True,
            )
        scheduler.start()

    @app.on_event("shutdown")
    async def stop_scheduler():
        scheduler.shutdown()

    return app


app = create_app()
