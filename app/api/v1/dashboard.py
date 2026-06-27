import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.alert import AlertRecord
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    summary = await get_dashboard_summary(session, user.company_id)
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "summary": summary}
    )


@router.get("/dashboard/alerts-partial", response_class=HTMLResponse)
async def alerts_partial(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    summary = await get_dashboard_summary(session, user.company_id)
    return templates.TemplateResponse(
        "partials/alert_list.html", {"request": request, "summary": summary}
    )


@router.post("/dashboard/alerts/{alert_id}/resolve", response_class=HTMLResponse)
async def resolve_alert_from_dashboard(
    alert_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AlertRecord).where(AlertRecord.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert:
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolved_by = user.email
        alert.resolution_note = "Vyřešeno z dashboardu"
    await session.flush()

    summary = await get_dashboard_summary(session, user.company_id)
    return templates.TemplateResponse(
        "partials/alert_list.html", {"request": request, "summary": summary}
    )
