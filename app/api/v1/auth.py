from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.user import User
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user_web,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "user": None}
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate_user(session, email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "user": None, "error": "Nesprávný e-mail nebo heslo."},
            status_code=401,
        )
    user.last_login_at = datetime.now(timezone.utc)
    token = create_access_token(user.id, user.company_id, user.role)

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=3600,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(
        "access_token",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return response


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    user: User = Depends(get_current_user_web),
):
    return templates.TemplateResponse(
        "change_password.html", {"request": request, "user": user}
    )


@router.post("/change-password", response_class=HTMLResponse)
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(get_current_user_web),
    session: AsyncSession = Depends(get_session),
):
    error = None
    success = None
    db_user = await session.get(User, user.id)
    if not db_user or not verify_password(current_password, db_user.hashed_password):
        error = "Současné heslo je nesprávné."
    elif new_password != confirm_password:
        error = "Nová hesla se neshodují."
    elif len(new_password) < 8:
        error = "Nové heslo musí mít alespoň 8 znaků."
    else:
        db_user.hashed_password = hash_password(new_password)
        success = "Heslo bylo úspěšně změněno."
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request, "user": user, "error": error, "success": success},
    )
